from django import forms

from .models import LifeArea


class LifeAreaForm(forms.ModelForm):
    class Meta:
        model = LifeArea

        fields = [
            "name",
            "description",
            "importance_weight",
            "current_satisfaction",
            "desired_satisfaction",
            "weekly_hours_target",
        ]

        labels = {
            "name": "Nombre",
            "description": "Descripción",
            "importance_weight": "Importancia",
            "current_satisfaction": "Satisfacción actual",
            "desired_satisfaction": "Satisfacción deseada",
            "weekly_hours_target": "Horas objetivo por semana",
        }

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": "Ej: Estudios",
                    "class": "form-control",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "placeholder": "¿Qué representa esta área?",
                    "rows": 4,
                    "class": "form-control",
                }
            ),

            "importance_weight": forms.NumberInput(
                attrs={
                    "min": 0,
                    "max": 100,
                    "class": "form-control",
                }
            ),

            "current_satisfaction": forms.NumberInput(
                attrs={
                    "min": 0,
                    "max": 100,
                    "class": "form-control",
                }
            ),

            "desired_satisfaction": forms.NumberInput(
                attrs={
                    "min": 0,
                    "max": 100,
                    "class": "form-control",
                }
            ),

            "weekly_hours_target": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": "0.5",
                    "class": "form-control",
                }
            ),
        }





from django import forms
from django.forms import inlineformset_factory

from .models import Plan, Task, TaskImpact


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan

        fields = [
            "life_area",
            "name",
            "description",
            "importance_weight",
            "estimated_hours",
            "status",
            "start_date",
            "target_date",
        ]

        labels = {
            "life_area": "Área de vida",
            "name": "Nombre",
            "description": "Descripción",
            "importance_weight": "Importancia",
            "estimated_hours": "Horas estimadas",
            "status": "Estado",
            "start_date": "Fecha de inicio",
            "target_date": "Fecha objetivo",
        }

        widgets = {
            "life_area": forms.Select(attrs={"class": "form-control"}),

            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej: Aprender Machine Learning",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "¿Qué quieres conseguir con este plan?",
                }
            ),

            "importance_weight": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "max": 100,
                }
            ),

            "estimated_hours": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "step": "0.5",
                }
            ),

            "status": forms.Select(
                attrs={"class": "form-control"}
            ),

            "start_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),

            "target_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        if user:
            self.fields["life_area"].queryset = (
                self.fields["life_area"]
                .queryset
                .filter(user=user)
            )


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task

        fields = [
            "name",
            "description",
            "parent",
            "estimated_hours",
            "actual_hours",
            "status",
            "due_date",
        ]

        labels = {
            "name": "Nombre",
            "description": "Descripción",
            "parent": "Tarea principal",
            "estimated_hours": "Horas estimadas",
            "actual_hours": "Horas reales",
            "status": "Estado",
            "due_date": "Fecha límite",
        }

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ej: Leer capítulo de vectores",
                }
            ),

            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                }
            ),

            "parent": forms.Select(
                attrs={"class": "form-control"}
            ),

            "estimated_hours": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "step": "0.5",
                }
            ),

            "actual_hours": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "step": "0.5",
                }
            ),

            "status": forms.Select(
                attrs={"class": "form-control"}
            ),

            "due_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            from .selectors.tasks import tasks_for_user

            queryset = tasks_for_user(user)
            if self.instance and self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            self.fields["parent"].queryset = queryset


class TaskImpactForm(forms.ModelForm):
    class Meta:
        model = TaskImpact

        fields = [
            "plan",
            "impact_percent",
        ]

        labels = {
            "plan": "Plan",
            "impact_percent": "Impacto %",
        }

        widgets = {
            "plan": forms.Select(
                attrs={"class": "form-control"}
            ),

            "impact_percent": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": -100,
                    "max": 100,
                    "step": "0.5",
                }
            ),
        }


TaskImpactFormSet = inlineformset_factory(
    Task,
    TaskImpact,
    form=TaskImpactForm,
    extra=3,
    can_delete=True,
)


class WeeklyPlannerForm(forms.Form):
    available_hours = forms.IntegerField(
        min_value=0,
        max_value=84,
        initial=20,
        label="Horas disponibles esta semana",
        widget=forms.NumberInput(
            attrs={
                "type": "range",
                "min": "0",
                "max": "84",
                "step": "1",
                "id": "available-hours",
            }
        ),
    )

    exclude_saturday = forms.BooleanField(
        required=False,
        initial=True,
        label="Sábado no disponible",
    )

    exclude_sunday = forms.BooleanField(
        required=False,
        initial=True,
        label="Domingo no disponible",
    )
