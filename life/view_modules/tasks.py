from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ..forms import TaskForm, TaskImpactFormSet
from ..models import Task
from ..selectors.plans import plans_for_user
from ..selectors.tasks import task_for_user
from ..services.tasks import delete_task, save_task_with_impacts


def _task_forms(*, user, data=None, task):
    form = TaskForm(data, instance=task, user=user)
    formset = TaskImpactFormSet(data, instance=task)
    allowed_plans = plans_for_user(user)
    for impact_form in formset.forms:
        impact_form.fields["plan"].queryset = allowed_plans
    return form, formset


@login_required
def task_create(request):
    task = Task(user=request.user)
    data = request.POST if request.method == "POST" else None
    form, formset = _task_forms(user=request.user, data=data, task=task)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        task = save_task_with_impacts(form=form, formset=formset)
        return redirect("life:task_detail", pk=task.pk)
    return render(request, "life/task_form.html", {"form": form, "formset": formset})


@login_required
def task_edit(request, pk):
    task = task_for_user(user=request.user, pk=pk)
    old_plan_ids = list(task.impacts.values_list("plan_id", flat=True))
    data = request.POST if request.method == "POST" else None
    form, formset = _task_forms(user=request.user, data=data, task=task)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        task = save_task_with_impacts(
            form=form,
            formset=formset,
            old_plan_ids=old_plan_ids,
        )
        return redirect("life:task_detail", pk=task.pk)
    return render(request, "life/task_form.html", {
        "form": form,
        "formset": formset,
        "task": task,
        "editing": True,
    })


@login_required
def task_delete(request, pk):
    task = task_for_user(user=request.user, pk=pk)
    if request.method == "POST":
        delete_task(task)
    return redirect("life:task_list")
