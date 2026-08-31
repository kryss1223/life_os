from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ..forms import LifeAreaForm
from ..selectors.areas import area_for_user, areas_for_user
from ..services.areas import delete_area


@login_required
def life_area_create(request):
    form = LifeAreaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        area = form.save(commit=False)
        area.user = request.user
        area.save()
        return redirect("life:dashboard")
    return render(request, "life/life_area_form.html", {"form": form})


@login_required
def life_area_list(request):
    return render(request, "life/life_area_list.html", {"areas": areas_for_user(request.user)})


@login_required
def life_area_edit(request, pk):
    area = area_for_user(user=request.user, pk=pk)
    form = LifeAreaForm(request.POST or None, instance=area)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("life:life_area_detail", pk=area.pk)
    return render(request, "life/life_area_form.html", {"form": form, "area": area, "editing": True})


@login_required
def life_area_detail(request, pk):
    area = area_for_user(user=request.user, pk=pk)
    return render(request, "life/life_area_detail.html", {
        "area": area,
        "plans": area.plans.all(),
        "snapshots": area.snapshots.all().order_by("-week"),
    })


@login_required
def life_area_delete(request, pk):
    area = area_for_user(user=request.user, pk=pk)
    if request.method == "POST":
        delete_area(area)
        return redirect("life:life_area_list")
    return render(request, "life/life_area_confirm_delete.html", {"area": area})
