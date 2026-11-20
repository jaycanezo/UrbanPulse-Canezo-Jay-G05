from django.urls import path

from .views import (
    AdminReportResolveView,
    CommunityReportListView,
    DispatchQueueView,
    HazardReportCancelView,
    HazardReportCreateView,
    HazardReportDeleteView,
    HazardReportDetailView,
    HazardReportUpdateView,
    PowerUpVoteToggleView,
)

urlpatterns = [
    path("", CommunityReportListView.as_view(), name="report_list"),
    path("new/", HazardReportCreateView.as_view(), name="report_create"),
    path("dispatch/", DispatchQueueView.as_view(), name="dispatch_queue"),
    path("dispatch/<int:pk>/", AdminReportResolveView.as_view(), name="dispatch_resolve"),
    path("<int:pk>/", HazardReportDetailView.as_view(), name="report_detail"),
    path("<int:pk>/edit/", HazardReportUpdateView.as_view(), name="report_update"),
    path("<int:pk>/cancel/", HazardReportCancelView.as_view(), name="report_cancel"),
    path("<int:pk>/delete/", HazardReportDeleteView.as_view(), name="report_delete"),
    path("<int:pk>/vote/", PowerUpVoteToggleView.as_view(), name="report_vote"),
]
