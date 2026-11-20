from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """Authenticate users by either case-insensitive username or email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or password is None:
            return None
        identifier = username.strip()
        if not identifier:
            return None

        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(Q(username__iexact=identifier) | Q(email__iexact=identifier))
        except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned):
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
