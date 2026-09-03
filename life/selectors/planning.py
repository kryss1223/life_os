from ..models import Task, Week, WeeklyTaskAllocation


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


def tasks_for_year(*, user, year):
    return Task.objects.filter(
        plans__life_area__user=user,
        due_date__year=year,
    ).distinct()


def upcoming_deadlines(*, user, start, end):
    return (
        Task.objects.filter(
            plans__life_area__user=user,
            due_date__gte=start,
            due_date__lte=end,
        )
        .exclude(status__in=(Task.Status.COMPLETED, Task.Status.CANCELLED))
        .prefetch_related("plans", "plans__life_area")
        .order_by("due_date")
        .distinct()
    )


def saved_week_plan(*, user, week_start):
    week = Week.objects.filter(user=user, week_start=week_start).first()
    if not week:
        return None, []
    allocations = list(
        WeeklyTaskAllocation.objects.filter(week=week, planned_date__isnull=False)
        .select_related("task")
        .prefetch_related("task__plans__life_area")
        .order_by("planned_date", "task__due_date")
    )
    return week, allocations
