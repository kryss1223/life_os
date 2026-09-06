from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q

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
    if planned_date != allocation.planned_date and planned_date < timezone.localdate():
        raise ValueError("No puedes mover un bloque a un día pasado.")
    if allocation.is_locked and planned_date != allocation.planned_date:
        raise ValueError("Desfija el bloque antes de cambiar su día.")
    monday = allocation.week.week_start
    if not monday <= planned_date <= monday + timedelta(days=6):
        raise AllocationOutsideWeek


@transaction.atomic
def add_allocation(*, user, task, planned_date, planned_hours, is_locked=False):
    if planned_date < timezone.localdate():
        raise ValueError("No puedes añadir bloques en días pasados.")
    hours = max(Decimal("0.5"), Decimal(planned_hours))
    monday = planned_date - timedelta(days=planned_date.weekday())
    week, _ = Week.objects.get_or_create(user=user, week_start=monday)
    allocation, created = WeeklyTaskAllocation.objects.get_or_create(
        week=week,
        task=task,
        planned_date=planned_date,
        defaults={"planned_hours": hours, "is_locked": is_locked},
    )
    if not created:
        allocation.planned_hours += hours
        allocation.is_locked = allocation.is_locked or is_locked
        allocation.save(update_fields=["planned_hours", "is_locked"])
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
def update_allocation(allocation, *, planned_date, planned_hours, is_locked=None):
    _ensure_date_in_week(allocation, planned_date)
    hours = max(Decimal("0.5"), Decimal(planned_hours))
    existing = WeeklyTaskAllocation.objects.filter(
        week=allocation.week,
        task=allocation.task,
        planned_date=planned_date,
    ).exclude(pk=allocation.pk).first()
    if existing:
        existing.planned_hours += hours
        existing.is_locked = existing.is_locked or allocation.is_locked or bool(is_locked)
        existing.save(update_fields=["planned_hours", "is_locked"])
        allocation.delete()
        return existing
    allocation.planned_date = planned_date
    allocation.planned_hours = hours
    if is_locked is not None:
        allocation.is_locked = is_locked
    allocation.save(update_fields=["planned_date", "planned_hours", "is_locked"])
    return allocation


def remove_allocation(allocation):
    if allocation.is_locked:
        raise ValueError("Desfija el bloque antes de quitarlo del planning.")
    allocation.delete()


@transaction.atomic
def save_optimized_schedule(*, user, week_start, available_hours, schedule, preserve_past=False, include_saturday=False, include_sunday=False):
    """Reemplaza el calendario semanal por una propuesta optimizada."""
    week, _ = Week.objects.get_or_create(user=user, week_start=week_start)
    week.available_hours = available_hours
    week.planning_mode = Week.PlanningMode.OPTIMIZED
    week.include_saturday = include_saturday
    week.include_sunday = include_sunday
    week.save(update_fields=["available_hours", "planning_mode", "include_saturday", "include_sunday"])
    protected = Q(is_locked=True)
    if preserve_past:
        protected |= Q(planned_date__lt=timezone.localdate())
    kept = set(week.task_allocations.filter(protected).values_list("task_id", "planned_date"))
    week.task_allocations.exclude(protected).delete()
    allocations = []
    for day in schedule:
        for item in day["tasks"]:
            if (item["task"].pk, day["date"]) in kept:
                continue
            allocations.append(
                WeeklyTaskAllocation(
                    week=week,
                    task=item["task"],
                    planned_date=day["date"],
                    planned_hours=item["hours"],
                    is_locked=item.get("is_locked", False),
                )
            )
    WeeklyTaskAllocation.objects.bulk_create(allocations)
    return week
