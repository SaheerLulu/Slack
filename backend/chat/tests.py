import jwt
from django.conf import settings
from rest_framework.test import APITestCase

from .models import Channel, Message, Notification, Workspace


class ChatFlowTests(APITestCase):
    def setUp(self):
        # Seeded by migration 0002, but tests run on a fresh DB without data
        # migrations applied in some configs; ensure the default workspace.
        if not Workspace.objects.exists():
            ws = Workspace.objects.create(name="Acme", slug="acme")
            Channel.objects.create(workspace=ws, name="general", is_dm=False)
        self.workspace = Workspace.objects.first()

    def _register(self, username, password="secret123"):
        resp = self.client.post(
            "/api/auth/register",
            {"username": username, "password": password, "display_name": username.title()},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        return resp.data

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_register_and_me(self):
        data = self._register("alice")
        self._auth(data["access"])
        resp = self.client.get("/api/auth/me")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["username"], "alice")

    def test_login_wrong_password(self):
        self._register("bob")
        resp = self.client.post(
            "/api/auth/login", {"username": "bob", "password": "nope"}, format="json"
        )
        self.assertEqual(resp.status_code, 401)

    def test_channel_message_react_thread_flow(self):
        alice = self._register("alice")
        self._auth(alice["access"])

        # New users auto-join the default workspace + #general.
        resp = self.client.get("/api/workspaces")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        wid = resp.data[0]["id"]

        # Create a channel.
        resp = self.client.post(
            f"/api/workspaces/{wid}/channels",
            {"name": "random", "topic": "Misc"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        channel_id = resp.data["id"]

        # Post a message.
        resp = self.client.post(
            f"/api/channels/{channel_id}/messages",
            {"content": "Hello world"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        msg_id = resp.data["id"]

        # Edit it.
        resp = self.client.patch(
            f"/api/messages/{msg_id}", {"content": "Hello edited"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["content"], "Hello edited")
        self.assertIsNotNone(resp.data["edited_at"])

        # React.
        resp = self.client.put(
            f"/api/messages/{msg_id}/reactions", {"emoji": "👍"}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data[0]["emoji"], "👍")
        self.assertEqual(resp.data[0]["count"], 1)

        # Thread reply.
        resp = self.client.post(
            f"/api/channels/{channel_id}/messages",
            {"content": "a reply", "parent": msg_id},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

        resp = self.client.get(f"/api/messages/{msg_id}/thread")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["replies"]), 1)

        # List messages excludes thread replies at top level.
        resp = self.client.get(f"/api/channels/{channel_id}/messages")
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["reply_count"], 1)

        # Search finds the message.
        resp = self.client.get(f"/api/workspaces/{wid}/search", {"q": "edited"})
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)

        # Delete (soft).
        resp = self.client.delete(f"/api/messages/{msg_id}")
        self.assertEqual(resp.status_code, 204)
        self.assertTrue(Message.objects.get(pk=msg_id).is_deleted)

    def test_mention_creates_notification(self):
        alice = self._register("alice")
        bob = self._register("bob")
        wid = self.workspace.id

        # Both already in #general via auto-join.
        general = Channel.objects.get(name="general")

        self._auth(alice["access"])
        resp = self.client.post(
            f"/api/channels/{general.id}/messages",
            {"content": "hey @bob look at this"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

        self._auth(bob["access"])
        resp = self.client.get("/api/notifications")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["unread"], 1)
        self.assertEqual(resp.data["items"][0]["type"], "mention")

    def test_dm_open_and_message(self):
        alice = self._register("alice")
        bob = self._register("bob")
        wid = self.workspace.id

        self._auth(alice["access"])
        resp = self.client.post(f"/api/workspaces/{wid}/dm/{bob['user']['id']}")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data["isDm"])
        dm_id = resp.data["id"]

        resp = self.client.post(
            f"/api/channels/{dm_id}/messages", {"content": "hi bob"}, format="json"
        )
        self.assertEqual(resp.status_code, 201)

        # Bob sees the DM and the message.
        self._auth(bob["access"])
        resp = self.client.get(f"/api/channels/{dm_id}/messages")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_call_token_grants_room_access(self):
        alice = self._register("alice")
        self._auth(alice["access"])
        general = Channel.objects.get(name="general")

        resp = self.client.post(f"/api/channels/{general.id}/call/token")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["room"], f"channel-{general.id}")
        self.assertTrue(resp.data["url"])

        # The token is a LiveKit JWT signed with the API secret; verify grants.
        claims = jwt.decode(
            resp.data["token"], settings.LIVEKIT_API_SECRET, algorithms=["HS256"]
        )
        self.assertEqual(claims["video"]["room"], f"channel-{general.id}")
        self.assertTrue(claims["video"]["roomJoin"])
        self.assertTrue(claims["video"]["canPublish"])

    def test_call_token_requires_membership(self):
        alice = self._register("alice")
        bob = self._register("bob")
        wid = self.workspace.id

        self._auth(alice["access"])
        resp = self.client.post(
            f"/api/workspaces/{wid}/channels",
            {"name": "secret", "isPrivate": True},
            format="json",
        )
        channel_id = resp.data["id"]

        self._auth(bob["access"])
        resp = self.client.post(f"/api/channels/{channel_id}/call/token")
        self.assertEqual(resp.status_code, 403)

    def test_non_member_cannot_read_private_channel(self):
        alice = self._register("alice")
        bob = self._register("bob")
        wid = self.workspace.id

        self._auth(alice["access"])
        resp = self.client.post(
            f"/api/workspaces/{wid}/channels",
            {"name": "secret", "isPrivate": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        channel_id = resp.data["id"]

        self._auth(bob["access"])
        resp = self.client.get(f"/api/channels/{channel_id}/messages")
        self.assertEqual(resp.status_code, 403)
