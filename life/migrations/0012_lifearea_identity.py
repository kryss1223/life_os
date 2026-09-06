from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("life", "0011_backfill_task_user")]

    operations = [
        migrations.AddField(
            model_name="lifearea",
            name="icon_key",
            field=models.CharField(
                choices=[("heart", "Corazón"), ("target", "Objetivo"), ("briefcase", "Trabajo"), ("book-open", "Estudios"), ("music", "Música"), ("star", "Estrella")],
                default="heart",
                max_length=24,
            ),
        ),
        migrations.AddField(
            model_name="lifearea",
            name="color_key",
            field=models.CharField(
                choices=[("green", "Verde"), ("blue", "Azul"), ("purple", "Morado"), ("orange", "Naranja"), ("pink", "Rosa")],
                default="green",
                max_length=16,
            ),
        ),
    ]
