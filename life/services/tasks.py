from django.db import transaction

from ..models import Plan


def add_actual_hours(task, raw_hours):
    from decimal import Decimal, InvalidOperation

    try:
        hours = Decimal(raw_hours or "0")
    except InvalidOperation:
        return task
    if hours > 0:
        task.actual_hours = Decimal(str(task.actual_hours or 0)) + hours
        task.save(update_fields=["actual_hours"])
    return task


@transaction.atomic
def save_task_with_impacts(*, form, formset, old_plan_ids=()):
    task = form.save()
    formset.instance = task
    formset.save()

    new_plan_ids = task.impacts.values_list("plan_id", flat=True)
    affected_ids = set(old_plan_ids) | set(new_plan_ids)
    for plan in Plan.objects.filter(id__in=affected_ids):
        plan.recalculate_progress()
    return task


@transaction.atomic
def delete_task(task):
    plans = list(Plan.objects.filter(task_impacts__task=task).distinct())
    task.delete()
    for plan in plans:
        plan.recalculate_progress()
