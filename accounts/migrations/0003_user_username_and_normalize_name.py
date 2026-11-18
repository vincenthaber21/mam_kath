import re
import unicodedata

from django.db import migrations, models


def normalize_full_name(value):
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return ""
    return " ".join(part[:1].upper() + part[1:].lower() if part else "" for part in text.split(" "))


def normalize_username(value):
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    text = text.replace(" ", "_")
    text = re.sub(r"[^a-z0-9._-]", "", text)
    text = re.sub(r"[._-]{2,}", lambda m: m.group(0)[0], text)
    return text.strip("._-")


def populate_usernames_and_names(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    used = set()
    for user in User.objects.all().order_by("id"):
        user.name = normalize_full_name(user.name)
        base = normalize_username(user.email.split("@", 1)[0]) or f"user{user.pk}"
        candidate = base[:140]
        n = 2
        while candidate.lower() in used:
            suffix = f"_{n}"
            candidate = f"{base[:150 - len(suffix)]}{suffix}"
            n += 1
        used.add(candidate.lower())
        user.username = candidate
        user.save(update_fields=["username", "name"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_roles_and_incident_responses"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="username",
            field=models.CharField(
                help_text="Unique handle for the account (letters, numbers, ., _, -).",
                max_length=150,
                null=True,
                verbose_name="username",
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="name",
            field=models.CharField(blank=True, max_length=120, verbose_name="full name"),
        ),
        migrations.RunPython(populate_usernames_and_names, noop_reverse),
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(
                help_text="Unique handle for the account (letters, numbers, ., _, -).",
                max_length=150,
                unique=True,
                verbose_name="username",
            ),
        ),
    ]
