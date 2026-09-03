from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction

from ..selectors.planning import eligible_planner_tasks
from .allocations import save_optimized_schedule
from .weekly_planner import build_weekly_plan


@dataclass(frozen=True)
class PlanningSubmission:
    result: dict
    saved: bool


def _selected_ids(data, action):
    if action not in {"update_plan", "save"}:
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
    include_saturday = not cleaned_data["exclude_saturday"]
    include_sunday = not cleaned_data["exclude_sunday"]
    tasks = list(eligible_planner_tasks(user))
    selected_ids = _selected_ids(data, action)

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
    )
    saved = action == "save"
    if saved:
        save_optimized_schedule(
            user=user,
            week_start=week_start,
            available_hours=available_hours,
            schedule=result["schedule"],
        )
    return PlanningSubmission(result=result, saved=saved)
