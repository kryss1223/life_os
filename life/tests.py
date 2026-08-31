from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve, reverse

from . import views
from .models import LifeArea, Plan, Task, Week, WeeklyTaskAllocation
from .presenters.planning import planning_week
from .selectors.planning import eligible_planner_tasks
from .services.allocations import save_optimized_schedule


class AuthenticationTests(TestCase):
    protected_routes = (
        "life:dashboard",
        "life:life_area_list",
        "life:plan_list",
        "life:task_list",
        "life:weekly_tracking",
        "life:statistics",
        "life:planning",
    )

    def test_anonymous_users_are_redirected_from_protected_pages(self):
        for route_name in self.protected_routes:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertRedirects(
                    response,
                    f"{reverse('login')}?next={reverse(route_name)}",
                    fetch_redirect_response=False,
                )


class PlanningUrlTests(TestCase):
    def test_planning_route_resolves_to_planning_view(self):
        self.assertIs(resolve(reverse("life:planning")).func, views.planning)

    def test_allocation_move_route_is_available(self):
        url = reverse("life:allocation_move", kwargs={"pk": 12})
        self.assertEqual(url, "/planning/allocation/12/move/")
        self.assertIs(resolve(url).func, views.allocation_move)


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

    def test_user_cannot_open_another_users_task_detail(self):
        response = self.client.get(
            reverse("life:task_detail", kwargs={"pk": self.other_task.pk})
        )
        self.assertEqual(response.status_code, 404)


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
