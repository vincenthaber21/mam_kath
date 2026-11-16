from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from classifier.models import Classification


class FrontPageTests(TestCase):
    def test_front_page_is_public_and_explains_the_workflow(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "From incident photo")
        self.assertContains(response, "How the classifier works")
        self.assertContains(response, "Human verification required")
        self.assertContains(response, reverse("classify"))
        self.assertContains(response, "No classification yet")
        self.assertNotContains(response, "Example values only")

    def test_front_page_shows_latest_real_classification(self):
        Classification.objects.create(
            filename="scene.png",
            predicted_label="fire",
            confidence=0.912,
            scores={"fire": 0.912, "crime": 0.04, "medical_emergency": 0.02, "accident": 0.018, "disaster": 0.01},
            status="success",
            demo=False,
            image=SimpleUploadedFile("scene.png", b"\x89PNG\r\n\x1a\n", content_type="image/png"),
        )
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Fire")
        self.assertContains(response, "91.2")
        self.assertContains(response, "Live result")
        self.assertContains(response, "Real classification from your workspace")
        self.assertNotContains(response, "Example values only")

    def test_classify_has_its_own_signed_in_address(self):
        response = self.client.get(reverse("classify"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertIn(reverse("classify"), response["Location"])
