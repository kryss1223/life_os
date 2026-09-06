from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("life", "0012_lifearea_identity")]
    operations = [
        migrations.AddField(model_name="weeklytaskallocation", name="is_locked", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="week", name="include_saturday", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="week", name="include_sunday", field=models.BooleanField(default=False)),
    ]
