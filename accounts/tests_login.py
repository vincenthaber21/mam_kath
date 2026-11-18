from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class UsernameOrEmailLoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="officer@example.com",
            password="pass12345",
            username="officer.ana",
            first_name="Ana",
            last_name="Santos",
            role=User.Role.OFFICER,
        )

    def test_login_with_email(self):
        response = self.client.post(reverse("login"), {
            "username": "officer@example.com",
            "password": "pass12345",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_with_username(self):
        self.client.logout()
        response = self.client.post(reverse("login"), {
            "username": "Officer.Ana",
            "password": "pass12345",
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_page_mentions_username(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Username or email")
