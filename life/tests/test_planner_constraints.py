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
from life.services.weekly_planner import build_weekly_plan, calculate_task_weekly_load


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

    def planner_winner(self, *tasks):
        result = build_weekly_plan(
            list(tasks),
            Decimal('0.5'),
            planning_week_start=self.today,
            today=self.today,
        )
        scheduled = [item['task'] for day in result['schedule'] for item in day['tasks']]
        self.assertEqual(len(scheduled), 1)
        return scheduled[0]

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

    def test_urgent_low_importance_beats_distant_high_importance(self):
        low_area = LifeArea.objects.create(user=self.user, name='Área menor', importance_weight=1)
        low_plan = Plan.objects.create(life_area=low_area, name='Plan menor', importance_weight=1)
        urgent = self.make_task('Z urgente', low_plan)
        urgent.due_date = self.today + timedelta(days=1)
        urgent.save(update_fields=['due_date'])
        distant = self.make_task('A lejana', self.plan)
        distant.estimated_hours = 20
        distant.due_date = self.today + timedelta(days=35)
        distant.save(update_fields=['estimated_hours', 'due_date'])
        self.assertEqual(self.planner_winner(distant, urgent), urgent)

    def test_temporal_fields_follow_remaining_days_and_weekly_need_formula(self):
        task = self.make_task('Cálculo temporal', self.plan)
        task.estimated_hours = 10
        task.actual_hours = 3
        task.due_date = self.today + timedelta(days=14)
        task.save(update_fields=['estimated_hours', 'actual_hours', 'due_date'])
        load = calculate_task_weekly_load(task, today=self.today)
        self.assertEqual(load['remaining_hours'], Decimal('7'))
        self.assertEqual(load['days_left'], 14)
        self.assertEqual(load['weeks_left'], Decimal('2'))
        self.assertEqual(load['hours_needed_this_week'], Decimal('3.5'))

    def test_risk_level_uses_discrete_deadline_bands(self):
        task = self.make_task('Bandas de riesgo', self.plan)
        for days_left, expected in ((0, 3), (7, 3), (8, 2), (14, 2), (15, 1), (28, 1), (29, 0)):
            with self.subTest(days_left=days_left):
                task.due_date = self.today + timedelta(days=days_left)
                load = calculate_task_weekly_load(task, today=self.today)
                self.assertEqual(load['risk_level'], expected)

    def test_same_urgency_prefers_greater_weekly_need(self):
        smaller = self.make_task('A menor necesidad', self.plan)
        greater = self.make_task('Z mayor necesidad', self.plan)
        greater.estimated_hours = 4
        greater.save(update_fields=['estimated_hours'])
        self.assertEqual(self.planner_winner(smaller, greater), greater)

    def test_same_risk_and_need_prefers_closer_deadline_over_importance(self):
        low_area = LifeArea.objects.create(user=self.user, name='Área cercana baja', importance_weight=1)
        low_plan = Plan.objects.create(life_area=low_area, name='Plan cercano bajo', importance_weight=1)
        closer = self.make_task('Z cercana', low_plan)
        closer.estimated_hours = 8
        closer.due_date = self.today + timedelta(days=8)
        closer.save(update_fields=['estimated_hours', 'due_date'])

        farther = self.make_task('A lejana importante', self.plan)
        farther.estimated_hours = 10
        farther.due_date = self.today + timedelta(days=10)
        farther.save(update_fields=['estimated_hours', 'due_date'])

        self.assertEqual(self.planner_winner(farther, closer), closer)

    def test_critical_task_due_first_day_gets_its_hours_before_later_larger_task(self):
        due_first_day = self.make_task('Tarea Y', self.plan)
        due_first_day.due_date = self.today
        due_first_day.save(update_fields=['due_date'])
        later_larger = self.make_task('Tarea X', self.plan)
        later_larger.estimated_hours = 4
        later_larger.due_date = self.today + timedelta(days=5)
        later_larger.save(update_fields=['estimated_hours', 'due_date'])

        result = build_weekly_plan(
            [later_larger, due_first_day],
            Decimal('10'),
            planning_week_start=self.today,
            today=self.today,
        )
        monday = next(day for day in result['schedule'] if day['date'] == self.today)
        monday_hours = {item['task'].pk: item['hours'] for item in monday['tasks']}
        self.assertEqual(monday_hours[due_first_day.pk], Decimal('2'))
        self.assertNotIn(later_larger.pk, monday_hours)
        scheduled = {
            task.pk: sum(
                (item['hours'] for day in result['schedule'] for item in day['tasks'] if item['task'].pk == task.pk),
                Decimal('0'),
            )
            for task in (due_first_day, later_larger)
        }
        self.assertEqual(scheduled[due_first_day.pk], Decimal('2'))
        self.assertEqual(scheduled[later_larger.pk], Decimal('4'))

    def test_same_urgency_and_need_prefers_area_importance(self):
        low_area = LifeArea.objects.create(user=self.user, name='Área baja', importance_weight=5)
        high_area = LifeArea.objects.create(user=self.user, name='Área alta', importance_weight=95)
        low_plan = Plan.objects.create(life_area=low_area, name='Plan bajo', importance_weight=50)
        high_plan = Plan.objects.create(life_area=high_area, name='Plan alto', importance_weight=50)
        low = self.make_task('A área baja', low_plan)
        high = self.make_task('Z área alta', high_plan)
        self.assertEqual(self.planner_winner(low, high), high)

    def test_same_area_prefers_plan_importance(self):
        low_plan = Plan.objects.create(life_area=self.area, name='Plan bajo', importance_weight=5)
        high_plan = Plan.objects.create(life_area=self.area, name='Plan alto', importance_weight=95)
        low = self.make_task('A plan bajo', low_plan)
        high = self.make_task('Z plan alto', high_plan)
        self.assertEqual(self.planner_winner(low, high), high)

    def test_equal_urgency_need_area_and_plan_prefers_impact(self):
        low = self.make_task('A impacto bajo', self.plan)
        high = self.make_task('Z impacto alto', self.plan)
        low.impacts.update(impact_percent=5)
        high.impacts.update(impact_percent=95)
        self.assertEqual(self.planner_winner(low, high), high)

    def test_two_phase_allocation_respects_risk_and_reports_explicit_deficit(self):
        low_area = LifeArea.objects.create(user=self.user, name='Área crítica baja', importance_weight=30)
        low_plan = Plan.objects.create(life_area=low_area, name='Plan crítico bajo', importance_weight=40)
        critical = self.make_task('A crítica', low_plan)
        critical.due_date = self.today + timedelta(days=2)
        critical.save(update_fields=['due_date'])

        high_area = LifeArea.objects.create(user=self.user, name='Área normal alta', importance_weight=100)
        high_plan = Plan.objects.create(life_area=high_area, name='Plan normal alto', importance_weight=100)
        normal = self.make_task('B normal', high_plan)
        normal.estimated_hours = 15
        normal.due_date = self.today + timedelta(days=21)
        normal.save(update_fields=['estimated_hours', 'due_date'])

        result = build_weekly_plan([normal, critical], Decimal('2'), planning_week_start=self.today, today=self.today)
        loads = {item['task'].pk: item for item in result['tasks']}
        self.assertEqual(loads[critical.pk]['allocated_hours'], Decimal('2'))
        self.assertEqual(loads[normal.pk]['allocated_hours'], Decimal('0'))
        self.assertEqual(loads[normal.pk]['capacity_deficit_hours'], Decimal('5'))
        self.assertEqual(result['deficit_hours'], Decimal('5'))
        self.assertEqual(result['remaining_capacity'], Decimal('0'))
        self.assertTrue(any('5 h' in warning for warning in result['warnings']))

    def test_two_phase_allocation_leaves_surplus_capacity_free(self):
        task = self.make_task('Necesidad pequeña', self.plan)
        result = build_weekly_plan([task], Decimal('5'), planning_week_start=self.today, today=self.today)
        self.assertEqual(result['tasks'][0]['allocated_hours'], Decimal('2'))
        self.assertEqual(result['remaining_capacity'], Decimal('3'))
        self.assertEqual(result['deficit_hours'], Decimal('0'))

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
