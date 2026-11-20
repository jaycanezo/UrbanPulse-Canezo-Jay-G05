from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from accounts.models import CustomUser


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restricts a view to users with a specific role."""

    allowed_role = None

    def test_func(self):
        return (self.request.user.role or "").upper() == self.allowed_role


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
        context["checklist"] = checklist
        context["completed_steps"] = completed_steps
        context["total_steps"] = total_steps
        context["completion_pct"] = int((completed_steps / total_steps) * 100)
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
        return context
