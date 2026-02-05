from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from datetime import date
from django.db import transaction

from django.shortcuts import render, redirect
from .forms import PropertyForm, TenantForm, RentPaymentForm, MaintenanceRequestForm

from .models import Property, Tenant, RentPayment, MaintenanceRequest
from django.db.models import Sum
from django.shortcuts import get_object_or_404
@login_required
def dashboard(request):
    properties_qs = Property.objects.filter(owner=request.user)
    tenants_qs = Tenant.objects.filter(property__owner=request.user, is_active=True)
    rent_qs = RentPayment.objects.filter(tenant__property__owner=request.user)
    maintenance_qs = MaintenanceRequest.objects.filter(property__owner=request.user)
    # --- Property-level summary ---
    property_summaries = []
    for p in properties_qs.order_by("name"):
        active_tenants = Tenant.objects.filter(property=p, is_active=True).count()
        rent_for_property = rent_qs.filter(tenant__property=p)
        rent_due_total = rent_for_property.filter(status=RentPayment.Status.DUE).aggregate(s=Sum("amount_due"))["s"] or 0
        rent_late_total = rent_for_property.filter(status=RentPayment.Status.LATE).aggregate(s=Sum("amount_due"))["s"] or 0
        rent_paid_total = rent_for_property.filter(status=RentPayment.Status.PAID).aggregate(s=Sum("amount_due"))["s"] or 0

        open_maintenance = maintenance_qs.filter(property=p, status=MaintenanceRequest.Status.OPEN).count()
        urgent_open = maintenance_qs.filter(
            property=p,
            status=MaintenanceRequest.Status.OPEN,
            priority=MaintenanceRequest.Priority.URGENT,
        ).count()

        property_summaries.append({
        "property": p,
        "active_tenants": active_tenants,
        "rent_paid_total": rent_paid_total,
        "rent_due_total": rent_due_total,
        "rent_late_total": rent_late_total,
        "open_maintenance": open_maintenance,
        "urgent_open": urgent_open,
        })


    today = date.today()
    current_month = today.month
    current_year = today.year

    rent_this_month = rent_qs.filter(period_month=current_month, period_year=current_year)

    due_this_month = rent_this_month.filter(status=RentPayment.Status.DUE).aggregate(s=Sum("amount_due"))["s"] or 0
    late_this_month = rent_this_month.filter(status=RentPayment.Status.LATE).aggregate(s=Sum("amount_due"))["s"] or 0
    paid_this_month = rent_this_month.filter(status=RentPayment.Status.PAID).aggregate(s=Sum("amount_due"))["s"] or 0

    # Rent stats
    total_due = rent_qs.filter(status=RentPayment.Status.DUE).aggregate(s=Sum("amount_due"))["s"] or 0
    total_late = rent_qs.filter(status=RentPayment.Status.LATE).aggregate(s=Sum("amount_due"))["s"] or 0
    total_paid = rent_qs.filter(status=RentPayment.Status.PAID).aggregate(s=Sum("amount_due"))["s"] or 0

    # Maintenance stats by priority
    urgent_open = maintenance_qs.filter(status=MaintenanceRequest.Status.OPEN, priority=MaintenanceRequest.Priority.URGENT).count()
    high_open = maintenance_qs.filter(status=MaintenanceRequest.Status.OPEN, priority=MaintenanceRequest.Priority.HIGH).count()

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
    properties = Property.objects.filter(owner=request.user).order_by("-created_at")
    return render(request, "core/properties_list.html", {"properties": properties})


@login_required
def tenants_list(request):
    tenants = Tenant.objects.filter(property__owner=request.user).order_by("-created_at")
    return render(request, "core/tenants_list.html", {"tenants": tenants})


@login_required
def rent_list(request):
    rent_payments = RentPayment.objects.filter(
        tenant__property__owner=request.user
    ).select_related("tenant", "tenant__property")
    return render(request, "core/rent_list.html", {"rent_payments": rent_payments})


@login_required
def maintenance_list(request):
    requests = MaintenanceRequest.objects.filter(
        property__owner=request.user
    ).select_related("property").order_by("-created_at")
    return render(request, "core/maintenance_list.html", {"requests": requests})

# Create your views here.
@login_required
def property_create(request):
    if request.method == "POST":
        form = PropertyForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.owner = request.user
            obj.save()
            return redirect("core:properties_list")
    else:
        form = PropertyForm()
    return render(request, "core/form.html", {"form": form, "title": "Add Property"})


@login_required
def tenant_create(request):
    if request.method == "POST":
        form = TenantForm(request.POST)
        form.fields["property"].queryset = Property.objects.filter(owner=request.user)

        if form.is_valid():
            tenant = form.save(commit=False)

            # extra safety check (ownership)
            if tenant.property.owner != request.user:
                form.add_error("property", "Invalid property selection.")
            else:
                try:
                    with transaction.atomic():
                        tenant.save()

                        # Auto-create rent payments for next 6 months
                        today = date.today()
                        start_month = today.month
                        start_year = today.year
                        months_to_create = 6

                        for i in range(months_to_create):
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

                    return redirect("core:tenants_list")

                except Exception as e:
                    form.add_error(None, f"Error creating tenant/rent schedule: {e}")

    else:
        form = TenantForm()
        form.fields["property"].queryset = Property.objects.filter(owner=request.user)

    return render(request, "core/form.html", {"form": form, "title": "Add Tenant"})
@login_required
def rent_create(request):
    if request.method == "POST":
        form = RentPaymentForm(request.POST)
        form.fields["tenant"].queryset = Tenant.objects.filter(property__owner=request.user)
        if form.is_valid():
            rp = form.save(commit=False)
            if rp.tenant.property.owner != request.user:
                form.add_error("tenant", "Invalid tenant selection.")
            else:
                rp.save()
                return redirect("core:rent_list")
    else:
        form = RentPaymentForm()
        form.fields["tenant"].queryset = Tenant.objects.filter(property__owner=request.user)

    return render(request, "core/form.html", {"form": form, "title": "Add Rent Payment"})


@login_required
def maintenance_create(request):
    if request.method == "POST":
        form = MaintenanceRequestForm(request.POST)
        form.fields["property"].queryset = Property.objects.filter(owner=request.user)
        if form.is_valid():
            mr = form.save(commit=False)
            mr.created_by = request.user
            if mr.property.owner != request.user:
                form.add_error("property", "Invalid property selection.")
            else:
                mr.save()
                return redirect("core:maintenance_list")
    else:
        form = MaintenanceRequestForm()
        form.fields["property"].queryset = Property.objects.filter(owner=request.user)
    return render(request, "core/form.html", {"form": form, "title": "Add Maintenance Request"})

@login_required
def property_edit(request, pk):
    obj = get_object_or_404(Property, pk=pk, owner=request.user)

    if request.method == "POST":
        form = PropertyForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            return redirect("core:properties_list")
    else:
        form = PropertyForm(instance=obj)

    return render(request, "core/form.html", {"form": form, "title": "Edit Property"})
@login_required
def tenant_edit(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk, property__owner=request.user)

    if request.method == "POST":
        form = TenantForm(request.POST, instance=tenant)
        # Limit property dropdown to user's properties
        form.fields["property"].queryset = Property.objects.filter(owner=request.user)
        if form.is_valid():
            updated = form.save(commit=False)
            # Extra safety
            if updated.property.owner != request.user:
                form.add_error("property", "Invalid property selection.")
            else:
                updated.save()
                return redirect("core:tenants_list")
    else:
        form = TenantForm(instance=tenant)
        form.fields["property"].queryset = Property.objects.filter(owner=request.user)

    return render(request, "core/form.html", {"form": form, "title": "Edit Tenant"})


@login_required
def rent_edit(request, pk):
    rent_payment = get_object_or_404(RentPayment, pk=pk, tenant__property__owner=request.user)

    if request.method == "POST":
        form = RentPaymentForm(request.POST, instance=rent_payment)
        form.fields["tenant"].queryset = Tenant.objects.filter(property__owner=request.user)
        if form.is_valid():
            updated = form.save(commit=False)
            if updated.tenant.property.owner != request.user:
                form.add_error("tenant", "Invalid tenant selection.")
            else:
                updated.save()
                return redirect("core:rent_list")
    else:
        form = RentPaymentForm(instance=rent_payment)
        form.fields["tenant"].queryset = Tenant.objects.filter(property__owner=request.user)

    return render(request, "core/form.html", {"form": form, "title": "Edit Rent Payment"})


@login_required
def maintenance_edit(request, pk):
    req = get_object_or_404(MaintenanceRequest, pk=pk, property__owner=request.user)

    if request.method == "POST":
        form = MaintenanceRequestForm(request.POST, instance=req)
        form.fields["property"].queryset = Property.objects.filter(owner=request.user)
        if form.is_valid():
            updated = form.save(commit=False)
            # Keep created_by stable (don’t allow changes)
            updated.created_by = req.created_by
            if updated.property.owner != request.user:
                form.add_error("property", "Invalid property selection.")
            else:
                updated.save()
                return redirect("core:maintenance_list")
    else:
        form = MaintenanceRequestForm(instance=req)
        form.fields["property"].queryset = Property.objects.filter(owner=request.user)

    return render(request, "core/form.html", {"form": form, "title": "Edit Maintenance Request"})


@login_required
def property_delete(request, pk):
    obj = get_object_or_404(Property, pk=pk, owner=request.user)
    if request.method == "POST":
        obj.delete()
        return redirect("core:properties_list")
    return render(request, "core/confirm_delete.html", {"object": obj, "title": "Delete Property"})


@login_required
def tenant_delete(request, pk):
    obj = get_object_or_404(Tenant, pk=pk, property__owner=request.user)
    if request.method == "POST":
        obj.delete()
        return redirect("core:tenants_list")
    return render(request, "core/confirm_delete.html", {"object": obj, "title": "Delete Tenant"})


@login_required
def rent_delete(request, pk):
    obj = get_object_or_404(RentPayment, pk=pk, tenant__property__owner=request.user)
    if request.method == "POST":
        obj.delete()
        return redirect("core:rent_list")
    return render(request, "core/confirm_delete.html", {"object": obj, "title": "Delete Rent Payment"})


@login_required
def maintenance_delete(request, pk):
    obj = get_object_or_404(MaintenanceRequest, pk=pk, property__owner=request.user)
    if request.method == "POST":
        obj.delete()
        return redirect("core:maintenance_list")
    return render(request, "core/confirm_delete.html", {"object": obj, "title": "Delete Maintenance Request"})

@login_required
def property_detail(request, pk):
    prop = get_object_or_404(Property, pk=pk, owner=request.user)

    tenants = Tenant.objects.filter(property=prop).order_by("-created_at")
    rent_payments = RentPayment.objects.filter(tenant__property=prop).select_related("tenant").order_by("-period_year", "-period_month")
    maintenance = MaintenanceRequest.objects.filter(property=prop).order_by("-created_at")

    # totals
    rent_paid_total = rent_payments.filter(status=RentPayment.Status.PAID).aggregate(s=Sum("amount_due"))["s"] or 0
    rent_due_total = rent_payments.filter(status=RentPayment.Status.DUE).aggregate(s=Sum("amount_due"))["s"] or 0
    rent_late_total = rent_payments.filter(status=RentPayment.Status.LATE).aggregate(s=Sum("amount_due"))["s"] or 0

    # this month
    today = date.today()
    rent_this_month = rent_payments.filter(period_month=today.month, period_year=today.year)
    paid_this_month = rent_this_month.filter(status=RentPayment.Status.PAID).aggregate(s=Sum("amount_due"))["s"] or 0
    due_this_month = rent_this_month.filter(status=RentPayment.Status.DUE).aggregate(s=Sum("amount_due"))["s"] or 0
    late_this_month = rent_this_month.filter(status=RentPayment.Status.LATE).aggregate(s=Sum("amount_due"))["s"] or 0

    context = {
        "property": prop,
        "tenants": tenants,
        "rent_payments": rent_payments[:25],  # keep it simple
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
