from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ..presenters.catalog import (
    plan_detail_context,
    plan_list_context,
    task_detail_context,
    task_list_context,
)
from ..selectors.tasks import task_for_user
from ..services.tasks import add_actual_hours, create_subtask, toggle_subtask


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
        search_query=request.GET.get("q", ""),
    )
    return render(request, "life/task_list.html", context)


@login_required
def task_detail(request, pk):
    task = task_for_user(user=request.user, pk=pk)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_hours":
            add_actual_hours(task, request.POST.get("hours_to_add", "0"))
        elif action == "add_subtask":
            create_subtask(
                parent=task,
                user=request.user,
                name=request.POST.get("subtask_name"),
                estimated_hours=request.POST.get("estimated_hours", "0"),
                due_date=request.POST.get("due_date"),
            )
        elif action == "toggle_subtask":
            subtask = task.subtasks.filter(pk=request.POST.get("subtask_id")).first()
            if subtask:
                toggle_subtask(subtask)
        return redirect("life:task_detail", pk=task.pk)
    return render(request, "life/task_detail.html", task_detail_context(user=request.user, pk=pk))
