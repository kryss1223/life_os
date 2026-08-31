"""Fachada pública de vistas.

Las URLs conservan sus imports históricos desde ``life.views``. Los dominios
refactorizados se exponen aquí y el resto se mantiene temporalmente aislado en
``legacy_views`` hasta completar su extracción.
"""

from .legacy_views import (
    planning,
)
from .view_modules.allocations import (
    allocation_create,
    allocation_move,
    allocation_remove,
    allocation_update,
)
from .view_modules.analytics import statistics, weekly_tracking
from .view_modules.catalog import plan_detail, plan_list, task_detail, task_list
from .view_modules.dashboard import dashboard
from .view_modules.areas import (
    life_area_create,
    life_area_delete,
    life_area_detail,
    life_area_edit,
    life_area_list,
)
from .view_modules.auth import register
from .view_modules.plans import plan_create, plan_delete, plan_edit
from .view_modules.tasks import task_create, task_delete, task_edit

__all__ = [
    "allocation_create",
    "allocation_move",
    "allocation_remove",
    "allocation_update",
    "dashboard",
    "life_area_create",
    "life_area_delete",
    "life_area_detail",
    "life_area_edit",
    "life_area_list",
    "plan_create",
    "plan_delete",
    "plan_detail",
    "plan_edit",
    "plan_list",
    "planning",
    "register",
    "statistics",
    "task_create",
    "task_delete",
    "task_detail",
    "task_edit",
    "task_list",
    "weekly_tracking",
]
