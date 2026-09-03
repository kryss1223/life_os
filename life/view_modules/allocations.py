from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse

from ..selectors.tasks import task_for_user
from ..services.allocations import (
    AllocationOutsideWeek,
    add_allocation,
    allocation_for_user,
    move_allocation,
    remove_allocation,
    update_allocation,
)


def _planning_redirect(week_offset=0):
    return redirect(f"{reverse('life:planning')}?week={week_offset}")


def _offset_for(week_start):
    current_monday = date.today() - timedelta(days=date.today().weekday())
    return (week_start - current_monday).days // 7


@login_required
def allocation_create(request):
    if request.method != "POST":
        return redirect("life:planning")
    try:
        task = task_for_user(user=request.user, pk=request.POST.get("task_id"))
        planned_date = date.fromisoformat(request.POST.get("planned_date"))
        planned_hours = Decimal(request.POST.get("planned_hours", "0.5"))
        week_offset = int(request.POST.get("week_offset", 0))
    except (TypeError, ValueError, InvalidOperation):
        return redirect("life:planning")
    add_allocation(
        user=request.user,
        task=task,
        planned_date=planned_date,
        planned_hours=planned_hours,
    )
    return _planning_redirect(week_offset)


@login_required
def allocation_move(request, pk):
    allocation = allocation_for_user(user=request.user, pk=pk)
    if request.method != "POST":
        return redirect("life:planning")
    try:
        planned_date = date.fromisoformat(request.POST.get("planned_date"))
        move_allocation(allocation, planned_date=planned_date)
    except (TypeError, ValueError, AllocationOutsideWeek):
        pass
    return redirect("life:planning")


@login_required
def allocation_update(request, pk):
    allocation = allocation_for_user(user=request.user, pk=pk)
    week_start = allocation.week.week_start
    if request.method != "POST":
        return redirect("life:planning")
    try:
        planned_date = date.fromisoformat(request.POST.get("planned_date"))
        planned_hours = Decimal(request.POST.get("planned_hours"))
        update_allocation(
            allocation,
            planned_date=planned_date,
            planned_hours=planned_hours,
        )
    except (TypeError, ValueError, InvalidOperation, AllocationOutsideWeek):
        return redirect("life:planning")
    return _planning_redirect(_offset_for(week_start))


@login_required
def allocation_remove(request, pk):
    allocation = allocation_for_user(user=request.user, pk=pk)
    week_start = allocation.week.week_start
    if request.method == "POST":
        remove_allocation(allocation)
    return _planning_redirect(_offset_for(week_start))
