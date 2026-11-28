from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("models", "0002_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="printmodel",
            name="draft_id",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="printmodel",
            name="validation_result",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
