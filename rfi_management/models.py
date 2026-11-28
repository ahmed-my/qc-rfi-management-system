from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from qc_rfi_system.private_storage import PrivateMediaStorage
from django.db.models.functions import Lower


# ============================================================
# USER PROFILE
# ============================================================

class UserProfile(models.Model):

    class Role(models.TextChoices):
        SUPERVISOR = "SUPERVISOR", "Supervisor"
        INSPECTOR = "INSPECTOR", "Inspector"
        ADMIN = "ADMIN", "Administrator"
        CLIENT = "CLIENT", "Client"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices
    )

    is_active_qc = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_role_display()}"


# ============================================================
# RFI
# ============================================================

class RFI(models.Model):

    class Status(models.TextChoices):
        RETURNED_TO_SUPERVISOR = (
            "RETURNED_TO_SUPERVISOR",
            "Returned to Supervisor",
        )
        RECEIVED = "RECEIVED", "Received"
        UNASSIGNED = "UNASSIGNED", "Unassigned"
        ASSIGNED = "ASSIGNED", "Assigned"
        SCHEDULED = "SCHEDULED", "Scheduled"
        OVERDUE = "OVERDUE", "Overdue"
        UNDER_INSPECTION = "UNDER_INSPECTION", "Under Inspection"
        AWAITING_PUNCH = "AWAITING_PUNCH", "Awaiting Punch List"
        FOLLOW_UP = "FOLLOW_UP", "Follow-up Required"
        RETURNED = "RETURNED", "Returned to Construction"
        REJECTED = "REJECTED", "Rejected"
        CLOSED = "CLOSED", "Closed"

    class OverallResult(models.TextChoices):
        COMPLETED = "COMPLETED", "Completed"
        COMPLETED_WITH_PUNCH = (
            "COMPLETED_WITH_PUNCH",
            "Completed with Punch List"
        )
        PARTIALLY_COMPLETED = (
            "PARTIALLY_COMPLETED",
            "Partially Completed"
        )
        REJECTED = "REJECTED", "Rejected"
        RETURNED = "RETURNED", "Returned to Construction"
        PENDING = "PENDING", "Pending / Not Yet Determined"

    class FollowUpReason(models.TextChoices):
        PUNCH_LIST = "PUNCH_LIST", "Punch List"
        INSPECTION_FAILED = (
            "INSPECTION_FAILED",
            "Inspection Failed"
        )
        PARTIAL_COMPLETION = (
            "PARTIAL_COMPLETION",
            "Partial Completion"
        )
        OTHER = "OTHER", "Other"

    # --------------------------------------------------------
    # Identification
    # --------------------------------------------------------

    internal_reference = models.CharField(
        max_length=50,
        unique=True,
        editable=False
    )

    rfi_number = models.CharField(
        max_length=100
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("rfi_number"),
                name="unique_rfi_number_case_insensitive",
            ),
        ]

    revision = models.CharField(
        max_length=20,
        blank=True
    )

    certificate_code = models.CharField(
        max_length=100,
        blank=True
    )

    client_rfi_number = models.CharField(
        max_length=100,
        blank=True
    )

    # --------------------------------------------------------
    # Contractor
    # --------------------------------------------------------

    contractor = models.CharField(
        max_length=100,
        default="Daewoo"
    )

    # --------------------------------------------------------
    # Planning
    # --------------------------------------------------------

    date_received = models.DateField()

    original_planned_start = models.DateField()
    original_planned_end = models.DateField()
    current_planned_start = models.DateField()
    current_planned_end = models.DateField()

    planned_time = models.TimeField(
        null=True,
        blank=True
    )

    # --------------------------------------------------------
    # Technical information
    # --------------------------------------------------------

    discipline = models.CharField(
        max_length=100,
        blank=True
    )

    area = models.CharField(
        max_length=100,
        blank=True
    )

    unit = models.CharField(
        max_length=100,
        blank=True
    )

    system = models.CharField(
        max_length=150,
        blank=True
    )

    subsystem = models.CharField(
        max_length=150,
        blank=True
    )

    qc_code = models.CharField(
        max_length=100,
        blank=True
    )

    itp_document = models.CharField(
        max_length=200,
        blank=True
    )

    form_code = models.CharField(
        max_length=100,
        blank=True
    )

    iwp_code = models.CharField(
        max_length=150,
        blank=True
    )

    inspection_activity = models.TextField(
        blank=True
    )

    reference_documents = models.TextField(
        blank=True
    )

    # --------------------------------------------------------
    # Workflow
    # --------------------------------------------------------

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.RECEIVED
    )

    overall_result = models.CharField(
        max_length=30,
        choices=OverallResult.choices,
        blank=True
    )

    # --------------------------------------------------------
    # Follow-up RFI
    # --------------------------------------------------------

    parent_rfi = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="follow_up_rfis"
    )

    follow_up_reason = models.CharField(
        max_length=30,
        choices=FollowUpReason.choices,
        blank=True
    )

    # --------------------------------------------------------
    # Record keeping
    # --------------------------------------------------------

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="rfis_created"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def save(self, *args, **kwargs):
        if self.internal_reference:
            super().save(*args, **kwargs)
            return

        with transaction.atomic():
            # First save lets the database generate the unique primary key.
            super().save(*args, **kwargs)

            # Use the database-generated ID as the internal sequence.
            self.internal_reference = f"RFI-{self.pk:06d}"

            # Save only the generated internal reference.
            super().save(update_fields=["internal_reference"])

    def __str__(self):
        return self.rfi_number


# ============================================================
# RFI ITEM
# ============================================================

class RFIItem(models.Model):

    rfi = models.ForeignKey(
        RFI,
        on_delete=models.CASCADE,
        related_name="items"
    )

    item_number = models.PositiveIntegerField()

    item_code = models.CharField(
        max_length=150,
        blank=True
    )

    description = models.TextField()

    area = models.CharField(
        max_length=100,
        blank=True
    )

    subsystem = models.CharField(
        max_length=150,
        blank=True
    )

    iwp_code = models.CharField(
        max_length=150,
        blank=True
    )

    source_page = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    extraction_confidence = models.CharField(
        max_length=20,
        blank=True
    )

    manually_verified = models.BooleanField(
        default=False
    )

    class Meta:
        ordering = ["item_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["rfi", "item_number"],
                name="unique_rfi_item_number"
            )
        ]

    def __str__(self):
        return f"{self.rfi.rfi_number} - Item {self.item_number}"


# ============================================================
# ASSIGNMENT
# ============================================================

class Assignment(models.Model):

    rfi = models.ForeignKey(
        RFI,
        on_delete=models.CASCADE,
        related_name="assignments"
    )

    inspector = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="rfi_assignments"
    )

    assigned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="assignments_made"
    )

    assigned_at = models.DateTimeField(
        auto_now_add=True
    )

    unassigned_at = models.DateTimeField(
        null=True,
        blank=True
    )

    reason = models.TextField(
        blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["rfi"],
                condition=Q(unassigned_at__isnull=True),
                name="unique_active_rfi_assignment",
            ),
        ]

    def __str__(self):
        return (
            f"{self.rfi.rfi_number} -> "
            f"{self.inspector.get_full_name()}"
        )


# ============================================================
# INSPECTION
# ============================================================

class Inspection(models.Model):

    class ExecutionResult(models.TextChoices):
        ACCEPTED = "ACCEPTED", "Accepted"
        ACCEPTED_WITH_PUNCH_LIST = (
            "ACCEPTED_WITH_PUNCH_LIST",
            "Accepted with Punch List"
        )
        REJECTED = "REJECTED", "Rejected"
        POSTPONED = "POSTPONED", "Postponed"
        CANCELLED = "CANCELLED", "Cancelled"
        PARTIALLY_ACCEPTED = (
            "PARTIALLY_ACCEPTED",
            "Partially Accepted"
    )

    rfi = models.ForeignKey(
        RFI,
        on_delete=models.CASCADE,
        related_name="inspections"
    )

    inspection_number = models.PositiveIntegerField()

    inspector = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="inspections"
    )

    inspection_date = models.DateField()

    start_time = models.TimeField()

    overall_result = models.CharField(
        max_length=30,
        choices=ExecutionResult.choices,
        blank=True
    )

    remarks = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["inspection_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["rfi", "inspection_number"],
                name="unique_inspection_number"
            )
        ]

    def __str__(self):
        return (
            f"{self.rfi.rfi_number} - "
            f"Inspection #{self.inspection_number}"
        )


# ============================================================
# ITEM RESULT
# ============================================================

class ItemResult(models.Model):

    class ResultType(models.TextChoices):
        DONE = "DONE", "Done"
        FAILED = "FAILED", "Failed"

    class DoneCode(models.TextChoices):
        COMPLETED = "1", "Completed"
        COMPLETED_WITH_PUNCH = (
            "2",
            "Completed with Punch List"
        )
        PARTIALLY_COMPLETED = (
            "3",
            "Partially Completed"
        )

    class FailedCode(models.TextChoices):
        ITEM_NOT_READY = (
            "1",
            "Item Not Ready"
        )
        ITEM_NOT_INSPECTABLE = (
            "2",
            "Item Not Inspectable"
        )
        INSPECTION_FAILED = (
            "3",
            "Inspection Failed"
        )
        TIME_CONSTRAINTS = (
            "4",
            "Time Constraints"
        )
        NCR = (
            "5",
            "NCR"
        )

    inspection = models.ForeignKey(
        Inspection,
        on_delete=models.CASCADE,
        related_name="item_results"
    )

    rfi_item = models.ForeignKey(
        RFIItem,
        on_delete=models.CASCADE,
        related_name="inspection_results"
    )

    result_type = models.CharField(
        max_length=10,
        choices=ResultType.choices
    )

    result_code = models.CharField(
        max_length=1
    )

    remarks = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["inspection", "rfi_item"],
                name="unique_item_result_per_inspection"
            )
        ]

    def clean(self):

        if self.result_type == self.ResultType.DONE:

            valid_codes = {
                choice[0]
                for choice in self.DoneCode.choices
            }

        elif self.result_type == self.ResultType.FAILED:

            valid_codes = {
                choice[0]
                for choice in self.FailedCode.choices
            }

        else:
            valid_codes = set()

        if self.result_code not in valid_codes:
            raise ValidationError(
                "Invalid result code for the selected result type."
            )

    def __str__(self):
        return (
            f"{self.rfi_item} - "
            f"{self.result_type} {self.result_code}"
        )


# ============================================================
# RFI RENEWAL
# ============================================================

class RFIRenewal(models.Model):
    rfi = models.ForeignKey(
        RFI,
        on_delete=models.CASCADE,
        related_name="renewals"
    )

    previous_start = models.DateField()
    previous_end = models.DateField()
    new_start = models.DateField()
    new_end = models.DateField()

    renewed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="rfi_renewals"
    )

    renewed_at = models.DateTimeField(
        auto_now_add=True
    )

    reason = models.TextField(
        blank=True
    )

    def __str__(self):
        return (
            f"{self.rfi.internal_reference}: "
            f"{self.previous_start} -> {self.new_start}"
        )


# ============================================================
# PUNCH LIST
# ============================================================


class PunchList(models.Model):

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SIGNED = "SIGNED", "Signed"
        FOLLOW_UP = "FOLLOW_UP", "Follow-up RFI Raised"
        CLOSED = "CLOSED", "Closed"

    rfi = models.ForeignKey(
        RFI,
        on_delete=models.CASCADE,
        related_name="punch_lists",
    )

    inspection = models.ForeignKey(
        Inspection,
        on_delete=models.PROTECT,
        related_name="punch_lists",
    )

    punch_list_number = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
    )

    date_created = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    remarks = models.TextField(blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="punch_lists_created",
        null=True,
        blank=True,
    )

    signed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    closed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-date_created", "-id"]

    def save(self, *args, **kwargs):
        if not self.punch_list_number:
            if self.pk is None:
                super().save(*args, **kwargs)

            if not self.punch_list_number:
                self.punch_list_number = f"PL-{self.pk:06d}"
                update_fields = kwargs.get("update_fields")

                if update_fields is not None:
                    kwargs["update_fields"] = set(update_fields) | {
                        "punch_list_number"
                    }

                super().save(*args, **kwargs)
            return

        super().save(*args, **kwargs)

    def __str__(self):
        return self.punch_list_number or f"Punch List #{self.pk}"


# ============================================================
# PUNCH ITEM
# ============================================================

class PunchItem(models.Model):

    class Category(models.TextChoices):
        A = "A", "Category A - Before MCC"
        B = "B", "Category B - Before RFSU"
        C = "C", "Category C - Before Completion"

    class ActionCode(models.TextChoices):
        CON = "CON", "Construction Contractor"
        EN = "EN", "Engineering"
        V = "V", "Vendor"
        CO = "CO", "Commissioning"
        CPY = "CPY", "Company"
        D = "D", "Others (Specified)"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed - Awaiting Verification"
        VERIFIED = "VERIFIED", "Verified and Closed"

    punch_list = models.ForeignKey(
        PunchList,
        on_delete=models.CASCADE,
        related_name="items"
    )

    item_number = models.PositiveIntegerField()

    item_tag = models.CharField(
        max_length=150,
        blank=True
    )

    description = models.TextField()

    category = models.CharField(
        max_length=1,
        choices=Category.choices
    )

    action_code = models.CharField(
        max_length=3,
        choices=ActionCode.choices,
        blank=True,
        default=""
    )

    action = models.TextField(
        blank=True
    )

    responsible_party = models.CharField(
        max_length=150,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN
    )

    target_date = models.DateField(
        null=True,
        blank=True
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )

    completion_remarks = models.TextField(
        blank=True
    )

    verified_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="punch_items_verified",
        null=True,
        blank=True
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True
    )

    verification_remarks = models.TextField(
        blank=True
    )

    class Meta:
        ordering = ["item_number"]

        constraints = [
            models.UniqueConstraint(
                fields=["punch_list", "item_number"],
                name="unique_punch_item_number"
            )
        ]

    def __str__(self):
        return (
            f"{self.punch_list.punch_list_number} - "
            f"Item {self.item_number}"
        )

# ============================================================
# DOCUMENT
# ============================================================


class Document(models.Model):

    class DocumentType(models.TextChoices):
        ORIGINAL_RFI = (
            "ORIGINAL_RFI",
            "Original RFI"
        )
        SIGNED_RFI = (
            "SIGNED_RFI",
            "Signed RFI"
        )
        PUNCH_LIST = (
            "PUNCH_LIST",
            "Punch List"
        )
        SIGNED_PUNCH_LIST = (
            "SIGNED_PUNCH_LIST",
            "Signed Punch List"
        )
        SUPPORTING = (
            "SUPPORTING",
            "Supporting Document"
        )
        OTHER = (
            "OTHER",
            "Other"
        )

    rfi = models.ForeignKey(
        RFI,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    punch_list = models.ForeignKey(
        "PunchList",
        on_delete=models.CASCADE,
        related_name="uploaded_documents",
        null=True,
        blank=True,
    )

    file = models.FileField(
        upload_to="rfi_documents/%Y/%m/"
    )

    document_type = models.CharField(
        max_length=30,
        choices=DocumentType.choices
    )

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    description = models.CharField(
        max_length=255,
        blank=True
    )

    superseded_by = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="previous_versions",
    )

    replacement_reason = models.TextField(
        blank=True
    )

    def __str__(self):
        return self.file.name

# ============================================================
# RFI HISTORY
# ============================================================

class RFIHistory(models.Model):

    rfi = models.ForeignKey(
        RFI,
        on_delete=models.CASCADE,
        related_name="history"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT
    )

    action = models.CharField(
        max_length=100
    )

    description = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.rfi.rfi_number} - "
            f"{self.action}"
        )

# ============================================================
# RFI UPLOAD / EXTRACTION STAGING
# ============================================================

class RFIUpload(models.Model):

    class Status(models.TextChoices):
        UPLOADED = "UPLOADED", "Uploaded"
        PROCESSING = "PROCESSING", "Processing"
        AWAITING_REVIEW = (
            "AWAITING_REVIEW",
            "Awaiting QC Review"
        )
        CONFIRMED = "CONFIRMED", "Confirmed"
        FAILED = "FAILED", "Extraction Failed"

    file = models.FileField(
        upload_to="rfi_uploads/%Y/%m/"
    )

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="rfi_uploads"
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.UPLOADED
    )

    page_count = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    extracted_text = models.TextField(
        blank=True
    )

    extraction_error = models.TextField(
        blank=True
    )

    def __str__(self):
        return f"Upload #{self.pk} - {self.get_status_display()}"



# ============================================================
# CLIENT SIGNED RFI RECORDS
# ============================================================

class ClientSignedRFI(models.Model):

    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="signed_rfi_records",
    )

    rfi_number = models.CharField(
        max_length=150,
        db_index=True,
    )

    rfi_activity = models.TextField(
        blank=True,
    )

    number_of_items_inspected = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    signed_copy = models.FileField(
        upload_to="client_signed_rfis/%Y/%m/",
        storage=PrivateMediaStorage(),
        blank=True,
        null=True,
    )

    recorded_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.rfi_number} - {self.client.username}"
