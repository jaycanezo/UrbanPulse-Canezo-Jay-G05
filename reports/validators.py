from django.core.exceptions import ValidationError

MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024  # 5 MB


def validate_landmark_desc(value: str) -> None:
    """Validate street/landmark description (10-1000 chars, no HTML angle brackets)."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValidationError("Please describe the exact street or visual landmark.")
    if "<" in cleaned or ">" in cleaned:
        raise ValidationError("Angle brackets (< or >) are not allowed in the description.")
    if len(cleaned) < 10 or len(cleaned) > 1000:
        raise ValidationError("Landmark description must be between 10 and 1000 characters.")
    if sum(1 for ch in cleaned if ch.isalnum()) < 5:
        raise ValidationError("Please provide a meaningful landmark or street description.")


def validate_dispatch_remarks(value: str) -> None:
    """Validate optional LGU dispatch remarks (5-500 chars when provided, no HTML brackets)."""
    cleaned = (value or "").strip()
    if not cleaned:
        return
    if "<" in cleaned or ">" in cleaned:
        raise ValidationError("Angle brackets (< or >) are not allowed in remarks.")
    if len(cleaned) < 5 or len(cleaned) > 500:
        raise ValidationError("Remarks must be between 5 and 500 characters.")


def validate_attachment_file(file_obj) -> None:
    """Enforce 5 MB size cap and image MIME type on hazard report photos."""
    if not file_obj:
        return
    if file_obj.size > MAX_ATTACHMENT_BYTES:
        raise ValidationError("Attachment photo must be 5 MB or smaller.")
    content_type = getattr(file_obj, "content_type", None)
    if content_type and not content_type.startswith("image/"):
        raise ValidationError("Please upload a valid image file (JPG, PNG, or WEBP).")
