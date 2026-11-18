from django.db import migrations, models


def split_existing_names(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.all():
        text = (user.name or "").strip()
        # Prefer already-filled AbstractUser parts when present.
        if user.first_name or user.last_name:
            parts = [user.first_name, getattr(user, "middle_name", "") or "", user.last_name]
            user.name = " ".join(p for p in parts if p).strip()
            user.save(update_fields=["name"])
            continue
        if not text:
            continue
        words = text.split()
        if len(words) == 1:
            user.first_name = words[0]
        elif len(words) == 2:
            user.first_name, user.last_name = words[0], words[1]
        else:
            user.first_name = words[0]
            user.middle_name = " ".join(words[1:-1])
            user.last_name = words[-1]
        user.name = " ".join(p for p in [user.first_name, user.middle_name, user.last_name] if p)
        user.save(update_fields=["first_name", "middle_name", "last_name", "name"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_username_and_normalize_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="middle_name",
            field=models.CharField(blank=True, max_length=150, verbose_name="middle name"),
        ),
        migrations.AlterField(
            model_name="user",
            name="first_name",
            field=models.CharField(blank=True, max_length=150, verbose_name="first name"),
        ),
        migrations.AlterField(
            model_name="user",
            name="last_name",
            field=models.CharField(blank=True, max_length=150, verbose_name="last name"),
        ),
        migrations.AlterField(
            model_name="user",
            name="name",
            field=models.CharField(blank=True, max_length=200, verbose_name="full name"),
        ),
        migrations.RunPython(split_existing_names, noop_reverse),
    ]
