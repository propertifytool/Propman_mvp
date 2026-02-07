from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MaintenanceRequestForm, PropertyForm, RentPaymentForm, TenantForm
from .models import MaintenanceRequest, Property, RentPayment, Tenant, UserProfile


def healthz(request):
    return HttpResponse("ok")


def landing_page(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    return render(request, "core/landing.html")


def about_page(request):
    return render(request, "core/about.html")


def _render_form(request, form, title, cancel_url):
    return render(
        request,
        "core/form.html",
        {
            "form": form,
            "title": title,
            "cancel_url": cancel_url,
        },
    )


def _get_role(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile.role


def _can_manage(user):
    role = _get_role(user)
    return role in (UserProfile.Role.LANDLORD, UserProfile.Role.MANAGER)


def _property_queryset(user):
    role = _get_role(user)
    if role == UserProfile.Role.MANAGER:
        return Property.objects.all()
    if role == UserProfile.Role.TENANT:
        return Property.objects.filter(tenants__user=user).distinct()
    return Property.objects.filter(owner=user)


def _manageable_property_queryset(user):
    if not _can_manage(user):
        return Property.objects.none()
    return _property_queryset(user)


def _tenant_queryset(user):
    role = _get_role(user)
    if role == UserProfile.Role.MANAGER:
        return Tenant.objects.all()
    if role == UserProfile.Role.TENANT:
        return Tenant.objects.filter(user=user)
    return Tenant.objects.filter(property__owner=user)


def _rent_queryset(user):
    return RentPayment.objects.filter(tenant__in=_tenant_queryset(user))


def _maintenance_queryset(user):
    return MaintenanceRequest.objects.filter(property__in=_property_queryset(user))


def _forbidden_manage(request):
    messages.error(request, "You do not have permission to modify records.")
    return HttpResponseForbidden("Forbidden")


@login_required
def dashboard(request):
    properties_qs = _property_queryset(request.user)
    tenants_qs = _tenant_queryset(request.user).filter(is_active=True)
    rent_qs = _rent_queryset(request.user)
    maintenance_qs = _maintenance_queryset(request.user)

    property_summaries = []
    for prop in properties_qs.order_by("name"):
        active_tenants = Tenant.objects.filter(property=prop, is_active=True).count()
        rent_for_property = rent_qs.filter(tenant__property=prop)
        rent_due_total = (
            rent_for_property.filter(status=RentPayment.Status.DUE).aggregate(s=Sum("amount_due"))["s"] or 0
        )
        rent_late_total = (
            rent_for_property.filter(status=RentPayment.Status.LATE).aggregate(s=Sum("amount_due"))["s"] or 0
        )
        rent_paid_total = (
            rent_for_property.filter(status=RentPayment.Status.PAID).aggregate(s=Sum("amount_due"))["s"] or 0
        )

        open_maintenance = maintenance_qs.filter(property=prop, status=MaintenanceRequest.Status.OPEN).count()
        urgent_open = maintenance_qs.filter(
            property=prop,
            status=MaintenanceRequest.Status.OPEN,
            priority=MaintenanceRequest.Priority.URGENT,
        ).count()

        property_summaries.append(
            {
                "property": prop,
                "active_tenants": active_tenants,
                "rent_paid_total": rent_paid_total,
                "rent_due_total": rent_due_total,
                "rent_late_total": rent_late_total,
                "open_maintenance": open_maintenance,
                "urgent_open": urgent_open,
            }
        )

    today = date.today()
    current_month = today.month
    current_year = today.year

    rent_this_month = rent_qs.filter(period_month=current_month, period_year=current_year)

    due_this_month = rent_this_month.filter(status=RentPayment.Status.DUE).aggregate(s=Sum("amount_due"))["s"] or 0
    late_this_month = rent_this_month.filter(status=RentPayment.Status.LATE).aggregate(s=Sum("amount_due"))["s"] or 0
    paid_this_month = rent_this_month.filter(status=RentPayment.Status.PAID).aggregate(s=Sum("amount_due"))["s"] or 0

    total_due = rent_qs.filter(status=RentPayment.Status.DUE).aggregate(s=Sum("amount_due"))["s"] or 0
    total_late = rent_qs.filter(status=RentPayment.Status.LATE).aggregate(s=Sum("amount_due"))["s"] or 0
    total_paid = rent_qs.filter(status=RentPayment.Status.PAID).aggregate(s=Sum("amount_due"))["s"] or 0

    urgent_open = maintenance_qs.filter(
        status=MaintenanceRequest.Status.OPEN,
        priority=MaintenanceRequest.Priority.URGENT,
    ).count()
    high_open = maintenance_qs.filter(
        status=MaintenanceRequest.Status.OPEN,
        priority=MaintenanceRequest.Priority.HIGH,
    ).count()

    context = {
        "properties_count": properties_qs.count(),
        "active_tenants_count": tenants_qs.count(),
        "rent_due_count": rent_qs.filter(status=RentPayment.Status.DUE).count(),
        "rent_late_count": rent_qs.filter(status=RentPayment.Status.LATE).count(),
        "rent_paid_count": rent_qs.filter(status=RentPayment.Status.PAID).count(),
        "rent_due_total": total_due,
        "rent_late_total": total_late,
        "rent_paid_total": total_paid,
        "open_maintenance_count": maintenance_qs.filter(status=MaintenanceRequest.Status.OPEN).count(),
        "in_progress_maintenance_count": maintenance_qs.filter(status=MaintenanceRequest.Status.IN_PROGRESS).count(),
        "urgent_open_count": urgent_open,
        "high_open_count": high_open,
        "current_month": current_month,
        "current_year": current_year,
        "due_this_month": due_this_month,
        "late_this_month": late_this_month,
        "paid_this_month": paid_this_month,
        "property_summaries": property_summaries,
    }
    return render(request, "core/dashboard.html", context)


@login_required
def properties_list(request):
    properties = _property_queryset(request.user).order_by("-created_at")
    return render(request, "core/properties_list.html", {"properties": properties})


@login_required
def tenants_list(request):
    tenants = _tenant_queryset(request.user).order_by("-created_at")
    return render(request, "core/tenants_list.html", {"tenants": tenants})


@login_required
def rent_list(request):
    rent_payments = (
        _rent_queryset(request.user)
        .select_related("tenant", "tenant__property")
        .order_by("-period_year", "-period_month", "due_date")
    )
    return render(request, "core/rent_list.html", {"rent_payments": rent_payments})


@login_required
def maintenance_list(request):
    requests = (
        _maintenance_queryset(request.user)
        .select_related("property")
        .order_by("-created_at")
    )
    return render(request, "core/maintenance_list.html", {"requests": requests})


@login_required
def property_create(request):
    if not _can_manage(request.user):
        return _forbidden_manage(request)

    if request.method == "POST":
        form = PropertyForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.owner = request.user
            obj.save()
            messages.success(request, "Property created successfully.")
            return redirect("core:properties_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = PropertyForm()

    return _render_form(request, form, "Add Property", "core:properties_list")


@login_required
def tenant_create(request):
    if not _can_manage(request.user):
        return _forbidden_manage(request)

    allowed_properties = _manageable_property_queryset(request.user)

    if request.method == "POST":
        form = TenantForm(request.POST)
        form.fields["property"].queryset = allowed_properties

        if form.is_valid():
            tenant = form.save(commit=False)
            if not allowed_properties.filter(pk=tenant.property_id).exists():
                form.add_error("property", "Invalid property selection.")
                messages.error(request, "Please select a valid property.")
            else:
                try:
                    with transaction.atomic():
                        tenant.save()

                        today = date.today()
                        start_month = today.month
                        start_year = today.year

                        for i in range(6):
                            month = ((start_month - 1 + i) % 12) + 1
                            year = start_year + ((start_month - 1 + i) // 12)
                            due = date(year, month, 1)

                            RentPayment.objects.get_or_create(
                                tenant=tenant,
                                period_month=month,
                                period_year=year,
                                defaults={
                                    "due_date": due,
                                    "amount_due": tenant.monthly_rent,
                                    "status": RentPayment.Status.DUE,
                                },
                            )
                    messages.success(request, "Tenant created and rent schedule generated.")
                    return redirect("core:tenants_list")
                except Exception as exc:
                    form.add_error(None, f"Error creating tenant/rent schedule: {exc}")
                    messages.error(request, "Could not create tenant and rent schedule.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = TenantForm()
        form.fields["property"].queryset = allowed_properties

    return _render_form(request, form, "Add Tenant", "core:tenants_list")


@login_required
def rent_create(request):
    if not _can_manage(request.user):
        return _forbidden_manage(request)

    allowed_tenants = _tenant_queryset(request.user)

    if request.method == "POST":
        form = RentPaymentForm(request.POST)
        form.fields["tenant"].queryset = allowed_tenants
        if form.is_valid():
            rp = form.save(commit=False)
            if not allowed_tenants.filter(pk=rp.tenant_id).exists():
                form.add_error("tenant", "Invalid tenant selection.")
                messages.error(request, "Please select a valid tenant.")
            else:
                rp.save()
                messages.success(request, "Rent payment created successfully.")
                return redirect("core:rent_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RentPaymentForm()
        form.fields["tenant"].queryset = allowed_tenants

    return _render_form(request, form, "Add Rent Payment", "core:rent_list")


@login_required
def maintenance_create(request):
    if not _can_manage(request.user):
        return _forbidden_manage(request)

    allowed_properties = _manageable_property_queryset(request.user)

    if request.method == "POST":
        form = MaintenanceRequestForm(request.POST)
        form.fields["property"].queryset = allowed_properties
        if form.is_valid():
            req = form.save(commit=False)
            req.created_by = request.user
            if not allowed_properties.filter(pk=req.property_id).exists():
                form.add_error("property", "Invalid property selection.")
                messages.error(request, "Please select a valid property.")
            else:
                req.save()
                messages.success(request, "Maintenance request created successfully.")
                return redirect("core:maintenance_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = MaintenanceRequestForm()
        form.fields["property"].queryset = allowed_properties

    return _render_form(request, form, "Add Maintenance Request", "core:maintenance_list")


@login_required
def property_edit(request, pk):
    if not _can_manage(request.user):
        return _forbidden_manage(request)

    obj = get_object_or_404(_property_queryset(request.user), pk=pk)

    if request.method == "POST":
        form = PropertyForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Property updated successfully.")
            return redirect("core:properties_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = PropertyForm(instance=obj)

    return _render_form(request, form, "Edit Property", "core:properties_list")


@login_required
def tenant_edit(request, pk):
    if not _can_manage(request.user):
        return _forbidden_manage(request)

    tenant = get_object_or_404(_tenant_queryset(request.user), pk=pk)
    allowed_properties = _manageable_property_queryset(request.user)

    if request.method == "POST":
        form = TenantForm(request.POST, instance=tenant)
        form.fields["property"].queryset = allowed_properties
        if form.is_valid():
            updated = form.save(commit=False)
            if not allowed_properties.filter(pk=updated.property_id).exists():
                form.add_error("property", "Invalid property selection.")
                messages.error(request, "Please select a valid property.")
            else:
                updated.save()
                messages.success(request, "Tenant updated successfully.")
                return redirect("core:tenants_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = TenantForm(instance=tenant)
        form.fields["property"].queryset = allowed_properties

    return _render_form(request, form, "Edit Tenant", "core:tenants_list")


@login_required
def rent_edit(request, pk):
    if not _can_manage(request.user):
        return _forbidden_manage(request)

    rent_payment = get_object_or_404(_rent_queryset(request.user), pk=pk)
    previous_status = rent_payment.status
    allowed_tenants = _tenant_queryset(request.user)

    if request.method == "POST":
        form = RentPaymentForm(request.POST, instance=rent_payment)
        form.fields["tenant"].queryset = allowed_tenants
        if form.is_valid():
            updated = form.save(commit=False)
            if not allowed_tenants.filter(pk=updated.tenant_id).exists():
                form.add_error("tenant", "Invalid tenant selection.")
                messages.error(request, "Please select a valid tenant.")
            else:
                updated.save()
                if previous_status != RentPayment.Status.PAID and updated.status == RentPayment.Status.PAID:
                    messages.success(request, "Rent payment marked as paid.")
                else:
                    messages.success(request, "Rent payment updated successfully.")
                return redirect("core:rent_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = RentPaymentForm(instance=rent_payment)
        form.fields["tenant"].queryset = allowed_tenants

    return _render_form(request, form, "Edit Rent Payment", "core:rent_list")


@login_required
def maintenance_edit(request, pk):
    if not _can_manage(request.user):
        return _forbidden_manage(request)

    req = get_object_or_404(_maintenance_queryset(request.user), pk=pk)
    allowed_properties = _manageable_property_queryset(request.user)

    if request.method == "POST":
        form = MaintenanceRequestForm(request.POST, instance=req)
        form.fields["property"].queryset = allowed_properties
        if form.is_valid():
            updated = form.save(commit=False)
            updated.created_by = req.created_by
            if not allowed_properties.filter(pk=updated.property_id).exists():
                form.add_error("property", "Invalid property selection.")
                messages.error(request, "Please select a valid property.")
            else:
                updated.save()
                messages.success(request, "Maintenance request updated successfully.")
                return redirect("core:maintenance_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = MaintenanceRequestForm(instance=req)
        form.fields["property"].queryset = allowed_properties

    return _render_form(request, form, "Edit Maintenance Request", "core:maintenance_list")


@login_required
def property_delete(request, pk):
    if not _can_manage(request.user):
        return _forbidden_manage(request)

    obj = get_object_or_404(_property_queryset(request.user), pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Property deleted successfully.")
        return redirect("core:properties_list")
    return render(
        request,
        "core/confirm_delete.html",
        {"object": obj, "title": "Delete Property", "cancel_url": "core:properties_list"},
    )


@login_required
def tenant_delete(request, pk):
    if not _can_manage(request.user):
        return _forbidden_manage(request)

    obj = get_object_or_404(_tenant_queryset(request.user), pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Tenant deleted successfully.")
        return redirect("core:tenants_list")
    return render(
        request,
        "core/confirm_delete.html",
        {"object": obj, "title": "Delete Tenant", "cancel_url": "core:tenants_list"},
    )


@login_required
def rent_delete(request, pk):
    if not _can_manage(request.user):
        return _forbidden_manage(request)

    obj = get_object_or_404(_rent_queryset(request.user), pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Rent payment deleted successfully.")
        return redirect("core:rent_list")
    return render(
        request,
        "core/confirm_delete.html",
        {"object": obj, "title": "Delete Rent Payment", "cancel_url": "core:rent_list"},
    )


@login_required
def maintenance_delete(request, pk):
    if not _can_manage(request.user):
        return _forbidden_manage(request)

    obj = get_object_or_404(_maintenance_queryset(request.user), pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Maintenance request deleted successfully.")
        return redirect("core:maintenance_list")
    return render(
        request,
        "core/confirm_delete.html",
        {"object": obj, "title": "Delete Maintenance Request", "cancel_url": "core:maintenance_list"},
    )


@login_required
def property_detail(request, pk):
    prop = get_object_or_404(_property_queryset(request.user), pk=pk)

    tenants = _tenant_queryset(request.user).filter(property=prop).order_by("-created_at")
    rent_payments = _rent_queryset(request.user).filter(tenant__property=prop).select_related("tenant").order_by(
        "-period_year", "-period_month"
    )
    maintenance = _maintenance_queryset(request.user).filter(property=prop).order_by("-created_at")

    rent_paid_total = rent_payments.filter(status=RentPayment.Status.PAID).aggregate(s=Sum("amount_due"))["s"] or 0
    rent_due_total = rent_payments.filter(status=RentPayment.Status.DUE).aggregate(s=Sum("amount_due"))["s"] or 0
    rent_late_total = rent_payments.filter(status=RentPayment.Status.LATE).aggregate(s=Sum("amount_due"))["s"] or 0

    today = date.today()
    rent_this_month = rent_payments.filter(period_month=today.month, period_year=today.year)
    paid_this_month = rent_this_month.filter(status=RentPayment.Status.PAID).aggregate(s=Sum("amount_due"))["s"] or 0
    due_this_month = rent_this_month.filter(status=RentPayment.Status.DUE).aggregate(s=Sum("amount_due"))["s"] or 0
    late_this_month = rent_this_month.filter(status=RentPayment.Status.LATE).aggregate(s=Sum("amount_due"))["s"] or 0

    context = {
        "property": prop,
        "tenants": tenants,
        "rent_payments": rent_payments[:25],
        "maintenance": maintenance[:25],
        "rent_paid_total": rent_paid_total,
        "rent_due_total": rent_due_total,
        "rent_late_total": rent_late_total,
        "current_month": today.month,
        "current_year": today.year,
        "paid_this_month": paid_this_month,
        "due_this_month": due_this_month,
        "late_this_month": late_this_month,
    }
    return render(request, "core/property_detail.html", context)
