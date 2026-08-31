from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ..presenters.catalog import (
    plan_detail_context,
    plan_list_context,
    task_detail_context,
    task_list_context,
)
from ..selectors.tasks import task_for_user
from ..services.tasks import add_actual_hours


@login_required
def plan_list(request):
    context = plan_list_context(
        user=request.user,
        current_filter=request.GET.get("filter", "all"),
        current_sort=request.GET.get("sort", "importance"),
    )
    return render(request, "life/plan_list.html", context)


@login_required
def plan_detail(request, pk):
    return render(request, "life/plan_detail.html", plan_detail_context(user=request.user, pk=pk))


@login_required
def task_list(request):
    context = task_list_context(
        user=request.user,
        current_filter=request.GET.get("filter", "all"),
        current_sort=request.GET.get("sort", "recent"),
    )
    return render(request, "life/task_list.html", context)


@login_required
def task_detail(request, pk):
    task = task_for_user(user=request.user, pk=pk)
    if request.method == "POST" and request.POST.get("action") == "add_hours":
        add_actual_hours(task, request.POST.get("hours_to_add", "0"))
        return redirect("life:task_detail", pk=task.pk)
    return render(request, "life/task_detail.html", task_detail_context(user=request.user, pk=pk))
