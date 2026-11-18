from django.db import migrations


def dedupe_models(apps, schema_editor):
    """Keep one row per name+version (prefer active, then best val accuracy, then newest)."""
    MLModel = apps.get_model("registry", "MLModel")
    seen = {}
    for m in MLModel.objects.all().order_by("id"):
        key = (m.name, m.version)
        if key not in seen:
            seen[key] = m
            continue
        keep = seen[key]
        challenger = m
        keep_score = (keep.is_active, keep.val_accuracy if keep.val_accuracy is not None else -1.0, keep.id)
        challenger_score = (
            challenger.is_active,
            challenger.val_accuracy if challenger.val_accuracy is not None else -1.0,
            challenger.id,
        )
        if challenger_score > keep_score:
            keep.delete()
            seen[key] = challenger
        else:
            challenger.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("registry", "0003_selectionsetting"),
    ]

    operations = [
        migrations.RunPython(dedupe_models, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name="mlmodel",
            unique_together={("name", "version")},
        ),
    ]
