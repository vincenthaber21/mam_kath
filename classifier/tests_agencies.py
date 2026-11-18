from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from classifier.models import NotifyAgency

User = get_user_model()


class NotifyAgencyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="pass12345",
            first_name="Admin",
            last_name="User",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.resident = User.objects.create_user(
            email="resident@example.com",
            password="pass12345",
            first_name="Ben",
            last_name="Reyes",
            role=User.Role.RESIDENT,
        )
        self.agency = NotifyAgency.objects.create(
            name="Barangay Fire Station",
            agency_type=NotifyAgency.AgencyType.FIRE,
            phone="09170001111",
            email="fire@example.com",
            barangay="Poblacion",
        )

    def test_admin_can_open_agencies_page(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("agency_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Barangay Fire Station")
        self.assertContains(response, "Notify agencies")

    def test_resident_cannot_manage_agencies(self):
        self.client.force_login(self.resident)
        response = self.client.get(reverse("agency_list"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("history"))

    def test_admin_can_create_agency(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("agency_list"), {
            "intent": "create",
            "name": "  City Police Station ",
            "agency_type": NotifyAgency.AgencyType.CRIME,
            "contact_name": "Desk officer",
            "phone": "09172223333",
            "email": "Police@Example.com",
            "barangay": "Poblacion Sur",
            "address": "Main Street",
            "notes": "24/7 desk",
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        created = NotifyAgency.objects.get(name="City Police Station")
        self.assertEqual(created.agency_type, NotifyAgency.AgencyType.CRIME)
        self.assertEqual(created.email, "police@example.com")
        self.assertEqual(created.barangay, "Poblacion Sur")
        self.assertTrue(created.is_active)

    def test_create_requires_phone_or_email(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("agency_list"), {
            "intent": "create",
            "name": "No Contact Unit",
            "agency_type": NotifyAgency.AgencyType.GENERAL,
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Provide at least a phone number or email")
        self.assertFalse(NotifyAgency.objects.filter(name="No Contact Unit").exists())

    def test_agencies_new_redirects_to_list_dialog(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("agency_create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/agencies/?new=1", response["Location"])

    def test_admin_can_edit_agency(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("agency_edit", args=[self.agency.pk]), {
            "name": "Barangay Fire Station",
            "agency_type": NotifyAgency.AgencyType.FIRE,
            "contact_name": "Captain Reyes",
            "phone": "09170001111",
            "email": "fire@example.com",
            "barangay": "Poblacion Norte",
            "address": "",
            "notes": "Radio channel 3",
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 302)
        self.agency.refresh_from_db()
        self.assertEqual(self.agency.contact_name, "Captain Reyes")
        self.assertEqual(self.agency.barangay, "Poblacion Norte")
        self.assertEqual(self.agency.notes, "Radio channel 3")


class NotifyAgencyLocationFormTests(TestCase):
    base = {"name": "Santa Maria Fire Station", "agency_type": "fire", "phone": "09171234567", "is_active": "on"}

    def test_saves_station_location(self):
        from .forms import NotifyAgencyForm
        form = NotifyAgencyForm({**self.base, "latitude": "17.36", "longitude": "120.49"})
        self.assertTrue(form.is_valid(), form.errors)
        agency = form.save()
        self.assertTrue(agency.has_location)
        self.assertAlmostEqual(agency.latitude, 17.36)

    def test_requires_both_coordinates(self):
        from .forms import NotifyAgencyForm
        form = NotifyAgencyForm({**self.base, "latitude": "17.36"})
        self.assertFalse(form.is_valid())
        self.assertIn("longitude", form.errors)

    def test_location_optional(self):
        from .forms import NotifyAgencyForm
        form = NotifyAgencyForm(self.base)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.save().has_location)


class NotifyAgencyLocationViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin2@example.com", password="pass12345", first_name="Admin", last_name="Two",
            role=User.Role.ADMIN, is_staff=True,
        )
        self.agency = NotifyAgency.objects.create(
            name="Santa Maria PNP", agency_type=NotifyAgency.AgencyType.CRIME, phone="09170002222",
            barangay="Poblacion Norte", latitude=17.3615, longitude=120.4846,
        )
        self.client.force_login(self.admin)

    def test_list_edit_and_map_show_location(self):
        res = self.client.get(reverse("agency_list"))
        self.assertContains(res, "17.36150, 120.48460")
        self.assertContains(res, "Station location in Santa Maria")
        res = self.client.get(reverse("agency_edit", args=[self.agency.pk]))
        self.assertContains(res, 'value="17.3615"')
        res = self.client.get(reverse("incident_map"))
        self.assertContains(res, "incident-map-agencies")
        self.assertContains(res, "Santa Maria PNP")

    def test_edit_saves_location(self):
        self.client.post(reverse("agency_edit", args=[self.agency.pk]), {
            "name": "Santa Maria PNP", "agency_type": "crime", "phone": "09170002222",
            "latitude": "17.35", "longitude": "120.50", "is_active": "on",
        })
        self.agency.refresh_from_db()
        self.assertAlmostEqual(self.agency.longitude, 120.50)
