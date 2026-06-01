from django.db import migrations


def seed(apps, schema_editor):
    Workspace = apps.get_model("chat", "Workspace")
    Channel = apps.get_model("chat", "Channel")
    if Workspace.objects.exists():
        return
    workspace = Workspace.objects.create(name="Acme", slug="acme")
    Channel.objects.create(
        workspace=workspace,
        name="general",
        topic="Company-wide announcements and chatter",
        is_private=False,
        is_dm=False,
    )


def unseed(apps, schema_editor):
    # No-op: keep user data on reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
