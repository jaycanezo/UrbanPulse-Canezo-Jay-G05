from django.db import migrations


def normalize_user_roles(apps, schema_editor):
    CustomUser = apps.get_model("accounts", "CustomUser")
    CustomUser.objects.filter(role__iexact="user").update(role="CITIZEN")
    CustomUser.objects.filter(role__iexact="admin").update(role="ADMIN")
    CustomUser.objects.filter(is_superuser=True).exclude(role="ADMIN").update(role="ADMIN")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_alter_customuser_managers"),
    ]

    operations = [
        migrations.RunPython(normalize_user_roles, noop_reverse),
    ]
