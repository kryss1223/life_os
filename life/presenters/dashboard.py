from datetime import timedelta
from decimal import Decimal

from ..models import Task


def weekly_capacity(*, current_week, allocations, areas):
    assigned = sum((item.planned_hours or Decimal("0") for item in allocations), Decimal("0"))
    target = sum((area.weekly_hours_target or Decimal("0") for area in areas), Decimal("0"))
    available = Decimal(str(current_week.available_hours)) if current_week and current_week.available_hours is not None else target
    free = max(Decimal("0"), available - assigned)
    load = min(Decimal("100"), assigned / available * 100) if available > 0 else Decimal("0")
    return assigned, available, free, load


def dashboard_kpis(*, areas, plans, tasks):
    open_tasks = tasks.exclude(status__in=(Task.Status.COMPLETED, Task.Status.CANCELLED))
    active_plans = plans.filter(status="ACTIVE").order_by("-importance_weight", "target_date", "name")
    return {
        "open_tasks": open_tasks,
        "active_plans": active_plans,
        "visible_plans": plans.exclude(status="CANCELLED"),
        "active_tasks_count": open_tasks.count(),
        "total_tasks_count": tasks.exclude(status=Task.Status.CANCELLED).count(),
        "active_plans_count": active_plans.count(),
        "total_plans_count": plans.exclude(status="CANCELLED").count(),
        "life_balance": round(sum(a.current_satisfaction for a in areas) / len(areas)) if areas else 0,
    }


def weekly_focus(active_plans, today):
    plan = active_plans.first()
    actual = remaining = Decimal("0")
    next_deadline = days_remaining = None
    if plan:
        focus_tasks = list(plan.tasks.exclude(status=Task.Status.CANCELLED).order_by("due_date", "name"))
        actual = sum((task.actual_hours or Decimal("0") for task in focus_tasks), Decimal("0"))
        remaining = max(Decimal("0"), (plan.estimated_hours or Decimal("0")) - actual)
        next_deadline = plan.tasks.exclude(
            status__in=(Task.Status.COMPLETED, Task.Status.CANCELLED)
        ).filter(due_date__isnull=False, due_date__gte=today).order_by("due_date").first()
        if next_deadline:
            days_remaining = (next_deadline.due_date - today).days
    return plan, actual, remaining, next_deadline, days_remaining


def upcoming_deadline_rows(open_tasks, today):
    tasks = open_tasks.filter(
        due_date__isnull=False,
        due_date__gte=today,
        due_date__lte=today + timedelta(days=30),
    ).order_by("due_date", "name")[:5]
    rows = []
    for task in tasks:
        days_left = (task.due_date - today).days
        plans = list(task.plans.all())
        if days_left <= 3:
            tone, label = "urgent", "Urgente"
        elif task.status == Task.Status.IN_PROGRESS:
            tone, label = "progress", "En progreso"
        else:
            tone, label = "next", "Próximo"
        rows.append({"task": task, "plan": plans[0] if plans else None, "days_left": days_left, "tone": tone, "label": label})
    return rows


def area_cards(areas):
    rows = []
    for index, area in enumerate(areas[:4]):
        balance = "good" if area.current_satisfaction >= 75 else "medium" if area.current_satisfaction >= 55 else "low"
        rows.append({"area": area, "tone": f"tone-{(index % 5) + 1}", "balance_tone": balance})
    return rows


def recent_activity_items(*, tasks, plans):
    activity = []
    for task in tasks.order_by("-created_at")[:5]:
        task_plans = list(task.plans.all())
        activity.append({"kind": "created", "at": task.created_at, "title": f'Creaste la tarea "{task.name}"', "context": task_plans[0].name if task_plans else "Tarea"})
    for task in tasks.filter(completed_at__isnull=False).order_by("-completed_at")[:5]:
        task_plans = list(task.plans.all())
        activity.append({"kind": "completed", "at": task.completed_at, "title": f'Completaste "{task.name}"', "context": task_plans[0].name if task_plans else "Tarea"})
    for plan in plans.order_by("-created_at")[:5]:
        activity.append({"kind": "plan", "at": plan.created_at, "title": f'Creaste el plan "{plan.name}"', "context": plan.life_area.name})
    return sorted(activity, key=lambda item: item["at"], reverse=True)[:5]
