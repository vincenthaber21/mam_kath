from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from classifier.models import Classification, IncidentResponse

User = get_user_model()


class UserManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="pass12345",
            first_name="Admin",
            last_name="User",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.officer = User.objects.create_user(
            email="officer@example.com",
            password="pass12345",
            first_name="Ana",
            last_name="Santos",
            role=User.Role.OFFICER,
        )
        self.resident = User.objects.create_user(
            email="resident@example.com",
            password="pass12345",
            first_name="Ben",
            last_name="Reyes",
            role=User.Role.RESIDENT,
        )

    def test_admin_can_open_users_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("user_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Santos, Ana")
        self.assertContains(response, "Reyes, Ben")

    def test_resident_cannot_manage_users(self):
        self.client.force_login(self.resident)
        response = self.client.get(reverse("user_list"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("history"))

    def test_admin_can_create_officer(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("user_list"), {
            "intent": "create",
            "username": "New.Officer!",
            "email": "new.officer@example.com",
            "last_name": "  dela   cruz ",
            "first_name": "juan",
            "middle_name": "santos",
            "role": User.Role.OFFICER,
            "phone": "09171234567",
            "barangay": "Poblacion Norte",
            "password1": "securepass99",
            "password2": "securepass99",
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        created = User.objects.get(email="new.officer@example.com")
        self.assertEqual(created.role, User.Role.OFFICER)
        self.assertEqual(created.barangay, "Poblacion Norte")
        self.assertEqual(created.username, "new.officer")
        self.assertEqual(created.last_name, "Dela Cruz")
        self.assertEqual(created.first_name, "Juan")
        self.assertEqual(created.middle_name, "Santos")
        self.assertEqual(created.name, "Juan Santos Dela Cruz")
        self.assertEqual(created.formal_name, "Dela Cruz, Juan Santos")

    def test_users_new_redirects_to_list_dialog(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("user_create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/users/?new=1", response["Location"])

    def test_users_page_includes_create_dialog(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("user_list"))
        self.assertContains(response, 'id="user-create-dialog"')
        self.assertContains(response, "Add user")


class IncidentResponseTests(TestCase):
    def setUp(self):
        self.officer = User.objects.create_user(
            email="officer@example.com",
            password="pass12345",
            first_name="Ana",
            last_name="Santos",
            role=User.Role.OFFICER,
        )
        self.resident = User.objects.create_user(
            email="resident@example.com",
            password="pass12345",
            first_name="Ben",
            last_name="Reyes",
            role=User.Role.RESIDENT,
        )
        self.other = User.objects.create_user(
            email="other@example.com",
            password="pass12345",
            first_name="Other",
            last_name="Resident",
            role=User.Role.RESIDENT,
        )
        self.incident = Classification.objects.create(
            user=self.resident,
            filename="fire.jpg",
            predicted_label="fire",
            confidence=0.9,
            status="success",
            response_status="open",
        )

    def test_resident_only_sees_own_incidents(self):
        Classification.objects.create(
            user=self.other,
            filename="other.jpg",
            predicted_label="crime",
            confidence=0.8,
            status="success",
        )
        self.client.force_login(self.resident)
        response = self.client.get(reverse("history"))
        self.assertContains(response, self.incident.record_no)
        self.assertNotContains(response, "#0002")

    def test_officer_sees_all_and_can_acknowledge(self):
        self.client.force_login(self.officer)
        response = self.client.get(reverse("history"))
        self.assertContains(response, self.incident.record_no)
        self.assertContains(response, "Pending")
        self.assertContains(response, "Responding")
        self.assertContains(response, 'name="action" value="responding"')

        response = self.client.post(reverse("incident_respond", args=[self.incident.pk]), {
            "action": IncidentResponse.Action.ACKNOWLEDGE,
            "message": "BFP notified. En route.",
        })
        self.assertEqual(response.status_code, 302)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.response_status, "acknowledged")
        self.assertEqual(self.incident.assigned_officer_id, self.officer.id)
        self.assertEqual(self.incident.responses.count(), 1)

    def test_officer_can_mark_responding_and_cancel_from_incidents_list(self):
        self.client.force_login(self.officer)
        response = self.client.post(reverse("incident_respond", args=[self.incident.pk]), {
            "action": IncidentResponse.Action.RESPONDING,
            "next": reverse("history"),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("history"))
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.response_status, "responding")
        self.assertEqual(self.incident.assigned_officer_id, self.officer.id)

        list_page = self.client.get(reverse("history"))
        self.assertContains(list_page, "Responding")
        self.assertContains(list_page, 'name="action" value="cancel"')

        response = self.client.post(reverse("incident_respond", args=[self.incident.pk]), {
            "action": IncidentResponse.Action.CANCEL,
            "next": reverse("history"),
        })
        self.assertEqual(response.status_code, 302)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.response_status, "open")
        self.assertIsNone(self.incident.assigned_officer_id)
        self.assertEqual(self.incident.responses.count(), 2)

    def test_resident_can_comment_but_not_change_status(self):
        self.client.force_login(self.resident)
        response = self.client.post(reverse("incident_respond", args=[self.incident.pk]), {
            "action": IncidentResponse.Action.COMMENT,
            "message": "Smoke is getting thicker near the market.",
        })
        self.assertEqual(response.status_code, 302)
        self.incident.refresh_from_db()
        self.assertEqual(self.incident.response_status, "open")
        self.assertEqual(self.incident.responses.count(), 1)

    def test_resident_cannot_open_others_incident(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("result", args=[self.incident.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("history"))

    def test_uncertain_prediction_hides_incident_response(self):
        uncertain = Classification.objects.create(
            user=self.resident,
            filename="unclear.jpg",
            predicted_label="",
            confidence=0.4,
            low_confidence=True,
            status="success",
            response_status="open",
        )
        self.client.force_login(self.officer)
        result = self.client.get(reverse("result", args=[uncertain.pk]))
        self.assertContains(result, "Uncertain")
        self.assertContains(result, "No category assigned")
        self.assertNotContains(result, "Incident response")
        self.assertNotContains(result, "No responses yet")

        list_page = self.client.get(reverse("history"))
        self.assertContains(list_page, "Uncertain")
        # Uncertain rows must not offer Responding actions.
        self.assertNotContains(
            list_page,
            f'action="{reverse("incident_respond", args=[uncertain.pk])}"',
        )

        blocked = self.client.post(reverse("incident_respond", args=[uncertain.pk]), {
            "action": IncidentResponse.Action.RESPONDING,
            "next": reverse("history"),
        })
        self.assertEqual(blocked.status_code, 302)
        uncertain.refresh_from_db()
        self.assertEqual(uncertain.response_status, "open")
        self.assertEqual(uncertain.responses.count(), 0)
