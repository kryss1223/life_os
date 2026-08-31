from ..models import Task


def eligible_planner_tasks(user):
    """Tareas abiertas y fechadas que pueden entrar en una propuesta automática."""
    return (
        Task.objects.filter(
            plans__life_area__user=user,
            due_date__isnull=False,
        )
        .exclude(status__in=(Task.Status.COMPLETED, Task.Status.CANCELLED))
        .distinct()
        .order_by("due_date", "name")
    )


def available_calendar_tasks(user):
    return (
        Task.objects.filter(plans__life_area__user=user)
        .exclude(status__in=(Task.Status.COMPLETED, Task.Status.CANCELLED))
        .prefetch_related("plans", "plans__life_area")
        .distinct()
        .order_by("due_date", "name")
    )
