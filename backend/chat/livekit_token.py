"""Mint LiveKit access tokens.

A LiveKit access token is just an HS256 JWT signed with the project's API
secret, carrying a ``video`` grant claim. We build it directly with PyJWT (a
dependency we already have via SimpleJWT) so the backend needs no extra
LiveKit SDK.

Reference: https://docs.livekit.io/home/get-started/authentication/
"""
import time

import jwt
from django.conf import settings


def create_access_token(identity, name, room, ttl_seconds=3600,
                         can_publish=True, can_subscribe=True):
    """Return a signed LiveKit JWT granting access to ``room``."""
    now = int(time.time())
    claims = {
        "iss": settings.LIVEKIT_API_KEY,
        "sub": str(identity),
        "name": name or str(identity),
        "nbf": now,
        "iat": now,
        "exp": now + ttl_seconds,
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": can_publish,
            "canSubscribe": can_subscribe,
            "canPublishData": True,
        },
    }
    return jwt.encode(claims, settings.LIVEKIT_API_SECRET, algorithm="HS256")


def room_name_for_channel(channel_id):
    return f"channel-{channel_id}"
