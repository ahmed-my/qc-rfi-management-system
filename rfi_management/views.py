from io import BytesIO
import os

from datetime import date, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
from openpyxl.utils import get_column_letter
from django.http import FileResponse, Http404, HttpResponse

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.db.models import Max, Q, Sum

from .forms import (
    LoginForm,
    QCSetPasswordForm,
    QCUserCreationForm,
    QCUserEditForm,
    RFIRegistrationForm,
    RFIAssignmentForm,
    InspectionForm,
    StartInspectionForm,
    PunchListCreateForm,
    RFIRenewalForm,
    ReturnToSupervisorForm,
    ClientSignedRFIForm,
)

from .models import (
    RFI,
    UserProfile,
    Assignment,
    Inspection,
    PunchList,
    PunchItem,
    RFIHistory,
    Document,
    RFIRenewal,
    ClientSignedRFI,
)

def inspector_can_access_rfi(rfi, user):
    """
    An inspector can access an RFI if:
    1. The inspector registered it personally, or
    2. A supervisor/admin currently assigned it to them.
    """

    if rfi.created_by_id == user.id:
        return True

    return Assignment.objects.filter(
        rfi=rfi,
        inspector=user,
        unassigned_at__isnull=True,
    ).exists()

def login_view(request):
    """
    Handle user login.

    Only users with an active QC profile are allowed
    to access the QC RFI Management System.
    """

    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)

        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")

            user = authenticate(
                request,
                username=username,
                password=password,
            )

            if user is not None:

                profile = getattr(user, "profile", None)

                if profile is None:
                    messages.error(
                        request,
                        "Your account does not have a QC profile.",
                    )
                    return redirect("login")

                if not profile.is_active_qc:
                    messages.error(
                        request,
                        "Your QC access is currently inactive. "
                        "Please contact an administrator.",
                    )
                    return redirect("login")

                login(request, user)

                return redirect("dashboard")

        messages.error(
            request,
            "Invalid username or password.",
        )

    else:
        form = LoginForm()

    return render(
        request,
        "rfi_management/login.html",
        {"form": form},
    )


@login_required
def dashboard_view(request):
    """
    Display the dashboard according to the user's QC role.
    """

    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile.",
        )

        logout(request)

        return redirect("login")

    if not profile.is_active_qc:
        messages.error(
            request,
            "Your QC access is inactive.",
        )

        logout(request)

        return redirect("login")

    context = {
        "profile": profile,
    }

    if profile.role == UserProfile.Role.ADMIN:
        context["total_users"] = User.objects.count()

        context["supervisor_count"] = UserProfile.objects.filter(
            role=UserProfile.Role.SUPERVISOR
        ).count()

        context["inspector_count"] = UserProfile.objects.filter(
            role=UserProfile.Role.INSPECTOR
        ).count()

    elif profile.role == UserProfile.Role.CLIENT:
        signed_rfis = ClientSignedRFI.objects.filter(
            client=request.user
        )

        current_time = timezone.now()

        context["total_signed_rfis"] = signed_rfis.count()

        context["signed_rfis_this_month"] = signed_rfis.filter(
            recorded_at__year=current_time.year,
            recorded_at__month=current_time.month,
        ).count()

        context["latest_signed_rfi"] = signed_rfis.order_by(
            "-recorded_at"
        ).first()

    elif profile.role == UserProfile.Role.INSPECTOR:

        inspector_rfis = (
            RFI.objects.filter(
                Q(created_by=request.user)
                | Q(
                    assignments__inspector=request.user,
                    assignments__unassigned_at__isnull=True,
                )
            )
            .distinct()
        )

        context["inspector_total_rfis"] = inspector_rfis.count()

        context["inspector_overdue_rfis"] = inspector_rfis.filter(
            status=RFI.Status.OVERDUE
        ).count()

        context["inspector_awaiting_punch_rfis"] = inspector_rfis.filter(
            status=RFI.Status.AWAITING_PUNCH
        ).count()

        context["inspector_closed_rfis"] = inspector_rfis.filter(
            status=RFI.Status.CLOSED
        ).count()

        context["inspector_recent_rfis"] = (
            inspector_rfis
            .select_related("created_by")
            .order_by("-created_at")[:5]
        )

    return render(
        request,
        "rfi_management/dashboard.html",
        context,
    )


@login_required
def user_list_view(request):
    """
    Display all system users.

    Only administrators can access this page.
    """

    profile = getattr(request.user, "profile", None)

    if profile is None or profile.role != UserProfile.Role.ADMIN:
        messages.error(
            request,
            "You do not have permission to access user management.",
        )

        return redirect("dashboard")

    users = User.objects.select_related("profile").order_by(
        "first_name",
        "last_name",
        "username",
    )

    return render(
        request,
        "rfi_management/user_list.html",
        {
            "users": users,
        },
    )


@login_required
def user_create_view(request):
    """
    Create a new QC user and their UserProfile.

    Only administrators can create users.
    """

    profile = getattr(request.user, "profile", None)

    if profile is None or profile.role != UserProfile.Role.ADMIN:
        messages.error(
            request,
            "You do not have permission to create users.",
        )

        return redirect("dashboard")

    if request.method == "POST":
        form = QCUserCreationForm(request.POST)

        if form.is_valid():

            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
            )

            UserProfile.objects.create(
                user=user,
                role=form.cleaned_data["role"],
                is_active_qc=form.cleaned_data["is_active_qc"],
            )

            messages.success(
                request,
                (
                    f"User '{user.get_full_name()}' "
                    "was created successfully."
                ),
            )

            return redirect("user_list")

    else:
        form = QCUserCreationForm()

    return render(
        request,
        "rfi_management/user_create.html",
        {
            "form": form,
        },
    )


@login_required
def user_edit_view(request, user_id):
    """
    Edit an existing user's details, role and QC access.

    Only administrators can access this page.

    The currently logged-in administrator cannot change
    their own role or deactivate their own QC access.
    """

    admin_profile = getattr(request.user, "profile", None)

    if (
        admin_profile is None
        or admin_profile.role != UserProfile.Role.ADMIN
    ):
        messages.error(
            request,
            "You do not have permission to edit users.",
        )

        return redirect("dashboard")

    user = get_object_or_404(
        User.objects.select_related("profile"),
        pk=user_id,
    )

    target_profile = getattr(user, "profile", None)

    if target_profile is None:
        messages.error(
            request,
            "The selected user does not have a QC profile.",
        )

        return redirect("user_list")

    is_self = user.pk == request.user.pk

    if request.method == "POST":
        form = QCUserEditForm(
            request.POST,
            user_instance=user,
        )

        if form.is_valid():

            user.first_name = form.cleaned_data["first_name"]
            user.last_name = form.cleaned_data["last_name"]
            user.username = form.cleaned_data["username"]

            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "username",
                ]
            )

            if not is_self:
                target_profile.role = form.cleaned_data["role"]
                target_profile.is_active_qc = form.cleaned_data[
                    "is_active_qc"
                ]

                target_profile.save(
                    update_fields=[
                        "role",
                        "is_active_qc",
                    ]
                )

            messages.success(
                request,
                (
                    f"User '{user.get_full_name()}' "
                    "was updated successfully."
                ),
            )

            return redirect("user_list")

    else:
        form = QCUserEditForm(
            initial={
                "first_name": user.first_name,
                "last_name": user.last_name,
                "username": user.username,
                "role": target_profile.role,
                "is_active_qc": target_profile.is_active_qc,
            },
            user_instance=user,
        )

    return render(
        request,
        "rfi_management/user_edit.html",
        {
            "form": form,
            "user_obj": user,
            "profile": target_profile,
            "is_self": is_self,
        },
    )


@login_required
def user_password_view(request, user_id):
    """
    Change another user's password.

    Only administrators can access this page.
    """

    admin_profile = getattr(request.user, "profile", None)

    if (
        admin_profile is None
        or admin_profile.role != UserProfile.Role.ADMIN
    ):
        messages.error(
            request,
            "You do not have permission to change user passwords.",
        )

        return redirect("dashboard")

    user = get_object_or_404(User, pk=user_id)

    if user.pk == request.user.pk:
        messages.error(
            request,
            "Use the normal account password-change process "
            "to change your own password.",
        )

        return redirect("user_list")

    if request.method == "POST":
        form = QCSetPasswordForm(
            user,
            request.POST,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                (
                    f"The password for '{user.get_full_name()}' "
                    "was changed successfully."
                ),
            )

            return redirect("user_list")

    else:
        form = QCSetPasswordForm(user)

    return render(
        request,
        "rfi_management/user_password.html",
        {
            "form": form,
            "user_obj": user,
        },
    )

@login_required
def client_signed_rfi_list_view(request):
    """Display signed RFI records belonging to the logged-in client."""

    profile = getattr(request.user, "profile", None)

    if profile is None or profile.role != UserProfile.Role.CLIENT:
        messages.error(
            request,
            "You do not have permission to access this page."
        )
        return redirect("dashboard")

    records = ClientSignedRFI.objects.filter(
        client=request.user
    ).order_by("-recorded_at")

    summary = records.aggregate(
        total_items=Sum("number_of_items_inspected"),
        latest_submission=Max("recorded_at"),
    )

    context = {
        "records": records,
        "total_signed_rfis": records.count(),
        "total_items_inspected": summary["total_items"] or 0,
        "latest_submission": summary["latest_submission"],
    }

    return render(
        request,
        "rfi_management/client_signed_rfi_list.html",
        context,
    )


@login_required
def client_signed_rfi_export_view(request):
    """Export the logged-in client's signed RFI records to Excel."""

    profile = getattr(request.user, "profile", None)

    if profile is None or profile.role != UserProfile.Role.CLIENT:
        messages.error(
            request,
            "You do not have permission to access this page."
        )
        return redirect("dashboard")

    period = request.GET.get("period", "").lower()
    selected_date_text = request.GET.get("date", "")

    if period not in ["daily", "weekly", "monthly"]:
        return HttpResponse(
            "Invalid reporting period.",
            status=400,
        )

    try:
        selected_date = date.fromisoformat(selected_date_text)
    except (ValueError, TypeError):
        return HttpResponse(
            "Please provide a valid reporting date.",
            status=400,
        )

    # Determine the reporting period.
    if period == "daily":
        start_date = selected_date
        end_date = selected_date
        period_label = "Daily"

    elif period == "weekly":
        start_date = selected_date - timedelta(
            days=selected_date.weekday()
        )
        end_date = start_date + timedelta(days=6)
        period_label = "Weekly"

    else:
        start_date = selected_date.replace(day=1)

        if selected_date.month == 12:
            next_month = date(selected_date.year + 1, 1, 1)
        else:
            next_month = date(
                selected_date.year,
                selected_date.month + 1,
                1,
            )

        end_date = next_month - timedelta(days=1)
        period_label = "Monthly"

    # Retrieve only this client's records within the selected period.
    records = ClientSignedRFI.objects.filter(
        client=request.user,
        recorded_at__date__gte=start_date,
        recorded_at__date__lte=end_date,
    ).order_by("recorded_at")

    total_records = records.count()

    total_items = (
        records.aggregate(
            total=Sum("number_of_items_inspected")
        )["total"] or 0
    )

    # Create the Excel workbook.
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Signed RFI Records"

    # Colours.
    navy = "17365D"
    blue = "2563EB"
    light_blue = "E8EFFA"
    white = "FFFFFF"
    grey = "64748B"

    # Report heading.
    worksheet.merge_cells("A1:F1")
    worksheet["A1"] = "CLIENT SIGNED RFI REPORT"
    worksheet["A1"].font = Font(
        name="Arial",
        size=16,
        bold=True,
        color=white,
    )
    worksheet["A1"].fill = PatternFill(
        "solid",
        fgColor=navy,
    )
    worksheet["A1"].alignment = Alignment(
        horizontal="center",
        vertical="center",
    )
    worksheet.row_dimensions[1].height = 32

    # Reporting information.
    worksheet.merge_cells("A2:F2")
    worksheet["A2"] = (
        f"{period_label} Report | "
        f"{start_date:%d %b %Y} - {end_date:%d %b %Y}"
    )
    worksheet["A2"].font = Font(
        name="Arial",
        size=11,
        bold=True,
        color=navy,
    )
    worksheet["A2"].alignment = Alignment(
        horizontal="center",
    )

    worksheet.merge_cells("A3:F3")
    worksheet["A3"] = f"Client: {request.user.get_full_name() or request.user.username}"
    worksheet["A3"].font = Font(
        name="Arial",
        size=10,
        color=grey,
    )

    # Summary section.
    worksheet["A5"] = "Total Signed RFIs"
    worksheet["B5"] = total_records
    worksheet["C5"] = "Total Items Inspected"
    worksheet["D5"] = total_items

    for cell in ["A5", "C5"]:
        worksheet[cell].font = Font(
            bold=True,
            color=white,
        )
        worksheet[cell].fill = PatternFill(
            "solid",
            fgColor=blue,
        )

    for cell in ["B5", "D5"]:
        worksheet[cell].font = Font(
            bold=True,
            color=navy,
        )
        worksheet[cell].fill = PatternFill(
            "solid",
            fgColor=light_blue,
        )

    # Table headings.
    headers = [
        "S/N",
        "RFI Number",
        "RFI Activity",
        "Items Inspected",
        "Date Recorded",
        "Signed Copy",
    ]

    header_row = 7

    for column, heading in enumerate(headers, start=1):
        cell = worksheet.cell(
            row=header_row,
            column=column,
            value=heading,
        )
        cell.font = Font(
            bold=True,
            color=white,
        )
        cell.fill = PatternFill(
            "solid",
            fgColor=navy,
        )
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )

    # Populate records.
    for index, record in enumerate(records, start=1):
        row = header_row + index

        values = [
            index,
            record.rfi_number,
            record.rfi_activity,
            record.number_of_items_inspected,
            timezone.localtime(record.recorded_at).strftime(
                "%d %b %Y, %I:%M %p"
            ),
            "Attached" if record.signed_copy else "No attachment",
        ]

        for column, value in enumerate(values, start=1):
            cell = worksheet.cell(
                row=row,
                column=column,
                value=value,
            )
            cell.alignment = Alignment(
                vertical="top",
                wrap_text=True,
            )

            if index % 2 == 0:
                cell.fill = PatternFill(
                    "solid",
                    fgColor="F4F7FB",
                )

        worksheet.cell(row=row, column=1).alignment = Alignment(
            horizontal="center",
            vertical="top",
        )
        worksheet.cell(row=row, column=4).alignment = Alignment(
            horizontal="center",
            vertical="top",
        )

    # Column widths.
    column_widths = {
        "A": 8,
        "B": 32,
        "C": 55,
        "D": 18,
        "E": 25,
        "F": 20,
    }

    for column, width in column_widths.items():
        worksheet.column_dimensions[column].width = width

    worksheet.row_dimensions[header_row].height = 30

    # Freeze table headings and enable filters.
    worksheet.freeze_panes = "A8"
    worksheet.auto_filter.ref = (
        f"A{header_row}:F{header_row + total_records}"
    )

    # Add borders.
    thin_border = Border(
        bottom=Side(
            style="thin",
            color="DCE4EF",
        )
    )

    for row in worksheet.iter_rows(
        min_row=header_row,
        max_row=header_row + total_records,
        min_col=1,
        max_col=6,
    ):
        for cell in row:
            cell.border = thin_border

    # Prepare Excel download.
    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    filename = (
        f"signed_rfi_{period}_"
        f"{start_date:%Y%m%d}_{end_date:%Y%m%d}.xlsx"
    )

    response = HttpResponse(
        output.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    return response

@login_required
def client_signed_rfi_file_view(request, pk):
    """Allow a client to view only their own uploaded signed RFI."""

    profile = getattr(request.user, "profile", None)

    if profile is None or profile.role != UserProfile.Role.CLIENT:
        raise Http404("File not found.")

    record = get_object_or_404(
        ClientSignedRFI,
        pk=pk,
        client=request.user,
    )

    if not record.signed_copy:
        raise Http404("File not found.")

    return FileResponse(
        record.signed_copy.open("rb"),
        as_attachment=False,
        filename=record.signed_copy.name.split("/")[-1],
    )


@login_required
def client_signed_rfi_create_view(request):
    """Allow a client to record an RFI they have signed."""

    profile = getattr(request.user, "profile", None)

    if profile is None or profile.role != UserProfile.Role.CLIENT:
        messages.error(request, "You do not have permission to access this page.")
        return redirect("dashboard")

    if request.method == "POST":
        form = ClientSignedRFIForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            record = form.save(commit=False)
            record.client = request.user
            record.save()

            messages.success(
                request,
                "Your signed RFI has been recorded successfully.",
            )

            return redirect("client_signed_rfi_list")

    else:
        form = ClientSignedRFIForm()

    return render(
        request,
        "rfi_management/client_signed_rfi_form.html",
        {
            "form": form,
        },
    )


@login_required
def logout_view(request):
    """
    Log the current user out.
    """

    logout(request)

    return redirect("login")

@login_required
def rfi_list_view(request):
    """
    Display registered RFIs with search by:
    - RFI number or internal reference
    - Current QC inspector's name
    """

    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile.",
        )
        return redirect("login")

    if profile.role not in [
        UserProfile.Role.ADMIN,
        UserProfile.Role.SUPERVISOR,
        UserProfile.Role.INSPECTOR,
    ]:
        messages.error(
            request,
            "You do not have permission to access the RFI register.",
        )
        return redirect("dashboard")

    query = request.GET.get("q", "").strip()
    result_filter = request.GET.get("result", "").strip()

    rfis = RFI.objects.select_related(
        "created_by"
    ).order_by(
        "-date_received",
        "-created_at",
    )

    if query:
        rfis = rfis.filter(
            Q(rfi_number__icontains=query)
            | Q(internal_reference__icontains=query)
            | Q(
                assignments__inspector__first_name__icontains=query,
                assignments__unassigned_at__isnull=True,
            )
            | Q(
                assignments__inspector__last_name__icontains=query,
                assignments__unassigned_at__isnull=True,
            )
            | Q(
                assignments__inspector__username__icontains=query,
                assignments__unassigned_at__isnull=True,
            )
        ).distinct()

    # Filter RFIs by recorded inspection outcome or item result.
    result_filters = {
        "ACCEPTED": Q(
            inspections__overall_result="ACCEPTED"
        ),
        "PARTIALLY_ACCEPTED": Q(
            inspections__overall_result="PARTIALLY_ACCEPTED"
        ),
        "ITEM_NOT_READY": Q(
            inspections__item_results__result_type="FAILED",
            inspections__item_results__result_code="1",
        ),
        "ITEM_NOT_INSPECTABLE": Q(
            inspections__item_results__result_type="FAILED",
            inspections__item_results__result_code="2",
        ),
        "INSPECTION_FAILED": Q(
            inspections__item_results__result_type="FAILED",
            inspections__item_results__result_code="3",
        ),
        "TIME_CONSTRAINT": Q(
            inspections__item_results__result_type="FAILED",
            inspections__item_results__result_code="4",
        ),
        "NCR": Q(
            inspections__item_results__result_type="FAILED",
            inspections__item_results__result_code="5",
        ),
    }

    if result_filter in result_filters:
        rfis = rfis.filter(result_filters[result_filter]).distinct()

    return render(
        request,
        "rfi_management/rfi_list.html",
        {
            "rfis": rfis,
            "search_query": query,
            "rfi_count": rfis.count(),
            "result_filter": result_filter,
        },
    )

@login_required
def rfi_create_view(request):
    """
    Register a newly received RFI.

    Only Supervisors and Administrators and Supervisor can register RFIs.
    """

    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile.",
        )
        return redirect("login")

    if profile.role not in [
        UserProfile.Role.ADMIN,
        UserProfile.Role.SUPERVISOR,
        UserProfile.Role.INSPECTOR,
    ]:
        messages.error(
            request,
            "You do not have permission to register RFIs.",
        )
        return redirect("dashboard")

    if request.method == "POST":
        form = RFIRegistrationForm(request.POST)

        if form.is_valid():
            rfi = form.save(commit=False)

            rfi.created_by = request.user

            rfi.current_planned_start = rfi.original_planned_start
            rfi.current_planned_end = rfi.original_planned_end

            rfi.status = RFI.Status.RECEIVED

            rfi.save()

            messages.success(
                request,
                f"RFI {rfi.internal_reference} registered successfully."
            )

            return redirect("rfi_detail", rfi_id=rfi.id)

    else:
        form = RFIRegistrationForm(
            initial={
                "date_received": timezone.localdate(),
            }
        )

    return render(
        request,
        "rfi_management/rfi_create.html",
        {
            "form": form,
        },
    )

@login_required
def rfi_detail_view(request, rfi_id):
    """
    Display the details of a registered RFI.
    """

    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile.",
        )
        return redirect("login")

    if profile.role not in [
        UserProfile.Role.ADMIN,
        UserProfile.Role.SUPERVISOR,
        UserProfile.Role.INSPECTOR,
    ]:
        messages.error(
            request,
            "You do not have permission to view RFIs.",
        )
        return redirect("dashboard")

    rfi = get_object_or_404(
        RFI.objects
        .select_related("created_by")
        .prefetch_related(
            "assignments__inspector",
            "assignments__assigned_by",
        ),
        pk=rfi_id,
    )

    assignments = rfi.assignments.order_by("-assigned_at")

    active_assignment = next(
        (
            assignment
            for assignment in assignments
            if assignment.unassigned_at is None
        ),
        None,
    )

    active_inspection = (
        rfi.inspections
        .filter(
            inspector=request.user,
            overall_result="",
        )
        .order_by("-inspection_number")
        .first()
    )

    inspections = (
        rfi.inspections
        .select_related("inspector")
        .prefetch_related("punch_lists")
        .order_by("-inspection_number")
    )

    return render(
        request,
        "rfi_management/rfi_detail.html",
        {
            "rfi": rfi,
            "assignments": assignments,
            "active_assignment": active_assignment,
            "active_inspection": active_inspection,
            "inspections": inspections,
        },
    )

@login_required
def rfi_assign_view(request, rfi_id):
    """
    Assign an RFI to an active QC Inspector.

    An RFI can only have one active assignment at a time.
    A separate reassignment workflow can be implemented later.
    """

    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile.",
        )
        return redirect("login")

    if profile.role not in [
        UserProfile.Role.ADMIN,
        UserProfile.Role.SUPERVISOR,
        UserProfile.Role.INSPETOR,
    ]:
        messages.error(
            request,
            "You do not have permission to assign RFIs.",
        )
        return redirect("dashboard")

    rfi = get_object_or_404(RFI, pk=rfi_id)

    # Check whether the RFI already has an active assignment.
    active_assignment = (
        Assignment.objects
        .filter(
            rfi=rfi,
            unassigned_at__isnull=True,
        )
        .select_related("inspector")
        .first()
    )

    if active_assignment:
        inspector_name = (
            active_assignment.inspector.get_full_name()
            or active_assignment.inspector.username
        )

        messages.warning(
            request,
            (
                f"RFI {rfi.internal_reference} is already assigned "
                f"to {inspector_name}. "
                "It cannot be assigned to another inspector while "
                "the current assignment is active."
            ),
        )

        return redirect(
            "rfi_detail",
            rfi_id=rfi.id,
        )

    if request.method == "POST":
        form = RFIAssignmentForm(request.POST)

        if form.is_valid():

            inspector = form.cleaned_data["inspector"]
            reason = form.cleaned_data["reason"]

            Assignment.objects.create(
                rfi=rfi,
                inspector=inspector,
                assigned_by=request.user,
                reason=reason,
            )

            rfi.status = RFI.Status.ASSIGNED
            rfi.save(update_fields=["status", "updated_at"])

            messages.success(
                request,
                f"RFI {rfi.internal_reference} assigned successfully.",
            )

            return redirect(
                "rfi_detail",
                rfi_id=rfi.id,
            )

    else:
        form = RFIAssignmentForm()

    return render(
        request,
        "rfi_management/rfi_assign.html",
        {
            "rfi": rfi,
            "form": form,
        },
    )

@login_required
def rfi_reassign_view(request, rfi_id):
    """
    Allow administrators to reassign an RFI while preserving
    its previous assignment history.
    """

    profile = getattr(request.user, "profile", None)

    if profile is None or profile.role != UserProfile.Role.ADMIN:
        messages.error(
            request,
            "Only administrators can reassign RFIs.",
        )
        return redirect("rfi_list")

    rfi = get_object_or_404(RFI, pk=rfi_id)

    active_assignment = (
        Assignment.objects
        .filter(rfi=rfi, unassigned_at__isnull=True)
        .select_related("inspector")
        .first()
    )

    if active_assignment is None:
        messages.warning(
            request,
            "This RFI has no active assignment. Use Assign RFI instead.",
        )
        return redirect("rfi_assign", rfi_id=rfi.id)

    # Do not change the responsible inspector during an inspection
    # that is still in progress.
    if rfi.inspections.filter(overall_result="").exists():
        messages.error(
            request,
            "This RFI has an inspection in progress. "
            "Complete or resolve that inspection before reassigning it.",
        )
        return redirect("rfi_detail", rfi_id=rfi.id)

    # Only active QC inspectors may receive assignments.
    eligible_inspectors = UserProfile.objects.filter(
        role=UserProfile.Role.INSPECTOR,
        is_active_qc=True,
        user__is_active=True,
    ).select_related("user").order_by(
        "user__first_name",
        "user__last_name",
        "user__username",
    )

    if request.method == "POST":
        inspector_id = request.POST.get("inspector")
        reason = request.POST.get("reason", "").strip()

        try:
            new_profile = eligible_inspectors.get(user_id=inspector_id)
        except (UserProfile.DoesNotExist, ValueError, TypeError):
            messages.error(
                request,
                "Select a valid, active QC inspector.",
            )
            return render(
                request,
                "rfi_management/rfi_reassign.html",
                {
                    "rfi": rfi,
                    "active_assignment": active_assignment,
                    "eligible_inspectors": eligible_inspectors,
                },
            )

        new_inspector = new_profile.user

        if new_inspector.pk == active_assignment.inspector_id:
            messages.warning(
                request,
                "The selected inspector is already assigned to this RFI.",
            )
            return redirect("rfi_reassign", rfi_id=rfi.id)

        from django.db import transaction

        with transaction.atomic():
            # Close the existing assignment; do not delete it.
            active_assignment.unassigned_at = timezone.now()
            active_assignment.save(update_fields=["unassigned_at"])

            # Create a new assignment so the audit trail remains intact.
            Assignment.objects.create(
                rfi=rfi,
                inspector=new_inspector,
                assigned_by=request.user,
                reason=reason or (
                    f"Reassigned from "
                    f"{active_assignment.inspector.get_full_name() or active_assignment.inspector.username}"
                ),
            )

            RFIHistory.objects.create(
                rfi=rfi,
                user=request.user,
                action="RFI_REASSIGNED",
                description=(
                    f"Assignment changed from "
                    f"{active_assignment.inspector.get_full_name() or active_assignment.inspector.username} "
                    f"to {new_inspector.get_full_name() or new_inspector.username}. "
                    f"Reason: {reason or 'No reason provided.'}"
                ),
            )

            # Do not reopen or reset RFIs that have already progressed
            # to a later workflow status.
            if rfi.status in [
                RFI.Status.RECEIVED,
                RFI.Status.UNASSIGNED,
                RFI.Status.ASSIGNED,
                RFI.Status.SCHEDULED,
                RFI.Status.OVERDUE,
            ]:
                rfi.status = RFI.Status.ASSIGNED
                rfi.save(update_fields=["status", "updated_at"])

        messages.success(
            request,
            f"{rfi.internal_reference} was reassigned successfully.",
        )
        return redirect("rfi_detail", rfi_id=rfi.id)

    return render(
        request,
        "rfi_management/rfi_reassign.html",
        {
            "rfi": rfi,
            "active_assignment": active_assignment,
            "eligible_inspectors": eligible_inspectors,
        },
    )

@login_required
def rfi_delete_view(request, rfi_id):
    """
    Allow administrators to delete an RFI only when it has no
    inspection or punch-list records.
    """

    profile = getattr(request.user, "profile", None)

    if profile is None or profile.role != UserProfile.Role.ADMIN:
        messages.error(
            request,
            "Only administrators can delete RFIs.",
        )
        return redirect("rfi_list")

    rfi = get_object_or_404(RFI, pk=rfi_id)

    # Protect operational history and relationships.
    has_inspections = rfi.inspections.exists()
    has_punch_lists = rfi.punch_lists.exists()

    if request.method == "POST":
        if has_inspections or has_punch_lists:
            messages.error(
                request,
                "This RFI cannot be deleted because it has inspection "
                "or punch-list records. Preserve the record and correct "
                "its assignment instead.",
            )
            return redirect("rfi_detail", rfi_id=rfi.id)

        reference = rfi.internal_reference
        contractor_number = rfi.rfi_number

        # The confirmation page submits POST; GET never deletes.
        rfi.delete()

        messages.success(
            request,
            f"RFI {reference} ({contractor_number}) was deleted.",
        )
        return redirect("rfi_list")

    return render(
        request,
        "rfi_management/rfi_delete_confirm.html",
        {
            "rfi": rfi,
            "has_inspections": has_inspections,
            "has_punch_lists": has_punch_lists,
        },
    )

@login_required
def inspector_rfi_list_view(request):
    """
    Show RFIs currently assigned to the logged-in inspector.
    Search by RFI number/internal reference and inspection result.
    """

    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile.",
        )
        return redirect("login")

    if profile.role != UserProfile.Role.INSPECTOR:
        messages.error(
            request,
            "Only QC Inspectors can access their assigned RFIs.",
        )
        return redirect("dashboard")

    search_query = request.GET.get("q", "").strip()
    result_filter = request.GET.get("result", "").strip()

    assigned_rfis = (
        RFI.objects.filter(
            Q(created_by=request.user)
            | Q(
                assignments__inspector=request.user,
                assignments__unassigned_at__isnull=True,
            )
        )
        .select_related("created_by")
        .distinct()
        .order_by(
            "current_planned_start",
            "rfi_number",
        )
    )

    # Search by contractor RFI number or internal reference.
    if search_query:
        assigned_rfis = assigned_rfis.filter(
            Q(rfi_number__icontains=search_query)
            | Q(internal_reference__icontains=search_query)
        )

    # Filter by recorded inspection result.
    result_filters = {
        "ACCEPTED": Q(
            inspections__overall_result="ACCEPTED"
        ),
        "PARTIALLY_ACCEPTED": Q(
            inspections__overall_result="PARTIALLY_ACCEPTED"
        ),
        "ITEM_NOT_READY": Q(
            inspections__item_results__result_type="FAILED",
            inspections__item_results__result_code="1",
        ),
        "ITEM_NOT_INSPECTABLE": Q(
            inspections__item_results__result_type="FAILED",
            inspections__item_results__result_code="2",
        ),
        "INSPECTION_FAILED": Q(
            inspections__item_results__result_type="FAILED",
            inspections__item_results__result_code="3",
        ),
        "TIME_CONSTRAINT": Q(
            inspections__item_results__result_type="FAILED",
            inspections__item_results__result_code="4",
        ),
        "NCR": Q(
            inspections__item_results__result_type="FAILED",
            inspections__item_results__result_code="5",
        ),
    }

    if result_filter in result_filters:
        assigned_rfis = assigned_rfis.filter(
            result_filters[result_filter]
        ).distinct()
    else:
        result_filter = ""

    return render(
        request,
        "rfi_management/inspector_rfi_list.html",
        {
            "rfis": assigned_rfis,
            "search_query": search_query,
            "result_filter": result_filter,
            "rfi_count": assigned_rfis.count(),
        },
    )

@login_required
def start_inspection_view(request, rfi_id):
    """
    Start a new inspection for an RFI.

    Only the QC Inspector currently assigned to the RFI
    can start the inspection.

    The inspection date must fall within the RFI's
    current Inspection Planned Period.
    """

    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile.",
        )
        return redirect("login")

    if profile.role != UserProfile.Role.INSPECTOR:
        messages.error(
            request,
            "Only QC Inspectors can start inspections.",
        )
        return redirect("dashboard")

    rfi = get_object_or_404(RFI, pk=rfi_id)

    if not inspector_can_access_rfi(rfi, request.user):
        messages.error(
            request,
            "You are not authorized to inspect this RFI.",
        )
        return redirect("inspector_rfi_list")

    active_inspection = (
        rfi.inspections
        .filter(
            overall_result="",
        )
        .order_by("-inspection_number")
        .first()
    )

    if active_inspection:
        messages.warning(
            request,
            (
                f"Inspection #{active_inspection.inspection_number} "
                f"for RFI {rfi.internal_reference} "
                "is already in progress."
            ),
        )

        return redirect(
            "inspection_detail",
            inspection_id=active_inspection.id,
        )

    if rfi.status not in [
        RFI.Status.RECEIVED,
        RFI.Status.ASSIGNED,
        RFI.Status.SCHEDULED,
    ]:

        messages.error(
            request,
            (
                f"RFI {rfi.internal_reference} cannot be started "
                f"while its status is "
                f"{rfi.get_status_display()}."
            ),
        )

        return redirect(
            "rfi_detail",
            rfi_id=rfi.id,
        )

    today = timezone.localdate()

    if today > rfi.current_planned_end:
        if rfi.status != RFI.Status.OVERDUE:
            rfi.status = RFI.Status.OVERDUE
            rfi.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

        messages.error(
            request,
            (
                f"The Inspection Planned Period for "
                f"RFI {rfi.internal_reference} has expired. "
                "A supervisor must renew the inspection period "
                "before inspection can begin."
            ),
        )

        return redirect(
            "rfi_detail",
            rfi_id=rfi.id,
        )

    if request.method == "POST":

        form = StartInspectionForm(
            request.POST,
            rfi=rfi,
        )

        if form.is_valid():

            last_inspection = (
                rfi.inspections
                .order_by("-inspection_number")
                .first()
            )

            if last_inspection:
                next_inspection_number = (
                    last_inspection.inspection_number + 1
                )
            else:
                next_inspection_number = 1

            inspection = Inspection.objects.create(
                rfi=rfi,
                inspection_number=next_inspection_number,
                inspector=request.user,
                inspection_date=form.cleaned_data[
                    "inspection_date"
                ],
                start_time=form.cleaned_data[
                    "start_time"
                ],
            )

            rfi.status = RFI.Status.UNDER_INSPECTION
            rfi.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            messages.success(
                request,
                (
                    f"Inspection #{inspection.inspection_number} "
                    f"started for RFI {rfi.internal_reference}."
                ),
            )

            return redirect(
                "inspection_detail",
                inspection_id=inspection.id,
            )

    else:

        form = StartInspectionForm(
            rfi=rfi,
            initial={
                "inspection_date": today,
            },
        )

    return render(
        request,
        "rfi_management/start_inspection.html",
        {
            "rfi": rfi,
            "form": form,
        },
    )

@login_required
def rfi_renew_period_view(request, rfi_id):
    profile = getattr(request.user, "profile", None)

    if profile is None or profile.role != UserProfile.Role.INSPECTOR:
        messages.error(request, "Only QC Inspectors can renew an RFI period.")
        return redirect("dashboard")

    rfi = get_object_or_404(RFI, pk=rfi_id)

    if not inspector_can_access_rfi(rfi, request.user):
        messages.error(request, "You are not authorized to update this RFI.")
        return redirect("inspector_rfi_list")

    if rfi.status != RFI.Status.OVERDUE:
        messages.error(request, "Only overdue RFIs can have their period renewed.")
        return redirect("rfi_detail", rfi_id=rfi.id)

    if request.method == "POST":
        form = RFIRenewalForm(request.POST)

        if form.is_valid():
            new_start = form.cleaned_data["new_start"]
            new_end = form.cleaned_data["new_end"]
            reason = form.cleaned_data["reason"]

            if new_start < timezone.localdate():
                form.add_error("new_start", "The new start date cannot be in the past.")
            else:
                with transaction.atomic():
                    RFIRenewal.objects.create(
                        rfi=rfi,
                        previous_start=rfi.current_planned_start,
                        previous_end=rfi.current_planned_end,
                        new_start=new_start,
                        new_end=new_end,
                        renewed_by=request.user,
                        reason=reason,
                    )

                    rfi.current_planned_start = new_start
                    rfi.current_planned_end = new_end
                    rfi.status = RFI.Status.SCHEDULED
                    rfi.save(update_fields=[
                        "current_planned_start",
                        "current_planned_end",
                        "status",
                        "updated_at",
                    ])

                    RFIHistory.objects.create(
                        rfi=rfi,
                        user=request.user,
                        action="INSPECTION_PERIOD_RENEWED",
                        description=(
                            f"Previous period: {rfi.current_planned_start} to "
                            f"{rfi.current_planned_end}. New period: {new_start} to "
                            f"{new_end}. Reason: {reason}"
                        ),
                    )

                messages.success(request, "The inspection period has been renewed.")
                return redirect("rfi_detail", rfi_id=rfi.id)
    else:
        form = RFIRenewalForm()

    return render(
        request,
        "rfi_management/rfi_renew_period.html",
        {"rfi": rfi, "form": form},
    )


@login_required
def rfi_return_to_supervisor_view(request, rfi_id):
    profile = getattr(request.user, "profile", None)

    if profile is None or profile.role != UserProfile.Role.INSPECTOR:
        messages.error(request, "Only QC Inspectors can return an RFI to the supervisor.")
        return redirect("dashboard")

    rfi = get_object_or_404(RFI, pk=rfi_id)

    if not inspector_can_access_rfi(rfi, request.user):
        messages.error(request, "You are not authorized to update this RFI.")
        return redirect("inspector_rfi_list")

    if rfi.status != RFI.Status.OVERDUE:
        messages.error(request, "Only overdue RFIs can be returned to the supervisor.")
        return redirect("rfi_detail", rfi_id=rfi.id)

    if request.method == "POST":
        form = ReturnToSupervisorForm(request.POST)

        if form.is_valid():
            reason = form.cleaned_data["reason"]

            with transaction.atomic():
                rfi.status = RFI.Status.RETURNED_TO_SUPERVISOR
                rfi.save(update_fields=["status", "updated_at"])

                RFIHistory.objects.create(
                    rfi=rfi,
                    user=request.user,
                    action="RETURNED_TO_SUPERVISOR",
                    description=reason,
                )

            messages.success(request, "The RFI has been returned to the supervisor.")
            return redirect("rfi_detail", rfi_id=rfi.id)
    else:
        form = ReturnToSupervisorForm()

    return render(
        request,
        "rfi_management/rfi_return_to_supervisor.html",
        {"rfi": rfi, "form": form},
    )


@login_required
def inspection_detail_view(request, inspection_id):
    """
    Display and update an inspection.

    Only the QC Inspector assigned to the RFI can
    record the inspection result.
    """

    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile.",
        )
        return redirect("login")

    if profile.role != UserProfile.Role.INSPECTOR:
        messages.error(
            request,
            "Only QC Inspectors can record inspection results.",
        )
        return redirect("dashboard")

    inspection = get_object_or_404(
        Inspection.objects.select_related(
            "rfi",
            "inspector",
        ),
        pk=inspection_id,
    )

    if (
        inspection.inspector_id != request.user.id
        or not inspector_can_access_rfi(inspection.rfi, request.user)
    ):
        messages.error(
            request,
            "You do not have permission to modify this inspection.",
        )
        return redirect("inspector_rfi_list")

    # Do not allow an inspection that already has a final result
    # to be edited as if it were still in progress.
    if inspection.overall_result:
        messages.info(
            request,
            (
                f"Inspection #{inspection.inspection_number} "
                "has already been completed."
            ),
        )
        return redirect(
            "rfi_detail",
            rfi_id=inspection.rfi.id,
        )

    if request.method == "POST":

        form = InspectionForm(
            request.POST,
            instance=inspection,
        )

        if form.is_valid():

            inspection = form.save()
            result = inspection.overall_result

            if result == Inspection.ExecutionResult.ACCEPTED:

                inspection.rfi.overall_result = (
                    RFI.OverallResult.COMPLETED
                )
                inspection.rfi.status = RFI.Status.CLOSED

                inspection.rfi.save(
                    update_fields=[
                        "overall_result",
                        "status",
                        "updated_at",
                    ]
                )

                messages.success(
                    request,
                    (
                        f"Inspection #{inspection.inspection_number} "
                        f"for RFI {inspection.rfi.internal_reference} "
                        "was accepted. The RFI has been closed."
                    ),
                )

            elif result == Inspection.ExecutionResult.PARTIALLY_ACCEPTED:

                with transaction.atomic():

                    inspection.rfi.overall_result = (
                        RFI.OverallResult.COMPLETED_WITH_PUNCH
                    )
                    inspection.rfi.status = (
                        RFI.Status.AWAITING_PUNCH
                    )

                    inspection.rfi.save(
                        update_fields=[
                            "overall_result",
                            "status",
                            "updated_at",
                        ]
                    )

                    # Check whether a punch list already exists.
                    punch_list = (
                        PunchList.objects
                        .filter(inspection=inspection)
                        .first()
                    )

                    # Automatically create a draft punch list
                    # if one does not already exist.
                    if punch_list is None:
                        punch_list = PunchList(
                            rfi=inspection.rfi,
                            inspection=inspection,
                            date_created=timezone.localdate(),
                            status=PunchList.Status.DRAFT,
                            remarks="",
                            created_by=request.user,
                        )
                        punch_list.save()

                messages.success(
                    request,
                    (
                        f"Inspection #{inspection.inspection_number} "
                        "was partially accepted. "
                        f"Punch list {punch_list.punch_list_number} "
                        "has been created."
                    ),
                )

                return redirect(
                    "punch_list_detail",
                    punch_list_id=punch_list.id,
                )

            elif result == Inspection.ExecutionResult.REJECTED:

                inspection.rfi.overall_result = (
                    RFI.OverallResult.REJECTED
                )
                inspection.rfi.status = RFI.Status.FOLLOW_UP

                inspection.rfi.save(
                    update_fields=[
                        "overall_result",
                        "status",
                        "updated_at",
                    ]
                )

                messages.warning(
                    request,
                    (
                        f"Inspection #{inspection.inspection_number} "
                        f"for RFI {inspection.rfi.internal_reference} "
                        "was rejected. Follow-up action is required."
                    ),
                )

            elif result == Inspection.ExecutionResult.POSTPONED:

                inspection.rfi.overall_result = (
                    RFI.OverallResult.PENDING
                )
                inspection.rfi.status = RFI.Status.SCHEDULED

                inspection.rfi.save(
                    update_fields=[
                        "overall_result",
                        "status",
                        "updated_at",
                    ]
                )

                messages.info(
                    request,
                    (
                        f"Inspection #{inspection.inspection_number} "
                        f"for RFI {inspection.rfi.internal_reference} "
                        "was postponed. The RFI has been returned "
                        "to scheduled status."
                    ),
                )

            elif result == Inspection.ExecutionResult.CANCELLED:

                inspection.rfi.overall_result = (
                    RFI.OverallResult.RETURNED
                )
                inspection.rfi.status = RFI.Status.RETURNED

                inspection.rfi.save(
                    update_fields=[
                        "overall_result",
                        "status",
                        "updated_at",
                    ]
                )

                messages.warning(
                    request,
                    (
                        f"Inspection #{inspection.inspection_number} "
                        f"for RFI {inspection.rfi.internal_reference} "
                        "was cancelled. The RFI has been returned."
                    ),
                )

            return redirect(
                "rfi_detail",
                rfi_id=inspection.rfi.id,
            )

    else:

        form = InspectionForm(
            instance=inspection,
        )

    return render(
        request,
        "rfi_management/inspection_detail.html",
        {
            "inspection": inspection,
            "rfi": inspection.rfi,
            "form": form,
        },
    )


@login_required
def punch_list_create_view(request, inspection_id):
    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile."
        )
        return redirect("login")

    allowed_roles = [
        UserProfile.Role.ADMIN,
        UserProfile.Role.SUPERVISOR,
        UserProfile.Role.INSPECTOR,
    ]

    if profile.role not in allowed_roles:
        messages.error(
            request,
            "You do not have permission to create punch lists."
        )
        return redirect("dashboard")

    inspection = get_object_or_404(
        Inspection.objects.select_related(
            "rfi",
            "inspector",
        ),
        pk=inspection_id,
    )

    rfi = inspection.rfi

    if (
        inspection.overall_result
        != Inspection.ExecutionResult.PARTIALLY_ACCEPTED
    ):
        messages.error(
            request,
            "A punch list can only be created for a partially accepted inspection."
        )
        return redirect(
            "rfi_detail",
            rfi_id=rfi.id,
        )

    if rfi.status != RFI.Status.AWAITING_PUNCH:
        messages.error(
            request,
            "This RFI is not awaiting punch-list processing."
        )
        return redirect(
            "rfi_detail",
            rfi_id=rfi.id,
        )

    if profile.role == UserProfile.Role.INSPECTOR:
        if (
            inspection.inspector_id != request.user.id
            or not inspector_can_access_rfi(inspection.rfi, request.user)
        ):
            messages.error(
                request,
                "You are not authorized to access this inspection."
            )
            return redirect("inspector_rfi_list")

    existing_punch_list = (
        PunchList.objects
        .filter(inspection=inspection)
        .first()
    )

    if existing_punch_list:
        messages.info(
            request,
            "A punch list already exists for this inspection."
        )
        return redirect(
            "punch_list_detail",
            punch_list_id=existing_punch_list.id,
        )

    if request.method == "POST":
        form = PunchListCreateForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                punch_list = form.save(commit=False)
                punch_list.rfi = rfi
                punch_list.inspection = inspection
                punch_list.created_by = request.user
                punch_list.status = PunchList.Status.DRAFT
                punch_list.save()

            messages.success(
                request,
                f"Punch list {punch_list.punch_list_number} created successfully."
            )

            return redirect(
                "punch_list_detail",
                punch_list_id=punch_list.id,
            )

    else:
        form = PunchListCreateForm()

    return render(
        request,
        "rfi_management/punch_list_create.html",
        {
            "form": form,
            "rfi": rfi,
            "inspection": inspection,
        },
    )

@login_required
def punch_list_detail_view(request, punch_list_id):
    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile."
        )
        return redirect("login")

    punch_list = get_object_or_404(
        PunchList.objects.select_related(
            "rfi",
            "inspection",
            "created_by",
        ).prefetch_related("items"),
        pk=punch_list_id,
    )

    if profile.role not in [
        UserProfile.Role.ADMIN,
        UserProfile.Role.SUPERVISOR,
        UserProfile.Role.INSPECTOR,
    ]:
        messages.error(
            request,
            "You do not have permission to view this punch list."
        )
        return redirect("dashboard")

    if profile.role == UserProfile.Role.INSPECTOR:
        if (
            punch_list.inspection.inspector_id != request.user.id
            or not inspector_can_access_rfi(punch_list.rfi, request.user)
        ):
            messages.error(
                request,
                "You are not authorized to access this punch list."
            )
            return redirect("inspector_rfi_list")

    return render(
        request,
        "rfi_management/punch_list_detail.html",
        {
            "punch_list": punch_list,
            "rfi": punch_list.rfi,
            "inspection": punch_list.inspection,
            "items": punch_list.items.all(),
            "can_add_items": (
                punch_list.status == PunchList.Status.DRAFT
            ),
            "signed_documents": punch_list.uploaded_documents.filter(
                document_type=Document.DocumentType.SIGNED_PUNCH_LIST
            ),
        },
    )

@login_required
def punch_list_signed_upload_view(request, punch_list_id):
    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile."
        )
        return redirect("login")

    allowed_roles = [
        UserProfile.Role.ADMIN,
        UserProfile.Role.SUPERVISOR,
        UserProfile.Role.INSPECTOR,
    ]

    if profile.role not in allowed_roles:
        messages.error(
            request,
            "You do not have permission to upload signed punch lists."
        )
        return redirect("dashboard")

    punch_list = get_object_or_404(
        PunchList.objects.select_related(
            "rfi",
            "inspection",
            "inspection__inspector",
        ),
        pk=punch_list_id,
    )

    # Apply the same inspector authorization as the detail view.
    if profile.role == UserProfile.Role.INSPECTOR:
        if (
            punch_list.inspection.inspector_id != request.user.id
            or not inspector_can_access_rfi(punch_list.rfi, request.user)
        ):
            messages.error(
                request,
                "You are not authorized to access this punch list."
            )
            return redirect("inspector_rfi_list")

    if request.method != "POST":
        return redirect(
            "punch_list_detail",
            punch_list_id=punch_list.id,
        )

    if punch_list.status != PunchList.Status.DRAFT:
        messages.error(
            request,
            "A signed document can only be uploaded while the punch list is in Draft status."
        )
        return redirect(
            "punch_list_detail",
            punch_list_id=punch_list.id,
        )

    uploaded_file = request.FILES.get("signed_file")

    if not uploaded_file:
        messages.error(
            request,
            "Please select the signed punch-list document to upload."
        )
        return redirect(
            "punch_list_detail",
            punch_list_id=punch_list.id,
        )

    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png"}
    file_extension = os.path.splitext(uploaded_file.name)[1].lower()

    if file_extension not in allowed_extensions:
        messages.error(
            request,
            "Invalid file format. Upload a PDF, JPG, JPEG, or PNG file."
        )
        return redirect(
            "punch_list_detail",
            punch_list_id=punch_list.id,
        )

    max_file_size = 10 * 1024 * 1024  # 10 MB

    if uploaded_file.size > max_file_size:
        messages.error(
            request,
            "The file exceeds the maximum allowed size of 10 MB."
        )
        return redirect(
            "punch_list_detail",
            punch_list_id=punch_list.id,
        )

    with transaction.atomic():
        Document.objects.create(
            rfi=punch_list.rfi,
            punch_list=punch_list,
            file=uploaded_file,
            document_type=Document.DocumentType.SIGNED_PUNCH_LIST,
            uploaded_by=request.user,
            description=(
                f"Client-signed punch list "
                f"{punch_list.punch_list_number}"
            ),
        )

        punch_list.status = PunchList.Status.SIGNED
        punch_list.signed_at = timezone.now()
        punch_list.save(
            update_fields=["status", "signed_at"]
        )

        RFIHistory.objects.create(
            rfi=punch_list.rfi,
            user=request.user,
            action="SIGNED_PUNCH_LIST_UPLOADED",
            description=(
                f"Client-signed document uploaded for punch list "
                f"{punch_list.punch_list_number}."
            ),
        )

    messages.success(
        request,
        "The signed punch-list document was uploaded successfully."
    )

    return redirect(
        "punch_list_detail",
        punch_list_id=punch_list.id,
    )


@login_required
def punch_item_create_view(request, punch_list_id):
    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile."
        )
        return redirect("login")

    punch_list = get_object_or_404(
        PunchList.objects.select_related(
            "rfi",
            "inspection",
        ),
        pk=punch_list_id,
    )

    if profile.role not in [
        UserProfile.Role.ADMIN,
        UserProfile.Role.SUPERVISOR,
        UserProfile.Role.INSPECTOR,
    ]:
        messages.error(
            request,
            "You do not have permission to add punch items."
        )
        return redirect("dashboard")

    if profile.role == UserProfile.Role.INSPECTOR:
        if (
            punch_list.inspection.inspector_id != request.user.id
            or not inspector_can_access_rfi(punch_list.rfi, request.user)
        ):
            messages.error(
                request,
                "You are not authorized to access this punch list."
            )
            return redirect("inspector_rfi_list")

    if punch_list.status != PunchList.Status.DRAFT:
        messages.error(
            request,
            "Punch items can only be added while the punch list is in Draft status."
        )
        return redirect(
            "punch_list_detail",
            punch_list_id=punch_list.id,
        )

    if request.method == "POST":
        form = PunchItemCreateForm(request.POST)

        if form.is_valid():
            item = form.save(commit=False)
            item.punch_list = punch_list
            item.status = PunchItem.Status.OPEN

            try:
                with transaction.atomic():
                    item.save()
            except IntegrityError:
                form.add_error(
                    "item_number",
                    "This item number already exists on this punch list."
                )
            else:
                messages.success(
                    request,
                    f"Punch Item {item.item_number} added successfully."
                )
                return redirect(
                    "punch_list_detail",
                    punch_list_id=punch_list.id,
                )

    else:
        next_item_number = (
            punch_list.items.aggregate(
                maximum=Max("item_number")
            )["maximum"] or 0
        ) + 1

        form = PunchItemCreateForm(
            initial={"item_number": next_item_number}
        )

    return render(
        request,
        "rfi_management/punch_item_form.html",
        {
            "form": form,
            "punch_list": punch_list,
        },
    )


@login_required
def change_own_password_view(request):
    """
    Allow logged-in Inspectors and Clients to change their own passwords.
    """

    profile = getattr(request.user, "profile", None)

    if profile is None:
        messages.error(
            request,
            "Your account does not have a QC profile.",
        )
        return redirect("login")

    if profile.role not in [
        UserProfile.Role.INSPECTOR,
        UserProfile.Role.CLIENT,
    ]:
        messages.error(
            request,
            "You do not have permission to use this page.",
        )
        return redirect("dashboard")

    if request.method == "POST":
        form = PasswordChangeForm(
            user=request.user,
            data=request.POST,
        )

        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)

            messages.success(
                request,
                "Your password was changed successfully.",
            )

            return redirect("dashboard")

    else:
        form = PasswordChangeForm(user=request.user)

    return render(
        request,
        "rfi_management/change_own_password.html",
        {
            "form": form,
        },
    )
