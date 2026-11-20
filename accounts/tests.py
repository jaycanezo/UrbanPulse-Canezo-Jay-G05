from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AccountsAuthAndProfileTests(TestCase):
    def setUp(self):
        self.citizen = User.objects.create_user(
            username="citizen_juan",
            email="juan@example.com",
            password="StrongPassword123!",
            first_name="Juan",
            last_name="Dela Cruz",
            barangay="Lahug",
            role=User.Role.CITIZEN,
        )
        self.admin = User.objects.create_user(
            username="lgu_maria",
            email="maria@lgu.gov.ph",
            password="StrongPassword123!",
            first_name="Maria",
            last_name="Santos",
            department="City Engineering",
            role=User.Role.ADMIN,
        )

    def test_create_superuser_defaults_to_admin_role(self):
        su = User.objects.create_superuser(
            username="super_admin",
            email="super@lgu.gov.ph",
            password="SuperPassword123!",
        )
        self.assertEqual(su.role, User.Role.ADMIN)
        self.assertTrue(su.is_lgu_admin)

    def test_signup_creates_citizen_with_hashed_password(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "new_resident",
                "email": "NEW.RESIDENT@EXAMPLE.COM",
                "first_name": "Ana",
                "last_name": "Reyes",
                "barangay": "Guadalupe",
                "contact_number": "09171234567",
                "password1": "CivicPass2026!",
                "password2": "CivicPass2026!",
                "role": User.Role.ADMIN,  # Must be ignored on public signup
            },
            follow=True,
        )
        self.assertRedirects(response, reverse("login"))
        new_user = User.objects.get(username="new_resident")
        self.assertEqual(new_user.email, "new.resident@example.com")
        self.assertEqual(new_user.role, User.Role.CITIZEN)
        self.assertNotEqual(new_user.password, "CivicPass2026!")
        self.assertTrue(new_user.check_password("CivicPass2026!"))
        self.assertContains(response, "Account created successfully!")

    def test_signup_rejects_duplicate_email_and_password_mismatch(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "another_user",
                "email": "JUAN@EXAMPLE.COM",
                "first_name": "Pedro",
                "last_name": "Cruz",
                "password1": "CivicPass2026!",
                "password2": "DifferentPass2026!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email address already exists.")
        self.assertContains(response, "The two password fields didn’t match.")

    def test_invalid_login_stays_on_login_page_without_redirect(self):
        response = self.client.post(
            reverse("login"),
            {"username": "nonexistent_user", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.get("Location"))
        self.assertContains(
            response,
            "Incorrect username/email or password. Please check your credentials and try again.",
        )
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_accepts_username_or_email_and_redirects_by_role(self):
        # Login citizen using email
        res_citizen = self.client.post(
            reverse("login"),
            {"username": "JUAN@EXAMPLE.COM", "password": "StrongPassword123!"},
        )
        self.assertRedirects(res_citizen, reverse("dashboard_redirect"), fetch_redirect_response=False)

        # Logout ends session
        res_logout = self.client.post(reverse("logout"))
        self.assertRedirects(res_logout, reverse("login"), fetch_redirect_response=False)

        # Login admin using username
        res_admin = self.client.post(
            reverse("login"),
            {"username": "lgu_maria", "password": "StrongPassword123!"},
            follow=True,
        )
        self.assertRedirects(res_admin, reverse("admin_panel"))

    def test_profile_requires_login_and_edits_only_own_profile(self):
        res_anon = self.client.get(reverse("profile"))
        self.assertRedirects(res_anon, f"{reverse('login')}?next={reverse('profile')}")

        self.client.force_login(self.citizen)
        res_view = self.client.get(reverse("profile"))
        self.assertEqual(res_view.status_code, 200)
        self.assertContains(res_view, "juan@example.com")

        # Duplicate email owned by admin should fail inline
        res_dup = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Juan",
                "last_name": "Dela Cruz",
                "email": "maria@lgu.gov.ph",
                "contact_number": "09170000000",
                "barangay": "Lahug",
            },
        )
        self.assertEqual(res_dup.status_code, 200)
        self.assertContains(res_dup, "An account with this email address already exists.")

        # Valid update persists for own user
        res_ok = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Juanito",
                "last_name": "Dela Cruz",
                "email": "juan@example.com",
                "contact_number": "09179998888",
                "barangay": "Apas",
            },
            follow=True,
        )
        self.assertRedirects(res_ok, reverse("profile"))
        self.citizen.refresh_from_db()
        self.assertEqual(self.citizen.first_name, "Juanito")
        self.assertEqual(self.citizen.barangay, "Apas")
        self.assertContains(res_ok, "Your profile has been updated.")

    def test_profile_rejects_letters_and_invalid_lengths_in_contact_number(self):
        self.client.force_login(self.citizen)
        for bad_number in ("0917abc4567", "letters", "12345", "123456789012345678"):
            response = self.client.post(
                reverse("profile_edit"),
                {
                    "first_name": "Juan",
                    "last_name": "Dela Cruz",
                    "email": "juan@example.com",
                    "contact_number": bad_number,
                    "barangay": "Lahug",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "is-invalid")

        ok_response = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Juan",
                "last_name": "Dela Cruz",
                "email": "juan@example.com",
                "contact_number": "+63 917 123 4567",
                "barangay": "Lahug",
            },
        )
        self.assertRedirects(ok_response, reverse("profile"), fetch_redirect_response=False)

    def test_signup_validates_names_and_username(self):
        res_bad = self.client.post(
            reverse("signup"),
            {
                "username": "CITIZEN_JUAN",  # case-insensitive duplicate
                "email": "fresh@example.com",
                "first_name": "Juan123",
                "last_name": "Cruz!",
                "password1": "CivicPass2026!",
                "password2": "CivicPass2026!",
            },
        )
        self.assertEqual(res_bad.status_code, 200)
        self.assertContains(res_bad, "This username is already taken.")
        self.assertContains(
            res_bad,
            "Enter a valid name using letters, spaces, hyphens, or apostrophes only (2-50 characters).",
        )

        res_ok = self.client.post(
            reverse("signup"),
            {
                "username": "jay_canezo",
                "email": "jay@example.com",
                "first_name": "Mary-Ann",
                "last_name": "Cañezo",
                "password1": "CivicPass2026!",
                "password2": "CivicPass2026!",
            },
        )
        self.assertRedirects(res_ok, reverse("login"), fetch_redirect_response=False)

    def test_profile_edit_enforces_barangay_and_photo_validation(self):
        self.client.force_login(self.citizen)

        # Reject XSS/invalid characters in barangay & digits in first_name
        res_bad_fields = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Juan99",
                "last_name": "Dela Cruz",
                "email": "juan@example.com",
                "contact_number": "09171234567",
                "barangay": "<script>alert(1)</script>",
            },
        )
        self.assertEqual(res_bad_fields.status_code, 200)
        self.assertContains(res_bad_fields, "is-invalid")
        self.assertContains(
            res_bad_fields,
            "Use 2-100 valid characters (letters, numbers, spaces, and standard punctuation only).",
        )

        # Reject non-image extension
        bad_file = SimpleUploadedFile("note.txt", b"hello", content_type="text/plain")
        res_bad_ext = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Juan",
                "last_name": "Dela Cruz",
                "email": "juan@example.com",
                "contact_number": "09171234567",
                "barangay": "Lahug",
                "profile_photo": bad_file,
            },
        )
        self.assertEqual(res_bad_ext.status_code, 200)

        # Reject oversized photo (> 5 MB)
        oversized = SimpleUploadedFile(
            "large.png", b"0" * (5 * 1024 * 1024 + 10), content_type="image/png"
        )
        res_oversized = self.client.post(
            reverse("profile_edit"),
            {
                "first_name": "Juan",
                "last_name": "Dela Cruz",
                "email": "juan@example.com",
                "contact_number": "09171234567",
                "barangay": "Lahug",
                "profile_photo": oversized,
            },
        )
        self.assertEqual(res_oversized.status_code, 200)
        self.assertContains(res_oversized, "Profile photo must be 5 MB or smaller.")
