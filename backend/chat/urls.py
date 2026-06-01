from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    # Auth
    path("auth/register", views.register),
    path("auth/login", views.login),
    path("auth/refresh", TokenRefreshView.as_view()),
    path("auth/me", views.me),

    # Workspaces
    path("workspaces", views.WorkspaceListCreate.as_view()),
    path("workspaces/<int:workspace_id>/join", views.join_workspace),
    path("workspaces/<int:workspace_id>/members", views.workspace_members),
    path("workspaces/<int:workspace_id>/channels",
         views.ChannelListCreate.as_view()),
    path("workspaces/<int:workspace_id>/dm/<int:user_id>", views.open_dm),
    path("workspaces/<int:workspace_id>/search", views.search),

    # Channels
    path("channels/<int:channel_id>/join", views.join_channel),
    path("channels/<int:channel_id>/members", views.channel_members),
    path("channels/<int:channel_id>/read", views.mark_read),
    path("channels/<int:channel_id>/messages", views.channel_messages),

    # Messages
    path("messages/<int:message_id>", views.message_detail),
    path("messages/<int:message_id>/thread", views.message_thread),
    path("messages/<int:message_id>/reactions", views.reactions),

    # Files
    path("files", views.upload_file),
    path("files/<int:attachment_id>", views.download_file),

    # Notifications
    path("notifications", views.list_notifications),
    path("notifications/read", views.read_notifications),
]
