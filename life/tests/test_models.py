from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from ..models import LifeArea, Plan, Task, TaskImpact, Week


class TaskModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user("model-user", password="test-pass")
        cls.other = user_model.objects.create_user("model-other", password="test-pass")
        cls.area = LifeArea.objects.create(user=cls.user, name="Trabajo")
        cls.other_area = LifeArea.objects.create(user=cls.other, name="Privada")
        cls.plan = Plan.objects.create(life_area=cls.area, name="Proyecto")
        cls.other_plan = Plan.objects.create(life_area=cls.other_area, name="Secreto")

    def test_completed_at_tracks_completed_status(self):
        task = Task.objects.create(user=self.user, name="Entrega")
        self.assertIsNone(task.completed_at)
        task.status = Task.Status.COMPLETED
        task.save()
        self.assertIsNotNone(task.completed_at)
        completed_at = task.completed_at
        task.save()
        self.assertEqual(task.completed_at, completed_at)
        task.status = Task.Status.IN_PROGRESS
        task.save()
        self.assertIsNone(task.completed_at)

    def test_task_rejects_itself_as_parent(self):
        task = Task.objects.create(user=self.user, name="Circular")
        task.parent = task
        with self.assertRaises(ValidationError):
            task.full_clean()

    def test_task_rejects_parent_from_another_user(self):
        parent = Task.objects.create(user=self.other, name="Ajena")
        task = Task(user=self.user, name="Propia", parent=parent)
        with self.assertRaises(ValidationError):
            task.full_clean()

    def test_impact_rejects_plan_from_another_user(self):
        task = Task.objects.create(user=self.user, name="Propia")
        impact = TaskImpact(task=task, plan=self.other_plan, impact_percent=-10)
        with self.assertRaises(ValidationError):
            impact.full_clean()

    def test_duplicate_impact_is_rejected_but_negative_impact_is_valid(self):
        task = Task.objects.create(user=self.user, name="Propia")
        TaskImpact.objects.create(task=task, plan=self.plan, impact_percent=-10)
        duplicate = TaskImpact(task=task, plan=self.plan, impact_percent=20)
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

        other_plan = Plan.objects.create(life_area=self.area, name="Otro")
        negative = TaskImpact(task=task, plan=other_plan, impact_percent=-25)
        negative.full_clean()


class WeekModelTests(TestCase):
    def test_duplicate_week_is_rejected_during_validation(self):
        user = get_user_model().objects.create_user("week-user", password="test-pass")
        Week.objects.create(user=user, week_start="2026-08-31")
        duplicate = Week(user=user, week_start="2026-08-31")
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
