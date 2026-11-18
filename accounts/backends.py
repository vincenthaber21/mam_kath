from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

from .models import normalize_username


class EmailOrUsernameBackend(ModelBackend):
    """Allow sign-in with either email (USERNAME_FIELD) or account username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None

        login = str(username).strip()
        if not login:
            return None

        user = self._find_user(User, login)
        if user is None:
            # Run the default password hasher once so timing stays similar on misses.
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def _find_user(self, User, login):
        if "@" in login:
            try:
                return User.objects.get(email__iexact=login.lower())
            except User.DoesNotExist:
                return None

        candidates = []
        normalized = normalize_username(login)
        if normalized:
            candidates.append(normalized)
        lowered = login.lower()
        if lowered not in candidates:
            candidates.append(lowered)

        for candidate in candidates:
            try:
                return User.objects.get(username__iexact=candidate)
            except User.DoesNotExist:
                continue
        return None
