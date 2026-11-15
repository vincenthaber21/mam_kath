from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import MLModel


class RegistryTests(TestCase):
    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user("r@example.com", "pass-1234-word"))

    def test_only_one_active_model(self):
        a = MLModel.objects.create(name="A", is_active=True)
        b = MLModel.objects.create(name="B")
        self.client.post(reverse("model_activate", args=[b.pk]))
        a.refresh_from_db(); b.refresh_from_db()
        self.assertFalse(a.is_active)
        self.assertTrue(b.is_active)

    def test_seed_demo_and_pages_render(self):
        call_command("seed_demo", verbosity=0)
        self.assertEqual(MLModel.objects.count(), 3)
        for name in ("classify", "history", "evaluation", "models", "dataset"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
        self.assertContains(self.client.get(reverse("dataset")), "7,646")
