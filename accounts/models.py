from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import FileExtensionValidator
from django.db import models

from .validators import (
    validate_civic_label,
    validate_contact_number,
    validate_profile_photo_size,
)


class CustomUserManager(UserManager):
    """Custom manager ensuring superusers default to the LGU Admin role."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", CustomUser.Role.ADMIN)
        return super().create_superuser(username, email=email, password=password, **extra_fields)


class CustomUser(AbstractUser):
    """Custom user model supporting Citizen and LGU Admin/Dispatcher roles."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "LGU Staff / Admin"
        CITIZEN = "CITIZEN", "Citizen"

    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.CITIZEN,
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        validators=[validate_civic_label],
    )
    contact_number = models.CharField(
        max_length=20,
        blank=True,
        default="",
        validators=[validate_contact_number],
    )
    barangay = models.CharField(
        max_length=100,
        blank=True,
        default="",
        validators=[validate_civic_label],
    )
    profile_photo = models.FileField(
        upload_to="profile_photos/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp"]),
            validate_profile_photo_size,
        ],
    )

    objects = CustomUserManager()

    @property
    def is_lgu_admin(self) -> bool:
        return (self.role or "").upper() == self.Role.ADMIN

    @property
    def is_citizen(self) -> bool:
        return (self.role or "").upper() == self.Role.CITIZEN

    @property
    def initials(self) -> str:
        first = (self.first_name or "").strip()
        last = (self.last_name or "").strip()
        if first and last:
            return f"{first[0]}{last[0]}".upper()
        if first:
            return first[:2].upper()
        return (self.username or "UP")[:2].upper()

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"
