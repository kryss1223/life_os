from django.urls import path
from . import views

app_name = "life"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("areas/", views.life_area_list, name="life_area_list"),
    path("areas/new/", views.life_area_create, name="life_area_create"),
    path("areas/<int:pk>/", views.life_area_detail, name="life_area_detail"),

    path("plans/", views.plan_list, name="plan_list"),
    path("plans/new/", views.plan_create, name="plan_create"),
    path("plans/<int:pk>/edit/", views.plan_edit, name="plan_edit"),
    path("plans/<int:pk>/", views.plan_detail, name="plan_detail"),
    path("plans/<int:pk>/delete/", views.plan_delete, name="plan_delete"),

    path("tasks/", views.task_list, name="task_list"),
    path("tasks/new/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),

    path("weekly/", views.weekly_tracking, name="weekly_tracking"),

    path("stats/", views.statistics, name="statistics"),

    path("planning/", views.planning, name="planning",),

    path("areas/<int:pk>/edit/", views.life_area_edit, name="life_area_edit",),

path("areas/<int:pk>/delete/", views.life_area_delete, name="life_area_delete",),
]

