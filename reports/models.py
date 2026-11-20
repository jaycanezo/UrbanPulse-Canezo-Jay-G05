from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models

from .validators import (
    validate_attachment_file,
    validate_dispatch_remarks,
    validate_landmark_desc,
)


class Barangay(models.Model):
    """Lookup table for LGU barangay jurisdictions."""

    barangay_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    district_code = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        db_table = "barangay"
        ordering = ["name"]
        verbose_name_plural = "Barangays"

    def __str__(self) -> str:
        return self.name


class HazardCategory(models.Model):
    """Lookup table for civic infrastructure hazard types."""

    category_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "hazard_category"
        ordering = ["name"]
        verbose_name_plural = "Hazard Categories"

    def __str__(self) -> str:
        return self.name


class HazardReport(models.Model):
    """Civic infrastructure hazard ticket submitted by a citizen."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        REVIEW = "REVIEW", "Under Review"
        SCHEDULED = "SCHEDULED", "Scheduled"
        RESOLVED = "RESOLVED", "Resolved"
        CANCELLED = "CANCELLED", "Cancelled"

    report_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="user_id",
        related_name="hazard_reports",
    )
    category = models.ForeignKey(
        HazardCategory,
        on_delete=models.PROTECT,
        db_column="category_id",
        related_name="hazard_reports",
    )
    barangay = models.ForeignKey(
        Barangay,
        on_delete=models.PROTECT,
        db_column="barangay_id",
        related_name="hazard_reports",
    )
    landmark_desc = models.TextField(validators=[validate_landmark_desc])
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "hazard_report"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["PENDING", "REVIEW", "SCHEDULED", "RESOLVED", "CANCELLED"]
                ),
                name="hazard_report_valid_status",
            ),
        ]

    @property
    def is_pending(self) -> bool:
        return self.status == self.Status.PENDING

    @property
    def can_receive_votes(self) -> bool:
        return self.status in {self.Status.PENDING, self.Status.REVIEW, self.Status.SCHEDULED}

    @property
    def can_citizen_delete(self) -> bool:
        return self.status in {self.Status.PENDING, self.Status.CANCELLED}

    def __str__(self) -> str:
        return f"#{self.report_id} — {self.category.name} ({self.barangay.name})"


class ReportAttachment(models.Model):
    """Photo attachment linked to a specific hazard report."""

    attachment_id = models.AutoField(primary_key=True)
    report = models.ForeignKey(
        HazardReport,
        on_delete=models.CASCADE,
        db_column="report_id",
        related_name="attachments",
    )
    file_url = models.FileField(
        upload_to="report_attachments/",
        max_length=255,
        db_column="file_url",
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "webp"]),
            validate_attachment_file,
        ],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "report_attachment"
        ordering = ["uploaded_at"]

    def __str__(self) -> str:
        return f"Attachment #{self.attachment_id} for Report #{self.report_id}"


class PowerUpVote(models.Model):
    """Community urgency vote cast once per citizen per hazard report."""

    vote_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="user_id",
        related_name="power_up_votes",
    )
    report = models.ForeignKey(
        HazardReport,
        on_delete=models.CASCADE,
        db_column="report_id",
        related_name="votes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "power_up_vote"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "report"],
                name="unique_user_report_vote",
            ),
        ]

    def __str__(self) -> str:
        return f"Vote by {self.user_id} on Report #{self.report_id}"


class TicketStatusHistory(models.Model):
    """Audit trail recording every status change on a hazard report."""

    log_id = models.AutoField(primary_key=True)
    report = models.ForeignKey(
        HazardReport,
        on_delete=models.CASCADE,
        db_column="report_id",
        related_name="status_history",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        db_column="changed_by",
        related_name="status_changes",
    )
    old_status = models.CharField(max_length=20, choices=HazardReport.Status.choices)
    new_status = models.CharField(max_length=20, choices=HazardReport.Status.choices)
    remarks = models.TextField(blank=True, null=True, validators=[validate_dispatch_remarks])
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ticket_status_history"
        ordering = ["-changed_at", "-log_id"]
        verbose_name_plural = "Ticket Status Histories"

    def __str__(self) -> str:
        return f"Report #{self.report_id}: {self.old_status} -> {self.new_status}"
