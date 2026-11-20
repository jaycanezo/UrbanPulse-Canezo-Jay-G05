import re

from django.core.exceptions import ValidationError

MAX_PROFILE_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB

_CONTACT_CHARS_RE = re.compile(r"^\+?[\d\s\-()]+$")
_CIVIC_LABEL_RE = re.compile(r"^[A-Za-z0-9À-ÖØ-öø-ÿ\s.,'\-&/()]+$")


def validate_person_name(value: str) -> None:
    """Allow 2-50 Unicode letters, spaces, hyphens, apostrophes, and periods."""
    cleaned = (value or "").strip()
    if not cleaned:
        return
    allowed_punct = {" ", "-", "'", "."}
    if (
        len(cleaned) < 2
        or len(cleaned) > 50
        or not any(ch.isalpha() for ch in cleaned)
        or not all(ch.isalpha() or ch in allowed_punct for ch in cleaned)
    ):
        raise ValidationError(
            "Enter a valid name using letters, spaces, hyphens, or apostrophes only (2-50 characters)."
        )


def validate_contact_number(value: str) -> None:
    """Reject letters/symbols and require 10-15 digits (optional leading '+')."""
    cleaned = (value or "").strip()
    if not cleaned:
        return
    if not _CONTACT_CHARS_RE.match(cleaned):
        raise ValidationError(
            "Enter a valid contact number using digits only (10-15 digits, e.g., 09171234567 or +63 917 123 4567)."
        )
    digits = re.sub(r"\D", "", cleaned)
    if not (10 <= len(digits) <= 15):
        raise ValidationError(
            "Contact number must contain between 10 and 15 digits."
        )


def validate_civic_label(value: str) -> None:
    """Validate barangay or department labels (2-100 safe characters)."""
    cleaned = (value or "").strip()
    if not cleaned:
        return
    if (
        len(cleaned) < 2
        or len(cleaned) > 100
        or not any(ch.isalnum() for ch in cleaned)
        or not _CIVIC_LABEL_RE.match(cleaned)
    ):
        raise ValidationError(
            "Use 2-100 valid characters (letters, numbers, spaces, and standard punctuation only)."
        )


def validate_profile_photo_size(file_obj) -> None:
    """Enforce a 5 MB max file size and image content type on profile photos."""
    if not file_obj:
        return
    if file_obj.size > MAX_PROFILE_PHOTO_BYTES:
        raise ValidationError("Profile photo must be 5 MB or smaller.")
    content_type = getattr(file_obj, "content_type", None)
    if content_type and not content_type.startswith("image/"):
        raise ValidationError("Please upload a valid image file (JPG, PNG, or WEBP).")
