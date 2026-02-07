
from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    class Role(models.TextChoices):
        LANDLORD = "LANDLORD", "Landlord"
        MANAGER = "MANAGER", "Manager"
        TENANT = "TENANT", "Tenant"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.LANDLORD)

    def __str__(self) -> str:
        return f"{self.user.username} ({self.role})"


class Property(models.Model):
    class PropertyType(models.TextChoices):
        APARTMENT = "APARTMENT", "Apartment"
        HOUSE = "HOUSE", "House"
        ROOM = "ROOM", "Room"
        COMMERCIAL = "COMMERCIAL", "Commercial"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="properties",
    )
    name = models.CharField(max_length=120)
    address = models.TextField()
    city = models.CharField(max_length=80)
    country = models.CharField(max_length=80, default="Germany")
    property_type = models.CharField(
        max_length=20,
        choices=PropertyType.choices,
        default=PropertyType.APARTMENT,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.city})"


class Tenant(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="tenant_account",
        null=True,
        blank=True,
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="tenants",
    )
    full_name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    lease_start = models.DateField()
    lease_end = models.DateField(null=True, blank=True)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.full_name} - {self.property.name}"


class RentPayment(models.Model):
    class Status(models.TextChoices):
        DUE = "DUE", "Due"
        PAID = "PAID", "Paid"
        LATE = "LATE", "Late"

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="rent_payments",
    )
    period_month = models.PositiveSmallIntegerField()
    period_year = models.PositiveSmallIntegerField()
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DUE)
    paid_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("tenant", "period_month", "period_year")
        ordering = ["-period_year", "-period_month", "due_date"]

    def __str__(self) -> str:
        return f"{self.tenant.full_name} {self.period_month}/{self.period_year} - {self.status}"


class MaintenanceRequest(models.Model):
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RESOLVED = "RESOLVED", "Resolved"

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="maintenance_requests",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="maintenance_requests_created",
    )
    title = models.CharField(max_length=120)
    description = models.TextField()
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)
    vendor_name = models.CharField(max_length=120, blank=True)
    cost_estimate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.title} - {self.property.name}"
