from django.contrib.auth.decorators import login_required
from django.shortcuts import render,redirect,get_object_or_404
from django.urls import reverse

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

from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render


def register(request):
    if request.user.is_authenticated:
        return redirect("life:dashboard")

    if request.method == "POST":
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)

            return redirect("life:dashboard")
    else:
        form = UserCreationForm()

    return render(
        request,
        "registration/register.html",
        {"form": form},
    )

@login_required
def dashboard(request):
    areas = (
        LifeArea.objects
        .filter(user=request.user)
        .prefetch_related("plans")
        .order_by("-importance_weight")
    )

    active_plans = Plan.objects.filter(
        life_area__user=request.user,
        status=Plan.Status.ACTIVE,
    ).select_related("life_area")

    pending_tasks = Task.objects.filter(
        plans__life_area__user=request.user,
    ).exclude(
        status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED]
    ).distinct()[:8]

    context = {
        "areas": areas,
        "active_plans": active_plans,
        "pending_tasks": pending_tasks,
    }

    return render(request, "life/dashboard.html", context)


@login_required
def life_area_create(request):

    if request.method == "POST":

        form = LifeAreaForm(request.POST)

        if form.is_valid():
            area = form.save(commit=False)

            area.user = request.user

            area.save()

            return redirect("life:dashboard")

    else:
        form = LifeAreaForm()

    return render(
        request,
        "life/life_area_form.html",
        {
            "form": form,
        },
    )

@login_required
def life_area_list(request):
    areas = (
        LifeArea.objects
        .filter(user=request.user)
        .prefetch_related("plans")
        .order_by("-importance_weight")
    )

    return render(
        request,
        "life/life_area_list.html",
        {"areas": areas},
    )

@login_required
def life_area_edit(request, pk):
    area = get_object_or_404(
        LifeArea,
        pk=pk,
        user=request.user,
    )

    if request.method == "POST":
        form = LifeAreaForm(
            request.POST,
            instance=area,
        )

        if form.is_valid():
            form.save()

            return redirect(
                "life:life_area_detail",
                pk=area.pk,
            )

    else:
        form = LifeAreaForm(instance=area)

    return render(
        request,
        "life/life_area_form.html",
        {
            "form": form,
            "area": area,
            "editing": True,
        },
    )

@login_required
def life_area_detail(request, pk):
    area = get_object_or_404(
        LifeArea,
        pk=pk,
        user=request.user,
    )

    plans = area.plans.all()

    snapshots = area.snapshots.all().order_by("-week")

    return render(
        request,
        "life/life_area_detail.html",
        {
            "area": area,
            "plans": plans,
            "snapshots": snapshots,
        },
    )

@login_required
def life_area_delete(request, pk):
    area = get_object_or_404(
        LifeArea,
        pk=pk,
        user=request.user,
    )

    if request.method == "POST":

        # Guardamos tareas potencialmente afectadas
        task_ids = list(
            Task.objects
            .filter(plans__life_area=area)
            .values_list("id", flat=True)
            .distinct()
        )

        area.delete()

        # Borra tareas que se hayan quedado sin ningún plan.
        # Si una tarea también pertenecía a otro plan,
        # se conserva.
        Task.objects.filter(
            id__in=task_ids,
            plans__isnull=True,
        ).delete()

        return redirect("life:life_area_list")

    return render(
        request,
        "life/life_area_confirm_delete.html",
        {
            "area": area,
        },
    )


@login_required
def plan_list(request):

    # =========================================
    # BASE
    # =========================================

    base_plans = (
        Plan.objects
        .filter(
            life_area__user=request.user
        )
        .select_related(
            "life_area"
        )
    )

    # =========================================
    # STATS
    # =========================================

    total_plans = base_plans.count()

    active_plans = base_plans.filter(
        status=Plan.Status.ACTIVE
    ).count()

    completed_plans = base_plans.filter(
        status=Plan.Status.COMPLETED
    ).count()

    paused_plans = base_plans.filter(
        status=Plan.Status.PAUSED
    ).count()

    # =========================================
    # FILTROS
    # =========================================

    current_filter = request.GET.get(
        "filter",
        "all",
    )

    plans = base_plans

    if current_filter == "active":

        plans = plans.filter(
            status=Plan.Status.ACTIVE
        )

    elif current_filter == "paused":

        plans = plans.filter(
            status=Plan.Status.PAUSED
        )

    elif current_filter == "completed":

        plans = plans.filter(
            status=Plan.Status.COMPLETED
        )

    # =========================================
    # ORDEN
    # =========================================

    current_sort = request.GET.get(
        "sort",
        "importance",
    )

    if current_sort == "progress":

        plans = plans.order_by(
            "-progress",
            "-importance_weight",
        )

    elif current_sort == "target":

        plans = plans.order_by(
            "target_date",
            "-importance_weight",
        )

    elif current_sort == "recent":

        plans = plans.order_by(
            "-created_at"
        )

    else:

        plans = plans.order_by(
            "-importance_weight",
            "-created_at",
        )

    # =========================================
    # TASKS + HORAS DE CADA PLAN
    # =========================================

    plans = list(
        plans.prefetch_related("tasks")
    )

    plan_rows = []

    for plan in plans:

        tasks = list(
            plan.tasks.all()
        )

        total_tasks = len(tasks)

        completed_tasks = sum(
            1
            for task in tasks
            if task.status == Task.Status.COMPLETED
        )

        actual_hours = sum(
            (
                task.actual_hours
                or Decimal("0")
                for task in tasks
            ),
            Decimal("0"),
        )

        plan_rows.append({
            "plan": plan,

            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,

            "actual_hours": actual_hours,
        })

    # =========================================
    # HISTÓRICO RECIENTE
    # =========================================

    recent_tracking = (
        WeeklyTracking.objects
        .filter(
            plan__life_area__user=request.user
        )
        .select_related(
            "plan",
            "week",
        )
        .order_by(
            "-week__week_start"
        )[:6]
    )

    context = {
        "plan_rows": plan_rows,

        "total_plans": total_plans,
        "active_plans": active_plans,
        "completed_plans": completed_plans,
        "paused_plans": paused_plans,

        "current_filter": current_filter,
        "current_sort": current_sort,

        "recent_tracking": recent_tracking,
    }

    return render(
        request,
        "life/plan_list.html",
        context,
    )


@login_required
def plan_detail(request, pk):
    plan = get_object_or_404(
        Plan.objects.select_related("life_area"),
        pk=pk,
        life_area__user=request.user,
    )

    tasks = (
        plan.tasks
        .all()
        .distinct()
        .prefetch_related("impacts")
        .order_by("status", "due_date", "name")
    )

    tracking = (
        plan.weekly_tracking
        .select_related("week")
        .all()
        .order_by("-week__week_start")
    )

    # =========================
    # RESUMEN DEL PLAN
    # =========================

    total_tasks = tasks.count()

    completed_tasks = tasks.filter(
        status=Task.Status.COMPLETED
    ).count()

    total_actual_hours = sum(
        (
            task.actual_hours or Decimal("0")
            for task in tasks
        ),
        Decimal("0"),
    )

    remaining_hours = max(
        Decimal("0"),
        (plan.estimated_hours or Decimal("0"))
        - total_actual_hours,
    )

    today = date.today()

    days_remaining = None

    if plan.target_date:
        days_remaining = (
            plan.target_date - today
        ).days

    # =========================
    # INFO DETALLADA DE TAREAS
    # =========================

    task_rows = []

    for task in tasks:

        impact = (
            task.impacts
            .filter(plan=plan)
            .first()
        )

        estimated = (
            task.estimated_hours
            or Decimal("0")
        )

        actual = (
            task.actual_hours
            or Decimal("0")
        )

        task_remaining = max(
            Decimal("0"),
            estimated - actual,
        )

        if estimated > 0:
            time_progress = min(
                Decimal("100"),
                (
                    actual
                    / estimated
                    * Decimal("100")
                ),
            )
        else:
            time_progress = Decimal("0")

        if task.status == Task.Status.COMPLETED:
            time_progress = Decimal("100")

        task_rows.append({
            "task": task,

            "impact": (
                impact.impact_percent
                if impact
                else Decimal("0")
            ),

            "remaining_hours": task_remaining,

            "time_progress": time_progress,
        })

    context = {
        "plan": plan,

        "tasks": tasks,
        "task_rows": task_rows,

        "tracking": tracking,

        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,

        "total_actual_hours": total_actual_hours,
        "remaining_hours": remaining_hours,

        "days_remaining": days_remaining,
    }

    return render(
        request,
        "life/plan_detail.html",
        context,
    )


@login_required
def plan_edit(request, pk):
    plan = get_object_or_404(
        Plan,
        pk=pk,
        life_area__user=request.user,
    )

    if request.method == "POST":
        form = PlanForm(
            request.POST,
            instance=plan,
            user=request.user,
        )

        if form.is_valid():
            form.save()

            return redirect(
                "life:plan_detail",
                pk=plan.pk,
            )

    else:
        form = PlanForm(
            instance=plan,
            user=request.user,
        )

    return render(
        request,
        "life/plan_form.html",
        {
            "form": form,
            "plan": plan,
            "editing": True,
        },
    )

@login_required
def task_list(request):

    today = date.today()

    # =========================================
    # BASE
    # =========================================

    base_tasks = (
        Task.objects
        .filter(
            plans__life_area__user=request.user
        )
        .prefetch_related(
            "plans",
            "plans__life_area",
        )
        .distinct()
    )

    # =========================================
    # ESTADÍSTICAS
    # =========================================

    total_tasks = base_tasks.count()

    in_progress_tasks = base_tasks.filter(
        status=Task.Status.IN_PROGRESS
    ).count()

    completed_tasks = base_tasks.filter(
        status=Task.Status.COMPLETED
    ).count()

    pending_tasks = base_tasks.filter(
        status=Task.Status.PENDING
    ).count()

    urgent_limit = (
        today + timedelta(days=3)
    )

    urgent_tasks = (
        base_tasks
        .exclude(
            status__in=[
                Task.Status.COMPLETED,
                Task.Status.CANCELLED,
            ]
        )
        .filter(
            due_date__isnull=False,
            due_date__lte=urgent_limit,
        )
        .count()
    )

    # =========================================
    # FILTROS
    # =========================================

    current_filter = request.GET.get(
        "filter",
        "all",
    )

    tasks = base_tasks

    if current_filter == "today":

        tasks = tasks.filter(
            due_date=today
        )

    elif current_filter == "week":

        end_of_week = (
            today
            + timedelta(
                days=6 - today.weekday()
            )
        )

        tasks = tasks.filter(
            due_date__gte=today,
            due_date__lte=end_of_week,
        )

    elif current_filter == "completed":

        tasks = tasks.filter(
            status=Task.Status.COMPLETED
        )

    # =========================================
    # ORDEN
    # =========================================

    current_sort = request.GET.get(
        "sort",
        "recent",
    )

    if current_sort == "deadline":

        tasks = tasks.order_by(
            "due_date",
            "name",
        )

    elif current_sort == "name":

        tasks = tasks.order_by(
            "name"
        )

    else:

        tasks = tasks.order_by(
            "-created_at"
        )

    # =========================================
    # DATOS VISUALES
    # =========================================

    task_rows = []

    for task in tasks:

        estimated = Decimal(
            str(
                task.estimated_hours
                or 0
            )
        )

        actual = Decimal(
            str(
                task.actual_hours
                or 0
            )
        )

        if estimated > 0:

            progress = (
                actual
                / estimated
                * Decimal("100")
            )

            progress = min(
                progress,
                Decimal("100"),
            )

        else:

            progress = Decimal("0")

        if (
            task.status
            == Task.Status.COMPLETED
        ):
            progress = Decimal("100")

        is_overdue = bool(
            task.due_date
            and task.due_date < today
            and task.status
            not in [
                Task.Status.COMPLETED,
                Task.Status.CANCELLED,
            ]
        )

        is_urgent = bool(
            task.due_date
            and task.due_date <= urgent_limit
            and task.status
            not in [
                Task.Status.COMPLETED,
                Task.Status.CANCELLED,
            ]
        )

        task_rows.append({
            "task": task,

            "progress_percent":
                round(float(progress)),

            "is_urgent": is_urgent,

            "is_overdue": is_overdue,
        })

    context = {
        "task_rows": task_rows,

        "total_tasks": total_tasks,
        "in_progress_tasks": in_progress_tasks,
        "completed_tasks": completed_tasks,
        "pending_tasks": pending_tasks,
        "urgent_tasks": urgent_tasks,

        "current_filter": current_filter,
        "current_sort": current_sort,
    }

    return render(
        request,
        "life/task_list.html",
        context,
    )

@login_required
def task_detail(request, pk):

    task = get_object_or_404(
        Task.objects
        .filter(
            plans__life_area__user=request.user
        )
        .distinct(),
        pk=pk,
    )

    # =========================================
    # REGISTRAR HORAS
    # =========================================

    if request.method == "POST":

        action = request.POST.get("action")

        if action == "add_hours":

            raw_hours = request.POST.get(
                "hours_to_add",
                "0",
            )

            try:
                hours_to_add = Decimal(
                    raw_hours
                )

            except InvalidOperation:
                hours_to_add = Decimal("0")

            if hours_to_add > 0:

                task.actual_hours = (
                    Decimal(
                        str(task.actual_hours or 0)
                    )
                    + hours_to_add
                )

                task.save(
                    update_fields=[
                        "actual_hours"
                    ]
                )

            return redirect(
                "life:task_detail",
                pk=task.pk,
            )

    # =========================================
    # RELACIONES
    # =========================================

    impacts = (
        task.impacts
        .select_related(
            "plan",
            "plan__life_area",
        )
        .order_by(
            "-impact_percent"
        )
    )

    subtasks = (
        task.subtasks
        .all()
        .order_by(
            "status",
            "due_date",
        )
    )

    # =========================================
    # HORAS
    # =========================================

    estimated_hours = Decimal(
        str(task.estimated_hours or 0)
    )

    actual_hours = Decimal(
        str(task.actual_hours or 0)
    )

    remaining_hours = max(
        Decimal("0"),
        estimated_hours - actual_hours,
    )

    # =========================================
    # PROGRESO POR TIEMPO
    # =========================================

    if estimated_hours > 0:

        progress_percent = (
            actual_hours
            / estimated_hours
            * Decimal("100")
        )

        progress_percent = min(
            Decimal("100"),
            progress_percent,
        )

    else:
        progress_percent = Decimal("0")

    if task.status == Task.Status.COMPLETED:
        progress_percent = Decimal("100")

    remaining_percent = max(
        Decimal("0"),
        Decimal("100")
        - progress_percent,
    )

    # =========================================
    # DEADLINE
    # =========================================

    today = date.today()

    days_remaining = None

    if task.due_date:

        days_remaining = (
            task.due_date - today
        ).days

    # =========================================
    # SUBTAREAS
    # =========================================

    total_subtasks = subtasks.count()

    completed_subtasks = subtasks.filter(
        status=Task.Status.COMPLETED
    ).count()

    context = {
        "task": task,

        "impacts": impacts,
        "subtasks": subtasks,

        "estimated_hours": estimated_hours,
        "actual_hours": actual_hours,
        "remaining_hours": remaining_hours,

        "progress_percent": progress_percent,
        "remaining_percent": remaining_percent,

        "days_remaining": days_remaining,

        "total_subtasks": total_subtasks,
        "completed_subtasks": completed_subtasks,
    }

    return render(
        request,
        "life/task_detail.html",
        context,
    )


@login_required
def weekly_tracking(request):
    tracking = (
        WeeklyTracking.objects
        .filter(plan__life_area__user=request.user)
        .select_related("plan", "plan__life_area")
        .order_by("-week_start")
    )

    return render(
        request,
        "life/weekly_tracking.html",
        {"tracking": tracking},
    )


@login_required
def statistics(request):
    areas = LifeArea.objects.filter(user=request.user)

    plans = Plan.objects.filter(
        life_area__user=request.user,
    )

    tasks = Task.objects.filter(
        plans__life_area__user=request.user,
    ).distinct()

    snapshots = LifeAreaSnapshot.objects.filter(
        life_area__user=request.user,
    )

    context = {
        "area_count": areas.count(),

        "average_satisfaction":
            areas.aggregate(
                value=Avg("current_satisfaction")
            )["value"] or 0,

        "active_plans":
            plans.filter(
                status=Plan.Status.ACTIVE
            ).count(),

        "completed_tasks":
            tasks.filter(
                status=Task.Status.COMPLETED
            ).count(),

        "weekly_hours_target":
            areas.aggregate(
                value=Sum("weekly_hours_target")
            )["value"] or 0,

        "snapshots": snapshots.order_by("-week_start")[:20],
    }

    return render(
        request,
        "life/statistics.html",
        context,
    )


@login_required
def plan_create(request):
    if request.method == "POST":
        form = PlanForm(
            request.POST,
            user=request.user,
        )

        if form.is_valid():
            plan = form.save()
            return redirect(
                "life:plan_detail",
                pk=plan.pk,
            )

    else:
        form = PlanForm(user=request.user)

    return render(
        request,
        "life/plan_form.html",
        {
            "form": form,
        },
    )



@login_required
def task_create(request):
    task = Task()

    if request.method == "POST":
        form = TaskForm(
            request.POST,
            instance=task,
        )

        formset = TaskImpactFormSet(
            request.POST,
            instance=task,
        )

        # Solo permitir planes del usuario
        for impact_form in formset.forms:
            impact_form.fields["plan"].queryset = Plan.objects.filter(
                life_area__user=request.user
            )

        if form.is_valid() and formset.is_valid():
            task = form.save()

            formset.instance = task
            impacts = formset.save()

            # Aseguramos progreso actualizado
            for impact in impacts:
                impact.plan.recalculate_progress()

            return redirect(
                "life:task_detail",
                pk=task.pk,
            )

    else:
        form = TaskForm(instance=task)

        formset = TaskImpactFormSet(
            instance=task,
        )

        for impact_form in formset.forms:
            impact_form.fields["plan"].queryset = Plan.objects.filter(
                life_area__user=request.user
            )

    return render(
        request,
        "life/task_form.html",
        {
            "form": form,
            "formset": formset,
        },
    )


@login_required
def plan_delete(request, pk):
    plan = get_object_or_404(
        Plan,
        pk=pk,
        life_area__user=request.user,
    )

    if request.method == "POST":
        plan.delete()

    return redirect("life:plan_list")

@login_required
def task_edit(request, pk):
    task = get_object_or_404(
        Task.objects
        .filter(plans__life_area__user=request.user)
        .distinct(),
        pk=pk,
    )

    # Guardamos los planes antiguos por si eliminamos algún impacto
    old_plan_ids = list(
        task.impacts.values_list("plan_id", flat=True)
    )

    if request.method == "POST":
        form = TaskForm(
            request.POST,
            instance=task,
        )

        formset = TaskImpactFormSet(
            request.POST,
            instance=task,
        )

        # Solo permitir planes del usuario
        for impact_form in formset.forms:
            impact_form.fields["plan"].queryset = Plan.objects.filter(
                life_area__user=request.user
            )

        if form.is_valid() and formset.is_valid():

            with transaction.atomic():
                task = form.save()

                formset.instance = task
                formset.save()

                # Recalculamos tanto planes antiguos como nuevos
                new_plan_ids = list(
                    task.impacts.values_list(
                        "plan_id",
                        flat=True,
                    )
                )

                affected_plan_ids = set(
                    old_plan_ids + new_plan_ids
                )

                for plan in Plan.objects.filter(
                    id__in=affected_plan_ids
                ):
                    plan.recalculate_progress()

            return redirect(
                "life:task_detail",
                pk=task.pk,
            )

    else:
        form = TaskForm(instance=task)

        formset = TaskImpactFormSet(
            instance=task,
        )

        for impact_form in formset.forms:
            impact_form.fields["plan"].queryset = Plan.objects.filter(
                life_area__user=request.user
            )

    return render(
        request,
        "life/task_form.html",
        {
            "form": form,
            "formset": formset,
            "task": task,
            "editing": True,
        },
    )


@login_required
def task_delete(request, pk):
    task = get_object_or_404(
        Task.objects.filter(
            plans__life_area__user=request.user
        ).distinct(),
        pk=pk,
    )

    if request.method == "POST":
        plans = list(
            Plan.objects.filter(
                task_impacts__task=task
            ).distinct()
        )

        task.delete()

        for plan in plans:
            plan.recalculate_progress()

    return redirect("life:task_list")


import calendar
from collections import defaultdict
from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import LifeArea, Task
@login_required
def planning(request):
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

    total_importance = sum(
        area.importance_weight
        for area in areas
    )

    total_target_hours = sum(
        float(area.weekly_hours_target)
        for area in areas
    )

    area_names = [
        area.name
        for area in areas
    ]

    importance_values = [
        round(
            (
                area.importance_weight
                / total_importance
            ) * 100,
            1,
        )
        if total_importance
        else 0
        for area in areas
    ]

    time_values = [
        round(
            (
                float(area.weekly_hours_target)
                / total_target_hours
            ) * 100,
            1,
        )
        if total_target_hours
        else 0
        for area in areas
    ]


    # -------------------------
    # CALENDARIO
    # -------------------------

    tasks = (
        Task.objects
        .filter(
            plans__life_area__user=request.user,
            due_date__year=year,
        )
        .distinct()
    )

    tasks_by_date = defaultdict(list)

    for task in tasks:
        tasks_by_date[task.due_date].append(task)

    cal = calendar.Calendar(firstweekday=0)

    months = []

    for month_number in range(1, 13):
        month_weeks = []

        for week in cal.monthdayscalendar(
            year,
            month_number,
        ):
            week_data = []

            for day_number in week:
                if day_number == 0:
                    week_data.append(None)
                    continue

                current_date = date(
                    year,
                    month_number,
                    day_number,
                )

                week_data.append({
                    "day": day_number,
                    "date": current_date,
                    "tasks": tasks_by_date.get(
                        current_date,
                        [],
                    ),
                })

            month_weeks.append(week_data)

        months.append({
            "number": month_number,
            "name": calendar.month_name[month_number],
            "weeks": month_weeks,
        })


    # -------------------------
    # DESAJUSTES
    # -------------------------

    area_balance = []

    for area, importance_share, time_share in zip(
        areas,
        importance_values,
        time_values,
    ):
        difference = round(
            time_share - importance_share,
            1,
        )

        if difference <= -5:
            status = "under"
            status_label = "Poco tiempo"

        elif difference >= 5:
            status = "over"
            status_label = "Mucho tiempo"

        else:
            status = "balanced"
            status_label = "Equilibrado"

        area_balance.append({
            "area": area,
            "importance_share": importance_share,
            "time_share": time_share,
            "difference": difference,
            "status": status,
            "status_label": status_label,
        })

    area_balance.sort(
        key=lambda item: abs(item["difference"]),
        reverse=True,
    )

    largest_mismatch = (
        area_balance[0]
        if area_balance
        else None
    )


    # -------------------------
    # DEADLINES
    # -------------------------

    today = date.today()
    deadline_limit = today + timedelta(days=30)

    upcoming_deadlines = (
        Task.objects
        .filter(
            plans__life_area__user=request.user,
            due_date__gte=today,
            due_date__lte=deadline_limit,
        )
        .exclude(
            status__in=[
                Task.Status.COMPLETED,
                Task.Status.CANCELLED,
            ]
        )
        .prefetch_related(
            "plans",
            "plans__life_area",
        )
        .order_by("due_date")
        .distinct()
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

    try:
        week_offset = int(raw_week_offset)
    except (TypeError, ValueError):
        week_offset = 0

    # Evitamos offsets absurdos accidentalmente.
    week_offset = max(-52, min(52, week_offset))

    week_start = (
        current_week_start
        + timedelta(weeks=week_offset)
    )

    week_end = (
        week_start
        + timedelta(days=6)
    )

    previous_week_offset = week_offset - 1
    next_week_offset = week_offset + 1

    is_current_week = week_offset == 0

    # Las anteriores se pueden consultar,
    # pero no tiene sentido optimizarlas.
    can_plan_week = week_end >= today

    current_week = Week.objects.filter(
            user=request.user,
            week_start=week_start,
        ).first()


    fixed_allocations = (
        WeeklyTaskAllocation.objects
        .filter(
            week=current_week,
            planned_date__isnull=False,
        )
        .select_related("task")
        .order_by(
            "planned_date",
            "task__due_date",
        )
        if current_week
        else WeeklyTaskAllocation.objects.none()
    )
    allocations_by_date = defaultdict(list)

    for allocation in fixed_allocations:
        allocations_by_date[
            allocation.planned_date
        ].append(allocation)

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
            week_start + timedelta(days=index)
        )

        saved_schedule.append({
            "date": current_date,
            "name": day_names[index],
            "allocations": allocations_by_date.get(
                current_date,
                [],
            ),
        })


    planner_form = WeeklyPlannerForm(
        request.POST or None
    )

    planner_result = None


    if (
        request.method == "POST"
        and planner_form.is_valid()
    ):

        action = request.POST.get(
            "action",
            "calculate",
        )

        available_hours = (
            planner_form.cleaned_data[
                "available_hours"
            ]
        )

        exclude_saturday = (
            planner_form.cleaned_data[
                "exclude_saturday"
            ]
        )

        exclude_sunday = (
            planner_form.cleaned_data[
                "exclude_sunday"
            ]
        )

        include_saturday = (
            not exclude_saturday
        )

        include_sunday = (
            not exclude_sunday
        )


        planner_tasks = (
            Task.objects
            .filter(
                plans__life_area__user=request.user,
                due_date__isnull=False,
            )
            .exclude(
                status__in=[
                    Task.Status.COMPLETED,
                    Task.Status.CANCELLED,
                ]
            )
            .distinct()
            .order_by(
                "due_date",
                "name",
            )
        )


        # =====================================
        # ACTUALIZAR DATOS DE LA PROPUESTA
        # =====================================

        selected_task_ids = None

        if action in {
            "update_plan",
            "save",
        }:
            selected_task_ids = {
                int(task_id)
                for task_id
                in request.POST.getlist(
                    "selected_tasks"
                )
            }
            planner_result = build_weekly_plan(
                planner_tasks,
                available_hours,
                include_saturday=include_saturday,
                include_sunday=include_sunday,
                selected_task_ids=selected_task_ids,
                planning_week_start=week_start,
            )

            with transaction.atomic():

                for task in planner_tasks:

                    raw_hours = request.POST.get(
                        f"actual_add_{task.pk}",
                        "",
                    ).strip()

                    if not raw_hours:
                        continue

                    try:
                        added_hours = Decimal(
                            raw_hours
                        )

                    except InvalidOperation:
                        continue

                    if added_hours <= 0:
                        continue

                    task.actual_hours = (
                        Decimal(
                            str(
                                task.actual_hours
                                or 0
                            )
                        )
                        + added_hours
                    )

                    task.save(
                        update_fields=[
                            "actual_hours"
                        ]
                    )


        # =====================================
        # RECALCULAR
        # =====================================

        planner_result = build_weekly_plan(
            planner_tasks,
            available_hours,
            include_saturday=include_saturday,
            include_sunday=include_sunday,
            selected_task_ids=selected_task_ids,
            planning_week_start=week_start,
        )


        # =====================================
        # FIJAR CALENDARIO
        # =====================================

        if action == "save":

            week, created = (
                Week.objects.get_or_create(
                    user=request.user,
                    week_start=week_start,
                )
            )

            week.available_hours = (
                available_hours
            )

            week.planning_mode = (
                Week.PlanningMode.OPTIMIZED
            )

            week.save()

            with transaction.atomic():

                week.task_allocations.all().delete()

                for day in planner_result["schedule"]:

                    for item in day["tasks"]:

                        WeeklyTaskAllocation.objects.create(
                            week=week,
                            task=item["task"],
                            planned_date=day["date"],
                            planned_hours=item["hours"],
                        )

            return redirect(
                f"{reverse('life:planning')}?week={week_offset}"
            )
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

        "week_offset": week_offset,
        "previous_week_offset": previous_week_offset,
        "next_week_offset": next_week_offset,

        "week_start": week_start,
        "week_end": week_end,

        "is_current_week": is_current_week,
        "can_plan_week": can_plan_week,
    }

    return render(
        request,
        "life/planning.html",
        context,
    )

@login_required
def allocation_move(request, pk):

    allocation = get_object_or_404(
        WeeklyTaskAllocation,
        pk=pk,
        week__user=request.user,
    )

    if request.method != "POST":
        return redirect("life:planning")

    new_date_raw = request.POST.get("planned_date")

    try:
        new_date = date.fromisoformat(
            new_date_raw
        )
    except (TypeError, ValueError):
        return redirect("life:planning")

    monday = allocation.week.week_start
    sunday = monday + timedelta(days=6)

    # Solo puede moverse dentro de esa semana
    if not monday <= new_date <= sunday:
        return redirect("life:planning")

    # Si ya existe esa misma tarea ese día,
    # sumamos las horas.
    existing = (
        WeeklyTaskAllocation.objects
        .filter(
            week=allocation.week,
            task=allocation.task,
            planned_date=new_date,
        )
        .exclude(pk=allocation.pk)
        .first()
    )

    with transaction.atomic():

        if existing:
            existing.planned_hours += (
                allocation.planned_hours
            )
            existing.save(
                update_fields=["planned_hours"]
            )

            allocation.delete()

        else:
            allocation.planned_date = new_date
            allocation.save(
                update_fields=["planned_date"]
            )

    return redirect("life:planning")

@login_required
def allocation_update(request, pk):
    allocation = get_object_or_404(
        WeeklyTaskAllocation,
        pk=pk,
        week__user=request.user,
    )

    if request.method != "POST":
        return redirect("life:planning")

    new_date_raw = request.POST.get("planned_date")
    new_hours_raw = request.POST.get("planned_hours")

    try:
        new_date = date.fromisoformat(new_date_raw)
        new_hours = Decimal(new_hours_raw)

    except (TypeError, ValueError, InvalidOperation):
        return redirect("life:planning")

    # Bloque mínimo del calendario
    if new_hours < Decimal("0.5"):
        new_hours = Decimal("0.5")

    monday = allocation.week.week_start
    sunday = monday + timedelta(days=6)

    # No permitir sacar la tarea de su semana
    if not monday <= new_date <= sunday:
        return redirect("life:planning")

    existing = (
        WeeklyTaskAllocation.objects
        .filter(
            week=allocation.week,
            task=allocation.task,
            planned_date=new_date,
        )
        .exclude(pk=allocation.pk)
        .first()
    )

    with transaction.atomic():

        if existing:
            # Si la mueves encima de otra asignación
            # de la misma tarea, las fusionamos.
            existing.planned_hours += new_hours

            existing.save(
                update_fields=["planned_hours"]
            )

            allocation.delete()

        else:
            allocation.planned_date = new_date
            allocation.planned_hours = new_hours

            allocation.save(
                update_fields=[
                    "planned_date",
                    "planned_hours",
                ]
            )

    # Volver a la semana que estábamos editando
    current_monday = (
        date.today()
        - timedelta(days=date.today().weekday())
    )

    week_offset = (
        allocation.week.week_start
        - current_monday
    ).days // 7

    return redirect(
        f"{reverse('life:planning')}?week={week_offset}"
    )


@login_required
def allocation_remove(request, pk):
    allocation = get_object_or_404(
        WeeklyTaskAllocation,
        pk=pk,
        week__user=request.user,
    )

    week_start = allocation.week.week_start

    if request.method == "POST":
        allocation.delete()

    current_monday = (
        date.today()
        - timedelta(days=date.today().weekday())
    )

    week_offset = (
        week_start - current_monday
    ).days // 7

    return redirect(
        f"{reverse('life:planning')}?week={week_offset}"
    )