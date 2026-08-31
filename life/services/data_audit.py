from django.db.models import Count

from ..models import Task, TaskImpact, Week


def audit_model_data():
    duplicate_weeks = list(
        Week.objects.values("user_id", "week_start")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )
    duplicate_impacts = list(
        TaskImpact.objects.values("task_id", "plan_id")
        .annotate(count=Count("id"))
        .filter(count__gt=1)
    )
    owner_conflicts = []
    ownerless_tasks = []
    for task in Task.objects.prefetch_related("plans__life_area").iterator(
        chunk_size=500
    ):
        inferred = {plan.life_area.user_id for plan in task.plans.all()}
        if len(inferred) > 1 or (task.user_id and inferred and inferred != {task.user_id}):
            owner_conflicts.append(task.pk)
        elif task.user_id is None:
            ownerless_tasks.append(task.pk)

    cycles = []
    parent_by_id = dict(Task.objects.values_list("id", "parent_id"))
    for task_id in parent_by_id:
        seen = set()
        current = task_id
        while current is not None and current not in seen:
            seen.add(current)
            current = parent_by_id.get(current)
        if current is not None:
            cycles.append(task_id)

    return {
        "duplicate_weeks": duplicate_weeks,
        "duplicate_impacts": duplicate_impacts,
        "owner_conflicts": sorted(set(owner_conflicts)),
        "ownerless_tasks": sorted(set(ownerless_tasks)),
        "task_cycles": sorted(set(cycles)),
    }
