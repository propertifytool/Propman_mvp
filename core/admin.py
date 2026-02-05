
from django.contrib import admin
from .models import Property, Tenant, RentPayment, MaintenanceRequest


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "country", "property_type", "owner", "created_at")
    list_filter = ("property_type", "city", "country")
    search_fields = ("name", "address", "city", "owner__username", "owner__email")


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("full_name", "property", "monthly_rent", "is_active", "lease_start", "lease_end")
    list_filter = ("is_active", "lease_start")
    search_fields = ("full_name", "email", "phone", "property__name", "property__city")


@admin.register(RentPayment)
class RentPaymentAdmin(admin.ModelAdmin):
    list_display = ("tenant", "period_month", "period_year", "amount_due", "status", "due_date", "paid_date")
    list_filter = ("status", "period_year", "period_month")
    search_fields = ("tenant__full_name", "tenant__property__name", "notes")


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "property", "priority", "status", "vendor_name", "created_at", "resolved_at")
    list_filter = ("priority", "status", "created_at")
    search_fields = ("title", "description", "property__name", "property__city", "vendor_name")
