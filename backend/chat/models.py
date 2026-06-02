from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with a display name and optional avatar."""

    display_name = models.CharField(max_length=80, blank=True)
    avatar_url = models.URLField(blank=True)

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.username
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


class Workspace(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=80, unique=True)
    created_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="created_workspaces"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(
        User, through="WorkspaceMember", related_name="workspaces"
    )

    def __str__(self):
        return self.name


class WorkspaceMember(models.Model):
    OWNER = "owner"
    MEMBER = "member"
    ROLE_CHOICES = [(OWNER, "Owner"), (MEMBER, "Member")]

    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="workspace_memberships"
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("workspace", "user")


class Channel(models.Model):
    workspace = models.ForeignKey(
        Workspace, on_delete=models.CASCADE, related_name="channels"
    )
    name = models.CharField(max_length=80, blank=True)
    topic = models.CharField(max_length=250, blank=True)
    is_private = models.BooleanField(default=False)
    is_dm = models.BooleanField(default=False)
    # Stable sorted "wsId:id:id[:id...]" key identifying a DM / group DM.
    dm_key = models.CharField(max_length=255, unique=True, null=True, blank=True)
    created_by = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="created_channels"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    members = models.ManyToManyField(
        User, through="ChannelMember", related_name="channels"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"],
                condition=models.Q(is_dm=False),
                name="unique_channel_name_per_workspace",
            )
        ]

    def __str__(self):
        return self.name or f"DM:{self.dm_key}"


class ChannelMember(models.Model):
    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="channel_memberships"
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    # Last message this user has read in the channel (for unread counts).
    last_read_message = models.ForeignKey(
        "Message", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # Muted channels don't surface unread badges or notifications.
    muted = models.BooleanField(default=False)

    class Meta:
        unique_together = ("channel", "user")


class Message(models.Model):
    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="messages"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="messages"
    )
    content = models.TextField(blank=True)
    # Thread root; null for top-level messages.
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    # Pinned-to-channel metadata (pinned_at is set when pinned).
    pinned_at = models.DateTimeField(null=True, blank=True)
    pinned_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        indexes = [models.Index(fields=["channel", "id"])]
        ordering = ["id"]


class Attachment(models.Model):
    message = models.ForeignKey(
        Message, null=True, blank=True, on_delete=models.CASCADE,
        related_name="attachments",
    )
    uploaded_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(upload_to="attachments/%Y/%m/")
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120)
    size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class Reaction(models.Model):
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="reactions"
    )
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reactions"
    )
    emoji = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("message", "user", "emoji")


class SavedItem(models.Model):
    """A user's bookmarked / saved message."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="saved_items"
    )
    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="saved_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "message")
        ordering = ["-id"]


class Notification(models.Model):
    MENTION = "mention"
    REPLY = "reply"
    DM = "dm"
    TYPE_CHOICES = [(MENTION, "Mention"), (REPLY, "Reply"), (DM, "Direct message")]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    actor = models.ForeignKey(
        User, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    channel = models.ForeignKey(
        Channel, null=True, on_delete=models.CASCADE, related_name="+"
    )
    message = models.ForeignKey(
        Message, null=True, on_delete=models.CASCADE, related_name="+"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
