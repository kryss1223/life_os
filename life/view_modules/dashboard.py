from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..legacy_views import build_dashboard_context


@login_required
def dashboard(request):
    """Renderiza el dashboard usando su constructor de contexto aislado."""
    return render(
        request,
        "life/dashboard.html",
        build_dashboard_context(request),
    )
