from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from ..models import WeeklyTaskAllocation
from .weekly_planner import classify_urgency

from ..selectors.planning import eligible_planner_tasks
from .allocations import save_optimized_schedule
from .weekly_planner import build_weekly_plan


@dataclass(frozen=True)
class PlanningSubmission:
    result: dict
    saved: bool


def _selected_ids(data, action):
    if action not in {"update_plan", "save"} and not data.get("selection_present"):
        return None
    raw_values = data.getlist("selected_tasks") if hasattr(data, "getlist") else data.get("selected_tasks", [])
    selected = set()
    for value in raw_values:
        try:
            selected.add(int(value))
        except (TypeError, ValueError):
            continue
    return selected


@transaction.atomic
def process_planning_submission(*, user, data, cleaned_data, week_start):
    action = data.get("action", "calculate")
    available_hours = cleaned_data["available_hours"]
    include_saturday = cleaned_data["include_saturday"]
    include_sunday = cleaned_data["include_sunday"]
    tasks = list(eligible_planner_tasks(user))
    selected_ids = _selected_ids(data, action)
    if week_start + timedelta(days=6) < timezone.localdate():
        raise ValueError("No puedes regenerar una semana pasada.")
    reserved = list(WeeklyTaskAllocation.objects.select_related("task").prefetch_related("task__plans__life_area").filter(week__user=user, week__week_start=week_start).filter(Q(is_locked=True) | Q(planned_date__lt=timezone.localdate())))
    plan_filter, urgency_filter = data.get("plan_filter", ""), data.get("urgency_filter", "")
    if plan_filter or urgency_filter:
        candidates = {t.pk for t in tasks if (not plan_filter or any(str(p.pk) == plan_filter for p in t.plans.all())) and (not urgency_filter or classify_urgency((t.due_date - max(timezone.localdate(), week_start)).days)[0] == urgency_filter)}
        selected_ids = candidates if selected_ids is None else selected_ids & candidates

    if action in {"update_plan", "save"}:
        for task in tasks:
            raw_hours = str(data.get(f"actual_add_{task.pk}", "")).strip()
            if not raw_hours:
                continue
            try:
                added_hours = Decimal(raw_hours)
            except InvalidOperation:
                continue
            if added_hours > 0:
                task.actual_hours = Decimal(str(task.actual_hours or 0)) + added_hours
                task.save(update_fields=["actual_hours"])

    result = build_weekly_plan(
        tasks,
        available_hours,
        include_saturday=include_saturday,
        include_sunday=include_sunday,
        selected_task_ids=selected_ids,
        planning_week_start=week_start,
        reserved_allocations=reserved,
        today=timezone.localdate(),
    )
    saved = action == "save"
    if saved:
        save_optimized_schedule(
            user=user,
            week_start=week_start,
            available_hours=available_hours,
            schedule=result["schedule"],
            preserve_past=True,
            include_saturday=include_saturday,
            include_sunday=include_sunday,
        )
    return PlanningSubmission(result=result, saved=saved)
