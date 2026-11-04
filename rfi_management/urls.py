from django.urls import path

from .views import (
    dashboard_view,
    login_view,
    logout_view,
    rfi_create_view,
    rfi_detail_view,
    rfi_list_view,
    user_create_view,
    user_edit_view,
    user_list_view,
    user_password_view,
    rfi_assign_view,
    inspector_rfi_list_view,
    start_inspection_view,
    inspection_detail_view,
    punch_list_detail_view,
    punch_list_create_view,
    punch_item_create_view,
    rfi_reassign_view,
    rfi_delete_view,
    punch_list_signed_upload_view,
    rfi_renew_period_view,
    rfi_return_to_supervisor_view,
)

urlpatterns = [
    path("", login_view, name="login"),
    path("login/", login_view, name="login"),

    path(
        "dashboard/",
        dashboard_view,
        name="dashboard",
    ),

    path(
    "rfis/",
    rfi_list_view,
    name="rfi_list",
    ),

    path(
        "rfis/create/",
        rfi_create_view,
        name="rfi_create",
    ),

    path(
    "rfis/<int:rfi_id>/start-inspection/",
    start_inspection_view,
    name="start_inspection",
    ),

    path(
    "inspections/<int:inspection_id>/",
    inspection_detail_view,
    name="inspection_detail",
    ),

    path(
        "rfis/<int:rfi_id>/",
        rfi_detail_view,
        name="rfi_detail",
    ),

    path(
        "users/",
        user_list_view,
        name="user_list",
    ),

    path(
        "my-rfis/",
        inspector_rfi_list_view,
        name="inspector_rfi_list",
        ),

    path(
        "users/create/",
        user_create_view,
        name="user_create",
    ),

    path(
        "users/<int:user_id>/edit/",
        user_edit_view,
        name="user_edit",
    ),

    path(
        "users/<int:user_id>/password/",
        user_password_view,
        name="user_password",
    ),

    path(
        "logout/",
        logout_view,
        name="logout",
    ),

    path(
        "rfis/<int:rfi_id>/assign/",
        rfi_assign_view,
        name="rfi_assign",
        ),

    path(
        "inspections/<int:inspection_id>/punch-list/create/",
        punch_list_create_view,
        name="punch_list_create",
    ),

    path(
        "punch-lists/<int:punch_list_id>/",
        punch_list_detail_view,
        name="punch_list_detail",
    ),

    path(
        "punch-lists/<int:punch_list_id>/items/add/",
        punch_item_create_view,
        name="punch_item_create",
    ),

    path(
    "rfis/<int:rfi_id>/reassign/",
    rfi_reassign_view,
    name="rfi_reassign",
    ),

    path(
        "rfis/<int:rfi_id>/delete/",
        rfi_delete_view,
        name="rfi_delete",
    ),
       
    path(
        "punch-lists/<int:punch_list_id>/upload-signed/",
        punch_list_signed_upload_view,
        name="punch_list_signed_upload",
    ),

    path(
        "rfis/<int:rfi_id>/renew-period/",
        rfi_renew_period_view,
        name="rfi_renew_period",
    ),

    path(
        "rfis/<int:rfi_id>/return-to-supervisor/",
        rfi_return_to_supervisor_view,
        name="rfi_return_to_supervisor",
    ),
]