from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from accounts.mixins import RoleRequiredMixin
from accounts.models import CustomUser
from reports.models import HazardReport


class RoleRedirectView(LoginRequiredMixin, View):
    """Routes authenticated users to the dashboard matching their role."""

    def get(self, request, *args, **kwargs):
        if request.user.is_lgu_admin:
            return redirect("admin_panel")
        return redirect("dashboard")


class CitizenDashboardView(RoleRequiredMixin, TemplateView):
    """Dashboard for Citizen (Urban Resident) users."""

    allowed_role = CustomUser.Role.CITIZEN
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        checklist = [
            {
                "label": "Full name verified",
                "done": bool(user.first_name and user.last_name),
                "hint": "Helps LGU staff address follow-ups accurately",
            },
            {
                "label": "Barangay jurisdiction linked",
                "done": bool(user.barangay),
                "hint": "Connects reports to your neighborhood district",
            },
            {
                "label": "Contact number added",
                "done": bool(user.contact_number),
                "hint": "Optional hotline for urgent dispatch coordination",
            },
            {
                "label": "Profile photo uploaded",
                "done": bool(user.profile_photo),
                "hint": "Builds visible community trust",
            },
        ]
        completed_steps = sum(1 for item in checklist if item["done"])
        total_steps = len(checklist)
        my_reports = HazardReport.objects.filter(user=user)
        context["checklist"] = checklist
        context["completed_steps"] = completed_steps
        context["total_steps"] = total_steps
        context["completion_pct"] = int((completed_steps / total_steps) * 100)
        context["my_reports_count"] = my_reports.count()
        context["my_pending_count"] = my_reports.filter(status=HazardReport.Status.PENDING).count()
        context["my_resolved_count"] = my_reports.filter(status=HazardReport.Status.RESOLVED).count()
        context["recent_my_reports"] = (
            my_reports.select_related("barangay", "category")
            .annotate(vote_count=Count("votes", distinct=True))
            .order_by("-created_at")[:5]
        )
        return context


class AdminPanelView(RoleRequiredMixin, TemplateView):
    """Dispatch console for LGU Staff / Admin users."""

    allowed_role = CustomUser.Role.ADMIN
    template_name = "dashboard/admin_panel.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_users"] = CustomUser.objects.count()
        context["citizen_count"] = CustomUser.objects.filter(role__iexact=CustomUser.Role.CITIZEN).count()
        context["admin_count"] = CustomUser.objects.filter(role__iexact=CustomUser.Role.ADMIN).count()
        context["barangay_count"] = (
            CustomUser.objects.exclude(barangay="").values("barangay").distinct().count()
        )
        context["recent_users"] = CustomUser.objects.order_by("-date_joined")[:6]

        all_reports = HazardReport.objects.all()
        context["total_reports"] = all_reports.count()
        context["pending_reports"] = all_reports.filter(status=HazardReport.Status.PENDING).count()
        context["in_progress_reports"] = all_reports.filter(
            status__in=[HazardReport.Status.REVIEW, HazardReport.Status.SCHEDULED]
        ).count()
        context["resolved_reports"] = all_reports.filter(status=HazardReport.Status.RESOLVED).count()
        context["priority_reports"] = (
            all_reports.filter(
                status__in=[
                    HazardReport.Status.PENDING,
                    HazardReport.Status.REVIEW,
                    HazardReport.Status.SCHEDULED,
                ]
            )
            .select_related("barangay", "category")
            .annotate(vote_count=Count("votes", distinct=True))
            .order_by("-vote_count", "created_at")[:5]
        )
        return context
