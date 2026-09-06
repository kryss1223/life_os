from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..selectors.analytics import statistics_for_user, weekly_tracking_for_user


@login_required
def weekly_tracking(request):
    return render(
        request,
        "life/weekly_tracking.html",
        {"tracking": weekly_tracking_for_user(request.user)},
    )


@login_required
def statistics(request):
    return render(
        request,
        "life/statistics.html",
        statistics_for_user(request.user),
    )
