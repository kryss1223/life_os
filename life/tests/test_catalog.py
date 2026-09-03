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

class PlanAndTaskViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user("work-user", password="test-pass")
        cls.other_user = user_model.objects.create_user("work-other", password="test-pass")
        cls.area = LifeArea.objects.create(user=cls.user, name="Trabajo")
        cls.other_area = LifeArea.objects.create(user=cls.other_user, name="Privada")
        cls.plan = Plan.objects.create(life_area=cls.area, name="Proyecto")
        cls.other_plan = Plan.objects.create(life_area=cls.other_area, name="Secreto")
        cls.task = Task.objects.create(
            name="Tarea propia",
            estimated_hours=4,
            actual_hours=1,
        )
        cls.task.plans.add(cls.plan, through_defaults={"impact_percent": 10})
        cls.other_task = Task.objects.create(name="Tarea privada")
        cls.other_task.plans.add(cls.other_plan, through_defaults={"impact_percent": 10})

    def setUp(self):
        self.client.force_login(self.user)

    def test_plan_create_only_offers_current_users_areas(self):
        response = self.client.get(reverse("life:plan_create"))
        queryset = response.context["form"].fields["life_area"].queryset
        self.assertQuerySetEqual(queryset, [self.area])

    def test_plan_create_can_preselect_an_owned_area(self):
        response = self.client.get(
            reverse("life:plan_create"),
            {"area": self.area.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"].initial["life_area"], self.area)

    def test_plan_create_cannot_preselect_another_users_area(self):
        response = self.client.get(
            reverse("life:plan_create"),
            {"area": self.other_area.pk},
        )

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_edit_another_users_plan(self):
        response = self.client.get(
            reverse("life:plan_edit", kwargs={"pk": self.other_plan.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_task_form_does_not_expose_another_users_tasks_as_parents(self):
        response = self.client.get(
            reverse("life:task_edit", kwargs={"pk": self.task.pk})
        )
        queryset = response.context["form"].fields["parent"].queryset
        self.assertNotIn(self.task, queryset)
        self.assertNotIn(self.other_task, queryset)

    def test_user_cannot_delete_another_users_task(self):
        response = self.client.post(
            reverse("life:task_delete", kwargs={"pk": self.other_task.pk})
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Task.objects.filter(pk=self.other_task.pk).exists())

    def test_plan_list_only_contains_current_users_plans(self):
        response = self.client.get(reverse("life:plan_list"))
        listed = [row["plan"] for row in response.context["plan_rows"]]
        self.assertIn(self.plan, listed)
        self.assertNotIn(self.other_plan, listed)

    def test_plan_detail_renders_roadmap_tracking_modal(self):
        response = self.client.get(
            reverse("life:plan_detail", kwargs={"pk": self.plan.pk})
        )
        self.assertContains(response, 'id="roadmap-modal"')
        self.assertContains(response, "data-open-roadmap")
        self.assertContains(response, 'data-roadmap-tab="milestones"')
        self.assertContains(response, 'data-roadmap-tab="weekly"')
        self.assertContains(response, self.task.name)

    def test_task_list_exposes_hour_based_progress(self):
        response = self.client.get(reverse("life:task_list"))
        own_row = next(
            row for row in response.context["task_rows"] if row["task"] == self.task
        )
        self.assertEqual(own_row["progress_percent"], 25)

    def test_task_detail_accumulates_actual_hours(self):
        response = self.client.post(
            reverse("life:task_detail", kwargs={"pk": self.task.pk}),
            {"action": "add_hours", "hours_to_add": "1.5"},
        )
        self.assertRedirects(
            response,
            reverse("life:task_detail", kwargs={"pk": self.task.pk}),
            fetch_redirect_response=False,
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.actual_hours, 2.5)

    def test_task_detail_renders_subtasks_modal(self):
        response = self.client.get(
            reverse("life:task_detail", kwargs={"pk": self.task.pk})
        )
        self.assertContains(response, 'id="subtasks-modal"')
        self.assertContains(response, "Subtareas y actividad")
        self.assertContains(response, "data-open-subtasks")

    def test_task_detail_can_create_and_toggle_subtask(self):
        detail_url = reverse("life:task_detail", kwargs={"pk": self.task.pk})
        response = self.client.post(
            detail_url,
            {
                "action": "add_subtask",
                "subtask_name": "Primer paso",
                "estimated_hours": "1.5",
            },
        )
        self.assertRedirects(response, detail_url, fetch_redirect_response=False)
        subtask = self.task.subtasks.get(name="Primer paso")
        self.assertEqual(subtask.user, self.user)
        self.assertEqual(subtask.estimated_hours, 1.5)

        self.client.post(
            detail_url,
            {"action": "toggle_subtask", "subtask_id": subtask.pk},
        )
        subtask.refresh_from_db()
        self.assertEqual(subtask.status, Task.Status.COMPLETED)
        self.assertIsNotNone(subtask.completed_at)

    def test_task_list_searches_by_name(self):
        response = self.client.get(reverse("life:task_list"), {"q": "propia"})
        self.assertContains(response, self.task.name)
        self.assertNotContains(response, self.other_task.name)

    def test_user_cannot_open_another_users_task_detail(self):
        response = self.client.get(
            reverse("life:task_detail", kwargs={"pk": self.other_task.pk})
        )
        self.assertEqual(response.status_code, 404)
