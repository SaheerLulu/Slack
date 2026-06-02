import re

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from . import events, permissions as perms
from .models import (
    Attachment,
    Channel,
    ChannelMember,
    Message,
    Notification,
    Reaction,
    SavedItem,
    User,
    Workspace,
    WorkspaceMember,
)
from .serializers import (
    MessageSerializer,
    NotificationSerializer,
    RegisterSerializer,
    UserSerializer,
    WorkspaceSerializer,
)

MENTION_RE = re.compile(r"(?:^|\s)@([a-zA-Z0-9_.\-]{3,30})")


def tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


# --------------------------------------------------------------------------
# Channel shaping
# --------------------------------------------------------------------------
def shape_channel(channel, user):
    """Serialize a channel for a given viewer, including DM peer + unread count."""
    membership = ChannelMember.objects.filter(channel=channel, user=user).first()
    data = {
        "id": channel.id,
        "workspace": channel.workspace_id,
        "isDm": channel.is_dm,
        "isPrivate": channel.is_private,
        "isMember": membership is not None,
        "muted": membership.muted if membership else False,
        "topic": channel.topic,
    }
    if channel.is_dm:
        others = list(channel.members.exclude(id=user.id))
        if len(others) == 1:
            data["name"] = others[0].display_name
            data["peer"] = UserSerializer(others[0]).data
            data["isGroup"] = False
        elif len(others) > 1:
            # Group DM — name from the other participants' display names.
            data["name"] = ", ".join(u.display_name for u in others)
            data["peer"] = None
            data["isGroup"] = True
        else:
            data["name"] = "Direct message"
            data["peer"] = None
            data["isGroup"] = False
        data["peers"] = UserSerializer(others, many=True).data
    else:
        data["name"] = channel.name
        data["peer"] = None
        data["isGroup"] = False

    # Unread count: messages newer than the user's last-read marker.
    if membership:
        unread_qs = Message.objects.filter(channel=channel, is_deleted=False)
        if membership.last_read_message_id:
            unread_qs = unread_qs.filter(id__gt=membership.last_read_message_id)
        data["unread"] = unread_qs.exclude(user=user).count()
    else:
        data["unread"] = 0
    return data


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    _auto_join_default_workspace(user)
    return Response(
        {"user": UserSerializer(user).data, **tokens_for(user)},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    username = (request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    user = User.objects.filter(username__iexact=username).first()
    if not user or not user.check_password(password):
        return Response(
            {"detail": "Invalid username or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    return Response({"user": UserSerializer(user).data, **tokens_for(user)})


@api_view(["GET"])
def me(request):
    return Response(UserSerializer(request.user).data)


def _auto_join_default_workspace(user):
    """Place new users in the seeded default workspace + #general."""
    workspace = Workspace.objects.order_by("id").first()
    if not workspace:
        return
    WorkspaceMember.objects.get_or_create(workspace=workspace, user=user)
    general = Channel.objects.filter(
        workspace=workspace, name="general", is_dm=False
    ).first()
    if general:
        ChannelMember.objects.get_or_create(channel=general, user=user)


# --------------------------------------------------------------------------
# Workspaces
# --------------------------------------------------------------------------
class WorkspaceListCreate(APIView):
    def get(self, request):
        workspaces = Workspace.objects.filter(memberships__user=request.user)
        return Response(WorkspaceSerializer(workspaces, many=True).data)

    def post(self, request):
        serializer = WorkspaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"]
        base = slugify(name) or "workspace"
        slug, i = base, 1
        while Workspace.objects.filter(slug=slug).exists():
            i += 1
            slug = f"{base}-{i}"
        workspace = Workspace.objects.create(
            name=name, slug=slug, created_by=request.user
        )
        WorkspaceMember.objects.create(
            workspace=workspace, user=request.user, role=WorkspaceMember.OWNER
        )
        # Every workspace gets a #general channel.
        general = Channel.objects.create(
            workspace=workspace, name="general", topic="General discussion",
            created_by=request.user,
        )
        ChannelMember.objects.create(channel=general, user=request.user)
        return Response(
            WorkspaceSerializer(workspace).data, status=status.HTTP_201_CREATED
        )


@api_view(["POST"])
def join_workspace(request, workspace_id):
    workspace = perms.get_workspace_or_404(workspace_id)
    WorkspaceMember.objects.get_or_create(workspace=workspace, user=request.user)
    return Response(WorkspaceSerializer(workspace).data)


@api_view(["GET"])
def workspace_members(request, workspace_id):
    perms.require_workspace_member(request.user, workspace_id)
    members = User.objects.filter(workspace_memberships__workspace_id=workspace_id)
    return Response(UserSerializer(members, many=True).data)


# --------------------------------------------------------------------------
# Channels
# --------------------------------------------------------------------------
class ChannelListCreate(APIView):
    def get(self, request, workspace_id):
        perms.require_workspace_member(request.user, workspace_id)
        # Public channels in the workspace + private/DM channels the user is in.
        channels = (
            Channel.objects.filter(workspace_id=workspace_id)
            .filter(
                Q(is_private=False, is_dm=False)
                | Q(memberships__user=request.user)
            )
            .distinct()
        )
        shaped = [shape_channel(c, request.user) for c in channels]
        # Channels you belong to first, DMs last, then by name.
        shaped.sort(key=lambda c: (c["isDm"], not c["isMember"], c["name"].lower()))
        return Response(shaped)

    def post(self, request, workspace_id):
        perms.require_workspace_member(request.user, workspace_id)
        name = (request.data.get("name") or "").strip().lower()
        topic = (request.data.get("topic") or "").strip()
        is_private = bool(request.data.get("isPrivate", False))
        if not re.fullmatch(r"[a-z0-9\-_]{1,80}", name):
            return Response(
                {"detail": "Channel name: 1-80 chars, lowercase letters, "
                           "numbers, - and _."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if Channel.objects.filter(
            workspace_id=workspace_id, name=name, is_dm=False
        ).exists():
            return Response(
                {"detail": "A channel with that name already exists."},
                status=status.HTTP_409_CONFLICT,
            )
        channel = Channel.objects.create(
            workspace_id=workspace_id, name=name, topic=topic,
            is_private=is_private, created_by=request.user,
        )
        ChannelMember.objects.create(channel=channel, user=request.user)
        return Response(
            shape_channel(channel, request.user), status=status.HTTP_201_CREATED
        )


@api_view(["POST"])
def join_channel(request, channel_id):
    channel = perms.get_channel_or_404(channel_id)
    if channel.is_dm or channel.is_private:
        return Response(
            {"detail": "You can't self-join this channel."},
            status=status.HTTP_403_FORBIDDEN,
        )
    perms.require_workspace_member(request.user, channel.workspace_id)
    ChannelMember.objects.get_or_create(channel=channel, user=request.user)
    return Response(shape_channel(channel, request.user))


@api_view(["GET"])
def channel_members(request, channel_id):
    perms.require_channel_member(request.user, channel_id)
    members = User.objects.filter(channel_memberships__channel_id=channel_id)
    return Response(UserSerializer(members, many=True).data)


@api_view(["POST"])
def mark_read(request, channel_id):
    membership = ChannelMember.objects.filter(
        channel_id=channel_id, user=request.user
    ).first()
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)
    last = Message.objects.filter(channel_id=channel_id).order_by("-id").first()
    membership.last_read_message = last
    membership.save(update_fields=["last_read_message"])
    return Response({"ok": True, "lastReadMessage": last.id if last else None})


@api_view(["POST"])
def leave_channel(request, channel_id):
    channel = perms.get_channel_or_404(channel_id)
    if channel.is_dm:
        return Response({"detail": "You can't leave a DM."}, status=400)
    if channel.name == "general" and not channel.is_private:
        return Response({"detail": "You can't leave #general."}, status=400)
    ChannelMember.objects.filter(channel=channel, user=request.user).delete()
    return Response({"ok": True})


@api_view(["POST"])
def mute_channel(request, channel_id):
    membership = ChannelMember.objects.filter(
        channel_id=channel_id, user=request.user
    ).first()
    if not membership:
        return Response(status=status.HTTP_403_FORBIDDEN)
    membership.muted = bool(request.data.get("muted", True))
    membership.save(update_fields=["muted"])
    return Response({"ok": True, "muted": membership.muted})


# --------------------------------------------------------------------------
# Direct messages
# --------------------------------------------------------------------------
@api_view(["POST"])
def open_dm(request, workspace_id, user_id):
    perms.require_workspace_member(request.user, workspace_id)
    if user_id == request.user.id:
        return Response(
            {"detail": "You can't DM yourself."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    other = User.objects.filter(
        pk=user_id, workspace_memberships__workspace_id=workspace_id
    ).first()
    if not other:
        return Response(
            {"detail": "User is not in this workspace."},
            status=status.HTTP_404_NOT_FOUND,
        )
    lo, hi = sorted([request.user.id, other.id])
    dm_key = f"{workspace_id}:{lo}:{hi}"
    channel = Channel.objects.filter(dm_key=dm_key).first()
    if not channel:
        channel = Channel.objects.create(
            workspace_id=workspace_id, is_dm=True, dm_key=dm_key,
            created_by=request.user,
        )
        ChannelMember.objects.create(channel=channel, user=request.user)
        ChannelMember.objects.create(channel=channel, user=other)
    return Response(shape_channel(channel, request.user))


@api_view(["POST"])
def open_group_dm(request, workspace_id):
    """Open (or fetch) a group DM with 2+ other workspace members."""
    perms.require_workspace_member(request.user, workspace_id)
    raw_ids = request.data.get("userIds") or []
    try:
        other_ids = {int(i) for i in raw_ids} - {request.user.id}
    except (TypeError, ValueError):
        return Response({"detail": "Invalid userIds."}, status=400)
    if len(other_ids) < 2:
        return Response(
            {"detail": "A group DM needs at least 3 people."}, status=400
        )
    members = list(
        User.objects.filter(
            pk__in=other_ids, workspace_memberships__workspace_id=workspace_id
        )
    )
    if len(members) != len(other_ids):
        return Response(
            {"detail": "All members must be in this workspace."}, status=400
        )

    all_ids = sorted({request.user.id, *other_ids})
    dm_key = f"{workspace_id}:" + ":".join(str(i) for i in all_ids)
    channel = Channel.objects.filter(dm_key=dm_key).first()
    if not channel:
        now = timezone.now()
        with transaction.atomic():
            channel = Channel.objects.create(
                workspace_id=workspace_id, is_dm=True, dm_key=dm_key,
                created_by=request.user,
            )
            for uid in all_ids:
                ChannelMember.objects.create(channel=channel, user_id=uid)
    return Response(shape_channel(channel, request.user))


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------
def _annotate_messages(qs):
    return qs.select_related("user").prefetch_related(
        "attachments", "reactions"
    ).annotate(reply_count_annotated=Count("replies", distinct=True))


def serialize_messages(messages, user, many=True):
    """Serialize message(s) with the viewer's saved-item state attached."""
    ids = [m.id for m in messages] if many else [messages.id]
    saved_ids = set(
        SavedItem.objects.filter(user=user, message_id__in=ids).values_list(
            "message_id", flat=True
        )
    )
    return MessageSerializer(
        messages, many=many, context={"saved_ids": saved_ids}
    ).data


@api_view(["GET", "POST"])
def channel_messages(request, channel_id):
    channel = perms.require_channel_member(request.user, channel_id)

    if request.method == "GET":
        qs = _annotate_messages(
            Message.objects.filter(channel=channel, parent__isnull=True)
        )
        before = request.query_params.get("before")
        if before:
            qs = qs.filter(id__lt=before)
        limit = min(int(request.query_params.get("limit", 50)), 100)
        messages = list(qs.order_by("-id")[:limit])
        messages.reverse()
        return Response(serialize_messages(messages, request.user))

    # POST — create a message
    content = (request.data.get("content") or "").strip()
    parent_id = request.data.get("parent")
    attachment_ids = request.data.get("attachmentIds") or []
    if not content and not attachment_ids:
        return Response(
            {"detail": "Message is empty."}, status=status.HTTP_400_BAD_REQUEST
        )
    if len(content) > 8000:
        return Response(
            {"detail": "Message too long."}, status=status.HTTP_400_BAD_REQUEST
        )

    parent = None
    if parent_id:
        parent = Message.objects.filter(channel=channel, pk=parent_id).first()
        if not parent:
            return Response(
                {"detail": "Parent message not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    message = Message.objects.create(
        channel=channel, user=request.user, content=content, parent=parent
    )
    # Attach any pre-uploaded files owned by this user and not yet attached.
    if attachment_ids:
        Attachment.objects.filter(
            id__in=attachment_ids, uploaded_by=request.user, message__isnull=True
        ).update(message=message)

    data = MessageSerializer(_annotate_messages(
        Message.objects.filter(pk=message.pk)
    ).first()).data

    events.to_channel(channel_id, "message", {"message": data})
    _handle_notifications(message, channel, parent)
    return Response(data, status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
def message_detail(request, message_id):
    message = Message.objects.filter(pk=message_id).select_related("channel").first()
    if not message:
        raise Http404
    perms.require_channel_member(request.user, message.channel_id)
    if message.user_id != request.user.id:
        return Response(
            {"detail": "You can only modify your own messages."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.method == "DELETE":
        message.is_deleted = True
        message.content = ""
        message.save(update_fields=["is_deleted", "content"])
        events.to_channel(
            message.channel_id, "message:delete",
            {"messageId": message.id, "channelId": message.channel_id},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    content = (request.data.get("content") or "").strip()
    if not content:
        return Response(
            {"detail": "Message is empty."}, status=status.HTTP_400_BAD_REQUEST
        )
    message.content = content
    message.edited_at = timezone.now()
    message.save(update_fields=["content", "edited_at"])
    data = MessageSerializer(_annotate_messages(
        Message.objects.filter(pk=message.pk)
    ).first()).data
    events.to_channel(message.channel_id, "message:edit", {"message": data})
    return Response(data)


@api_view(["GET"])
def message_thread(request, message_id):
    parent = Message.objects.filter(pk=message_id).select_related("channel").first()
    if not parent:
        raise Http404
    perms.require_channel_member(request.user, parent.channel_id)
    replies = _annotate_messages(
        Message.objects.filter(parent=parent)
    ).order_by("id")
    root = _annotate_messages(Message.objects.filter(pk=parent.pk)).first()
    replies = list(replies)
    return Response({
        "root": serialize_messages(root, request.user, many=False),
        "replies": serialize_messages(replies, request.user),
    })


def _handle_notifications(message, channel, parent):
    """Create + push notifications for @mentions and thread replies."""
    notified = set()

    # Thread reply -> notify parent author (and earlier participants).
    if parent and parent.user_id != message.user_id:
        _notify(parent.user_id, Notification.REPLY, message, channel, notified)

    tokens = set(MENTION_RE.findall(message.content or ""))

    # Broadcast mentions (@channel / @here / @everyone) notify all members.
    if tokens & {"channel", "here", "everyone"}:
        member_ids = ChannelMember.objects.filter(channel=channel).values_list(
            "user_id", flat=True
        )
        for uid in member_ids:
            if uid != message.user_id:
                _notify(uid, Notification.MENTION, message, channel, notified)

    # @username -> notify that specific member.
    usernames = tokens - {"channel", "here", "everyone"}
    if usernames:
        member_ids = dict(
            ChannelMember.objects.filter(
                channel=channel, user__username__in=usernames
            ).values_list("user__username", "user_id")
        )
        for uid in member_ids.values():
            if uid != message.user_id:
                _notify(uid, Notification.MENTION, message, channel, notified)

    # DM -> notify the other participant.
    if channel.is_dm:
        for uid in channel.members.exclude(id=message.user_id).values_list(
            "id", flat=True
        ):
            _notify(uid, Notification.DM, message, channel, notified)


def _notify(user_id, ntype, message, channel, notified):
    if user_id in notified:
        return
    notified.add(user_id)
    notif = Notification.objects.create(
        user_id=user_id, type=ntype, actor=message.user,
        channel=channel, message=message,
    )
    events.to_user(
        user_id, "notification",
        {"notification": NotificationSerializer(notif).data},
    )


# --------------------------------------------------------------------------
# Reactions
# --------------------------------------------------------------------------
@api_view(["PUT", "DELETE"])
def reactions(request, message_id):
    message = Message.objects.filter(pk=message_id).select_related("channel").first()
    if not message:
        raise Http404
    perms.require_channel_member(request.user, message.channel_id)
    emoji = (request.data.get("emoji") or "").strip()
    if not emoji or len(emoji) > 40:
        return Response(
            {"detail": "Invalid emoji."}, status=status.HTTP_400_BAD_REQUEST
        )

    if request.method == "PUT":
        Reaction.objects.get_or_create(
            message=message, user=request.user, emoji=emoji
        )
    else:
        Reaction.objects.filter(
            message=message, user=request.user, emoji=emoji
        ).delete()

    data = MessageSerializer(_annotate_messages(
        Message.objects.filter(pk=message.pk)
    ).first()).data
    events.to_channel(
        message.channel_id, "reaction",
        {"messageId": message.id, "reactions": data["reactions"]},
    )
    return Response(data["reactions"])


# --------------------------------------------------------------------------
# Pins
# --------------------------------------------------------------------------
@api_view(["PUT", "DELETE"])
def pin_message(request, message_id):
    message = Message.objects.filter(pk=message_id).select_related("channel").first()
    if not message:
        raise Http404
    perms.require_channel_member(request.user, message.channel_id)
    if request.method == "PUT":
        message.pinned_at = timezone.now()
        message.pinned_by = request.user
    else:
        message.pinned_at = None
        message.pinned_by = None
    message.save(update_fields=["pinned_at", "pinned_by"])
    events.to_channel(
        message.channel_id, "pin",
        {"messageId": message.id, "channelId": message.channel_id,
         "pinned": message.pinned_at is not None},
    )
    return Response({"ok": True, "pinned": message.pinned_at is not None})


@api_view(["GET"])
def channel_pins(request, channel_id):
    perms.require_channel_member(request.user, channel_id)
    pinned = list(_annotate_messages(
        Message.objects.filter(
            channel_id=channel_id, pinned_at__isnull=False, is_deleted=False
        )
    ).order_by("-pinned_at"))
    return Response(serialize_messages(pinned, request.user))


# --------------------------------------------------------------------------
# Saved items (bookmarks)
# --------------------------------------------------------------------------
@api_view(["PUT", "DELETE"])
def save_message(request, message_id):
    message = Message.objects.filter(pk=message_id).select_related("channel").first()
    if not message:
        raise Http404
    perms.require_channel_member(request.user, message.channel_id)
    if request.method == "PUT":
        SavedItem.objects.get_or_create(user=request.user, message=message)
    else:
        SavedItem.objects.filter(user=request.user, message=message).delete()
    return Response({"ok": True})


@api_view(["GET"])
def list_saved(request):
    saved = SavedItem.objects.filter(user=request.user).values_list(
        "message_id", flat=True
    )
    messages = list(_annotate_messages(
        Message.objects.filter(pk__in=saved, is_deleted=False)
    ).order_by("-id"))
    return Response(serialize_messages(messages, request.user))


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------
ALLOWED_PREFIXES = ("image/", "video/", "audio/", "text/")
ALLOWED_EXACT = (
    "application/pdf",
    "application/zip",
    "application/json",
    "application/octet-stream",
)


@api_view(["POST"])
def upload_file(request):
    upload = request.FILES.get("file")
    if not upload:
        return Response(
            {"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST
        )
    if upload.size > settings.MAX_UPLOAD_BYTES:
        return Response(
            {"detail": "File too large."}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        )
    ctype = upload.content_type or "application/octet-stream"
    if not (ctype.startswith(ALLOWED_PREFIXES) or ctype in ALLOWED_EXACT):
        return Response(
            {"detail": f"File type {ctype} not allowed."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    attachment = Attachment.objects.create(
        uploaded_by=request.user, file=upload, filename=upload.name[:255],
        content_type=ctype, size=upload.size,
    )
    return Response(
        {
            "id": attachment.id,
            "filename": attachment.filename,
            "content_type": attachment.content_type,
            "size": attachment.size,
            "url": f"/api/files/{attachment.id}",
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
def download_file(request, attachment_id):
    attachment = Attachment.objects.filter(pk=attachment_id).first()
    if not attachment:
        raise Http404
    # If attached to a message, require channel membership; unattached files
    # are only visible to their uploader.
    if attachment.message_id:
        perms.require_channel_member(request.user, attachment.message.channel_id)
    elif attachment.uploaded_by_id != request.user.id:
        raise Http404
    response = FileResponse(
        attachment.file.open("rb"), content_type=attachment.content_type
    )
    response["Content-Disposition"] = f'inline; filename="{attachment.filename}"'
    return response


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------
@api_view(["GET"])
def search(request, workspace_id):
    perms.require_workspace_member(request.user, workspace_id)
    q = (request.query_params.get("q") or "").strip()
    if len(q) < 2:
        return Response([])
    member_channel_ids = ChannelMember.objects.filter(
        user=request.user, channel__workspace_id=workspace_id
    ).values_list("channel_id", flat=True)
    messages = list(_annotate_messages(
        Message.objects.filter(
            channel_id__in=member_channel_ids,
            is_deleted=False,
            content__icontains=q,
        )
    ).order_by("-id")[:50])
    return Response(serialize_messages(messages, request.user))


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------
@api_view(["GET"])
def list_notifications(request):
    qs = Notification.objects.filter(user=request.user).select_related("actor")[:100]
    return Response({
        "items": NotificationSerializer(qs, many=True).data,
        "unread": Notification.objects.filter(
            user=request.user, is_read=False
        ).count(),
    })


# --------------------------------------------------------------------------
# Calls (LiveKit SFU)
# --------------------------------------------------------------------------
@api_view(["POST"])
def call_token(request, channel_id):
    """Issue a LiveKit access token for the channel's call room.

    Pass ``{"ring": true}`` to also notify other channel members that a call
    is starting (shows an incoming-call prompt).
    """
    if not settings.CALLS_ENABLED:
        return Response(
            {"detail": "Calls are disabled on this server."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    channel = perms.require_channel_member(request.user, channel_id)

    from .livekit_token import create_access_token, room_name_for_channel

    room = room_name_for_channel(channel_id)
    token = create_access_token(
        identity=request.user.id,
        name=request.user.display_name,
        room=room,
    )

    if request.data.get("ring"):
        events.to_channel(
            channel_id,
            "call:ring",
            {
                "channelId": channel_id,
                "by": UserSerializer(request.user).data,
                "channelName": channel.name or "Direct message",
            },
        )

    return Response(
        {
            "url": settings.LIVEKIT_WS_URL,
            "token": token,
            "room": room,
            "iceServers": settings.EXTRA_ICE_SERVERS,
        }
    )


@api_view(["POST"])
def read_notifications(request):
    ids = request.data.get("ids")
    qs = Notification.objects.filter(user=request.user, is_read=False)
    if ids:
        qs = qs.filter(id__in=ids)
    qs.update(is_read=True)
    return Response({"ok": True})
