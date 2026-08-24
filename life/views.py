from django.contrib.auth.decorators import login_required
from django.shortcuts import render,redirect,get_object_or_404


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
    WeeklyTracking,
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
    plans = (
        Plan.objects
        .filter(life_area__user=request.user)
        .select_related("life_area")
        .order_by("life_area", "-importance_weight")
    )

    return render(
        request,
        "life/plan_list.html",
        {"plans": plans},
    )




@login_required
def plan_detail(request, pk):
    plan = get_object_or_404(
        Plan.objects.select_related("life_area"),
        pk=pk,
        life_area__user=request.user,
    )

    tasks = plan.tasks.all().distinct()

    tracking = plan.weekly_tracking.all().order_by("-week")

    return render(
        request,
        "life/plan_detail.html",
        {
            "plan": plan,
            "tasks": tasks,
            "tracking": tracking,
        },
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
    tasks = (
        Task.objects
        .filter(plans__life_area__user=request.user)
        .prefetch_related("plans")
        .distinct()
        .order_by("status", "due_date")
    )

    return render(
        request,
        "life/task_list.html",
        {"tasks": tasks},
    )


@login_required
def task_detail(request, pk):
    task = get_object_or_404(
        Task.objects
        .filter(plans__life_area__user=request.user)
        .distinct(),
        pk=pk,
    )

    impacts = task.impacts.select_related(
        "plan",
        "plan__life_area",
    )

    subtasks = task.subtasks.all()

    return render(
        request,
        "life/task_detail.html",
        {
            "task": task,
            "impacts": impacts,
            "subtasks": subtasks,
        },
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

    area_names = [area.name for area in areas]

    importance_values = [
        round(
            (area.importance_weight / total_importance) * 100,
            1,
        )
        if total_importance
        else 0
        for area in areas
    ]

    time_values = [
        round(
            (float(area.weekly_hours_target) / total_target_hours) * 100,
            1,
        )
        if total_target_hours
        else 0
        for area in areas
    ]

    # -------------------------
    # TASK DEADLINES
    # -------------------------

    tasks = (
        Task.objects
        .filter(
            plans__life_area__user=request.user,
            due_date__year=year,
        )
        .exclude(due_date=None)
        .distinct()
    )

    tasks_by_date = defaultdict(list)

    for task in tasks:
        tasks_by_date[task.due_date].append(task)

    # -------------------------
    # CALENDARIO
    # -------------------------

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
        # DESAJUSTES IMPORTANCIA / TIEMPO
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
    }

    return render(
        request,
        "life/planning.html",
        context,
    )