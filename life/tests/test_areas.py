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

class LifeAreaViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user("areas-user", password="test-pass")
        cls.other_user = user_model.objects.create_user("areas-other", password="test-pass")
        cls.area = LifeArea.objects.create(user=cls.user, name="Salud")

    def test_list_only_contains_current_users_areas(self):
        LifeArea.objects.create(user=self.other_user, name="Privada")
        self.client.force_login(self.user)
        response = self.client.get(reverse("life:life_area_list"))
        self.assertContains(response, "Salud")
        self.assertNotContains(response, "Privada")
        self.assertContains(response, 'id="life-balance-modal"')
        self.assertContains(response, "data-open-balance")

    def test_detail_exposes_balance_modal_with_users_areas(self):
        LifeArea.objects.create(user=self.user, name="Trabajo")
        LifeArea.objects.create(user=self.other_user, name="Privada")
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("life:life_area_detail", kwargs={"pk": self.area.pk})
        )
        self.assertContains(response, "Balance de vida")
        self.assertContains(response, "Trabajo")
        self.assertNotContains(response, "Privada")

    def test_user_cannot_open_another_users_area(self):
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse("life:life_area_detail", kwargs={"pk": self.area.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_create_assigns_area_to_current_user(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("life:life_area_create"),
            {
                "name": "Familia",
                "description": "",
                "importance_weight": 70,
                "current_satisfaction": 50,
                "desired_satisfaction": 80,
                "weekly_hours_target": 5,
            },
        )
        self.assertRedirects(response, reverse("life:dashboard"), fetch_redirect_response=False)
        self.assertTrue(LifeArea.objects.filter(user=self.user, name="Familia").exists())
