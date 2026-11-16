from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classifier", "0002_classification_selection_mode_classification_votes_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="classification",
            name="latitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="classification",
            name="location_text",
            field=models.CharField(blank=True, help_text="Place description", max_length=255),
        ),
        migrations.AddField(
            model_name="classification",
            name="longitude",
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="classification",
            name="notes",
            field=models.TextField(blank=True, help_text="Reporter notes / what happened"),
        ),
        migrations.AddField(
            model_name="classification",
            name="source",
            field=models.CharField(
                blank=True,
                default="web",
                help_text="web or mobile — where the report was submitted",
                max_length=10,
            ),
        ),
    ]
