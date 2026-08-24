from datetime import date
from decimal import Decimal


def calculate_task_weekly_load(task, today=None):
    today = today or date.today()

    if not task.due_date:
        return None

    estimated_hours = task.estimated_hours or Decimal("0")

    if estimated_hours <= 0:
        return None

    remaining_hours = estimated_hours

    days_remaining = (task.due_date - today).days

    if days_remaining < 0:
        return {
            "task": task,
            "remaining_hours": remaining_hours,
            "weeks_remaining": 0,
            "weekly_hours_needed": remaining_hours,
            "overdue": True,
        }

    weeks_remaining = max(
        1,
        (days_remaining + 6) // 7,
    )

    weekly_hours_needed = (
        remaining_hours / Decimal(weeks_remaining)
    )
    urgency, urgency_label = classify_urgency(days_remaining)

    return {
        "task": task,
        "remaining_hours": remaining_hours,
        "weeks_remaining": weeks_remaining,
        "weekly_hours_needed": weekly_hours_needed,
        "urgency": urgency,
        "urgency_label": urgency_label,
        "overdue": False,
    }


# IMPORTANTE: NO dentro de la función anterior
def build_weekly_plan(tasks, available_hours):
    available_hours = Decimal(str(available_hours))

    task_loads = []
    task_loads.sort(
    key=lambda item: (
        item["task"].due_date,
        item["task"].name.lower(),
    )
)

    for task in tasks:
        load = calculate_task_weekly_load(task)

        if load is not None:
            task_loads.append(load)

    total_needed = sum(
        (
            item["weekly_hours_needed"]
            for item in task_loads
        ),
        Decimal("0"),
    )

    for item in task_loads:
        if available_hours > 0:
            item["capacity_percent"] = (
                item["weekly_hours_needed"]
                / available_hours
                * Decimal("100")
            )
        else:
            item["capacity_percent"] = Decimal("0")

    remaining_capacity = available_hours - total_needed

    return {
        "tasks": task_loads,
        "available_hours": available_hours,
        "total_needed": total_needed,
        "remaining_capacity": remaining_capacity,
        "overloaded": total_needed > available_hours,
    }


def classify_urgency(days_remaining):
    if days_remaining <= 7:
        return "urgent", "Urgente"

    if days_remaining <= 28:
        return "upcoming", "Próximo"

    return "long_term", "Largo plazo"