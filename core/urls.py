from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("", views.dashboard, name="dashboard"),
    path("properties/", views.properties_list, name="properties_list"),
    path("tenants/", views.tenants_list, name="tenants_list"),
    path("rent/", views.rent_list, name="rent_list"),
    path("maintenance/", views.maintenance_list, name="maintenance_list"),
    path("properties/add/", views.property_create, name="property_create"),
    path("tenants/add/", views.tenant_create, name="tenant_create"),
    path("rent/add/", views.rent_create, name="rent_create"),
    path("maintenance/add/", views.maintenance_create, name="maintenance_create"),
    path("properties/<int:pk>/edit/", views.property_edit, name="property_edit"),
    path("tenants/<int:pk>/edit/", views.tenant_edit, name="tenant_edit"),
    path("rent/<int:pk>/edit/", views.rent_edit, name="rent_edit"),
    path("maintenance/<int:pk>/edit/", views.maintenance_edit, name="maintenance_edit"),
    path("properties/<int:pk>/delete/", views.property_delete, name="property_delete"),
    path("tenants/<int:pk>/delete/", views.tenant_delete, name="tenant_delete"),
    path("rent/<int:pk>/delete/", views.rent_delete, name="rent_delete"),
    path("maintenance/<int:pk>/delete/", views.maintenance_delete, name="maintenance_delete"),
    path("properties/<int:pk>/", views.property_detail, name="property_detail"),





]
