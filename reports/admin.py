from django.contrib import admin

from .models import (
    Barangay,
    HazardCategory,
    HazardReport,
    PowerUpVote,
    ReportAttachment,
    TicketStatusHistory,
)


@admin.register(Barangay)
class BarangayAdmin(admin.ModelAdmin):
    list_display = ["barangay_id", "name", "district_code"]
    search_fields = ["name", "district_code"]


@admin.register(HazardCategory)
class HazardCategoryAdmin(admin.ModelAdmin):
    list_display = ["category_id", "name", "description"]
    search_fields = ["name"]


@admin.register(HazardReport)
class HazardReportAdmin(admin.ModelAdmin):
    list_display = ["report_id", "category", "barangay", "user", "status", "created_at"]
    list_filter = ["status", "barangay", "category"]
    search_fields = ["landmark_desc", "user__username"]


@admin.register(ReportAttachment)
class ReportAttachmentAdmin(admin.ModelAdmin):
    list_display = ["attachment_id", "report", "file_url", "uploaded_at"]


@admin.register(PowerUpVote)
class PowerUpVoteAdmin(admin.ModelAdmin):
    list_display = ["vote_id", "report", "user", "created_at"]


@admin.register(TicketStatusHistory)
class TicketStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ["log_id", "report", "old_status", "new_status", "changed_by", "changed_at"]
    list_filter = ["new_status", "old_status"]
