from datetime import date, timedelta


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
