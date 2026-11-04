from django.db import migrations, models


def copy_planning_dates(apps, schema_editor):
    RFI = apps.get_model("rfi_management", "RFI")
    RFIRenewal = apps.get_model("rfi_management", "RFIRenewal")

    # --------------------------------------------------------
    # RFI planning dates
    # --------------------------------------------------------
    for rfi in RFI.objects.all():
        if rfi.original_planned_date:
            rfi.original_planned_start = rfi.original_planned_date
            rfi.original_planned_end = rfi.original_planned_date

        if rfi.current_planned_date:
            rfi.current_planned_start = rfi.current_planned_date
            rfi.current_planned_end = rfi.current_planned_date

        rfi.save(
            update_fields=[
                "original_planned_start",
                "original_planned_end",
                "current_planned_start",
                "current_planned_end",
            ]
        )

    # --------------------------------------------------------
    # RFI renewal dates
    # --------------------------------------------------------
    for renewal in RFIRenewal.objects.all():
        if renewal.previous_date:
            renewal.previous_start = renewal.previous_date
            renewal.previous_end = renewal.previous_date

        if renewal.new_date:
            renewal.new_start = renewal.new_date
            renewal.new_end = renewal.new_date

        renewal.save(
            update_fields=[
                "previous_start",
                "previous_end",
                "new_start",
                "new_end",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("rfi_management", "0002_rfiupload"),
    ]

    operations = [
        # ----------------------------------------------------
        # Add new fields first
        # ----------------------------------------------------
        migrations.AddField(
            model_name="rfi",
            name="current_planned_end",
            field=models.DateField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="rfi",
            name="current_planned_start",
            field=models.DateField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="rfi",
            name="original_planned_end",
            field=models.DateField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="rfi",
            name="original_planned_start",
            field=models.DateField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="rfirenewal",
            name="new_end",
            field=models.DateField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="rfirenewal",
            name="new_start",
            field=models.DateField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="rfirenewal",
            name="previous_end",
            field=models.DateField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="rfirenewal",
            name="previous_start",
            field=models.DateField(
                blank=True,
                null=True,
            ),
        ),

        # ----------------------------------------------------
        # Copy existing dates before removing old fields
        # ----------------------------------------------------
        migrations.RunPython(
            copy_planning_dates,
            migrations.RunPython.noop,
        ),

        # ----------------------------------------------------
        # Remove old fields
        # ----------------------------------------------------
        migrations.RemoveField(
            model_name="rfi",
            name="current_planned_date",
        ),
        migrations.RemoveField(
            model_name="rfi",
            name="original_planned_date",
        ),
        migrations.RemoveField(
            model_name="rfirenewal",
            name="new_date",
        ),
        migrations.RemoveField(
            model_name="rfirenewal",
            name="previous_date",
        ),

        # ----------------------------------------------------
        # Update RFI status choices
        # ----------------------------------------------------
        migrations.AlterField(
            model_name="rfi",
            name="status",
            field=models.CharField(
                choices=[
                    ("RECEIVED", "Received"),
                    ("UNASSIGNED", "Unassigned"),
                    ("ASSIGNED", "Assigned"),
                    ("SCHEDULED", "Scheduled"),
                    ("OVERDUE", "Overdue"),
                    ("UNDER_INSPECTION", "Under Inspection"),
                    ("AWAITING_PUNCH", "Awaiting Punch List"),
                    ("FOLLOW_UP", "Follow-up Required"),
                    ("RETURNED", "Returned to Construction"),
                    ("REJECTED", "Rejected"),
                    ("CLOSED", "Closed"),
                ],
                default="RECEIVED",
                max_length=30,
            ),
        ),
    ]