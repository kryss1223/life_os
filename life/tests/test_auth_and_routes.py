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

