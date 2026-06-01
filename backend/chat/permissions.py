"""Membership helpers used by the views to authorize access."""
from rest_framework.exceptions import NotFound, PermissionDenied

from .models import Channel, ChannelMember, Workspace, WorkspaceMember


def get_workspace_or_404(workspace_id):
    try:
        return Workspace.objects.get(pk=workspace_id)
    except Workspace.DoesNotExist:
        raise NotFound("Workspace not found.")


def require_workspace_member(user, workspace_id):
    workspace = get_workspace_or_404(workspace_id)
    if not WorkspaceMember.objects.filter(workspace=workspace, user=user).exists():
        raise PermissionDenied("You are not a member of this workspace.")
    return workspace


def get_channel_or_404(channel_id):
    try:
        return Channel.objects.select_related("workspace").get(pk=channel_id)
    except Channel.DoesNotExist:
        raise NotFound("Channel not found.")


def require_channel_member(user, channel_id):
    channel = get_channel_or_404(channel_id)
    if not ChannelMember.objects.filter(channel=channel, user=user).exists():
        raise PermissionDenied("Join the channel first.")
    return channel


def can_see_channel(user, channel):
    """Public channels are visible to workspace members; private/DM need membership."""
    if ChannelMember.objects.filter(channel=channel, user=user).exists():
        return True
    if channel.is_private or channel.is_dm:
        return False
    return WorkspaceMember.objects.filter(
        workspace=channel.workspace, user=user
    ).exists()
