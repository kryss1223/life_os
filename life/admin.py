from django.contrib import admin

from .models import (
    LifeArea,
    LifeAreaSnapshot,
    Plan,
    Task,
    TaskImpact,
    WeeklyTracking,
    Week
)


class LifeAreaSnapshotInline(admin.TabularInline):
    model = LifeAreaSnapshot
    extra = 0
    fields = (
        "week",
        "satisfaction_start",
        "satisfaction_end",
        "hours_spent",
        "notes",
    )

    ordering = ("-week",)


class PlanInline(admin.TabularInline):
    model = Plan
    extra = 0
    fields = (
        "name",
        "status",
        "importance_weight",
        "progress",
        "estimated_hours",
        "target_date",
    )


@admin.register(LifeArea)
class LifeAreaAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
        "importance_weight",
        "current_satisfaction",
        "desired_satisfaction",
        "display_gap",
        "display_priority",
        "weekly_hours_target",
    )

    list_filter = (
        "user",
        "importance_weight",
    )

    search_fields = (
        "name",
        "description",
        "user__username",
    )

    ordering = ("-importance_weight",)

    inlines = [
        PlanInline,
        LifeAreaSnapshotInline,
    ]

    fieldsets = (
        ("Área", {
            "fields": (
                "user",
                "name",
                "description",
            )
        }),
        ("Estado actual", {
            "fields": (
                "importance_weight",
                "current_satisfaction",
                "desired_satisfaction",
            )
        }),
        ("Tiempo", {
            "fields": (
                "weekly_hours_target",
            )
        }),
    )

    @admin.display(description="Gap")
    def display_gap(self, obj):
        return obj.gap

    @admin.display(description="Prioridad")
    def display_priority(self, obj):
        return obj.priority_score


@admin.register(LifeAreaSnapshot)
class LifeAreaSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "life_area",
        "week",
        "satisfaction_start",
        "satisfaction_end",
        "hours_spent",
    )

    list_filter = (
        "life_area",
        "week",
    )

    search_fields = (
        "life_area__name",
        "notes",
    )

    ordering = ("-week",)


class TaskImpactInline(admin.TabularInline):
    model = TaskImpact
    extra = 1
    fields = (
        "plan",
        "impact_percent",
    )


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "life_area",
        "status",
        "importance_weight",
        "progress",
        "estimated_hours",
        "target_date",
    )

    list_filter = (
        "status",
        "life_area",
    )

    search_fields = (
        "name",
        "description",
        "life_area__name",
    )

    ordering = (
        "life_area",
        "-importance_weight",
    )

    fieldsets = (
        ("Plan", {
            "fields": (
                "life_area",
                "name",
                "description",
            )
        }),
        ("Seguimiento", {
            "fields": (
                "status",
                "importance_weight",
                "progress",
            )
        }),
        ("Planificación", {
            "fields": (
                "estimated_hours",
                "start_date",
                "target_date",
            )
        }),
    )


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "status",
        "parent",
        "estimated_hours",
        "actual_hours",
        "due_date",
    )

    list_filter = (
        "status",
        "due_date",
    )

    search_fields = (
        "name",
        "description",
        "plans__name",
    )

    ordering = (
        "status",
        "due_date",
    )

    inlines = [
        TaskImpactInline,
    ]

    fieldsets = (
        ("Tarea", {
            "fields": (
                "name",
                "description",
                "parent",
            )
        }),
        ("Seguimiento", {
            "fields": (
                "status",
                "estimated_hours",
                "actual_hours",
            )
        }),
        ("Fechas", {
            "fields": (
                "due_date",
                "completed_at",
            )
        }),
    )


@admin.register(TaskImpact)
class TaskImpactAdmin(admin.ModelAdmin):
    list_display = (
        "task",
        "plan",
        "impact_percent",
    )

    list_filter = (
        "plan",
    )

    search_fields = (
        "task__name",
        "plan__name",
    )


@admin.register(WeeklyTracking)
class WeeklyTrackingAdmin(admin.ModelAdmin):
    list_display = (
        "plan",
        "week",
        "planned_hours",
        "actual_hours",
        "progress_start",
        "progress_end",
        "display_progress_change",
    )

    list_filter = (
        "plan",
        "week",
    )

    search_fields = (
        "plan__name",
    )

    ordering = ("-week",)

    @admin.display(description="Cambio progreso")
    def display_progress_change(self, obj):
        return obj.progress_change

@admin.register(Week)
class WeekAdmin(admin.ModelAdmin):
    list_display = (
        "week_start",
        "user",
        "available_hours",
        "overall_satisfaction_start",
        "overall_satisfaction_end",
    )

    list_filter = ("week_start",)
    date_hierarchy = "week_start"
    ordering = ("-week_start",)