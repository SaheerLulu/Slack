"""Realtime (Channels) tests using WebsocketCommunicator.

These exercise the exact production delivery path: a sync caller (mimicking a
DRF view) invokes the ``events`` helpers, which use ``async_to_sync`` on the
channel layer, and we assert the async consumer receives the broadcast.
"""
import asyncio

from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase

from chat import events
from chat.models import Channel, ChannelMember, User, Workspace, WorkspaceMember
from chat.routing import websocket_urlpatterns


def app():
    # Connect straight to the router (no JWT middleware) so the test can set
    # scope["user"] directly; the middleware is covered separately.
    return URLRouter(websocket_urlpatterns)


async def connect_as(user):
    communicator = WebsocketCommunicator(app(), "/ws/")
    communicator.scope["user"] = user
    connected, _ = await communicator.connect()
    assert connected, "WebSocket failed to connect"
    return communicator


async def await_event(comm, event_type, predicate=None, tries=20):
    """Read frames (ignoring others) until one of ``event_type`` matches."""
    for _ in range(tries):
        frame = await comm.receive_json_from(timeout=2)
        if frame.get("type") == event_type and (
            predicate is None or predicate(frame)
        ):
            return frame
    raise AssertionError(f"did not receive a matching {event_type} event")


class RealtimeTests(TransactionTestCase):
    def setUp(self):
        # Use a slug that won't collide with the migration-seeded "acme".
        self.ws = Workspace.objects.create(name="RT", slug="rt-ws")
        self.alice = User.objects.create_user(username="alice", password="x")
        self.bob = User.objects.create_user(username="bob", password="x")
        for u in (self.alice, self.bob):
            WorkspaceMember.objects.create(workspace=self.ws, user=u)
        self.channel = Channel.objects.create(
            workspace=self.ws, name="general", is_dm=False
        )
        for u in (self.alice, self.bob):
            ChannelMember.objects.create(channel=self.channel, user=u)

    async def test_message_broadcast_and_presence(self):
        bob_comm = await connect_as(self.bob)
        # Bob's own connect emits presence:init to himself.
        init = await bob_comm.receive_json_from(timeout=3)
        self.assertEqual(init["type"], "presence:init")

        # Connecting Alice broadcasts presence to the workspace group (Bob is in).
        alice_comm = await connect_as(self.alice)
        # Let Alice's connect() coroutine finish emitting its presence broadcast
        # before we enqueue the message (otherwise the two race).
        await asyncio.sleep(0.3)

        # Simulate a REST view broadcasting a new message from a sync context
        # (sync_to_async runs events.to_channel in a worker thread, where its
        # internal async_to_sync is valid — exactly like a DRF view).
        await sync_to_async(events.to_channel)(
            self.channel.id,
            "message",
            {"message": {"id": 1, "channel": self.channel.id, "content": "hi"}},
        )

        # Collect frames until the message arrives; assert presence was seen too.
        saw_alice_presence = False
        saw_message = False
        for _ in range(10):
            frame = await bob_comm.receive_json_from(timeout=3)
            if frame["type"] == "presence" and frame.get("userId") == self.alice.id:
                saw_alice_presence = True
                self.assertTrue(frame["online"])
            if frame["type"] == "message" and frame["message"]["content"] == "hi":
                saw_message = True
                break
        self.assertTrue(saw_message, "did not receive broadcast message")
        self.assertTrue(saw_alice_presence, "did not receive Alice's presence event")

        await alice_comm.disconnect()
        await bob_comm.disconnect()

    async def test_call_join_broadcasts_state_and_cleans_up(self):
        bob_comm = await connect_as(self.bob)
        alice_comm = await connect_as(self.alice)

        # Alice joins the channel's call -> Bob gets call:state active=true.
        await alice_comm.send_json_to(
            {"type": "call:join", "channelId": self.channel.id}
        )
        state = await await_event(
            bob_comm, "call:state", predicate=lambda f: f["active"]
        )
        self.assertEqual(state["channelId"], self.channel.id)
        self.assertIn(self.alice.id, [p["id"] for p in state["participants"]])

        # Alice leaves the call -> Bob gets call:state active=false.
        await alice_comm.send_json_to(
            {"type": "call:leave", "channelId": self.channel.id}
        )
        ended = await await_event(
            bob_comm, "call:state", predicate=lambda f: not f["active"]
        )
        self.assertEqual(ended["participants"], [])

        await alice_comm.disconnect()
        await bob_comm.disconnect()

    async def test_anonymous_rejected(self):
        communicator = WebsocketCommunicator(app(), "/ws/")
        communicator.scope["user"] = AnonymousUser()
        connected, _ = await communicator.connect()
        self.assertFalse(connected)
