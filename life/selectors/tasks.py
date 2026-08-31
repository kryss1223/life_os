from django.shortcuts import get_object_or_404

from ..models import Task


def tasks_for_user(user):
    return Task.objects.filter(plans__life_area__user=user).distinct()


def task_for_user(*, user, pk):
    return get_object_or_404(tasks_for_user(user), pk=pk)
