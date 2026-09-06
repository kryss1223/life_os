from ..models import LifeArea, Plan, Task, Week, WeeklyTaskAllocation


def dashboard_entities(user):
    areas = list(
        LifeArea.objects.filter(user=user)
        .prefetch_related("plans")
        .order_by("-importance_weight", "name")
    )
    plans = Plan.objects.filter(life_area__user=user).select_related("life_area")
    tasks = (
        Task.objects.filter(plans__life_area__user=user)
        .prefetch_related(
            "plans",
            "plans__life_area",
            "impacts",
            "impacts__plan",
            "impacts__plan__life_area",
        )
        .distinct()
    )
    return areas, plans, tasks


def current_week_with_allocations(*, user, week_start):
    week = Week.objects.filter(user=user, week_start=week_start).first()
    if not week:
        return None, []
    allocations = list(
        WeeklyTaskAllocation.objects.filter(week=week, planned_date__isnull=False)
        .select_related("task")
        .prefetch_related(
            "task__plans",
            "task__plans__life_area",
            "task__impacts",
            "task__impacts__plan",
            "task__impacts__plan__life_area",
        )
        .order_by("planned_date", "task__due_date", "task__name")
    )
    return week, allocations
