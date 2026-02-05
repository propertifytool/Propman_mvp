from django import forms
from .models import Property, Tenant, RentPayment, MaintenanceRequest


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ["name", "address", "city", "country", "property_type", "notes"]


class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = [
            "property",
            "full_name",
            "email",
            "phone",
            "lease_start",
            "lease_end",
            "monthly_rent",
            "deposit_amount",
            "is_active",
        ]


class RentPaymentForm(forms.ModelForm):
    class Meta:
        model = RentPayment
        fields = [
            "tenant",
            "period_month",
            "period_year",
            "due_date",
            "amount_due",
            "status",
            "paid_date",
            "notes",
        ]


class MaintenanceRequestForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRequest
        fields = [
            "property",
            "title",
            "description",
            "priority",
            "status",
            "vendor_name",
            "cost_estimate",
            "resolved_at",
        ]
