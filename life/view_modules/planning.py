from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse

from ..page_contexts import build_planning_context


@login_required
def planning(request):
    context = build_planning_context(request)
    if "redirect_week_offset" in context:
        offset = context["redirect_week_offset"]
        return redirect(f"{reverse('life:planning')}?week={offset}")
    return render(request, "life/planning.html", context)
