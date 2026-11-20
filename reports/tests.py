from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Barangay, HazardCategory, HazardReport, PowerUpVote, TicketStatusHistory

User = get_user_model()


class CitizenHazardReportTests(TestCase):
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

    def test_lookup_seed_data_exists(self):
        self.assertGreaterEqual(Barangay.objects.count(), 12)
        self.assertGreaterEqual(HazardCategory.objects.count(), 7)

    def test_anonymous_users_redirect_to_login(self):
        for route_name in ("report_list", "report_create"):
            url = reverse(route_name)
            res = self.client.get(url)
            self.assertRedirects(res, f"{reverse('login')}?next={url}")

    def test_citizen_full_crud_and_photo_upload(self):
        self.client.force_login(self.citizen_a)

        # Create
        photo = SimpleUploadedFile("pothole.png", b"\x89PNG\r\n\x1a\nfake", content_type="image/png")
        res_create = self.client.post(
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
        self.assertRedirects(res_create, reverse("report_detail", kwargs={"pk": report.pk}))
        self.assertEqual(report.status, HazardReport.Status.PENDING)
        self.assertEqual(report.attachments.count(), 1)

        # Read (Community feed + My Reports)
        res_feed = self.client.get(reverse("report_list"))
        self.assertContains(res_feed, report.landmark_desc[:30])
        res_mine = self.client.get(f"{reverse('report_list')}?scope=mine")
        self.assertContains(res_mine, f"#{report.report_id}")

        # Update while PENDING
        res_update = self.client.post(
            reverse("report_update", kwargs={"pk": report.pk}),
            {
                "barangay": self.barangay.pk,
                "category": self.category.pk,
                "landmark_desc": "Updated: Corner Salinas Drive in front of JY Square Mall",
            },
            follow=True,
        )
        self.assertRedirects(res_update, reverse("report_detail", kwargs={"pk": report.pk}))
        report.refresh_from_db()
        self.assertIn("Updated:", report.landmark_desc)

        # Cancel PENDING report -> creates audit log
        res_cancel = self.client.post(
            reverse("report_cancel", kwargs={"pk": report.pk}),
            follow=True,
        )
        self.assertRedirects(res_cancel, reverse("report_detail", kwargs={"pk": report.pk}))
        report.refresh_from_db()
        self.assertEqual(report.status, HazardReport.Status.CANCELLED)
        self.assertTrue(
            TicketStatusHistory.objects.filter(
                report=report, new_status=HazardReport.Status.CANCELLED
            ).exists()
        )

        # Delete CANCELLED report
        res_delete = self.client.post(
            reverse("report_delete", kwargs={"pk": report.pk}),
            follow=True,
        )
        self.assertRedirects(res_delete, reverse("report_list"))
        self.assertFalse(HazardReport.objects.filter(pk=report.pk).exists())

    def test_report_form_rejects_invalid_inputs_and_files(self):
        self.client.force_login(self.citizen_a)

        res_bad_text = self.client.post(
            reverse("report_create"),
            {
                "barangay": self.barangay.pk,
                "category": self.category.pk,
                "landmark_desc": "<script>bad</script>",
            },
        )
        self.assertEqual(res_bad_text.status_code, 200)
        self.assertEqual(HazardReport.objects.count(), 0)
        self.assertContains(res_bad_text, "Angle brackets")

        bad_file = SimpleUploadedFile("doc.txt", b"not an image", content_type="text/plain")
        res_bad_file = self.client.post(
            reverse("report_create"),
            {
                "barangay": self.barangay.pk,
                "category": self.category.pk,
                "landmark_desc": "Valid street landmark near public market",
                "photo": bad_file,
            },
        )
        self.assertEqual(res_bad_file.status_code, 200)
        self.assertEqual(HazardReport.objects.count(), 0)

    def test_ownership_and_status_guards_enforced(self):
        report = HazardReport.objects.create(
            user=self.citizen_a,
            barangay=self.barangay,
            category=self.category,
            landmark_desc="Broken drainage grate beside elementary school",
        )

        # Citizen B cannot edit, cancel, or delete Citizen A's report
        self.client.force_login(self.citizen_b)
        self.assertEqual(self.client.get(reverse("report_update", kwargs={"pk": report.pk})).status_code, 403)
        self.assertEqual(self.client.post(reverse("report_cancel", kwargs={"pk": report.pk})).status_code, 403)
        self.assertEqual(self.client.post(reverse("report_delete", kwargs={"pk": report.pk})).status_code, 403)

        # Admin cannot open citizen create route
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("report_create")).status_code, 403)

        # Citizen A cannot edit/cancel/delete once status moves to REVIEW
        report.status = HazardReport.Status.REVIEW
        report.save(update_fields=["status"])
        self.client.force_login(self.citizen_a)
        res_edit = self.client.get(reverse("report_update", kwargs={"pk": report.pk}))
        self.assertRedirects(res_edit, reverse("report_detail", kwargs={"pk": report.pk}))
        res_del = self.client.get(reverse("report_delete", kwargs={"pk": report.pk}))
        self.assertRedirects(res_del, reverse("report_detail", kwargs={"pk": report.pk}))

    def test_power_up_vote_toggle_and_user_deletion_anonymizes_reports(self):
        report = HazardReport.objects.create(
            user=self.citizen_a,
            barangay=self.barangay,
            category=self.category,
            landmark_desc="Dark streetlamp near main pedestrian crossing",
        )
        self.client.force_login(self.citizen_b)

        # Cast vote
        self.client.post(reverse("report_vote", kwargs={"pk": report.pk}))
        self.assertEqual(PowerUpVote.objects.filter(report=report, user=self.citizen_b).count(), 1)

        # Toggle off
        self.client.post(reverse("report_vote", kwargs={"pk": report.pk}))
        self.assertEqual(PowerUpVote.objects.filter(report=report, user=self.citizen_b).count(), 0)

        # Cast again and verify BR-09 on user delete
        self.client.post(reverse("report_vote", kwargs={"pk": report.pk}))
        self.citizen_b.delete()
        self.assertEqual(PowerUpVote.objects.filter(report=report).count(), 0)
        self.citizen_a.delete()
        report.refresh_from_db()
        self.assertIsNone(report.user)


class AdminDispatchResolutionTests(TestCase):
    def setUp(self):
        self.citizen = User.objects.create_user(
            username="citizen_one",
            email="citizen1@example.com",
            password="StrongPassword123!",
            first_name="Carla",
            last_name="Lim",
            barangay="Lahug",
            role=User.Role.CITIZEN,
        )
        self.admin = User.objects.create_user(
            username="lgu_dispatcher",
            email="dispatcher@lgu.gov.ph",
            password="StrongPassword123!",
            first_name="Marco",
            last_name="Diaz",
            department="City Engineering",
            role=User.Role.ADMIN,
        )
        self.barangay = Barangay.objects.first()
        self.category = HazardCategory.objects.first()
        self.report = HazardReport.objects.create(
            user=self.citizen,
            barangay=self.barangay,
            category=self.category,
            landmark_desc="Major pothole in front of Lahug Elementary School",
        )

    def test_citizen_cannot_access_dispatch_routes(self):
        self.client.force_login(self.citizen)
        self.assertEqual(self.client.get(reverse("dispatch_queue")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("dispatch_resolve", kwargs={"pk": self.report.pk})).status_code,
            403,
        )

    def test_admin_can_filter_queue_and_resolve_ticket_with_audit_history(self):
        self.client.force_login(self.admin)

        res_queue = self.client.get(reverse("dispatch_queue"), {"q": "Lahug"})
        self.assertEqual(res_queue.status_code, 200)
        self.assertContains(res_queue, f"#{self.report.report_id}")

        # Reject no-op same status
        res_noop = self.client.post(
            reverse("dispatch_resolve", kwargs={"pk": self.report.pk}),
            {"new_status": HazardReport.Status.PENDING, "remarks": ""},
        )
        self.assertEqual(res_noop.status_code, 200)
        self.assertContains(res_noop, "Please choose a different status than the current one.")

        # Reject RESOLVED without remarks
        res_no_remarks = self.client.post(
            reverse("dispatch_resolve", kwargs={"pk": self.report.pk}),
            {"new_status": HazardReport.Status.RESOLVED, "remarks": ""},
        )
        self.assertEqual(res_no_remarks.status_code, 200)
        self.assertContains(
            res_no_remarks,
            "Please provide resolution or cancellation remarks for citizen transparency.",
        )

        # Reject HTML brackets in remarks
        res_bad_remarks = self.client.post(
            reverse("dispatch_resolve", kwargs={"pk": self.report.pk}),
            {"new_status": HazardReport.Status.REVIEW, "remarks": "<script>x</script>"},
        )
        self.assertEqual(res_bad_remarks.status_code, 200)
        self.assertContains(res_bad_remarks, "Angle brackets")

        # Transition PENDING -> REVIEW -> RESOLVED
        res_review = self.client.post(
            reverse("dispatch_resolve", kwargs={"pk": self.report.pk}),
            {"new_status": HazardReport.Status.REVIEW, "remarks": "Assigned inspection team."},
            follow=True,
        )
        self.assertRedirects(
            res_review, reverse("dispatch_resolve", kwargs={"pk": self.report.pk})
        )

        res_resolved = self.client.post(
            reverse("dispatch_resolve", kwargs={"pk": self.report.pk}),
            {
                "new_status": HazardReport.Status.RESOLVED,
                "remarks": "Asphalt patched and road reopened to traffic.",
            },
            follow=True,
        )
        self.assertRedirects(
            res_resolved, reverse("dispatch_resolve", kwargs={"pk": self.report.pk})
        )

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, HazardReport.Status.RESOLVED)
        history = list(self.report.status_history.all())
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].old_status, HazardReport.Status.REVIEW)
        self.assertEqual(history[0].new_status, HazardReport.Status.RESOLVED)
        self.assertEqual(history[0].changed_by, self.admin)
        self.assertEqual(history[1].old_status, HazardReport.Status.PENDING)
        self.assertEqual(history[1].new_status, HazardReport.Status.REVIEW)
