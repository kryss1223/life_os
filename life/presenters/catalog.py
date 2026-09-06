from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q

from ..models import Plan, Task
from ..selectors.plans import plan_for_user, plans_for_user
from ..selectors.tasks import task_for_user, tasks_for_user
from ..models import WeeklyTracking


def _task_progress(task):
    estimated = Decimal(str(task.estimated_hours or 0))
    actual = Decimal(str(task.actual_hours or 0))
    progress = min(Decimal("100"), actual / estimated * 100) if estimated > 0 else Decimal("0")
    if task.status == Task.Status.COMPLETED:
        progress = Decimal("100")
    return progress


def _task_flags(task, today):
    open_status = task.status not in (Task.Status.COMPLETED, Task.Status.CANCELLED)
    return {
        "is_overdue": bool(task.due_date and task.due_date < today and open_status),
        "is_urgent": bool(task.due_date and task.due_date <= today + timedelta(days=3) and open_status),
    }


def plan_list_context(*, user, current_filter="all", current_sort="importance"):
    base = plans_for_user(user).select_related("life_area")
    counts = {
        "total_plans": base.count(),
        "active_plans": base.filter(status=Plan.Status.ACTIVE).count(),
        "completed_plans": base.filter(status=Plan.Status.COMPLETED).count(),
        "paused_plans": base.filter(status=Plan.Status.PAUSED).count(),
    }
    status_filters = {
        "active": Plan.Status.ACTIVE,
        "paused": Plan.Status.PAUSED,
        "completed": Plan.Status.COMPLETED,
    }
    plans = base.filter(status=status_filters[current_filter]) if current_filter in status_filters else base
    ordering = {
        "progress": ("-progress", "-importance_weight"),
        "target": ("target_date", "-importance_weight"),
        "recent": ("-created_at",),
    }.get(current_sort, ("-importance_weight", "-created_at"))
    plans = list(plans.order_by(*ordering).prefetch_related("tasks"))
    rows = []
    for plan in plans:
        tasks = list(plan.tasks.all())
        rows.append({
            "plan": plan,
            "total_tasks": len(tasks),
            "completed_tasks": sum(t.status == Task.Status.COMPLETED for t in tasks),
            "actual_hours": sum((t.actual_hours or Decimal("0") for t in tasks), Decimal("0")),
        })
    recent = WeeklyTracking.objects.filter(plan__life_area__user=user).select_related(
        "plan", "week"
    ).order_by("-week__week_start")[:6]
    return {
        "plan_rows": rows,
        **counts,
        "current_filter": current_filter,
        "current_sort": current_sort,
        "recent_tracking": recent,
    }


def plan_detail_context(*, user, pk, today=None):
    today = today or date.today()
    plan = plan_for_user(user=user, pk=pk)
    tasks = plan.tasks.all().distinct().prefetch_related(
        "impacts", "plans", "plans__life_area"
    ).order_by("status", "due_date", "name")
    task_list = list(tasks)
    total_actual = sum((t.actual_hours or Decimal("0") for t in task_list), Decimal("0"))
    rows = []
    for task in task_list:
        impact = next((i for i in task.impacts.all() if i.plan_id == plan.pk), None)
        flags = _task_flags(task, today)
        rows.append({
            "task": task,
            "progress_percent": round(float(_task_progress(task))),
            **flags,
            "impact": impact.impact_percent if impact else Decimal("0"),
            "remaining_hours": max(Decimal("0"), (task.estimated_hours or 0) - (task.actual_hours or 0)),
        })
    return {
        "plan": plan,
        "tasks": tasks,
        "task_rows": rows,
        "tracking": plan.weekly_tracking.select_related("week").order_by("-week__week_start"),
        "total_tasks": len(task_list),
        "completed_tasks": sum(t.status == Task.Status.COMPLETED for t in task_list),
        "total_actual_hours": total_actual,
        "remaining_hours": max(Decimal("0"), (plan.estimated_hours or 0) - total_actual),
        "days_remaining": (plan.target_date - today).days if plan.target_date else None,
    }


def task_list_context(*, user, current_filter="all", current_sort="recent", search_query="", plan_filter="", parent_filter="", current_group="tasks", today=None):
    today = today or date.today()
    base = tasks_for_user(user).select_related("parent").prefetch_related("plans", "plans__life_area", "subtasks")
    primary_base = base.filter(parent__isnull=True)
    counts = {
        "total_tasks": primary_base.count(),
        "in_progress_tasks": primary_base.filter(status=Task.Status.IN_PROGRESS).count(),
        "completed_tasks": primary_base.filter(status=Task.Status.COMPLETED).count(),
        "pending_tasks": primary_base.filter(status=Task.Status.PENDING).count(),
        "urgent_tasks": primary_base.exclude(status__in=(Task.Status.COMPLETED, Task.Status.CANCELLED)).filter(
            due_date__isnull=False, due_date__lte=today + timedelta(days=3)
        ).count(),
    }
    current_group = current_group if current_group in {"tasks", "plans"} else "tasks"
    current_filter = current_filter if current_filter in {"all", "today", "week", "completed", "subtasks"} else "all"
    is_subtasks = current_filter == "subtasks"
    tasks = base.filter(parent__isnull=False) if is_subtasks else primary_base
    available_plans = plans_for_user(user).select_related("life_area").order_by("life_area__name", "name")
    parent_tasks = primary_base.filter(subtasks__isnull=False).distinct().order_by("name")

    try:
        plan_id = int(plan_filter)
    except (TypeError, ValueError):
        plan_id = None
    if plan_id and available_plans.filter(pk=plan_id).exists():
        if is_subtasks:
            tasks = tasks.filter(Q(plans__pk=plan_id) | Q(parent__plans__pk=plan_id))
        else:
            tasks = tasks.filter(plans__pk=plan_id)
    else:
        plan_id = None

    try:
        parent_id = int(parent_filter)
    except (TypeError, ValueError):
        parent_id = None
    if is_subtasks and parent_id and parent_tasks.filter(pk=parent_id).exists():
        tasks = tasks.filter(parent_id=parent_id)
    else:
        parent_id = None
    search_query = (search_query or "").strip()
    if search_query:
        tasks = tasks.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))
    if current_filter == "today":
        tasks = tasks.filter(due_date=today)
    elif current_filter == "week":
        tasks = tasks.filter(due_date__gte=today, due_date__lte=today + timedelta(days=6 - today.weekday()))
    elif current_filter == "completed":
        tasks = tasks.filter(status=Task.Status.COMPLETED)
    ordering = {"deadline": ("due_date", "name"), "name": ("name",)}.get(current_sort, ("-created_at",))
    rows = []
    for task in tasks.distinct().order_by(*ordering):
        subtasks = list(task.subtasks.all())
        plans = list(task.plans.all())
        rows.append({
            "task": task,
            "progress_percent": round(float(_task_progress(task))),
            "plans": plans,
            "primary_plan": plans[0] if plans else None,
            "total_subtasks": len(subtasks),
            "completed_subtasks": sum(subtask.status == Task.Status.COMPLETED for subtask in subtasks),
            **_task_flags(task, today),
        })
    return {
        "task_rows": rows,
        **counts,
        "current_filter": current_filter,
        "current_sort": current_sort,
        "search_query": search_query,
        "available_plans": available_plans,
        "parent_tasks": parent_tasks,
        "current_plan_id": plan_id,
        "current_parent_id": parent_id,
        "current_group": current_group,
        "is_subtasks": is_subtasks,
    }


def task_detail_context(*, user, pk, today=None):
    today = today or date.today()
    task = task_for_user(user=user, pk=pk)
    impacts = task.impacts.select_related("plan", "plan__life_area").order_by("-impact_percent")
    subtasks = task.subtasks.order_by("status", "due_date")
    estimated = Decimal(str(task.estimated_hours or 0))
    actual = Decimal(str(task.actual_hours or 0))
    progress = _task_progress(task)
    return {
        "task": task,
        "impacts": impacts,
        "subtasks": subtasks,
        "estimated_hours": estimated,
        "actual_hours": actual,
        "remaining_hours": max(Decimal("0"), estimated - actual),
        "progress_percent": progress,
        "remaining_percent": max(Decimal("0"), Decimal("100") - progress),
        "days_remaining": (task.due_date - today).days if task.due_date else None,
        "total_subtasks": subtasks.count(),
        "completed_subtasks": subtasks.filter(status=Task.Status.COMPLETED).count(),
    }
