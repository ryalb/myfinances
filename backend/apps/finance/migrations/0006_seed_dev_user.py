from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import migrations


def seed_dev_user(apps, schema_editor):
    if not settings.DEBUG:
        return
    User = apps.get_model("auth", "User")
    user, created = User.objects.get_or_create(
        username="ryan.leite@gmail.com",
        defaults={
            "email": "ryan.leite@gmail.com",
            "password": make_password("dev"),
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )
    if created:
        print("Seeded dev user ryan.leite@gmail.com")


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("finance", "0005_documentchunk_embedding_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_dev_user, migrations.RunPython.noop),
    ]
