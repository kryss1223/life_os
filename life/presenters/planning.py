import calendar
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from ..models import Week


def planning_week(raw_offset, *, today=None):
    today = today or date.today()
    current_monday = today - timedelta(days=today.weekday())
    try:
        offset = int(raw_offset)
    except (TypeError, ValueError):
        offset = 0
    offset = max(-52, min(52, offset))
    start = current_monday + timedelta(weeks=offset)
    end = start + timedelta(days=6)
    return {
        "week_offset": offset,
        "week_start": start,
        "week_end": end,
        "previous_week_offset": offset - 1,
        "next_week_offset": offset + 1,
        "is_current_week": offset == 0,
        "can_plan_week": end >= today,
    }


def area_time_balance(areas):
    total_importance = sum(area.importance_weight for area in areas)
    total_hours = sum(float(area.weekly_hours_target) for area in areas)
    names = [area.name for area in areas]
    importance = [
        round(area.importance_weight / total_importance * 100, 1)
        if total_importance else 0
        for area in areas
    ]
    time = [
        round(float(area.weekly_hours_target) / total_hours * 100, 1)
        if total_hours else 0
        for area in areas
    ]
    rows = []
    for area, importance_share, time_share in zip(areas, importance, time):
        difference = round(time_share - importance_share, 1)
        if difference <= -5:
            status, label = "under", "Poco tiempo"
        elif difference >= 5:
            status, label = "over", "Mucho tiempo"
        else:
            status, label = "balanced", "Equilibrado"
        rows.append({
            "area": area,
            "importance_share": importance_share,
            "time_share": time_share,
            "difference": difference,
            "status": status,
            "status_label": label,
        })
    rows.sort(key=lambda item: abs(item["difference"]), reverse=True)
    return {
        "area_names": names,
        "importance_values": importance,
        "time_values": time,
        "area_balance": rows,
        "largest_mismatch": rows[0] if rows else None,
        "total_target_hours": total_hours,
    }


def year_calendar(*, year, tasks):
    tasks_by_date = defaultdict(list)
    for task in tasks:
        tasks_by_date[task.due_date].append(task)
    cal = calendar.Calendar(firstweekday=0)
    months = []
    for month_number in range(1, 13):
        weeks = []
        for week in cal.monthdayscalendar(year, month_number):
            days = []
            for day_number in week:
                if day_number == 0:
                    days.append(None)
                else:
                    current_date = date(year, month_number, day_number)
                    days.append({
                        "day": day_number,
                        "date": current_date,
                        "tasks": tasks_by_date.get(current_date, []),
                    })
            weeks.append(days)
        months.append({
            "number": month_number,
            "name": calendar.month_name[month_number],
            "weeks": weeks,
        })
    return months


def saved_week_calendar(*, week, allocations, week_start):
    allocations = list(allocations)
    by_date = defaultdict(list)
    for allocation in allocations:
        by_date[allocation.planned_date].append(allocation)
    total = sum((item.planned_hours or Decimal("0") for item in allocations), Decimal("0"))
    task_count = len({item.task_id for item in allocations})
    days_count = len({item.planned_date for item in allocations if item.planned_date})
    available = Decimal(str(week.available_hours)) if week and week.available_hours is not None else Decimal("0")
    free = max(Decimal("0"), available - total)
    load = min(Decimal("100"), total / available * 100) if available > 0 else Decimal("0")
    average = total / Decimal(days_count) if days_count else Decimal("0")
    is_fixed = bool(week and week.planning_mode in (Week.PlanningMode.OPTIMIZED, Week.PlanningMode.MANUAL))
    names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    schedule = []
    for index, name in enumerate(names):
        current_date = week_start + timedelta(days=index)
        day_items = by_date.get(current_date, [])
        schedule.append({
            "date": current_date,
            "name": name,
            "allocations": day_items,
            "used_hours": sum((item.planned_hours or Decimal("0") for item in day_items), Decimal("0")),
            "has_work": bool(day_items),
            "is_weekend": index >= 5,
        })
    return {
        "fixed_allocations": allocations,
        "saved_schedule": schedule,
        "calendar_is_fixed": is_fixed,
        "saved_total_hours": total,
        "saved_available_hours": available,
        "saved_free_hours": free,
        "saved_load_percent": load,
        "saved_task_count": task_count,
        "saved_days_with_work": days_count,
        "saved_daily_average": average,
    }
