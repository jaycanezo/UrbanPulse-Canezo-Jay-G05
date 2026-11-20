from django.urls import path

from .views import AdminPanelView, CitizenDashboardView, RoleRedirectView

urlpatterns = [
    path("", RoleRedirectView.as_view(), name="dashboard_redirect"),
    path("dashboard/", CitizenDashboardView.as_view(), name="dashboard"),
    path("admin-panel/", AdminPanelView.as_view(), name="admin_panel"),
]
