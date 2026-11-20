from django import forms
from django.core.validators import FileExtensionValidator

from accounts.forms import _CivicValidatedFormMixin, _style_form_fields

from .models import Barangay, HazardCategory, HazardReport
from .validators import validate_attachment_file, validate_dispatch_remarks, validate_landmark_desc


class HazardReportForm(_CivicValidatedFormMixin, forms.ModelForm):
    """Citizen form to create or update a pending hazard report."""

    photo = forms.FileField(
        required=False,
        label="Photo Evidence (Optional)",
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp"]),
            validate_attachment_file,
        ],
    )

    class Meta:
        model = HazardReport
        fields = ("barangay", "category", "landmark_desc")
        labels = {
            "barangay": "Barangay Jurisdiction",
            "category": "Hazard Category",
            "landmark_desc": "Street & Landmark Description",
        }
        widgets = {
            "landmark_desc": forms.Textarea(
                attrs={
                    "rows": 4,
                    "minlength": "10",
                    "maxlength": "1000",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["barangay"].queryset = Barangay.objects.all()
        self.fields["barangay"].empty_label = "Select your barangay"
        self.fields["category"].queryset = HazardCategory.objects.all()
        self.fields["category"].empty_label = "Select hazard type"
        _style_form_fields(
            self,
            placeholders={
                "landmark_desc": "e.g., Corner Salinas Drive near JY Square, deep pothole blocking right lane",
            },
            extra_attrs={
                "photo": {"accept": ".jpg,.jpeg,.png,.webp,image/*"},
            },
        )

    def clean_landmark_desc(self):
        cleaned = " ".join((self.cleaned_data.get("landmark_desc") or "").split())
        validate_landmark_desc(cleaned)
        return cleaned

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo and hasattr(photo, "size"):
            validate_attachment_file(photo)
        return photo


class ReportFilterForm(forms.Form):
    """Shared filter form for Community Feed and LGU Dispatch Queue."""

    barangay = forms.ModelChoiceField(
        queryset=Barangay.objects.all(),
        required=False,
        empty_label="All Barangays",
    )
    category = forms.ModelChoiceField(
        queryset=HazardCategory.objects.all(),
        required=False,
        empty_label="All Categories",
    )
    status = forms.ChoiceField(
        choices=[("", "All Statuses"), *HazardReport.Status.choices],
        required=False,
    )
    sort = forms.ChoiceField(
        choices=[("votes", "Most Power-Ups"), ("newest", "Newest First")],
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_form_fields(self)


class AdminStatusUpdateForm(_CivicValidatedFormMixin, forms.Form):
    """LGU Admin form to update ticket status and log transparent dispatch remarks."""

    new_status = forms.ChoiceField(
        label="New Ticket Status",
        choices=HazardReport.Status.choices,
    )
    remarks = forms.CharField(
        label="Dispatch / Resolution Remarks",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "maxlength": "500",
                "placeholder": "Explain the dispatch action, schedule, or resolution details...",
            }
        ),
    )

    def __init__(self, *args, current_status=None, **kwargs):
        self.current_status = current_status
        super().__init__(*args, **kwargs)
        if current_status and not self.is_bound:
            self.fields["new_status"].initial = current_status
        _style_form_fields(self)

    def clean_remarks(self):
        cleaned = " ".join((self.cleaned_data.get("remarks") or "").split())
        validate_dispatch_remarks(cleaned)
        return cleaned

    def clean(self):
        cleaned_data = super().clean()
        new_status = cleaned_data.get("new_status")
        remarks = cleaned_data.get("remarks", "")

        if new_status and self.current_status and new_status == self.current_status:
            self.add_error(
                "new_status",
                "Please choose a different status than the current one.",
            )

        if new_status in {HazardReport.Status.RESOLVED, HazardReport.Status.CANCELLED} and not remarks:
            self.add_error(
                "remarks",
                "Please provide resolution or cancellation remarks for citizen transparency.",
            )
        return cleaned_data
