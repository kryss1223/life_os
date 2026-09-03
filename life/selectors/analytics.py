from django.db.models import Avg, Sum

from ..models import LifeArea, LifeAreaSnapshot, Plan, Task, WeeklyTracking


def weekly_tracking_for_user(user):
    return (
        WeeklyTracking.objects.filter(plan__life_area__user=user)
        .select_related("week", "plan", "plan__life_area")
        .order_by("-week__week_start")
    )


def statistics_for_user(user):
    areas = LifeArea.objects.filter(user=user)
    plans = Plan.objects.filter(life_area__user=user)
    tasks = Task.objects.filter(plans__life_area__user=user).distinct()
    snapshots = LifeAreaSnapshot.objects.filter(
        life_area__user=user
    ).select_related("week", "life_area")

    return {
        "area_count": areas.count(),
        "average_satisfaction": areas.aggregate(
            value=Avg("current_satisfaction")
        )["value"] or 0,
        "active_plans": plans.filter(status=Plan.Status.ACTIVE).count(),
        "completed_tasks": tasks.filter(status=Task.Status.COMPLETED).count(),
        "weekly_hours_target": areas.aggregate(
            value=Sum("weekly_hours_target")
        )["value"] or 0,
        "snapshots": snapshots.order_by("-week__week_start")[:20],
    }
