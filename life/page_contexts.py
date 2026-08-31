from django.shortcuts import render,redirect,get_object_or_404

from django.urls import reverse

from django.contrib.auth.decorators import login_required

from django.db.models import Avg, Sum

from datetime import date, timedelta

from django.db import transaction

from .forms import(
    LifeAreaForm,
    PlanForm,
    TaskForm,
    TaskImpactFormSet,
)

from .models import (
    LifeArea,
    LifeAreaSnapshot,
    Plan,
    Task,
    Week,
    WeeklyTracking,
    WeeklyTaskAllocation,
)

from decimal import Decimal, InvalidOperation

from .forms import WeeklyPlannerForm

from .services.weekly_planner import build_weekly_plan

from .selectors.dashboard import dashboard_entities, current_week_with_allocations

from .presenters.dashboard import (
    area_cards,
    dashboard_kpis,
    recent_activity_items,
    upcoming_deadline_rows,
    weekly_capacity,
    weekly_focus,
    weekly_calendar_visuals,
)

from .presenters.planning import area_time_balance, planning_week, saved_week_calendar, year_calendar

from .selectors.planning import (
    available_calendar_tasks,
    eligible_planner_tasks,
    tasks_for_year,
    upcoming_deadlines as select_upcoming_deadlines,
    saved_week_plan,
)

from .services.allocations import save_optimized_schedule

from .services.planning import process_planning_submission

from django.contrib.auth import login

from django.contrib.auth.forms import UserCreationForm

from django.shortcuts import redirect, render

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

    day_names = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo",
    ]

    allocations_by_date = {}

    area_tone_by_id = {
        area.pk: f"tone-{(index % 5) + 1}"
        for index, area in enumerate(areas)
    }

    distribution_map = {}

    def allocation_area_info(allocation):
        impacts = list(
            allocation.task.impacts.all()
        )

        primary_impact = max(
            impacts,
            key=lambda item: item.impact_percent,
            default=None,
        )

        if primary_impact:
            area = (
                primary_impact
                .plan
                .life_area
            )

            return (
                area.pk,
                area.name,
                area_tone_by_id.get(
                    area.pk,
                    "tone-neutral",
                ),
            )

        task_plans = list(
            allocation.task.plans.all()
        )

        if task_plans:
            area = task_plans[0].life_area

            return (
                area.pk,
                area.name,
                area_tone_by_id.get(
                    area.pk,
                    "tone-neutral",
                ),
            )

        return (
            None,
            "Sin área",
            "tone-neutral",
        )

    for allocation in week_allocations:
        (
            area_id,
            area_name,
            tone,
        ) = allocation_area_info(
            allocation
        )

        allocation_row = {
            "allocation": allocation,
            "task": allocation.task,
            "hours": (
                allocation.planned_hours
                or Decimal("0")
            ),
            "area_name": area_name,
            "tone": tone,
        }

        allocations_by_date.setdefault(
            allocation.planned_date,
            [],
        ).append(allocation_row)

        distribution_key = (
            area_id,
            area_name,
            tone,
        )

        distribution_map[
            distribution_key
        ] = (
            distribution_map.get(
                distribution_key,
                Decimal("0"),
            )
            + allocation_row["hours"]
        )

    week_schedule = []

    for index in range(7):
        current_date = (
            current_week_start
            + timedelta(days=index)
        )

        day_allocations = (
            allocations_by_date.get(
                current_date,
                [],
            )
        )

        day_total = sum(
            (
                item["hours"]
                for item in day_allocations
            ),
            Decimal("0"),
        )

        week_schedule.append({
            "name": day_names[index],
            "date": current_date,
            "allocations": day_allocations[:3],
            "extra_count": max(
                0,
                len(day_allocations) - 3,
            ),
            "total_hours": day_total,
        })

    # =========================================
    # DISTRIBUCIÓN DEL TIEMPO
    # =========================================

    palette = {
        "tone-1": "#58d7df",
        "tone-2": "#8b5cf6",
        "tone-3": "#f2b632",
        "tone-4": "#34a853",
        "tone-5": "#87909d",
        "tone-neutral": "#5f6772",
    }

    time_distribution = []

    for (
        area_id,
        area_name,
        tone,
    ), hours in sorted(
        distribution_map.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        if weekly_assigned_hours > 0:
            percent = (
                hours
                / weekly_assigned_hours
                * Decimal("100")
            )
        else:
            percent = Decimal("0")

        time_distribution.append({
            "area_id": area_id,
            "name": area_name,
            "tone": tone,
            "hours": hours,
            "percent": percent,
        })

    gradient_segments = []
    gradient_start = Decimal("0")

    for row in time_distribution:
        gradient_end = (
            gradient_start
            + row["percent"]
        )

        gradient_segments.append(
            (
                f"{palette[row['tone']]} "
                f"{float(gradient_start):.2f}% "
                f"{float(gradient_end):.2f}%"
            )
        )

        gradient_start = gradient_end

    if gradient_segments:
        time_distribution_gradient = (
            ", ".join(gradient_segments)
        )
    else:
        time_distribution_gradient = (
            "#2a2a2f 0% 100%"
        )

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

        "week_schedule": week_schedule,

        "time_distribution": time_distribution,
        "time_distribution_gradient": time_distribution_gradient,

        "recent_activity": recent_activity,
    }

    return context

import calendar

from collections import defaultdict

from datetime import date

from django.contrib.auth.decorators import login_required

from django.shortcuts import render

from .models import LifeArea, Task

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

    fixed_allocations = list(fixed_allocations)

    allocations_by_date = defaultdict(list)

    for allocation in fixed_allocations:
        allocations_by_date[
            allocation.planned_date
        ].append(allocation)

    # -------------------------
    # MÉTRICAS DEL CALENDARIO
    # -------------------------

    saved_total_hours = sum(
        (
            allocation.planned_hours
            or Decimal("0")
            for allocation in fixed_allocations
        ),
        Decimal("0"),
    )

    saved_task_count = len({
        allocation.task_id
        for allocation in fixed_allocations
    })

    saved_days_with_work = len({
        allocation.planned_date
        for allocation in fixed_allocations
        if allocation.planned_date
    })

    if (
        current_week
        and current_week.available_hours is not None
    ):
        saved_available_hours = Decimal(
            str(current_week.available_hours)
        )
    else:
        saved_available_hours = Decimal("0")

    saved_free_hours = max(
        Decimal("0"),
        saved_available_hours - saved_total_hours,
    )

    if saved_available_hours > 0:
        saved_load_percent = min(
            Decimal("100"),
            (
                saved_total_hours
                / saved_available_hours
                * Decimal("100")
            ),
        )
    else:
        saved_load_percent = Decimal("0")

    if saved_days_with_work > 0:
        saved_daily_average = (
            saved_total_hours
            / Decimal(saved_days_with_work)
        )
    else:
        saved_daily_average = Decimal("0")

    calendar_is_fixed = bool(
        current_week
        and current_week.planning_mode
        in {
            Week.PlanningMode.OPTIMIZED,
            Week.PlanningMode.MANUAL,
        }
    )

    # -------------------------
    # CALENDARIO POR DÍA
    # -------------------------

    saved_schedule = []

    day_names = [
        "Lunes",
        "Martes",
        "Miércoles",
        "Jueves",
        "Viernes",
        "Sábado",
        "Domingo",
    ]

    for index in range(7):
        current_date = (
            week_start
            + timedelta(days=index)
        )

        day_allocations = (
            allocations_by_date.get(
                current_date,
                [],
            )
        )

        used_hours = sum(
            (
                allocation.planned_hours
                or Decimal("0")
                for allocation in day_allocations
            ),
            Decimal("0"),
        )

        saved_schedule.append({
            "date": current_date,
            "name": day_names[index],
            "allocations": day_allocations,
            "used_hours": used_hours,
            "has_work": bool(day_allocations),
            "is_weekend": index >= 5,
        })

    


    # =========================================
    # TAREAS DISPONIBLES PARA AÑADIR MANUALMENTE
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

