from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class DashboardRoleIsolationTests(TestCase):
    def setUp(self):
        self.citizen = User.objects.create_user(
            username="resident_one",
            email="resident1@example.com",
            password="StrongPassword123!",
            first_name="Carlo",
            last_name="Mendoza",
            barangay="Mabolo",
            role=User.Role.CITIZEN,
        )
        self.admin = User.objects.create_user(
            username="dispatcher_one",
            email="dispatcher1@lgu.gov.ph",
            password="StrongPassword123!",
            first_name="Elena",
            last_name="Ramos",
            department="Road Maintenance",
            role=User.Role.ADMIN,
        )

    def test_anonymous_users_redirect_to_login(self):
        for route_name in ("dashboard_redirect", "dashboard", "admin_panel"):
            url = reverse(route_name)
            response = self.client.get(url)
            self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_citizen_dashboard_accessible_and_admin_panel_forbidden(self):
        self.client.force_login(self.citizen)

        res_root = self.client.get(reverse("dashboard_redirect"))
        self.assertRedirects(res_root, reverse("dashboard"))

        res_home = self.client.get(reverse("dashboard"))
        self.assertEqual(res_home.status_code, 200)
        self.assertContains(res_home, "Brgy. Mabolo")

        res_admin = self.client.get(reverse("admin_panel"))
        self.assertEqual(res_admin.status_code, 403)
        self.assertContains(res_admin, "Access Restricted", status_code=403)

    def test_admin_panel_accessible_and_citizen_dashboard_forbidden(self):
        self.client.force_login(self.admin)

        res_root = self.client.get(reverse("dashboard_redirect"))
        self.assertRedirects(res_root, reverse("admin_panel"))

        res_admin = self.client.get(reverse("admin_panel"))
        self.assertEqual(res_admin.status_code, 200)
        self.assertContains(res_admin, "LGU Administrative Dispatch Console")
        self.assertEqual(res_admin.context["total_users"], 2)
        self.assertEqual(res_admin.context["citizen_count"], 1)
        self.assertEqual(res_admin.context["admin_count"], 1)
        self.assertEqual(res_admin.context["barangay_count"], 1)
        self.assertEqual(res_admin.context["total_reports"], 0)
        self.assertEqual(res_admin.context["pending_reports"], 0)

        res_citizen = self.client.get(reverse("dashboard"))
        self.assertEqual(res_citizen.status_code, 403)
