import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm

from .models import CustomUser
from .validators import (
    validate_civic_label,
    validate_contact_number,
    validate_person_name,
    validate_profile_photo_size,
)

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.+-]{3,30}$")


def _collapse_spaces(value: str) -> str:
    return " ".join((value or "").split())


def _validate_unique_email(email: str, exclude_pk=None) -> str:
    """Normalize email and ensure it is unique across users."""
    normalized = (email or "").strip().lower()
    qs = CustomUser.objects.filter(email__iexact=normalized)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise forms.ValidationError("An account with this email address already exists.")
    return normalized


def _clean_person_name(value: str) -> str:
    cleaned = _collapse_spaces(value)
    validate_person_name(cleaned)
    return cleaned


def _clean_contact_number(value: str) -> str:
    cleaned = _collapse_spaces(value)
    validate_contact_number(cleaned)
    return cleaned


def _clean_civic_label(value: str) -> str:
    cleaned = _collapse_spaces(value)
    validate_civic_label(cleaned)
    return cleaned


def _style_form_fields(
    form: forms.BaseForm,
    placeholders: dict[str, str] | None = None,
    extra_attrs: dict[str, dict[str, str]] | None = None,
) -> None:
    """Apply shared Civic Unity CSS classes, placeholders, and HTML5 validation attributes."""
    placeholders = placeholders or {}
    extra_attrs = extra_attrs or {}
    for name, field in form.fields.items():
        widget = field.widget
        is_file = isinstance(widget, forms.ClearableFileInput)
        base_class = "form-file" if is_file else "form-input"
        existing = widget.attrs.get("class", "")
        widget.attrs["class"] = f"{existing} {base_class}".strip()
        if name in placeholders and not is_file:
            widget.attrs.setdefault("placeholder", placeholders[name])
        if name in extra_attrs:
            widget.attrs.update(extra_attrs[name])


class _CivicValidatedFormMixin:
    """Marks errored fields with is-invalid and aria-invalid=true after validation."""

    def full_clean(self):
        super().full_clean()
        if not self.is_bound:
            return
        for field_name in self.errors:
            if field_name in self.fields:
                attrs = self.fields[field_name].widget.attrs
                css = attrs.get("class", "")
                if "is-invalid" not in css:
                    attrs["class"] = f"{css} is-invalid".strip()
                attrs["aria-invalid"] = "true"


_PROFILE_WIDGET_ATTRS = {
    "email": {
        "type": "email",
        "maxlength": "254",
        "autocomplete": "email",
    },
    "first_name": {
        "minlength": "2",
        "maxlength": "50",
        "title": "Letters, spaces, hyphens, or apostrophes only (2-50 characters)",
        "data-filter": "name",
        "autocomplete": "given-name",
    },
    "last_name": {
        "minlength": "2",
        "maxlength": "50",
        "title": "Letters, spaces, hyphens, or apostrophes only (2-50 characters)",
        "data-filter": "name",
        "autocomplete": "family-name",
    },
    "contact_number": {
        "type": "tel",
        "inputmode": "tel",
        "maxlength": "20",
        "pattern": r"^\+?[0-9\s\-()]{10,20}$",
        "title": "Digits only (10-15 digits), e.g., 09171234567 or +63 917 123 4567",
        "data-filter": "phone",
        "autocomplete": "tel",
    },
    "barangay": {
        "minlength": "2",
        "maxlength": "100",
        "title": "2-100 valid characters",
    },
}


class CustomAuthenticationForm(_CivicValidatedFormMixin, AuthenticationForm):
    """Login form accepting username or email with clear inline errors."""

    username = forms.CharField(
        label="Username or Email",
        max_length=254,
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "autocomplete": "username",
                "maxlength": "254",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
            }
        ),
    )

    error_messages = {
        "invalid_login": (
            "Incorrect username/email or password. Please check your credentials and try again."
        ),
        "inactive": "This account is currently inactive. Please contact your LGU administrator.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_form_fields(
            self,
            {
                "username": "Enter your username or email",
                "password": "Enter your password",
            },
        )

    def clean_username(self):
        return (self.cleaned_data.get("username") or "").strip()


class CustomUserCreationForm(_CivicValidatedFormMixin, UserCreationForm):
    """Public registration form; validates essential fields and assigns CITIZEN role."""

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("first_name", "last_name", "username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("email", "first_name", "last_name"):
            self.fields[field_name].required = True
        _style_form_fields(
            self,
            placeholders={
                "first_name": "Juan",
                "last_name": "Dela Cruz",
                "username": "juan.delacruz",
                "email": "you@example.com",
                "password1": "At least 8 characters",
                "password2": "Re-enter password",
            },
            extra_attrs={
                **_PROFILE_WIDGET_ATTRS,
                "username": {
                    "minlength": "3",
                    "maxlength": "30",
                    "pattern": r"^[A-Za-z0-9_.+-]{3,30}$",
                    "title": "3-30 characters: letters, numbers, and _ . + - only (no spaces)",
                    "data-filter": "username",
                    "autocomplete": "username",
                },
                "password1": {"minlength": "8", "autocomplete": "new-password"},
                "password2": {"minlength": "8", "autocomplete": "new-password"},
            },
        )

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not _USERNAME_RE.match(username):
            raise forms.ValidationError(
                "Username must be 3-30 characters using letters, numbers, and _ . + - only (no spaces)."
            )
        if CustomUser.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        return _validate_unique_email(self.cleaned_data["email"])

    def clean_first_name(self):
        return _clean_person_name(self.cleaned_data["first_name"])

    def clean_last_name(self):
        return _clean_person_name(self.cleaned_data["last_name"])

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.role = CustomUser.Role.CITIZEN
        if commit:
            user.save()
        return user


class CustomUserChangeForm(UserChangeForm):
    """Admin form for editing users including role and department."""

    class Meta(UserChangeForm.Meta):
        model = CustomUser
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "department",
            "contact_number",
            "barangay",
            "profile_photo",
        )


class ProfileUpdateForm(_CivicValidatedFormMixin, forms.ModelForm):
    """Form for logged-in users to update their own profile details."""

    class Meta:
        model = CustomUser
        fields = ("first_name", "last_name", "email", "contact_number", "barangay", "profile_photo")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ("email", "first_name", "last_name"):
            self.fields[field_name].required = True
        _style_form_fields(
            self,
            placeholders={
                "first_name": "First name",
                "last_name": "Last name",
                "email": "you@example.com",
                "contact_number": "0917 123 4567",
                "barangay": "e.g., Lahug",
            },
            extra_attrs=_PROFILE_WIDGET_ATTRS,
        )

    def clean_email(self):
        return _validate_unique_email(self.cleaned_data["email"], exclude_pk=self.instance.pk)

    def clean_first_name(self):
        return _clean_person_name(self.cleaned_data["first_name"])

    def clean_last_name(self):
        return _clean_person_name(self.cleaned_data["last_name"])

    def clean_contact_number(self):
        return _clean_contact_number(self.cleaned_data.get("contact_number", ""))

    def clean_barangay(self):
        return _clean_civic_label(self.cleaned_data.get("barangay", ""))

    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")
        if photo and hasattr(photo, "size"):
            validate_profile_photo_size(photo)
        return photo
