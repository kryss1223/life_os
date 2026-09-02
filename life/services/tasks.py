from django.db import transaction

from ..models import Plan, Task


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


def create_subtask(*, parent, user, name, estimated_hours="0", due_date=None):
    name = (name or "").strip()
    if not name:
        return None
    subtask = Task(
        user=user,
        parent=parent,
        name=name,
        estimated_hours=estimated_hours or 0,
        due_date=due_date or None,
    )
    subtask.full_clean()
    subtask.save()
    return subtask


def toggle_subtask(subtask):
    subtask.status = (
        Task.Status.PENDING
        if subtask.status == Task.Status.COMPLETED
        else Task.Status.COMPLETED
    )
    subtask.save(update_fields=["status"])
    return subtask


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
