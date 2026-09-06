from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ..forms import PlanForm
from ..selectors.areas import area_for_user
from ..selectors.plans import plan_for_user


@login_required
def plan_create(request):
    initial = {}
    if request.method == "GET" and request.GET.get("area"):
        initial["life_area"] = area_for_user(
            user=request.user,
            pk=request.GET["area"],
        )

    form = PlanForm(request.POST or None, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        plan = form.save()
        return redirect("life:plan_detail", pk=plan.pk)
    return render(request, "life/plan_form.html", {"form": form})


@login_required
def plan_edit(request, pk):
    plan = plan_for_user(user=request.user, pk=pk)
    form = PlanForm(request.POST or None, instance=plan, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("life:plan_detail", pk=plan.pk)
    return render(request, "life/plan_form.html", {
        "form": form,
        "plan": plan,
        "editing": True,
    })


@login_required
def plan_delete(request, pk):
    plan = plan_for_user(user=request.user, pk=pk)
    if request.method == "POST":
        plan.delete()
    return redirect("life:plan_list")
