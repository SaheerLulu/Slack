"""WebSocket consumer handling presence, typing, and event delivery.

Persistence happens over REST; this consumer is purely the realtime transport.
Each connection subscribes to:
  - its own ``user_<id>`` group (notifications, DMs)
  - ``channel_<id>`` for every channel the user belongs to
  - ``workspace_<id>`` for every workspace the user belongs to (presence)
"""
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from . import events

# Track how many live connections each user has, per process, so presence
# transitions (online/offline) only fire on the first/last connection.
_connection_counts = {}

# Active calls: channel_id -> { user_id: display_name }. LiveKit handles the
# actual media; this just tracks who's in a channel's call so we can show a
# "call in progress" banner and participant list to everyone.
_call_participants = {}


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        await self.accept()

        # Tell the freshly-connected client who is currently online.
        await self.send(
            json.dumps(
                {"type": "presence:init", "online": list(_connection_counts.keys())}
            )
        )

        self.channel_ids, self.workspace_ids = await self._memberships()
        self.groups_joined = (
            [events.user_group(self.user.id)]
            + [events.channel_group(cid) for cid in self.channel_ids]
            + [events.workspace_group(wid) for wid in self.workspace_ids]
        )
        for group in self.groups_joined:
            await self.channel_layer.group_add(group, self.channel_name)

        # Calls this connection is currently in (for disconnect cleanup).
        self.calls_joined = set()

        first = _connection_counts.get(self.user.id, 0) == 0
        _connection_counts[self.user.id] = _connection_counts.get(self.user.id, 0) + 1
        if first:
            await self._broadcast_presence(True)

        # Tell the new client about any calls already in progress.
        for cid in self.channel_ids:
            if _call_participants.get(cid):
                await self._send_call_state(cid)

    async def disconnect(self, code):
        if not getattr(self, "user", None) or not self.user.is_authenticated:
            return
        # Drop out of any calls this connection joined.
        for cid in list(getattr(self, "calls_joined", set())):
            await self._call_leave(cid)

        for group in getattr(self, "groups_joined", []):
            await self.channel_layer.group_discard(group, self.channel_name)

        _connection_counts[self.user.id] = max(
            0, _connection_counts.get(self.user.id, 1) - 1
        )
        if _connection_counts[self.user.id] == 0:
            _connection_counts.pop(self.user.id, None)
            await self._broadcast_presence(False)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or "{}")
        except json.JSONDecodeError:
            return

        msg_type = data.get("type")
        if msg_type == "typing":
            channel_id = data.get("channelId")
            if channel_id in self.channel_ids:
                await self.channel_layer.group_send(
                    events.channel_group(channel_id),
                    {
                        "type": "broadcast",
                        "event": {
                            "type": "typing",
                            "channelId": channel_id,
                            "userId": self.user.id,
                            "displayName": self.user.display_name,
                        },
                    },
                )
        elif msg_type == "subscribe":
            # Subscribe to a channel joined after connecting (e.g. new DM).
            channel_id = data.get("channelId")
            if channel_id and channel_id not in self.channel_ids:
                if await self._is_member(channel_id):
                    self.channel_ids.append(channel_id)
                    group = events.channel_group(channel_id)
                    self.groups_joined.append(group)
                    await self.channel_layer.group_add(group, self.channel_name)
        elif msg_type == "call:join":
            channel_id = data.get("channelId")
            if channel_id in self.channel_ids:
                _call_participants.setdefault(channel_id, {})[self.user.id] = (
                    self.user.display_name
                )
                self.calls_joined.add(channel_id)
                await self._send_call_state(channel_id, to_group=True)
        elif msg_type == "call:leave":
            channel_id = data.get("channelId")
            if channel_id in self.calls_joined:
                await self._call_leave(channel_id)
        elif msg_type == "ping":
            await self.send(json.dumps({"type": "pong"}))

    # --- group event handler: forwards a broadcast payload to this socket ---
    async def broadcast(self, message):
        await self.send(json.dumps(message["event"]))

    # --- helpers ---
    async def _broadcast_presence(self, online):
        # We're already inside the event loop here, so await the channel layer
        # directly rather than going through the sync (async_to_sync) helper.
        event = {
            "type": "broadcast",
            "event": {"type": "presence", "userId": self.user.id, "online": online},
        }
        for wid in getattr(self, "workspace_ids", []):
            await self.channel_layer.group_send(events.workspace_group(wid), event)

    async def _call_leave(self, channel_id):
        self.calls_joined.discard(channel_id)
        participants = _call_participants.get(channel_id)
        if participants and self.user.id in participants:
            # Only remove if this user has no other connection still in the call.
            # (Best-effort: per-connection tracking; multiple tabs share id.)
            del participants[self.user.id]
            if not participants:
                _call_participants.pop(channel_id, None)
            await self._send_call_state(channel_id, to_group=True)

    async def _send_call_state(self, channel_id, to_group=False):
        participants = _call_participants.get(channel_id, {})
        event = {
            "type": "broadcast",
            "event": {
                "type": "call:state",
                "channelId": channel_id,
                "active": bool(participants),
                "participants": [
                    {"id": uid, "displayName": name}
                    for uid, name in participants.items()
                ],
            },
        }
        if to_group:
            await self.channel_layer.group_send(
                events.channel_group(channel_id), event
            )
        else:
            await self.send(json.dumps(event["event"]))

    @database_sync_to_async
    def _memberships(self):
        from .models import ChannelMember, WorkspaceMember

        channel_ids = list(
            ChannelMember.objects.filter(user=self.user).values_list(
                "channel_id", flat=True
            )
        )
        workspace_ids = list(
            WorkspaceMember.objects.filter(user=self.user).values_list(
                "workspace_id", flat=True
            )
        )
        return channel_ids, workspace_ids

    @database_sync_to_async
    def _is_member(self, channel_id):
        from .models import ChannelMember

        return ChannelMember.objects.filter(
            channel_id=channel_id, user=self.user
        ).exists()
