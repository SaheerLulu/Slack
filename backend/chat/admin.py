from django.contrib import admin

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

admin.site.register(User)
admin.site.register(Workspace)
admin.site.register(WorkspaceMember)
admin.site.register(Channel)
admin.site.register(ChannelMember)
admin.site.register(Message)
admin.site.register(Attachment)
admin.site.register(Reaction)
admin.site.register(Notification)
