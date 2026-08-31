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

class AutomaticPlanningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user("planner", password="test-pass")
        area = LifeArea.objects.create(user=cls.user, name="Trabajo")
        plan = Plan.objects.create(life_area=area, name="Entrega")
        cls.eligible = Task.objects.create(
            name="Con fecha",
            due_date="2026-09-04",
            estimated_hours=2,
        )
        cls.eligible.plans.add(plan, through_defaults={"impact_percent": 20})
        cls.without_date = Task.objects.create(name="Sin fecha", estimated_hours=2)
        cls.without_date.plans.add(plan, through_defaults={"impact_percent": 20})

    def test_week_navigation_clamps_offsets(self):
        data = planning_week("999", today=date(2026, 8, 31))
        self.assertEqual(data["week_offset"], 52)
        self.assertEqual(data["week_start"], date(2027, 8, 30))

    def test_only_open_dated_tasks_are_eligible(self):
        self.assertQuerySetEqual(eligible_planner_tasks(self.user), [self.eligible])

    def test_saving_optimized_schedule_replaces_existing_allocations(self):
        week = Week.objects.create(user=self.user, week_start="2026-08-31")
        WeeklyTaskAllocation.objects.create(
            week=week,
            task=self.eligible,
            planned_date="2026-08-31",
            planned_hours=1,
        )
        saved_week = save_optimized_schedule(
            user=self.user,
            week_start=date(2026, 8, 31),
            available_hours=5,
            schedule=[{
                "date": date(2026, 9, 1),
                "tasks": [{"task": self.eligible, "hours": 2}],
            }],
        )
        allocation = saved_week.task_allocations.get()
        self.assertEqual(allocation.planned_date, date(2026, 9, 1))
        self.assertEqual(allocation.planned_hours, 2)
        self.assertEqual(saved_week.planning_mode, Week.PlanningMode.OPTIMIZED)

    def test_area_balance_compares_relative_importance_and_time(self):
        second = LifeArea.objects.create(
            user=self.user,
            name="Salud",
            importance_weight=50,
            weekly_hours_target=9,
        )
        first = self.eligible.plans.get().life_area
        first.importance_weight = 50
        first.weekly_hours_target = 1
        first.save(update_fields=["importance_weight", "weekly_hours_target"])
        result = area_time_balance([first, second])
        self.assertEqual(result["importance_values"], [50.0, 50.0])
        self.assertEqual(result["time_values"], [10.0, 90.0])
        self.assertEqual(result["area_balance"][0]["status"], "under")

    def test_year_calendar_places_task_on_due_date(self):
        self.eligible.refresh_from_db()
        months = year_calendar(year=2026, tasks=[self.eligible])
        september_days = [
            day
            for week in months[8]["weeks"]
            for day in week
            if day is not None
        ]
        due_day = next(day for day in september_days if day["date"] == date(2026, 9, 4))
        self.assertEqual(due_day["tasks"], [self.eligible])

    def test_saved_week_calendar_builds_metrics_and_seven_days(self):
        self.eligible.refresh_from_db()
        week = Week.objects.create(
            user=self.user,
            week_start=date(2026, 8, 31),
            available_hours=5,
            planning_mode=Week.PlanningMode.MANUAL,
        )
        allocation = WeeklyTaskAllocation.objects.create(
            week=week,
            task=self.eligible,
            planned_date=date(2026, 9, 1),
            planned_hours=2,
        )
        result = saved_week_calendar(
            week=week,
            allocations=[allocation],
            week_start=date(2026, 8, 31),
        )
        self.assertEqual(len(result["saved_schedule"]), 7)
        self.assertEqual(result["saved_total_hours"], 2)
        self.assertEqual(result["saved_free_hours"], 3)
        self.assertEqual(result["saved_load_percent"], 40)
        self.assertTrue(result["calendar_is_fixed"])

    def test_planning_page_loads_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("life:planning"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["saved_schedule"]), 7)
        self.assertContains(response, "life/css/core/tokens.css")
        self.assertContains(response, "life/css/core/base.css")
        self.assertContains(response, "life/css/core/layout.css")
        self.assertContains(response, "life/css/core/responsive.css")
        self.assertContains(response, "life/css/components/buttons.css")
        self.assertContains(response, "life/css/components/forms.css")
        self.assertContains(response, "life/css/components/progress.css")
        self.assertContains(response, "life/css/components/cards.css")
        self.assertContains(response, "life/css/pages/areas.css")
        self.assertContains(response, "life/css/pages/plans.css")
        self.assertContains(response, "life/css/pages/tasks.css")
        self.assertContains(response, "life/css/pages/dashboard.css")
        self.assertNotContains(response, "life/css/style.css")
        self.assertContains(response, "life/css/planning.css")

    def test_calculate_action_returns_proposal_without_saving_week(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("life:planning"),
            {"available_hours": 5, "action": "calculate", "week_offset": 0},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["planner_result"])
        self.assertFalse(Week.objects.filter(user=self.user).exists())

    def test_save_action_persists_optimized_week(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("life:planning"),
            {
                "available_hours": 5,
                "action": "save",
                "week_offset": 0,
                "selected_tasks": [self.eligible.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        week = Week.objects.get(user=self.user)
        self.assertEqual(week.planning_mode, Week.PlanningMode.OPTIMIZED)
        self.assertEqual(week.available_hours, 5)
