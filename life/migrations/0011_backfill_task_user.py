from django.db import migrations


def backfill_unambiguous_task_users(apps, schema_editor):
    Task = apps.get_model("life", "Task")
    for task in Task.objects.filter(user__isnull=True).iterator():
        user_ids = list(
            task.impacts.values_list("plan__life_area__user_id", flat=True)
            .distinct()[:2]
        )
        if len(user_ids) == 1:
            Task.objects.filter(pk=task.pk).update(user_id=user_ids[0])


def clear_task_users(apps, schema_editor):
    apps.get_model("life", "Task").objects.update(user=None)


class Migration(migrations.Migration):
    dependencies = [("life", "0010_task_user_nullable")]
    operations = [
        migrations.RunPython(
            backfill_unambiguous_task_users,
            reverse_code=clear_task_users,
        )
    ]
