from django.db import migrations, models


def set_existing_inspection_start_times(apps, schema_editor):
    Inspection = apps.get_model("rfi_management", "Inspection")

    Inspection.objects.filter(
        start_time__isnull=True
    ).update(
        start_time="00:00:00"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("rfi_management", "0005_assignment_unique_active_rfi_assignment"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="inspection",
            name="end_time",
        ),

        migrations.RunPython(
            set_existing_inspection_start_times,
            migrations.RunPython.noop,
        ),

        migrations.AlterField(
            model_name="inspection",
            name="start_time",
            field=models.TimeField(),
        ),
    ]