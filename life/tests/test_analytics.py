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

class AnalyticsViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user("analytics", password="test-pass")
        LifeArea.objects.create(
            user=cls.user,
            name="Salud",
            current_satisfaction=60,
            weekly_hours_target=5,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_statistics_page_loads_and_contains_current_totals(self):
        response = self.client.get(reverse("life:statistics"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["area_count"], 1)
        self.assertEqual(response.context["average_satisfaction"], 60)

    def test_weekly_tracking_page_loads_without_records(self):
        response = self.client.get(reverse("life:weekly_tracking"))
        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(response.context["tracking"], [])

