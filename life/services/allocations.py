from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404

from ..models import Week, WeeklyTaskAllocation


class AllocationOutsideWeek(ValueError):
    pass


def allocation_for_user(*, user, pk):
    return get_object_or_404(
        WeeklyTaskAllocation.objects.select_related("week", "task"),
        pk=pk,
        week__user=user,
    )


def _ensure_date_in_week(allocation, planned_date):
    monday = allocation.week.week_start
    if not monday <= planned_date <= monday + timedelta(days=6):
        raise AllocationOutsideWeek


@transaction.atomic
def add_allocation(*, user, task, planned_date, planned_hours):
    hours = max(Decimal("0.5"), Decimal(planned_hours))
    monday = planned_date - timedelta(days=planned_date.weekday())
    week, _ = Week.objects.get_or_create(user=user, week_start=monday)
    allocation, created = WeeklyTaskAllocation.objects.get_or_create(
        week=week,
        task=task,
        planned_date=planned_date,
        defaults={"planned_hours": hours},
    )
    if not created:
        allocation.planned_hours += hours
        allocation.save(update_fields=["planned_hours"])
    if week.planning_mode == Week.PlanningMode.PASSIVE:
        week.planning_mode = Week.PlanningMode.MANUAL
        week.save(update_fields=["planning_mode"])
    return allocation


@transaction.atomic
def move_allocation(allocation, *, planned_date):
    _ensure_date_in_week(allocation, planned_date)
    existing = WeeklyTaskAllocation.objects.filter(
        week=allocation.week,
        task=allocation.task,
        planned_date=planned_date,
    ).exclude(pk=allocation.pk).first()
    if existing:
        existing.planned_hours += allocation.planned_hours
        existing.save(update_fields=["planned_hours"])
        allocation.delete()
        return existing
    allocation.planned_date = planned_date
    allocation.save(update_fields=["planned_date"])
    return allocation


@transaction.atomic
def update_allocation(allocation, *, planned_date, planned_hours):
    _ensure_date_in_week(allocation, planned_date)
    hours = max(Decimal("0.5"), Decimal(planned_hours))
    existing = WeeklyTaskAllocation.objects.filter(
        week=allocation.week,
        task=allocation.task,
        planned_date=planned_date,
    ).exclude(pk=allocation.pk).first()
    if existing:
        existing.planned_hours += hours
        existing.save(update_fields=["planned_hours"])
        allocation.delete()
        return existing
    allocation.planned_date = planned_date
    allocation.planned_hours = hours
    allocation.save(update_fields=["planned_date", "planned_hours"])
    return allocation


def remove_allocation(allocation):
    allocation.delete()


@transaction.atomic
def save_optimized_schedule(*, user, week_start, available_hours, schedule):
    """Reemplaza el calendario semanal por una propuesta optimizada."""
    week, _ = Week.objects.get_or_create(user=user, week_start=week_start)
    week.available_hours = available_hours
    week.planning_mode = Week.PlanningMode.OPTIMIZED
    week.save(update_fields=["available_hours", "planning_mode"])
    week.task_allocations.all().delete()
    allocations = []
    for day in schedule:
        for item in day["tasks"]:
            allocations.append(
                WeeklyTaskAllocation(
                    week=week,
                    task=item["task"],
                    planned_date=day["date"],
                    planned_hours=item["hours"],
                )
            )
    WeeklyTaskAllocation.objects.bulk_create(allocations)
    return week
