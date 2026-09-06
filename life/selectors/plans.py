from django.shortcuts import get_object_or_404

from ..models import Plan


def plans_for_user(user):
    return Plan.objects.filter(life_area__user=user)


def plan_for_user(*, user, pk):
    return get_object_or_404(plans_for_user(user).select_related("life_area"), pk=pk)
