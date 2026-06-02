from rest_framework import serializers

from .models import (
    Attachment,
    Channel,
    Message,
    Notification,
    Reaction,
    User,
    Workspace,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "display_name", "avatar_url"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    display_name = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["id", "username", "display_name", "password"]

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("That username is taken.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(
            username=validated_data["username"],
            display_name=validated_data.get("display_name", ""),
        )
        user.set_password(password)
        user.save()
        return user


class WorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ["id", "name", "slug", "created_at"]
        read_only_fields = ["slug", "created_at"]


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ["id", "filename", "content_type", "size", "url"]

    def get_url(self, obj):
        return f"/api/files/{obj.id}"


class ReactionSummarySerializer(serializers.Serializer):
    """Aggregated reaction: one row per emoji with the user ids who reacted."""

    emoji = serializers.CharField()
    count = serializers.IntegerField()
    user_ids = serializers.ListField(child=serializers.IntegerField())


class MessageSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    reactions = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()
    is_pinned = serializers.SerializerMethodField()
    saved = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id", "channel", "user", "content", "parent",
            "created_at", "edited_at", "is_deleted",
            "attachments", "reactions", "reply_count",
            "is_pinned", "saved",
        ]

    def get_content(self, obj):
        return "" if obj.is_deleted else obj.content

    def get_is_pinned(self, obj):
        return obj.pinned_at is not None

    def get_saved(self, obj):
        # The view passes the set of message ids this user has saved.
        return obj.id in self.context.get("saved_ids", set())

    def get_reply_count(self, obj):
        # Annotated in the queryset where available; fall back to a count.
        if hasattr(obj, "reply_count_annotated"):
            return obj.reply_count_annotated
        return obj.replies.count()

    def get_reactions(self, obj):
        summary = {}
        for r in obj.reactions.all():
            entry = summary.setdefault(r.emoji, {"emoji": r.emoji, "count": 0, "user_ids": []})
            entry["count"] += 1
            entry["user_ids"].append(r.user_id)
        return list(summary.values())


class NotificationSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id", "type", "actor", "channel", "message", "is_read", "created_at",
        ]
