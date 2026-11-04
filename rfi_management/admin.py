from django.contrib import admin

from .models import (
    UserProfile,
    RFI,
    RFIItem,
    Assignment,
    Inspection,
    ItemResult,
    RFIRenewal,
    PunchList,
    PunchItem,
    Document,
    RFIHistory,
    RFIUpload,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "is_active_qc",
    )

    list_filter = (
        "role",
        "is_active_qc",
    )

    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
    )


@admin.register(RFI)
class RFIAdmin(admin.ModelAdmin):

    list_display = (
        "rfi_number",
        "contractor",
        "discipline",
        "original_planned_start",
        "original_planned_end",
        "current_planned_start",
        "current_planned_end",
        "status",
        "overall_result",
        "created_at",
    )

    list_filter = (
        "status",
        "overall_result",
        "discipline",
        "contractor",
    )

    search_fields = (
        "rfi_number",
        "internal_reference",
        "inspection_activity",
        "area",
        "iwp_code",
    )

    date_hierarchy = "created_at"

    readonly_fields = (
        "internal_reference",
        "created_at",
        "updated_at",
    )


@admin.register(RFIItem)
class RFIItemAdmin(admin.ModelAdmin):

    list_display = (
        "rfi",
        "item_number",
        "item_code",
        "area",
        "manually_verified",
    )

    list_filter = (
        "manually_verified",
    )

    search_fields = (
        "rfi__rfi_number",
        "item_code",
        "description",
        "area",
    )


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):

    list_display = (
        "rfi",
        "inspector",
        "assigned_by",
        "assigned_at",
        "unassigned_at",
    )

    list_filter = (
        "inspector",
        "assigned_by",
    )

    search_fields = (
        "rfi__rfi_number",
        "inspector__username",
    )


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):

    list_display = (
        "rfi",
        "inspection_number",
        "inspector",
        "inspection_date",
        "overall_result",
    )

    list_filter = (
        "overall_result",
        "inspector",
    )

    search_fields = (
        "rfi__rfi_number",
        "inspector__username",
    )


@admin.register(ItemResult)
class ItemResultAdmin(admin.ModelAdmin):

    list_display = (
        "inspection",
        "rfi_item",
        "result_type",
        "result_code",
        "created_at",
    )

    list_filter = (
        "result_type",
        "result_code",
    )

    search_fields = (
        "inspection__rfi__rfi_number",
        "rfi_item__item_code",
        "rfi_item__description",
    )


@admin.register(RFIRenewal)
class RFIRenewalAdmin(admin.ModelAdmin):

    list_display = (
        "rfi",
        "previous_start",
        "previous_end",
        "new_start",
        "new_end",
        "renewed_by",
        "renewed_at",
    )

    list_filter = (
        "renewed_by",
    )

    search_fields = (
        "rfi__rfi_number",
    )


class PunchItemInline(admin.TabularInline):
    model = PunchItem
    extra = 0


@admin.register(PunchList)
class PunchListAdmin(admin.ModelAdmin):
    list_display = (
        "punch_list_number",
        "rfi",
        "inspection",
        "date_created",
        "status",
    )

    list_filter = ("status", "date_created")
    search_fields = (
        "punch_list_number",
        "rfi__rfi_number",
        "rfi__internal_reference",
    )

    inlines = [PunchItemInline]


@admin.register(PunchItem)
class PunchItemAdmin(admin.ModelAdmin):
    list_display = (
        "punch_list",
        "item_number",
        "item_tag",
        "category",
        "status",
        "responsible_party",
        "target_date",
    )

    list_filter = ("category", "status")
    search_fields = (
        "item_tag",
        "description",
        "punch_list__punch_list_number",
    )

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):

    list_display = (
        "rfi",
        "document_type",
        "uploaded_by",
        "uploaded_at",
    )

    list_filter = (
        "document_type",
    )

    search_fields = (
        "rfi__rfi_number",
        "description",
    )


@admin.register(RFIHistory)
class RFIHistoryAdmin(admin.ModelAdmin):

    list_display = (
        "rfi",
        "action",
        "user",
        "created_at",
    )

    list_filter = (
        "action",
        "user",
    )

    search_fields = (
        "rfi__rfi_number",
        "action",
        "description",
    )

    readonly_fields = (
        "created_at",
    )

@admin.register(RFIUpload)
class RFIUploadAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "file",
        "uploaded_by",
        "uploaded_at",
        "status",
        "page_count",
    )

    list_filter = (
        "status",
        "uploaded_at",
    )

    search_fields = (
        "file",
        "uploaded_by__username",
    )

    readonly_fields = (
        "uploaded_at",
        "page_count",
        "extracted_text",
        "extraction_error",
    )