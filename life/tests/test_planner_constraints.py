from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.http import QueryDict
from django.test import TestCase
from django.urls import reverse

from life.models import LifeArea, Plan, Task, Week, WeeklyTaskAllocation
from life.services.allocations import move_allocation, update_allocation, remove_allocation
from life.services.planning import process_planning_submission
from life.services.weekly_planner import build_weekly_plan


class PlannerConstraintsTests(TestCase):
    def setUp(self):
        self.today = date(2026, 9, 7)
        self.user = get_user_model().objects.create_user('constraints')
        self.area = LifeArea.objects.create(user=self.user, name='Salud', importance_weight=80)
        self.plan = Plan.objects.create(life_area=self.area, name='Entrenar', importance_weight=80)
        self.task = self.make_task('Z importante', self.plan)
        self.week = Week.objects.create(user=self.user, week_start=self.today, available_hours=5, planning_mode=Week.PlanningMode.MANUAL)
        self.lock = WeeklyTaskAllocation.objects.create(week=self.week, task=self.task, planned_date=self.today + timedelta(days=1), planned_hours=2, is_locked=True)

    def make_task(self, name, plan):
        task = Task.objects.create(user=self.user, name=name, estimated_hours=2, due_date=self.today + timedelta(days=4))
        task.plans.add(plan, through_defaults={'impact_percent': 20})
        return task

    def submit(self, **values):
        data = QueryDict('', mutable=True)
        data.update({'action': 'calculate', 'selection_present': '1', **values})
        with patch('life.services.planning.timezone.localdate', return_value=self.today):
            return process_planning_submission(user=self.user, data=data, cleaned_data={'available_hours': 5, 'include_saturday': False, 'include_sunday': False}, week_start=self.today)

    def test_locked_block_keeps_date_hours_and_warns_on_overload(self):
        other = self.make_task('Otra', self.plan)
        result = build_weekly_plan([self.task, other], 5, planning_week_start=self.today, today=self.today, reserved_allocations=[self.lock])
        tuesday = next(d for d in result['schedule'] if d['date'] == self.lock.planned_date)
        self.assertEqual(tuesday['used_hours'], 2)
        self.assertEqual(tuesday['tasks'][0]['task'], self.task)
        self.assertTrue(tuesday['overloaded'])
        self.assertTrue(result['warnings'])
        self.assertLessEqual(sum(d['used_hours'] for d in result['schedule']), 5)
        self.assertFalse(any(t['task'] == self.task for d in result['schedule'] if d != tuesday for t in d['tasks']))

    def test_excluded_weekend_still_keeps_locked_block(self):
        self.lock.planned_date = self.today + timedelta(days=6)
        result = build_weekly_plan([], 0, planning_week_start=self.today, today=self.today, reserved_allocations=[self.lock])
        sunday = next(d for d in result['schedule'] if d['date'] == self.lock.planned_date)
        self.assertEqual(sunday['used_hours'], 2)
        self.assertTrue(sunday['overloaded'])

    def test_filters_exclude_unlocked_task_but_cannot_exclude_locked(self):
        other = self.make_task('Excluir', self.plan)
        result = self.submit(plan_filter='999999', urgency_filter='long_term').result
        scheduled = [t['task'].pk for d in result['schedule'] for t in d['tasks']]
        self.assertIn(self.task.pk, scheduled)
        self.assertNotIn(other.pk, scheduled)

    def test_manual_exclusion_and_locked_persistence_on_save(self):
        other = self.make_task('Excluir', self.plan)
        self.submit(action='save')
        self.lock.refresh_from_db()
        self.assertTrue(self.lock.is_locked)
        self.assertEqual(self.lock.planned_hours, Decimal('2'))
        self.assertFalse(self.week.task_allocations.filter(task=other).exists())

    def test_importance_breaks_equal_deadline_and_load(self):
        low_area = LifeArea.objects.create(user=self.user, name='Otra', importance_weight=10)
        low_plan = Plan.objects.create(life_area=low_area, name='Menor', importance_weight=10)
        low = self.make_task('A menor', low_plan)
        result = build_weekly_plan([low, self.task], Decimal('0.5'), planning_week_start=self.today, today=self.today)
        scheduled = [t['task'] for d in result['schedule'] for t in d['tasks']]
        self.assertEqual(scheduled, [self.task])
        low.due_date = self.today - timedelta(days=1)
        result = build_weekly_plan([low, self.task], Decimal('0.5'), planning_week_start=self.today, today=self.today)
        self.assertEqual(result['tasks'][0]['task'], low)

    def test_restored_proportional_hours_are_not_overridden_by_importance(self):
        low_area = LifeArea.objects.create(user=self.user, name='Baja importancia', importance_weight=1)
        low_plan = Plan.objects.create(life_area=low_area, name='Plan menor', importance_weight=1)
        urgent = self.make_task('Y urgente', low_plan)
        urgent.estimated_hours = 2
        urgent.due_date = self.today + timedelta(days=1)
        urgent.save(update_fields=['estimated_hours', 'due_date'])

        important_later = self.make_task('X importante', self.plan)
        important_later.estimated_hours = 4
        important_later.due_date = self.today + timedelta(days=6)
        important_later.save(update_fields=['estimated_hours', 'due_date'])

        result = build_weekly_plan(
            [important_later, urgent],
            Decimal('2'),
            include_saturday=True,
            include_sunday=True,
            planning_week_start=self.today,
            today=self.today,
        )
        loads = {item['task'].pk: item for item in result['tasks']}
        self.assertEqual(result['tasks'][0]['task'], urgent)
        self.assertEqual(loads[urgent.pk]['calendar_hours'], Decimal('0.5'))
        self.assertEqual(loads[important_later.pk]['calendar_hours'], Decimal('1.5'))

    def test_fill_phase_uses_capacity_an_urgent_task_cannot_fit_before_deadline(self):
        urgent = self.make_task('Urgente hoy', self.plan)
        urgent.due_date = self.today
        urgent.save(update_fields=['due_date'])
        later = self.make_task('Pendiente posterior', self.plan)
        later.estimated_hours = 4
        later.due_date = self.today + timedelta(days=4)
        later.save(update_fields=['estimated_hours', 'due_date'])

        result = build_weekly_plan([later, urgent], Decimal('2'), planning_week_start=self.today, today=self.today)
        loads = {item['task'].pk: item for item in result['tasks']}
        self.assertEqual(loads[urgent.pk]['scheduled_hours'], Decimal('0.5'))
        self.assertEqual(loads[later.pk]['scheduled_hours'], Decimal('1.5'))
        self.assertEqual(sum(day['used_hours'] for day in result['schedule']), Decimal('2'))

    def test_past_destination_rejected_for_move_and_update(self):
        self.lock.is_locked = False
        self.lock.save()
        with patch('life.services.allocations.timezone.localdate', return_value=self.today + timedelta(days=2)):
            for operation in (lambda: move_allocation(self.lock, planned_date=self.today), lambda: update_allocation(self.lock, planned_date=self.today, planned_hours=1)):
                with self.assertRaises(ValueError):
                    operation()
        self.lock.refresh_from_db()
        self.assertEqual(self.lock.planned_date, self.today + timedelta(days=1))

    def test_pin_can_be_toggled_and_locked_block_cannot_move_or_be_removed(self):
        with self.assertRaises(ValueError):
            move_allocation(self.lock, planned_date=self.today + timedelta(days=2))
        with self.assertRaises(ValueError):
            remove_allocation(self.lock)
        update_allocation(self.lock, planned_date=self.lock.planned_date, planned_hours=2, is_locked=False)
        self.lock.refresh_from_db()
        self.assertFalse(self.lock.is_locked)

    def test_current_view_does_not_modify_saved_calendar(self):
        self.client.force_login(self.user)
        before = list(self.week.task_allocations.values())
        with patch('life.page_contexts.date') as clock:
            clock.today.return_value = self.today
            response = self.client.get(reverse('life:planning') + '?week=0&view=week')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'planning-saved-week')
        self.assertContains(response, self.task.name)
        self.assertIsNone(response.context['planner_result'])
        self.assertEqual(before, list(self.week.task_allocations.values()))

    def test_past_days_preserved_when_regenerating(self):
        past = WeeklyTaskAllocation.objects.create(week=self.week, task=self.task, planned_date=self.today, planned_hours=1)
        self.today += timedelta(days=2)
        self.submit(action='save')
        self.assertTrue(WeeklyTaskAllocation.objects.filter(pk=past.pk).exists())
