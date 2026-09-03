from datetime import date, timedelta

from .forms import WeeklyPlannerForm
from .models import LifeArea, Task
from .presenters.dashboard import (
    area_cards,
    dashboard_kpis,
    recent_activity_items,
    weekly_calendar_visuals,
    weekly_capacity,
    weekly_focus,
)
from .presenters.planning import (
    area_time_balance,
    planning_week,
    saved_week_calendar,
    year_calendar,
)
from .selectors.dashboard import dashboard_entities, current_week_with_allocations
from .selectors.planning import (
    available_calendar_tasks,
    saved_week_plan,
    tasks_for_year,
    upcoming_deadlines as select_upcoming_deadlines,
)
from .services.planning import process_planning_submission

def build_dashboard_context(request):
    today = date.today()

    current_week_start = (
        today - timedelta(days=today.weekday())
    )

    current_week_end = (
        current_week_start + timedelta(days=6)
    )

    # =========================================
    # BASE
    # =========================================

    areas, plans, tasks = dashboard_entities(request.user)

    kpis = dashboard_kpis(areas=areas, plans=plans, tasks=tasks)
    active_plans = kpis["active_plans"]
    visible_plans = kpis["visible_plans"]
    open_tasks = kpis["open_tasks"]

    # =========================================
    # SEMANA ACTUAL
    # =========================================

    current_week, week_allocations = current_week_with_allocations(
        user=request.user,
        week_start=current_week_start,
    )

    weekly_assigned_hours, weekly_available_hours, weekly_free_hours, weekly_load_percent = weekly_capacity(
        current_week=current_week, allocations=week_allocations, areas=areas
    )

    # =========================================
    # KPI SUPERIORES
    # =========================================

    active_tasks_count = kpis["active_tasks_count"]
    total_tasks_count = kpis["total_tasks_count"]
    active_plans_count = kpis["active_plans_count"]
    total_plans_count = kpis["total_plans_count"]
    life_balance = kpis["life_balance"]

    # =========================================
    # FOCO DE LA SEMANA
    # =========================================

    focus_plan, focus_actual_hours, focus_remaining_hours, focus_next_deadline, focus_days_remaining = weekly_focus(
        active_plans, today
    )

    # =========================================
    # PRÓXIMOS DEADLINES
    # =========================================

    deadline_limit = today + timedelta(days=30)

    deadline_tasks = list(
        open_tasks
        .filter(
            due_date__isnull=False,
            due_date__gte=today,
            due_date__lte=deadline_limit,
        )
        .order_by(
            "due_date",
            "name",
        )[:5]
    )

    deadline_rows = []

    for task in deadline_tasks:
        days_left = (
            task.due_date - today
        ).days

        task_plans = list(
            task.plans.all()
        )

        primary_plan = (
            task_plans[0]
            if task_plans
            else None
        )

        if days_left <= 3:
            tone = "urgent"
            label = "Urgente"

        elif task.status == Task.Status.IN_PROGRESS:
            tone = "progress"
            label = "En progreso"

        else:
            tone = "next"
            label = "Próximo"

        deadline_rows.append({
            "task": task,
            "plan": primary_plan,
            "days_left": days_left,
            "tone": tone,
            "label": label,
        })

    # =========================================
    # ÁREAS DE VIDA
    # =========================================

    area_rows = area_cards(areas)

    # =========================================
    # CALENDARIO SEMANAL + DISTRIBUCIÓN
    # =========================================

    weekly_visuals = weekly_calendar_visuals(
        allocations=week_allocations,
        areas=areas,
        week_start=current_week_start,
        assigned_hours=weekly_assigned_hours,
    )
    week_schedule = weekly_visuals["week_schedule"]
    time_distribution = weekly_visuals["time_distribution"]
    time_distribution_gradient = weekly_visuals["time_distribution_gradient"]

    # =========================================
    # ACTIVIDAD RECIENTE
    # =========================================

    recent_activity = recent_activity_items(tasks=tasks, plans=plans)

    # =========================================
    # CONTEXT
    # =========================================

    context = {
        "today": today,

        "current_week": current_week,
        "current_week_start": current_week_start,
        "current_week_end": current_week_end,

        "weekly_assigned_hours": weekly_assigned_hours,
        "weekly_available_hours": weekly_available_hours,
        "weekly_free_hours": weekly_free_hours,
        "weekly_load_percent": weekly_load_percent,

        "active_tasks_count": active_tasks_count,
        "total_tasks_count": total_tasks_count,

        "active_plans_count": active_plans_count,
        "total_plans_count": total_plans_count,

        "life_balance": life_balance,

        "focus_plan": focus_plan,
        "focus_actual_hours": focus_actual_hours,
        "focus_remaining_hours": focus_remaining_hours,
        "focus_next_deadline": focus_next_deadline,
        "focus_days_remaining": focus_days_remaining,

        "deadline_rows": deadline_rows,
        "area_rows": area_rows,
        "areas": areas,

        "week_schedule": week_schedule,

        "time_distribution": time_distribution,
        "time_distribution_gradient": time_distribution_gradient,

        "recent_activity": recent_activity,
    }

    return context

def build_planning_context(request):
    year = int(
        request.GET.get("year", date.today().year)
    )

    # -------------------------
    # ÁREAS
    # -------------------------

    areas = list(
        LifeArea.objects
        .filter(user=request.user)
        .order_by("-importance_weight")
    )

    balance = area_time_balance(areas)
    area_names = balance["area_names"]
    importance_values = balance["importance_values"]
    time_values = balance["time_values"]
    total_target_hours = balance["total_target_hours"]


    # -------------------------
    # CALENDARIO
    # -------------------------

    tasks = tasks_for_year(user=request.user, year=year)
    months = year_calendar(year=year, tasks=tasks)


    # -------------------------
    # DESAJUSTES
    # -------------------------

    area_balance = balance["area_balance"]
    largest_mismatch = balance["largest_mismatch"]


    # -------------------------
    # DEADLINES
    # -------------------------

    today = date.today()
    deadline_limit = today + timedelta(days=30)

    upcoming_deadlines = select_upcoming_deadlines(
        user=request.user, start=today, end=deadline_limit
    )


    # -------------------------
    # WEEKLY PLANNER
    # -------------------------

    today = date.today()

    current_week_start = (
        today - timedelta(days=today.weekday())
    )

    # GET cuando navegas con las flechas.
    # POST cuando Generas / Actualizas / Fijas.
    raw_week_offset = (
        request.POST.get("week_offset")
        if request.method == "POST"
        else request.GET.get("week", "0")
    )

    week_data = planning_week(raw_week_offset, today=today)
    week_offset = week_data["week_offset"]
    week_start = week_data["week_start"]
    week_end = week_data["week_end"]
    previous_week_offset = week_data["previous_week_offset"]
    next_week_offset = week_data["next_week_offset"]
    is_current_week = week_data["is_current_week"]
    can_plan_week = week_data["can_plan_week"]

    current_week, fixed_allocations = saved_week_plan(
        user=request.user,
        week_start=week_start,
    )

    # =========================================
    # CALENDARIO FIJADO / RESUMEN SEMANAL
    # =========================================

    saved = saved_week_calendar(
        week=current_week,
        allocations=fixed_allocations,
        week_start=week_start,
    )
    fixed_allocations = saved["fixed_allocations"]
    saved_schedule = saved["saved_schedule"]
    calendar_is_fixed = saved["calendar_is_fixed"]
    saved_total_hours = saved["saved_total_hours"]
    saved_available_hours = saved["saved_available_hours"]
    saved_free_hours = saved["saved_free_hours"]
    saved_load_percent = saved["saved_load_percent"]
    saved_task_count = saved["saved_task_count"]
    saved_days_with_work = saved["saved_days_with_work"]
    saved_daily_average = saved["saved_daily_average"]

    calendar_available_tasks = available_calendar_tasks(request.user)


    # =========================================
    # FORMULARIO DEL PLANNER
    # =========================================

    planner_form = WeeklyPlannerForm(
        request.POST or None
    )

    planner_result = None


    if (
        request.method == "POST"
        and planner_form.is_valid()
    ):

        submission = process_planning_submission(
            user=request.user,
            data=request.POST,
            cleaned_data=planner_form.cleaned_data,
            week_start=week_start,
        )
        planner_result = submission.result
        if submission.saved:
            return {"redirect_week_offset": week_offset}
        calendar_available_tasks = available_calendar_tasks(request.user)
    context = {
        "year": year,
        "previous_year": year - 1,
        "next_year": year + 1,

        "months": months,

        "area_names": area_names,
        "importance_values": importance_values,
        "time_values": time_values,

        "total_target_hours": total_target_hours,

        "area_balance": area_balance,
        "largest_mismatch": largest_mismatch,
        "upcoming_deadlines": upcoming_deadlines,

        "planner_form": planner_form,
        "planner_result": planner_result,

        "current_week": current_week,
        "fixed_allocations": fixed_allocations,

        "saved_schedule": saved_schedule,

        "calendar_is_fixed": calendar_is_fixed,

        "saved_total_hours": saved_total_hours,
        "saved_available_hours": saved_available_hours,
        "saved_free_hours": saved_free_hours,
        "saved_load_percent": saved_load_percent,

        "saved_task_count": saved_task_count,
        "saved_days_with_work": saved_days_with_work,
        "saved_daily_average": saved_daily_average,

        "week_offset": week_offset,
        "previous_week_offset": previous_week_offset,
        "next_week_offset": next_week_offset,

        "week_start": week_start,
        "week_end": week_end,

        "is_current_week": is_current_week,
        "can_plan_week": can_plan_week,

        "calendar_available_tasks": calendar_available_tasks,
    }

    return context


