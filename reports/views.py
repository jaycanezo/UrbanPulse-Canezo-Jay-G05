from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.mixins import RoleRequiredMixin
from accounts.models import CustomUser

from .forms import HazardReportForm, ReportFilterForm
from .models import HazardReport, PowerUpVote, ReportAttachment, TicketStatusHistory


def _filter_report_queryset(queryset, params):
    """Apply barangay, category, status, and ordering filters from query parameters."""
    barangay_id = params.get("barangay")
    category_id = params.get("category")
    status = params.get("status")
    sort = params.get("sort") or "votes"

    if barangay_id and barangay_id.isdigit():
        queryset = queryset.filter(barangay_id=int(barangay_id))
    if category_id and category_id.isdigit():
        queryset = queryset.filter(category_id=int(category_id))
    if status and status in HazardReport.Status.values:
        queryset = queryset.filter(status=status)

    if sort == "newest":
        return queryset.order_by("-created_at")
    return queryset.order_by("-vote_count", "-created_at")


class CommunityReportListView(RoleRequiredMixin, ListView):
    """Citizen view of community hazard reports and personal submissions."""

    allowed_role = CustomUser.Role.CITIZEN
    template_name = "reports/report_list.html"
    context_object_name = "reports"

    def get_queryset(self):
        qs = (
            HazardReport.objects.select_related("user", "barangay", "category")
            .prefetch_related("attachments")
            .annotate(vote_count=Count("votes", distinct=True))
        )
        if self.request.GET.get("scope") == "mine":
            qs = qs.filter(user=self.request.user)
        return _filter_report_queryset(qs, self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = ReportFilterForm(self.request.GET or None)
        context["scope"] = self.request.GET.get("scope", "all")
        context["voted_report_ids"] = set(
            PowerUpVote.objects.filter(user=self.request.user).values_list("report_id", flat=True)
        )
        return context


class HazardReportCreateView(RoleRequiredMixin, CreateView):
    """Allows a Citizen to submit a new hazard report with an optional photo."""

    allowed_role = CustomUser.Role.CITIZEN
    model = HazardReport
    form_class = HazardReportForm
    template_name = "reports/report_form.html"

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.user = self.request.user
            form.instance.status = HazardReport.Status.PENDING
            self.object = form.save()
            photo = form.cleaned_data.get("photo")
            if photo:
                ReportAttachment.objects.create(report=self.object, file_url=photo)
        messages.success(
            self.request,
            f"Hazard report #{self.object.report_id} submitted for LGU review.",
        )
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, "Please fix the highlighted fields before submitting.")
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse("report_detail", kwargs={"pk": self.object.pk})


class HazardReportDetailView(LoginRequiredMixin, DetailView):
    """Displays full ticket details, photo attachments, and audit timeline."""

    model = HazardReport
    template_name = "reports/report_detail.html"
    context_object_name = "report"

    def get_queryset(self):
        return (
            HazardReport.objects.select_related("user", "barangay", "category")
            .prefetch_related("attachments", "status_history__changed_by")
            .annotate(vote_count=Count("votes", distinct=True))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["has_voted"] = PowerUpVote.objects.filter(
            user=self.request.user, report=self.object
        ).exists()
        context["is_owner"] = self.object.user_id == self.request.user.pk
        return context


class _OwnedCitizenReportMixin(RoleRequiredMixin):
    """Ensures only the owning Citizen can modify or remove their report."""

    allowed_role = CustomUser.Role.CITIZEN

    def get_owned_report(self, pk):
        report = get_object_or_404(HazardReport, pk=pk)
        if report.user_id != self.request.user.pk:
            raise PermissionDenied("You can only modify your own hazard reports.")
        return report


class HazardReportUpdateView(_OwnedCitizenReportMixin, UpdateView):
    """Allows the owning Citizen to edit a report while its status is PENDING (BR-07)."""

    model = HazardReport
    form_class = HazardReportForm
    template_name = "reports/report_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not self.test_func():
            return self.handle_no_permission()
        self.object = self.get_owned_report(kwargs["pk"])
        if not self.object.is_pending:
            messages.error(
                request,
                "Only PENDING hazard reports can be edited once LGU review begins.",
            )
            return redirect("report_detail", pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.object

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            photo = form.cleaned_data.get("photo")
            if photo:
                ReportAttachment.objects.create(report=self.object, file_url=photo)
        messages.success(self.request, f"Hazard report #{self.object.report_id} updated.")
        return redirect("report_detail", pk=self.object.pk)

    def form_invalid(self, form):
        messages.error(self.request, "Could not save changes. Please review the form errors.")
        return super().form_invalid(form)


class HazardReportCancelView(_OwnedCitizenReportMixin, View):
    """Cancels an owner's PENDING report and records a status history entry (BR-07)."""

    def post(self, request, pk, *args, **kwargs):
        report = self.get_owned_report(pk)
        if not report.is_pending:
            messages.error(request, "Only PENDING hazard reports can be cancelled.")
            return redirect("report_detail", pk=report.pk)

        with transaction.atomic():
            old_status = report.status
            report.status = HazardReport.Status.CANCELLED
            report.save(update_fields=["status", "updated_at"])
            TicketStatusHistory.objects.create(
                report=report,
                changed_by=request.user,
                old_status=old_status,
                new_status=HazardReport.Status.CANCELLED,
                remarks="Cancelled by citizen reporter.",
            )
        messages.info(request, f"Hazard report #{report.report_id} has been cancelled.")
        return redirect("report_detail", pk=report.pk)


class HazardReportDeleteView(_OwnedCitizenReportMixin, DeleteView):
    """Allows the owning Citizen to delete a PENDING or CANCELLED report."""

    model = HazardReport
    template_name = "reports/report_confirm_delete.html"
    context_object_name = "report"
    success_url = reverse_lazy("report_list")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not self.test_func():
            return self.handle_no_permission()
        self.object = self.get_owned_report(kwargs["pk"])
        if not self.object.can_citizen_delete:
            messages.error(
                request,
                "Active or resolved reports under LGU action cannot be deleted.",
            )
            return redirect("report_detail", pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.object

    def form_valid(self, form):
        report_id = self.object.report_id
        response = super().form_valid(form)
        messages.success(self.request, f"Hazard report #{report_id} deleted.")
        return response


class PowerUpVoteToggleView(RoleRequiredMixin, View):
    """Toggles a citizen's unique power-up vote on an active hazard report (BR-05)."""

    allowed_role = CustomUser.Role.CITIZEN

    def post(self, request, pk, *args, **kwargs):
        report = get_object_or_404(HazardReport, pk=pk)
        if not report.can_receive_votes:
            messages.error(
                request,
                "Voting is closed for resolved or cancelled hazard reports.",
            )
            return redirect("report_detail", pk=report.pk)

        with transaction.atomic():
            vote, created = PowerUpVote.objects.get_or_create(
                user=request.user,
                report=report,
            )
            if not created:
                vote.delete()
                messages.info(request, f"Removed power-up vote from report #{report.report_id}.")
            else:
                messages.success(request, f"Powered up report #{report.report_id}!")

        next_url = request.POST.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect("report_detail", pk=report.pk)
