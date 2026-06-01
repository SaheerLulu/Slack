import re

from django.conf import settings
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
        "topic": channel.topic,
    }
    if channel.is_dm:
        peer = (
            channel.members.exclude(id=user.id).first()
            or channel.members.first()
        )
        data["name"] = peer.display_name if peer else "Direct message"
        data["peer"] = UserSerializer(peer).data if peer else None
    else:
        data["name"] = channel.name
        data["peer"] = None

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


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------
def _annotate_messages(qs):
    return qs.select_related("user").prefetch_related(
        "attachments", "reactions"
    ).annotate(reply_count_annotated=Count("replies", distinct=True))


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
        return Response(MessageSerializer(messages, many=True).data)

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
    return Response({
        "root": MessageSerializer(root).data,
        "replies": MessageSerializer(replies, many=True).data,
    })


def _handle_notifications(message, channel, parent):
    """Create + push notifications for @mentions and thread replies."""
    notified = set()

    # Thread reply -> notify parent author (and earlier participants).
    if parent and parent.user_id != message.user_id:
        _notify(parent.user_id, Notification.REPLY, message, channel, notified)

    # @mentions -> notify mentioned channel members.
    usernames = set(MENTION_RE.findall(message.content or ""))
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
    messages = _annotate_messages(
        Message.objects.filter(
            channel_id__in=member_channel_ids,
            is_deleted=False,
            content__icontains=q,
        )
    ).order_by("-id")[:50]
    return Response(MessageSerializer(messages, many=True).data)


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


@api_view(["POST"])
def read_notifications(request):
    ids = request.data.get("ids")
    qs = Notification.objects.filter(user=request.user, is_read=False)
    if ids:
        qs = qs.filter(id__in=ids)
    qs.update(is_read=True)
    return Response({"ok": True})
