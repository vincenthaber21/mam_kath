from django.test import TestCase
from django.urls import reverse


class FrontPageTests(TestCase):
    def test_front_page_is_public_and_explains_the_workflow(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "From incident photo")
        self.assertContains(response, "How the classifier works")
        self.assertContains(response, "Human verification required")
        self.assertContains(response, reverse("classify"))

    def test_classify_has_its_own_signed_in_address(self):
        response = self.client.get(reverse("classify"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertIn(reverse("classify"), response["Location"])
