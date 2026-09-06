from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR


BLOCK_SIZE = Decimal("0.5")

DAY_NAMES = [
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
]


def format_hours(hours):
    rounded = Decimal(hours).quantize(Decimal("0.1"))
    return f"{rounded:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def task_importance_tuple(task):
    """Área, plan e impacto, respetando la relación concreta tarea-plan."""
    return max(
        (
            (
                impact.plan.life_area.importance_weight,
                impact.plan.importance_weight,
                impact.impact_percent,
            )
            for impact in task.impacts.all()
        ),
        default=(0, 0, Decimal("0")),
    )


def planner_priority_key(item):
    """Orden de elección de bloques; no modifica el cálculo proporcional."""
    area_weight, plan_weight, impact = task_importance_tuple(item["task"])
    return (
        -item["risk_level"],
        item["task"].due_date,
        -area_weight,
        -plan_weight,
        -impact,
        -item["hours_needed_this_week"],
        item["task"].name.lower(),
    )


def classify_urgency(days_remaining):
    if days_remaining <= 7:
        return "urgent", "Urgente"

    if days_remaining <= 28:
        return "upcoming", "Próximo"

    return "long_term", "Largo plazo"


def calculate_risk_level(days_left):
    if days_left <= 7:
        return 3, "CRITICAL"
    if days_left <= 14:
        return 2, "AT_RISK"
    if days_left <= 28:
        return 1, "NORMAL"
    return 0, "FLEXIBLE"


def calculate_task_weekly_load(task, today=None):
    today = today or date.today()

    if not task.due_date:
        return None

    estimated_hours = Decimal(
        str(task.estimated_hours or 0)
    )

    actual_hours = Decimal(
        str(task.actual_hours or 0)
    )

    if estimated_hours <= 0:
        return None

    # -------------------------
    # HORAS REALES RESTANTES
    # -------------------------

    remaining_hours = max(
        Decimal("0"),
        estimated_hours - actual_hours,
    )

    # Si ya hemos cubierto toda la estimación,
    # no necesita entrar en el planner.
    if remaining_hours <= 0:
        return None

    raw_days_left = (task.due_date - today).days
    days_left = max(raw_days_left, 0)
    weeks_left = max(
        Decimal(days_left) / Decimal("7"),
        Decimal("1") / Decimal("7"),
    )
    hours_needed_this_week = min(
        remaining_hours,
        remaining_hours / max(weeks_left, Decimal("1")),
    )
    risk_level, risk_label = calculate_risk_level(days_left)

    urgency, urgency_label = classify_urgency(
        raw_days_left
    )
    if raw_days_left < 0:
        urgency_label = "Vencida"

    return {
        "task": task,
        "estimated_hours": estimated_hours,
        "actual_hours": actual_hours,
        "remaining_hours": remaining_hours,
        "days_left": days_left,
        "weeks_left": weeks_left,
        "weeks_remaining": weeks_left,
        "hours_needed_this_week": hours_needed_this_week,
        "weekly_hours_needed": hours_needed_this_week,
        "risk_level": risk_level,
        "risk_label": risk_label,
        "urgency": urgency,
        "urgency_label": urgency_label,
        "overdue": raw_days_left < 0,
    }


def assign_calendar_blocks(
    task_loads,
    available_hours,
):
    """
    Convierte allocated_hours a bloques de 0.5h
    sin superar la capacidad semanal.
    """

    available_hours = Decimal(
        str(available_hours)
    )

    available_blocks = int(
        available_hours / BLOCK_SIZE
    )

    selected = [
        item
        for item in task_loads
        if (
            item["selected"]
            and item["allocated_hours"] > 0
        )
    ]

    for item in task_loads:
        item["calendar_hours"] = Decimal("0")
        item["_block_count"] = 0

    if not selected or available_blocks <= 0:
        return

    total_allocated = sum(
        (
            item["allocated_hours"]
            for item in selected
        ),
        Decimal("0"),
    )

    # Número de bloques que queremos usar.
    desired_blocks = int(
        (
            total_allocated / BLOCK_SIZE
        ).to_integral_value(
            rounding=ROUND_CEILING
        )
    )

    desired_blocks = min(
        desired_blocks,
        available_blocks,
    )

    base_blocks_used = 0

    # Primero damos los bloques completos
    # que corresponden a cada tarea.
    for item in selected:

        raw_blocks = (
            item["allocated_hours"]
            / BLOCK_SIZE
        )

        base_blocks = int(
            raw_blocks.to_integral_value(
                rounding=ROUND_FLOOR
            )
        )

        item["_raw_blocks"] = raw_blocks
        item["_block_count"] = base_blocks

        base_blocks_used += base_blocks

    # Los bloques sobrantes se reparten
    # según quién estaba más cerca
    # de necesitar otro bloque completo.
    remaining_blocks = max(
        0,
        desired_blocks - base_blocks_used,
    )

    candidates = sorted(
        selected,
        key=lambda item: planner_priority_key(item) + (
            -(
                item["_raw_blocks"]
                - Decimal(item["_block_count"])
            ),
        ),
    )

    while remaining_blocks > 0:

        changed = False

        for item in candidates:

            max_blocks = int(
                item["_raw_blocks"]
                .to_integral_value(
                    rounding=ROUND_CEILING
                )
            )

            if (
                item["_block_count"]
                < max_blocks
            ):
                item["_block_count"] += 1
                remaining_blocks -= 1
                changed = True

                if remaining_blocks <= 0:
                    break

        if not changed:
            break

    for item in selected:
        item["calendar_hours"] = (
            Decimal(item["_block_count"])
            * BLOCK_SIZE
        )


def build_weekly_plan(
    tasks,
    available_hours,
    include_saturday=False,
    include_sunday=False,
    selected_task_ids=None,
    planning_week_start=None,
    reserved_allocations=(),
    today=None,
):
    today = today or date.today()
    reserved_allocations = list(reserved_allocations)
    reserved_by_task = {}
    for allocation in reserved_allocations:
        reserved_by_task[allocation.task_id] = (
            reserved_by_task.get(allocation.task_id, Decimal("0"))
            + allocation.planned_hours
        )

    if planning_week_start is None:
        planning_week_start = (
            today
            - timedelta(days=today.weekday())
        )

    # Si planificamos esta semana, calculamos desde hoy.
    # Si es una semana futura, desde su lunes.
    reference_date = max(
        today,
        planning_week_start,
    )
    available_hours = Decimal(
        str(available_hours)
    )

    task_loads = []

    # -------------------------
    # 1. CALCULAR NECESIDAD
    # -------------------------

    for task in tasks:

        load = calculate_task_weekly_load(
            task,
            today=reference_date,
        )

        if load is None:
            continue

        # Primera generación:
        # todas seleccionadas.
        #
        # Actualización:
        # respetamos los checks.
        load["selected"] = (
            selected_task_ids is None
            or task.pk in selected_task_ids
            or task.pk in reserved_by_task
        )
        load["is_locked"] = any(
            allocation.is_locked and allocation.task_id == task.pk
            for allocation in reserved_allocations
        )
        load["weekly_hours_needed"] = max(
            Decimal("0"),
            load["weekly_hours_needed"] - reserved_by_task.get(task.pk, Decimal("0")),
        )
        load["hours_needed_this_week"] = load["weekly_hours_needed"]

        load["allocated_hours"] = Decimal("0")
        load["scheduled_hours"] = Decimal("0")
        load["unscheduled_hours"] = Decimal("0")

        task_loads.append(load)

    # -------------------------
    # 2. DEADLINE
    # -------------------------

    task_loads.sort(
        key=planner_priority_key
    )

    selected_loads = [
        item
        for item in task_loads
        if item["selected"]
    ]

    # -------------------------
    # 3. NECESIDAD TOTAL IDEAL
    # -------------------------

    total_needed = sum(
        (
            item["weekly_hours_needed"]
            for item in selected_loads
        ),
        Decimal("0"),
    )

    reserved_hours = sum(reserved_by_task.values(), Decimal("0"))
    flexible_hours = max(Decimal("0"), available_hours - reserved_hours)
    overloaded = total_needed > flexible_hours

    # -------------------------
    # 4. REFERENCIA DE CARGA
    # -------------------------

    if total_needed <= 0:
        load_factor = Decimal("0")

    else:
        load_factor = min(Decimal("1"), flexible_hours / total_needed)

    # -------------------------
    # 5. ASIGNACIÓN REAL
    # -------------------------

    capacity_left = flexible_hours

    for item in task_loads:

        if available_hours > 0:
            item["capacity_percent"] = (
                item["weekly_hours_needed"]
                / available_hours
                * Decimal("100")
            )
        else:
            item["capacity_percent"] = Decimal("0")

        if item["selected"]:
            item["allocated_hours"] = min(
                item["hours_needed_this_week"],
                capacity_left,
            )
            capacity_left -= item["allocated_hours"]
            item["capacity_deficit_hours"] = max(
                Decimal("0"),
                item["hours_needed_this_week"] - item["allocated_hours"],
            )
        else:
            item["allocated_hours"] = Decimal("0")
            item["capacity_deficit_hours"] = Decimal("0")

    # -------------------------
    # 6. BLOQUES DE 0.5H
    # -------------------------

    assign_calendar_blocks(
        task_loads,
        flexible_hours,
    )

    remaining_capacity = capacity_left
    deficit_hours = sum(
        (item["capacity_deficit_hours"] for item in selected_loads),
        Decimal("0"),
    )

    # -------------------------
    # 7. CALENDARIO
    # -------------------------

    weekly_schedule = distribute_weekly_schedule(
        selected_loads,
        available_hours,
        include_saturday=include_saturday,
        include_sunday=include_sunday,
        planning_week_start=planning_week_start,
        today=today,
        reserved_allocations=reserved_allocations,
    )
    warnings = [
        f"{day['name']}: los bloques fijados superan la capacidad del día; se mantienen en su fecha."
        for day in weekly_schedule
        if day.get("overloaded")
    ]
    if deficit_hours > 0:
        warnings.append(
            f"No caben {format_hours(deficit_hours)} h de necesidad semanal con la capacidad disponible."
        )

    return {
        "tasks": task_loads,
        "available_hours": available_hours,
        "total_needed": total_needed,
        "remaining_capacity": remaining_capacity,
        "deficit_hours": deficit_hours,
        "overloaded": overloaded,
        "load_factor": load_factor,
        "schedule": weekly_schedule,
        "warnings": warnings,
    }


def distribute_weekly_schedule(
    task_loads,
    available_hours,
    include_saturday=False,
    include_sunday=False,
    planning_week_start=None,
    today=None,
    reserved_allocations=(),
):
    today = today or date.today()

    if planning_week_start is None:
        planning_week_start = (
            today - timedelta(days=today.weekday())
        )

    monday = planning_week_start

    days = []

    # -------------------------
    # DÍAS DISPONIBLES
    # -------------------------

    for index in range(7):

        current_date = (
            monday
            + timedelta(days=index)
        )

        # No planificamos pasado.
        if current_date < today:
            continue

        if (
            index == 5
            and not include_saturday
        ):
            continue

        if (
            index == 6
            and not include_sunday
        ):
            continue

        days.append({
            "name": DAY_NAMES[index],
            "date": current_date,
            "capacity": Decimal("0"),
            "used_hours": Decimal("0"),
            "tasks": [],
        })

    if not days and not reserved_allocations:
        return []

    available_hours = Decimal(
        str(available_hours)
    )

    # -------------------------
    # CAPACIDAD POR DÍA
    # -------------------------

    total_blocks = int(
        available_hours / BLOCK_SIZE
    )

    base_blocks = (
        total_blocks // max(1, len(days))
    )

    extra_blocks = (
        total_blocks % max(1, len(days))
    )

    for index, day in enumerate(days):

        blocks = base_blocks

        if index < extra_blocks:
            blocks += 1

        day["capacity"] = (
            Decimal(blocks)
            * BLOCK_SIZE
        )

    # Los bloques fijados se insertan antes del reparto flexible. Esto no altera
    # la fórmula restaurada: únicamente reserva su espacio y conserva su fecha.
    for allocation in reserved_allocations:
        day = next((item for item in days if item["date"] == allocation.planned_date), None)
        if day is None:
            day = {
                "name": DAY_NAMES[allocation.planned_date.weekday()],
                "date": allocation.planned_date,
                "capacity": Decimal("0"),
                "used_hours": Decimal("0"),
                "tasks": [],
            }
            days.append(day)
        day["tasks"].append({
            "task": allocation.task,
            "hours": allocation.planned_hours,
            "is_locked": allocation.is_locked,
            "reserved": True,
        })
        day["used_hours"] += allocation.planned_hours
        day["overloaded"] = day["used_hours"] > day["capacity"] and day["date"] >= today
    days.sort(key=lambda item: item["date"])

    # -------------------------
    # DISTRIBUIR TAREAS
    # -------------------------

    for item in task_loads:

        remaining = item["calendar_hours"]

        if remaining <= 0:
            continue

        deadline = item["task"].due_date

        if deadline < today:
            eligible_days = [day for day in days if day["date"] >= today and not any(task.get("reserved") and task["task"].pk == item["task"].pk for task in day["tasks"])]

        else:
            eligible_days = [
                day
                for day in days
                if today <= day["date"] <= deadline and not any(task.get("reserved") and task["task"].pk == item["task"].pk for task in day["tasks"])
            ]

            # Deadline posterior a esta semana.
            if not eligible_days:
                eligible_days = [day for day in days if day["date"] >= today and not any(task.get("reserved") and task["task"].pk == item["task"].pk for task in day["tasks"])]

        while remaining > 0:

            possible_days = [
                day
                for day in eligible_days
                if (
                    day["used_hours"]
                    < day["capacity"]
                )
            ]

            if not possible_days:
                break

            # Día menos cargado.
            target_day = min(
                possible_days,
                key=lambda day: (
                    day["used_hours"],
                    day["date"],
                )
            )

            free_hours = (
                target_day["capacity"]
                - target_day["used_hours"]
            )

            assigned = min(
                BLOCK_SIZE,
                remaining,
                free_hours,
            )

            if assigned < BLOCK_SIZE:
                break

            existing = next(
                (
                    scheduled_task
                    for scheduled_task
                    in target_day["tasks"]
                    if (
                        scheduled_task["task"].pk
                        == item["task"].pk
                    )
                ),
                None,
            )

            if existing:
                existing["hours"] += assigned

            else:
                target_day["tasks"].append({
                    "task": item["task"],
                    "hours": assigned,
                    "urgency": item["urgency"],
                    "urgency_label":
                        item["urgency_label"],
                })

            target_day["used_hours"] += assigned
            remaining -= assigned

        item["scheduled_hours"] = (
            item["calendar_hours"]
            - remaining
        )

        item["unscheduled_hours"] = remaining

    return days
