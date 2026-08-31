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

class DashboardViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user("dashboard", password="test-pass")
        cls.other = user_model.objects.create_user("dashboard-other", password="test-pass")
        area = LifeArea.objects.create(
            user=cls.user,
            name="Salud",
            current_satisfaction=70,
            weekly_hours_target=6,
        )
        plan = Plan.objects.create(life_area=area, name="Correr")
        task = Task.objects.create(name="Entrenamiento", estimated_hours=2)
        task.plans.add(plan, through_defaults={"impact_percent": 20})
        other_area = LifeArea.objects.create(user=cls.other, name="Oculta")
        other_plan = Plan.objects.create(life_area=other_area, name="Plan oculto")
        other_task = Task.objects.create(name="Tarea oculta")
        other_task.plans.add(other_plan, through_defaults={"impact_percent": 10})

    def test_dashboard_metrics_only_use_current_users_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("life:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_plans_count"], 1)
        self.assertEqual(response.context["active_tasks_count"], 1)
        self.assertEqual(response.context["life_balance"], 70)
        self.assertNotContains(response, "Plan oculto")

    def test_empty_dashboard_loads_with_zero_metrics(self):
        empty_user = get_user_model().objects.create_user("empty", password="test-pass")
        self.client.force_login(empty_user)
        response = self.client.get(reverse("life:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tasks_count"], 0)
        self.assertEqual(response.context["life_balance"], 0)

