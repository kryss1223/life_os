from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from django.db.models import Sum


class LifeArea(models.Model):
    class Icon(models.TextChoices):
        HEART = "heart", "Corazón"
        TARGET = "target", "Objetivo"
        BRIEFCASE = "briefcase", "Trabajo"
        BOOK = "book-open", "Estudios"
        MUSIC = "music", "Música"
        STAR = "star", "Estrella"

    class Color(models.TextChoices):
        GREEN = "green", "Verde"
        BLUE = "blue", "Azul"
        PURPLE = "purple", "Morado"
        ORANGE = "orange", "Naranja"
        PINK = "pink", "Rosa"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="life_areas",
    )

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon_key = models.CharField(max_length=24, choices=Icon.choices, default=Icon.HEART)
    color_key = models.CharField(max_length=16, choices=Color.choices, default=Color.GREEN)

    importance_weight = models.PositiveSmallIntegerField(
    default=50,
    validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    current_satisfaction = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    desired_satisfaction = models.PositiveSmallIntegerField(
        default=80,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    weekly_hours_target = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    @property
    def area_progress(self):
        plans = self.plans.exclude(
            status=Plan.Status.CANCELLED
        )

        total_weight = sum(
            plan.importance_weight
            for plan in plans
        )

        if total_weight == 0:
            return Decimal("0")

        progress = sum(
            Decimal(plan.importance_weight)
            * plan.progress
            for plan in plans
    )   

        return progress / Decimal(total_weight)
    @property
    def gap(self):
        return self.desired_satisfaction - self.current_satisfaction

    @property
    def priority_score(self):
        return self.gap * self.importance_weight

    def __str__(self):
        return self.name




class Plan(models.Model):

    class Status(models.TextChoices):
        IDEA = "IDEA", "Idea"
        ACTIVE = "ACTIVE", "Activo"
        PAUSED = "PAUSED", "Pausado"
        COMPLETED = "COMPLETED", "Completado"
        CANCELLED = "CANCELLED", "Cancelado"

    life_area = models.ForeignKey(
        LifeArea,
        on_delete=models.CASCADE,
        related_name="plans",
    )

    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    importance_weight = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    estimated_hours = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
    )

    progress = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    start_date = models.DateField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def recalculate_progress(self):
        total = self.task_impacts.filter(
            task__status="COMPLETED"
        ).aggregate(
            total=Sum("impact_percent")
        )["total"] or Decimal("0")

        self.progress = max(
            Decimal("0"),
            min(Decimal("100"), total)
        )

        self.save(update_fields=["progress"])

    def __str__(self):
        return self.name


class Task(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        IN_PROGRESS = "IN_PROGRESS", "En progreso"
        COMPLETED = "COMPLETED", "Completada"
        CANCELLED = "CANCELLED", "Cancelada"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Nullable durante la migración progresiva de los datos desplegados.
    # Se convertirá en obligatorio cuando la auditoría de producción esté limpia.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
        null=True,
        blank=True,
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subtasks",
    )

    estimated_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
    )

    actual_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    plans = models.ManyToManyField(
        Plan,
        through="TaskImpact",
        related_name="tasks",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if not self.parent_id:
            return
        if self.pk and self.parent_id == self.pk:
            raise ValidationError({"parent": "Una tarea no puede ser su propia tarea principal."})
        if self.user_id and self.parent.user_id and self.parent.user_id != self.user_id:
            raise ValidationError({"parent": "La tarea principal pertenece a otro usuario."})

        visited = set()
        current = self.parent
        while current is not None:
            if current.pk in visited or (self.pk and current.pk == self.pk):
                raise ValidationError({"parent": "La jerarquía de tareas no puede contener ciclos."})
            visited.add(current.pk)
            current = current.parent

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        status_is_being_saved = update_fields is None or "status" in update_fields
        if status_is_being_saved:
            if self.status == self.Status.COMPLETED and self.completed_at is None:
                self.completed_at = timezone.now()
            elif self.status != self.Status.COMPLETED:
                self.completed_at = None
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"completed_at"}
        super().save(*args, **kwargs)
    
        for impact in self.impacts.select_related("plan"):
            impact.plan.recalculate_progress() 
            
    def __str__(self):
        return self.name
    
    


class TaskImpact(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="impacts",
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name="task_impacts",
    )

    impact_percent = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(-100), MaxValueValidator(100)],
    )

    def clean(self):
        super().clean()
        if self.task_id and self.plan_id:
            if self.task.user_id and self.task.user_id != self.plan.life_area.user_id:
                raise ValidationError({"plan": "El plan pertenece a otro usuario."})
            duplicate = TaskImpact.objects.filter(
                task_id=self.task_id,
                plan_id=self.plan_id,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError({"plan": "La tarea ya tiene un impacto para este plan."})

    def __str__(self):
        return f"{self.task} → {self.plan} ({self.impact_percent}%)"


class Week(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weeks",
    )

    week_start = models.DateField()

    available_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    

    overall_satisfaction_start = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )

    overall_satisfaction_end = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class PlanningMode(models.TextChoices):
        PASSIVE = "PASSIVE", "Sin planificación"
        MANUAL = "MANUAL", "Planificación manual"
        OPTIMIZED = "OPTIMIZED", "Optimizada"

    planning_mode = models.CharField(
        max_length=20,
        choices=PlanningMode.choices,
        default=PlanningMode.PASSIVE,
    )

    def clean(self):
        super().clean()
        if self.user_id and self.week_start:
            duplicate = Week.objects.filter(
                user_id=self.user_id,
                week_start=self.week_start,
            )
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError({"week_start": "Ya existe una semana con esta fecha."})

    def __str__(self):
        return str(self.week_start)


class LifeAreaSnapshot(models.Model):
    week = models.ForeignKey(
        Week,
        on_delete=models.CASCADE,
        related_name="area_snapshots",
        blank=True,
    )

    life_area = models.ForeignKey(
        LifeArea,
        on_delete=models.CASCADE,
        related_name="snapshots",
    )

    satisfaction_start = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ]
    )

    satisfaction_end = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ]
    )

    hours_spent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def satisfaction_change(self):
        return self.satisfaction_end - self.satisfaction_start

    class Meta:
        ordering = ["-week"]

    def __str__(self):
        return f"{self.life_area} - {self.week}"

class WeeklyTracking(models.Model):
    week = models.ForeignKey(
        Week,
        on_delete=models.CASCADE,
        related_name="plan_trackings",
        blank=True,
    )

    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name="weekly_tracking",
    )

    planned_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )

    actual_hours = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )

    progress_start = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )

    progress_end = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def progress_change(self):
        return self.progress_end - self.progress_start

    class Meta:
        ordering = ["-week"]

    def __str__(self):
        return f"{self.plan} - {self.week}"

class WeeklyTaskAllocation(models.Model):

    week = models.ForeignKey(
        Week,
        on_delete=models.CASCADE,
        related_name="task_allocations",
    )

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="weekly_allocations",
    )

    planned_date = models.DateField(
        null=True,
        blank=True,
    )

    planned_hours = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "planned_date",
            "task__due_date",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "week",
                    "task",
                    "planned_date",
                ],
                name="unique_task_allocation_per_day",
            )
        ]
