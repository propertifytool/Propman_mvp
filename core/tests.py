from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Property, RentPayment, Tenant, UserProfile


class RoleAccessTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.landlord_a = user_model.objects.create_user(username="landlord_a", password="pass12345")
        self.landlord_b = user_model.objects.create_user(username="landlord_b", password="pass12345")
        self.manager = user_model.objects.create_user(username="manager", password="pass12345")
        self.tenant_user = user_model.objects.create_user(username="tenant_u", password="pass12345")

        UserProfile.objects.update_or_create(user=self.landlord_a, defaults={"role": UserProfile.Role.LANDLORD})
        UserProfile.objects.update_or_create(user=self.landlord_b, defaults={"role": UserProfile.Role.LANDLORD})
        UserProfile.objects.update_or_create(user=self.manager, defaults={"role": UserProfile.Role.MANAGER})
        UserProfile.objects.update_or_create(user=self.tenant_user, defaults={"role": UserProfile.Role.TENANT})

        self.property_a = Property.objects.create(
            owner=self.landlord_a,
            name="Alpha Home",
            address="1 Main St",
            city="Berlin",
            country="Germany",
            property_type=Property.PropertyType.APARTMENT,
        )
        self.property_b = Property.objects.create(
            owner=self.landlord_b,
            name="Beta House",
            address="2 Side St",
            city="Munich",
            country="Germany",
            property_type=Property.PropertyType.HOUSE,
        )

        self.tenant = Tenant.objects.create(
            user=self.tenant_user,
            property=self.property_a,
            full_name="Tenant User",
            email="tenant@example.com",
            lease_start=date(2026, 1, 1),
            monthly_rent=1000,
        )

        self.rent = RentPayment.objects.create(
            tenant=self.tenant,
            period_month=1,
            period_year=2026,
            due_date=date(2026, 1, 1),
            amount_due=1000,
            status=RentPayment.Status.DUE,
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_landlord_sees_only_owned_properties(self):
        self.client.login(username="landlord_a", password="pass12345")
        response = self.client.get(reverse("core:properties_list"))
        self.assertContains(response, "Alpha Home")
        self.assertNotContains(response, "Beta House")

    def test_manager_sees_all_properties(self):
        self.client.login(username="manager", password="pass12345")
        response = self.client.get(reverse("core:properties_list"))
        self.assertContains(response, "Alpha Home")
        self.assertContains(response, "Beta House")

    def test_tenant_cannot_create_property(self):
        self.client.login(username="tenant_u", password="pass12345")
        response = self.client.get(reverse("core:property_create"))
        self.assertEqual(response.status_code, 403)

    def test_landlord_create_property_success_message(self):
        self.client.login(username="landlord_a", password="pass12345")
        response = self.client.post(
            reverse("core:property_create"),
            {
                "name": "Gamma Flat",
                "address": "3 New St",
                "city": "Hamburg",
                "country": "Germany",
                "property_type": Property.PropertyType.APARTMENT,
                "notes": "",
            },
            follow=True,
        )
        self.assertContains(response, "Property created successfully.")
        self.assertTrue(Property.objects.filter(name="Gamma Flat", owner=self.landlord_a).exists())

    def test_rent_marked_paid_message(self):
        self.client.login(username="landlord_a", password="pass12345")
        response = self.client.post(
            reverse("core:rent_edit", args=[self.rent.pk]),
            {
                "tenant": self.tenant.pk,
                "period_month": self.rent.period_month,
                "period_year": self.rent.period_year,
                "due_date": self.rent.due_date,
                "amount_due": self.rent.amount_due,
                "status": RentPayment.Status.PAID,
                "paid_date": date(2026, 1, 3),
                "notes": "Paid",
            },
            follow=True,
        )
        self.assertContains(response, "Rent payment marked as paid.")
        self.rent.refresh_from_db()
        self.assertEqual(self.rent.status, RentPayment.Status.PAID)
