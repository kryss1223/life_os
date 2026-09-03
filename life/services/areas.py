from django.db import transaction

from ..models import Task


@transaction.atomic
def delete_area(area):
    """Elimina un área y las tareas que hayan quedado sin ningún plan."""
    affected_task_ids = list(
        Task.objects.filter(plans__life_area=area)
        .values_list("id", flat=True)
        .distinct()
    )
    area.delete()
    Task.objects.filter(id__in=affected_task_ids, plans__isnull=True).delete()
