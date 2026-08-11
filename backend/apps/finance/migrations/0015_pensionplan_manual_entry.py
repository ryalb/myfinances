import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_user_from_connection(apps, schema_editor):
    # `.update(user=F("connection__user"))` nao e permitido: F() com lookup entre
    # tabelas estoura "Joined field references are not permitted" em update().
    PensionPlan = apps.get_model("finance", "PensionPlan")
    orphaned = PensionPlan.objects.filter(
        user__isnull=True, connection__isnull=False
    ).select_related("connection")
    for plan in orphaned:
        plan.user_id = plan.connection.user_id
    PensionPlan.objects.bulk_update(orphaned, ["user"])


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0014_account_number"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="pensionplan",
            name="external_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="pensionplan",
            name="user",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pension_plans",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_user_from_connection, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pensionplan",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pension_plans",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="pensionplan",
            name="connection",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="pension_plans",
                to="finance.connection",
            ),
        ),
    ]
