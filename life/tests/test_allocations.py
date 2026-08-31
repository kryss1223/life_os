from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from .. import views
from ..models import LifeArea, Plan, Task, Week, WeeklyTaskAllocation
from ..presenters.planning import (
    area_time_balance,
    planning_week,
    saved_week_calendar,
    year_calendar,
)
from ..selectors.planning import eligible_planner_tasks
from ..services.allocations import save_optimized_schedule

class AllocationOwnershipTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user("owner", password="test-pass")
        cls.other_user = user_model.objects.create_user("other", password="test-pass")
        area = LifeArea.objects.create(user=cls.owner, name="Salud")
        plan = Plan.objects.create(life_area=area, name="Entrenamiento")
        task = Task.objects.create(name="Correr")
        task.plans.add(plan, through_defaults={"impact_percent": 10})
        week = Week.objects.create(user=cls.owner, week_start="2026-08-31")
        cls.allocation = WeeklyTaskAllocation.objects.create(
            week=week,
            task=task,
            planned_date="2026-08-31",
            planned_hours=1,
        )

    def test_user_cannot_update_another_users_allocation(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("life:allocation_update", kwargs={"pk": self.allocation.pk}),
            {"planned_hours": "2"},
        )
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_remove_another_users_allocation(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("life:allocation_remove", kwargs={"pk": self.allocation.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_create_repeated_allocation_adds_hours_and_marks_week_manual(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("life:allocation_create"),
            {
                "task_id": self.allocation.task_id,
                "planned_date": "2026-08-31",
                "planned_hours": "1.5",
                "week_offset": 0,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.allocation.refresh_from_db()
        self.allocation.week.refresh_from_db()
        self.assertEqual(self.allocation.planned_hours, 2.5)
        self.assertEqual(self.allocation.week.planning_mode, Week.PlanningMode.MANUAL)

    def test_update_enforces_half_hour_minimum(self):
        self.client.force_login(self.owner)
        self.client.post(
            reverse("life:allocation_update", kwargs={"pk": self.allocation.pk}),
            {"planned_date": "2026-08-31", "planned_hours": "0.1"},
        )
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.planned_hours, 0.5)

    def test_move_rejects_dates_outside_allocation_week(self):
        self.client.force_login(self.owner)
        self.client.post(
            reverse("life:allocation_move", kwargs={"pk": self.allocation.pk}),
            {"planned_date": "2026-09-07"},
        )
        self.allocation.refresh_from_db()
        self.assertEqual(str(self.allocation.planned_date), "2026-08-31")

