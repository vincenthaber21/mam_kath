import re
import unicodedata

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


def _title_name_token(token):
    """Title-case one name token, keeping hyphens and apostrophes (Mary-Ann, O'Brien)."""
    if not token:
        return ""
    pieces = re.split(r"([-'])", token)
    out = []
    for piece in pieces:
        if piece in ("-", "'"):
            out.append(piece)
        elif piece:
            out.append(piece[:1].upper() + piece[1:].lower())
    return "".join(out)


def normalize_person_name(value):
    """Collapse whitespace and title-case a name part."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip()
    text = re.sub(r"[\t\r\n]+", " ", text)
    text = re.sub(r" +", " ", text)
    if not text:
        return ""
    return " ".join(_title_name_token(part) for part in text.split(" ") if part)


# Backwards-compatible alias used by older imports/tests.
normalize_full_name = normalize_person_name


def compose_full_name(last_name="", first_name="", middle_name=""):
    """Display as 'First Middle Last' when parts exist."""
    parts = [normalize_person_name(first_name), normalize_person_name(middle_name), normalize_person_name(last_name)]
    return " ".join(p for p in parts if p)


def split_full_name(value):
    """Best-effort split of a legacy full name into first / middle / last."""
    text = normalize_person_name(value)
    if not text:
        return "", "", ""
    parts = text.split(" ")
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], "", parts[1]
    return parts[0], " ".join(parts[1:-1]), parts[-1]


def normalize_username(value):
    """Lowercase slug-style username: letters, digits, dots, underscores, hyphens."""
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    text = text.replace(" ", "_")
    text = re.sub(r"[^a-z0-9._-]", "", text)
    text = re.sub(r"[._-]{2,}", lambda m: m.group(0)[0], text)
    return text.strip("._-")


class UserManager(BaseUserManager):
    """Users sign in with their email address instead of a username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()

        # Allow legacy `name="Juan Dela Cruz"` when creating users in tests/scripts.
        legacy_name = extra.pop("name", None)
        if legacy_name and not any(extra.get(k) for k in ("first_name", "middle_name", "last_name")):
            first, middle, last = split_full_name(legacy_name)
            extra.setdefault("first_name", first)
            extra.setdefault("middle_name", middle)
            extra.setdefault("last_name", last)

        for key in ("first_name", "middle_name", "last_name"):
            if key in extra:
                extra[key] = normalize_person_name(extra.get(key))

        extra["name"] = compose_full_name(
            extra.get("last_name", ""),
            extra.get("first_name", ""),
            extra.get("middle_name", ""),
        )

        username = extra.get("username")
        if username:
            extra["username"] = normalize_username(username)
        elif not extra.get("username"):
            base = normalize_username(email.split("@", 1)[0]) or "user"
            extra["username"] = self._unique_username(base)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def _unique_username(self, base):
        candidate = base[:140] or "user"
        if not self.model.objects.filter(username__iexact=candidate).exists():
            return candidate
        n = 2
        while True:
            suffix = f"_{n}"
            trimmed = candidate[: 150 - len(suffix)]
            trial = f"{trimmed}{suffix}"
            if not self.model.objects.filter(username__iexact=trial).exists():
                return trial
            n += 1

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        extra.setdefault("role", User.Role.RESIDENT)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", User.Role.ADMIN)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("A superuser needs is_staff=True and is_superuser=True.")
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    class Role(models.TextChoices):
        RESIDENT = "resident", "Resident"
        OFFICER = "officer", "Officer"
        ADMIN = "admin", "Administrator"

    username = models.CharField(
        "username",
        max_length=150,
        unique=True,
        help_text="Unique handle for the account (letters, numbers, ., _, -).",
    )
    email = models.EmailField("email address", unique=True)
    first_name = models.CharField("first name", max_length=150, blank=True)
    middle_name = models.CharField("middle name", max_length=150, blank=True)
    last_name = models.CharField("last name", max_length=150, blank=True)
    # Kept in sync for older templates/exports that still read `name`.
    name = models.CharField("full name", max_length=200, blank=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.RESIDENT,
        help_text="Residents report incidents; officers monitor and respond.",
    )
    phone = models.CharField(max_length=40, blank=True)
    barangay = models.CharField(max_length=120, blank=True, help_text="Barangay or area covered")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    objects = UserManager()

    class Meta:
        ordering = ["last_name", "first_name", "email"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.first_name = normalize_person_name(self.first_name)
        self.middle_name = normalize_person_name(self.middle_name)
        self.last_name = normalize_person_name(self.last_name)
        self.name = compose_full_name(self.last_name, self.first_name, self.middle_name)
        if self.username:
            self.username = normalize_username(self.username)
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.name or self.username or self.email

    @property
    def formal_name(self):
        """Last, First Middle — common on local forms/lists."""
        given = " ".join(p for p in [self.first_name, self.middle_name] if p)
        if self.last_name and given:
            return f"{self.last_name}, {given}"
        return self.last_name or given or self.display_name

    @property
    def role_label(self):
        return self.get_role_display()

    @property
    def is_resident(self):
        return self.role == self.Role.RESIDENT

    @property
    def is_officer(self):
        return self.role == self.Role.OFFICER or self.is_admin_role

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def can_manage_users(self):
        return self.is_admin_role or self.is_staff

    @property
    def can_monitor_incidents(self):
        """Officers and admins see every incident; residents see their own."""
        return self.is_officer or self.can_manage_users
