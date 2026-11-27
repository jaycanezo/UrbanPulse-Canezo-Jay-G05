from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Barangay, HazardCategory, HazardReport, PowerUpVote, TicketStatusHistory

User = get_user_model()


class CoreFeatureHardeningTests(TestCase):
    def setUp(self):
        self.citizen_a = User.objects.create_user(
            username="citizen_a",
            email="citizena@example.com",
            password="StrongPassword123!",
            first_name="Ana",
            last_name="Reyes",
            barangay="Lahug",
            role=User.Role.CITIZEN,
        )
        self.citizen_b = User.objects.create_user(
            username="citizen_b",
            email="citizenb@example.com",
            password="StrongPassword123!",
            first_name="Ben",
            last_name="Cruz",
            barangay="Mabolo",
            role=User.Role.CITIZEN,
        )
        self.admin = User.objects.create_user(
            username="lgu_admin",
            email="admin@lgu.gov.ph",
            password="StrongPassword123!",
            first_name="Maria",
            last_name="Santos",
            department="City Engineering",
            role=User.Role.ADMIN,
        )
        self.barangay = Barangay.objects.first()
        self.category = HazardCategory.objects.first()

    def _create_sample_report(self, user=None, status=HazardReport.Status.PENDING, desc=None):
        return HazardReport.objects.create(
            user=user or self.citizen_a,
            barangay=self.barangay,
            category=self.category,
            landmark_desc=desc or "Broken drainage grate beside Lahug Elementary School",
            status=status,
        )

    def test_lookup_seed_data_exists(self):
        self.assertGreaterEqual(Barangay.objects.count(), 12)
        self.assertGreaterEqual(HazardCategory.objects.count(), 7)

    def test_create_report_valid_with_photo(self):
        self.client.force_login(self.citizen_a)
        photo = SimpleUploadedFile("pothole.png", b"\x89PNG\r\n\x1a\nfake", content_type="image/png")

        response = self.client.post(
            reverse("report_create"),
            {
                "barangay": self.barangay.pk,
                "category": self.category.pk,
                "landmark_desc": "Corner Salinas Drive near JY Square, deep pothole",
                "photo": photo,
            },
            follow=True,
        )
        report = HazardReport.objects.get(user=self.citizen_a)
        self.assertRedirects(response, reverse("report_detail", kwargs={"pk": report.pk}))
        self.assertEqual(report.status, HazardReport.Status.PENDING)
        self.assertEqual(report.attachments.count(), 1)
        self.assertContains(response, f"Hazard report #{report.report_id} submitted")

    def test_create_report_invalid_inputs_rejected(self):
        self.client.force_login(self.citizen_a)

        # Short description & angle brackets rejected server-side
        res_short = self.client.post(
            reverse("report_create"),
            {
                "barangay": self.barangay.pk,
                "category": self.category.pk,
                "landmark_desc": "Short",
            },
        )
        self.assertEqual(res_short.status_code, 200)
        self.assertContains(res_short, "between 10 and 1000 characters")

        res_html = self.client.post(
            reverse("report_create"),
            {
                "barangay": self.barangay.pk,
                "category": self.category.pk,
                "landmark_desc": "<script>bad()</script>",
            },
        )
        self.assertEqual(res_html.status_code, 200)
        self.assertContains(res_html, "Angle brackets")

        # Non-image and oversized photo rejected
        bad_file = SimpleUploadedFile("doc.txt", b"not an image", content_type="text/plain")
        res_ext = self.client.post(
            reverse("report_create"),
            {
                "barangay": self.barangay.pk,
                "category": self.category.pk,
                "landmark_desc": "Valid landmark near main barangay hall",
                "photo": bad_file,
            },
        )
        self.assertEqual(res_ext.status_code, 200)

        oversized = SimpleUploadedFile(
            "huge.png", b"0" * (5 * 1024 * 1024 + 5), content_type="image/png"
        )
        res_big = self.client.post(
            reverse("report_create"),
            {
                "barangay": self.barangay.pk,
                "category": self.category.pk,
                "landmark_desc": "Valid landmark near main barangay hall",
                "photo": oversized,
            },
        )
        self.assertEqual(res_big.status_code, 200)
        self.assertContains(res_big, "5 MB or smaller")
        self.assertEqual(HazardReport.objects.count(), 0)

    def test_create_report_prevents_duplicate_pending_submission(self):
        self.client.force_login(self.citizen_a)
        desc = "Deep pothole right in front of Barangay Hall gate"
        self._create_sample_report(user=self.citizen_a, desc=desc)

        res_dup = self.client.post(
            reverse("report_create"),
            {
                "barangay": self.barangay.pk,
                "category": self.category.pk,
                "landmark_desc": f"  {desc.upper()}  ",
            },
        )
        self.assertEqual(res_dup.status_code, 200)
        self.assertContains(res_dup, "identical pending hazard report")
        self.assertEqual(HazardReport.objects.count(), 1)

    def test_report_views_require_login(self):
        report = self._create_sample_report()
        protected_routes = [
            reverse("report_list"),
            reverse("report_create"),
            reverse("report_detail", kwargs={"pk": report.pk}),
            reverse("report_update", kwargs={"pk": report.pk}),
            reverse("report_cancel", kwargs={"pk": report.pk}),
            reverse("report_delete", kwargs={"pk": report.pk}),
            reverse("report_vote", kwargs={"pk": report.pk}),
            reverse("dispatch_queue"),
            reverse("dispatch_resolve", kwargs={"pk": report.pk}),
        ]
        for url in protected_routes:
            response = self.client.get(url)
            self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_citizen_cannot_edit_cancel_delete_or_view_cancelled_other_users_report(self):
        report = self._create_sample_report(user=self.citizen_a)
        self.client.force_login(self.citizen_b)

        self.assertEqual(
            self.client.get(reverse("report_update", kwargs={"pk": report.pk})).status_code, 403
        )
        self.assertEqual(
            self.client.post(reverse("report_cancel", kwargs={"pk": report.pk})).status_code, 403
        )
        self.assertEqual(
            self.client.post(reverse("report_delete", kwargs={"pk": report.pk})).status_code, 403
        )

        # Cancelled report is hidden from public community feed and blocked on detail for other citizens
        report.status = HazardReport.Status.CANCELLED
        report.save(update_fields=["status"])
        res_feed = self.client.get(reverse("report_list"))
        self.assertNotContains(res_feed, f"#{report.report_id}")
        self.assertEqual(
            self.client.get(reverse("report_detail", kwargs={"pk": report.pk})).status_code, 403
        )

    def test_citizen_cannot_edit_cancel_or_delete_non_pending_report(self):
        report = self._create_sample_report(
            user=self.citizen_a, status=HazardReport.Status.REVIEW
        )
        self.client.force_login(self.citizen_a)

        res_edit = self.client.get(reverse("report_update", kwargs={"pk": report.pk}))
        self.assertRedirects(res_edit, reverse("report_detail", kwargs={"pk": report.pk}))

        res_cancel = self.client.post(reverse("report_cancel", kwargs={"pk": report.pk}))
        self.assertRedirects(res_cancel, reverse("report_detail", kwargs={"pk": report.pk}))

        res_del = self.client.get(reverse("report_delete", kwargs={"pk": report.pk}))
        self.assertRedirects(res_del, reverse("report_detail", kwargs={"pk": report.pk}))

    def test_citizen_cancel_and_delete_with_confirmation(self):
        report = self._create_sample_report(user=self.citizen_a)
        self.client.force_login(self.citizen_a)

        # Cancel PENDING -> CANCELLED + audit log
        res_cancel = self.client.post(
            reverse("report_cancel", kwargs={"pk": report.pk}), follow=True
        )
        self.assertRedirects(res_cancel, reverse("report_detail", kwargs={"pk": report.pk}))
        report.refresh_from_db()
        self.assertEqual(report.status, HazardReport.Status.CANCELLED)
        self.assertTrue(
            TicketStatusHistory.objects.filter(
                report=report, new_status=HazardReport.Status.CANCELLED
            ).exists()
        )

        # GET delete asks for confirmation instead of deleting
        res_confirm = self.client.get(reverse("report_delete", kwargs={"pk": report.pk}))
        self.assertEqual(res_confirm.status_code, 200)
        self.assertContains(res_confirm, f"Delete Hazard Report #{report.report_id}?")
        self.assertTrue(HazardReport.objects.filter(pk=report.pk).exists())

        # POST delete removes record and redirects
        res_delete = self.client.post(
            reverse("report_delete", kwargs={"pk": report.pk}), follow=True
        )
        self.assertRedirects(res_delete, reverse("report_list"))
        self.assertFalse(HazardReport.objects.filter(pk=report.pk).exists())

    def test_state_changing_endpoints_reject_get_requests(self):
        report = self._create_sample_report(user=self.citizen_a)
        self.client.force_login(self.citizen_a)

        self.assertEqual(
            self.client.get(reverse("report_cancel", kwargs={"pk": report.pk})).status_code, 405
        )
        self.assertEqual(
            self.client.get(reverse("report_vote", kwargs={"pk": report.pk})).status_code, 405
        )

    @override_settings(DEBUG=False)
    def test_invalid_report_ids_and_urls_return_404(self):
        self.client.force_login(self.citizen_a)

        for bad_url in (
            "/reports/999999/",
            "/reports/999999/edit/",
            "/reports/abc/",
            "/nonexistent-page/",
        ):
            res = self.client.get(bad_url)
            self.assertEqual(res.status_code, 404)
            self.assertContains(res, "Page Not Found", status_code=404)

        self.client.force_login(self.admin)
        res_dispatch_404 = self.client.get("/reports/dispatch/999999/")
        self.assertEqual(res_dispatch_404.status_code, 404)

    def test_malformed_filter_query_params_do_not_crash(self):
        self._create_sample_report(user=self.citizen_a)
        self.client.force_login(self.citizen_a)

        res_citizen = self.client.get(
            reverse("report_list"),
            {"barangay": "abc", "category": "-5", "status": "BOGUS", "sort": "invalid"},
        )
        self.assertEqual(res_citizen.status_code, 200)

        self.client.force_login(self.admin)
        res_admin = self.client.get(
            reverse("dispatch_queue"),
            {"barangay": "xyz", "category": "none", "status": "FAKE", "q": "<script>"},
        )
        self.assertEqual(res_admin.status_code, 200)

    def test_power_up_vote_unique_toggle_closed_blocked_and_open_redirect_safe(self):
        report = self._create_sample_report(user=self.citizen_a)
        self.client.force_login(self.citizen_b)

        # Open redirect attempt in next must fall back to report_detail
        res_vote = self.client.post(
            reverse("report_vote", kwargs={"pk": report.pk}),
            {"next": "https://evil.example.com/phish"},
        )
        self.assertRedirects(res_vote, reverse("report_detail", kwargs={"pk": report.pk}))
        self.assertEqual(PowerUpVote.objects.filter(report=report, user=self.citizen_b).count(), 1)

        # Toggle off
        self.client.post(reverse("report_vote", kwargs={"pk": report.pk}))
        self.assertEqual(PowerUpVote.objects.filter(report=report, user=self.citizen_b).count(), 0)

        # Voting blocked when RESOLVED
        report.status = HazardReport.Status.RESOLVED
        report.save(update_fields=["status"])
        self.client.post(reverse("report_vote", kwargs={"pk": report.pk}))
        self.assertEqual(PowerUpVote.objects.filter(report=report).count(), 0)

    def test_user_deletion_preserves_reports_anonymously_and_cascades_votes(self):
        report = self._create_sample_report(user=self.citizen_a)
        self.client.force_login(self.citizen_b)
        self.client.post(reverse("report_vote", kwargs={"pk": report.pk}))
        self.assertEqual(PowerUpVote.objects.filter(report=report).count(), 1)

        self.citizen_b.delete()
        self.assertEqual(PowerUpVote.objects.filter(report=report).count(), 0)

        self.citizen_a.delete()
        report.refresh_from_db()
        self.assertIsNone(report.user)

    def test_admin_dispatch_blocked_for_citizens_and_citizen_create_blocked_for_admins(self):
        report = self._create_sample_report(user=self.citizen_a)

        self.client.force_login(self.citizen_a)
        self.assertEqual(self.client.get(reverse("dispatch_queue")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("dispatch_resolve", kwargs={"pk": report.pk})).status_code,
            403,
        )

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("report_create")).status_code, 403)

    def test_admin_resolve_ticket_audit_trail_validation_and_cancelled_lock(self):
        report = self._create_sample_report(user=self.citizen_a)
        self.client.force_login(self.admin)

        # Reject no-op same status
        res_noop = self.client.post(
            reverse("dispatch_resolve", kwargs={"pk": report.pk}),
            {"new_status": HazardReport.Status.PENDING, "remarks": ""},
        )
        self.assertContains(res_noop, "Please choose a different status than the current one.")

        # Reject RESOLVED without remarks
        res_no_remarks = self.client.post(
            reverse("dispatch_resolve", kwargs={"pk": report.pk}),
            {"new_status": HazardReport.Status.RESOLVED, "remarks": ""},
        )
        self.assertContains(
            res_no_remarks,
            "Please provide resolution or cancellation remarks for citizen transparency.",
        )

        # Reject angle brackets in remarks
        res_bad_remarks = self.client.post(
            reverse("dispatch_resolve", kwargs={"pk": report.pk}),
            {"new_status": HazardReport.Status.REVIEW, "remarks": "<script>x</script>"},
        )
        self.assertContains(res_bad_remarks, "Angle brackets")

        # Valid transitions PENDING -> REVIEW -> RESOLVED
        self.client.post(
            reverse("dispatch_resolve", kwargs={"pk": report.pk}),
            {"new_status": HazardReport.Status.REVIEW, "remarks": "Assigned inspection team."},
        )
        self.client.post(
            reverse("dispatch_resolve", kwargs={"pk": report.pk}),
            {
                "new_status": HazardReport.Status.RESOLVED,
                "remarks": "Asphalt patched and road reopened to traffic.",
            },
        )
        report.refresh_from_db()
        self.assertEqual(report.status, HazardReport.Status.RESOLVED)
        history = list(report.status_history.all())
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].old_status, HazardReport.Status.REVIEW)
        self.assertEqual(history[0].new_status, HazardReport.Status.RESOLVED)
        self.assertEqual(history[0].changed_by, self.admin)

        # Cancelled tickets cannot be modified by admin
        cancelled_report = self._create_sample_report(
            user=self.citizen_b,
            status=HazardReport.Status.CANCELLED,
            desc="Duplicate streetlight report already withdrawn",
        )
        res_locked = self.client.post(
            reverse("dispatch_resolve", kwargs={"pk": cancelled_report.pk}),
            {"new_status": HazardReport.Status.REVIEW, "remarks": "Trying to reopen"},
        )
        self.assertContains(res_locked, "Cancelled tickets are closed and cannot be updated.")

    def test_custom_500_template_renders_without_context(self):
        rendered = render_to_string("500.html", {})
        self.assertIn("Something Went Wrong", rendered)
        self.assertIn('href="/"', rendered)
