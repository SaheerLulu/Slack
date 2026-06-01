"""Helpers for pushing realtime events to clients via the channel layer.

Group naming convention:
  - channel_<id>   : everyone currently viewing/subscribed to a channel
  - user_<id>      : all of a single user's open connections
  - workspace_<id> : everyone connected within a workspace (presence)
"""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def channel_group(channel_id):
    return f"channel_{channel_id}"


def user_group(user_id):
    return f"user_{user_id}"


def workspace_group(workspace_id):
    return f"workspace_{workspace_id}"


def _send(group, event_type, payload):
    layer = get_channel_layer()
    if layer is None:  # pragma: no cover - only when channels misconfigured
        return
    async_to_sync(layer.group_send)(
        group,
        {"type": "broadcast", "event": {"type": event_type, **payload}},
    )


def to_channel(channel_id, event_type, payload):
    _send(channel_group(channel_id), event_type, payload)


def to_user(user_id, event_type, payload):
    _send(user_group(user_id), event_type, payload)


def to_workspace(workspace_id, event_type, payload):
    _send(workspace_group(workspace_id), event_type, payload)
