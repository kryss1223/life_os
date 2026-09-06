from django.shortcuts import get_object_or_404

from ..models import LifeArea


def areas_for_user(user):
    return (
        LifeArea.objects.filter(user=user)
        .prefetch_related("plans")
        .order_by("-importance_weight")
    )


def area_for_user(*, user, pk):
    return get_object_or_404(LifeArea, pk=pk, user=user)
