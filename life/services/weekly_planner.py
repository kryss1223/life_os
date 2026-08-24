from datetime import date, timedelta
from decimal import Decimal



def calculate_task_weekly_load(task, today=None):
    today = today or date.today()

    if not task.due_date:
        return None

    estimated_hours = task.estimated_hours or Decimal("0")

    if estimated_hours <= 0:
        return None

    remaining_hours = estimated_hours

    days_remaining = (task.due_date - today).days

    if days_remaining < 0:
        return {
            "task": task,
            "remaining_hours": remaining_hours,
            "weeks_remaining": 0,
            "weekly_hours_needed": remaining_hours,
            "overdue": True,
        }

    weeks_remaining = max(
        1,
        (days_remaining + 6) // 7,
    )

    weekly_hours_needed = (
        remaining_hours / Decimal(weeks_remaining)
    )
    urgency, urgency_label = classify_urgency(days_remaining)

    return {
        "task": task,
        "remaining_hours": remaining_hours,
        "weeks_remaining": weeks_remaining,
        "weekly_hours_needed": weekly_hours_needed,
        "urgency": urgency,
        "urgency_label": urgency_label,
        "overdue": False,
    }


# IMPORTANTE: NO dentro de la función anterior
def build_weekly_plan(tasks,
    available_hours,
    include_saturday=False,
    include_sunday=False,):

    available_hours = Decimal(str(available_hours))

    task_loads = []

    # 1. Primero calculamos las tareas
    for task in tasks:
        load = calculate_task_weekly_load(task)

        if load is not None:
            task_loads.append(load)

    # 2. Luego las ordenamos por deadline
    task_loads.sort(
        key=lambda item: (
            item["task"].due_date,
            item["task"].name.lower(),
        )
    )

    # 3. Calculamos carga total
    total_needed = sum(
        (
            item["weekly_hours_needed"]
            for item in task_loads
        ),
        Decimal("0"),
    )

    # 4. % de capacidad
    for item in task_loads:
        if available_hours > 0:
            item["capacity_percent"] = (
                item["weekly_hours_needed"]
                / available_hours
                * Decimal("100")
            )
        else:
            item["capacity_percent"] = Decimal("0")

    remaining_capacity = available_hours - total_needed

    # 5. AHORA sí distribuimos las tareas por días
    weekly_schedule = distribute_weekly_schedule(
        task_loads,
        available_hours,
        include_saturday=include_saturday,
        include_sunday=include_sunday,
    )

    return {
        "tasks": task_loads,
        "available_hours": available_hours,
        "total_needed": total_needed,
        "remaining_capacity": remaining_capacity,
        "overloaded": total_needed > available_hours,
        "schedule": weekly_schedule,
    }


def classify_urgency(days_remaining):
    if days_remaining <= 7:
        return "urgent", "Urgente"

    if days_remaining <= 28:
        return "upcoming", "Próximo"

    return "long_term", "Largo plazo"


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


def distribute_weekly_schedule(
    task_loads,
    available_hours,
    include_saturday=False,
    include_sunday=False,
    today=None,
):
    today = today or date.today()

    # Lunes de esta semana
    monday = today - timedelta(days=today.weekday())

    days = []

    for index in range(7):
        current_date = monday + timedelta(days=index)

        # Días pasados
        if current_date < today:
            continue

        # Sábado
        if index == 5 and not include_saturday:
            continue

        # Domingo
        if index == 6 and not include_sunday:
            continue

        days.append({
            "name": DAY_NAMES[index],
            "date": current_date,
            "capacity": Decimal("0"),
            "used_hours": Decimal("0"),
            "tasks": [],
        })

    if not days:
        return []

    available_hours = Decimal(str(available_hours))

    # --------------------------------
    # REPARTIR CAPACIDAD ENTRE DÍAS
    # --------------------------------

    total_blocks = int(
        available_hours / BLOCK_SIZE
    )

    base_blocks = total_blocks // len(days)
    extra_blocks = total_blocks % len(days)

    for index, day in enumerate(days):

        blocks = base_blocks

        if index < extra_blocks:
            blocks += 1

        day["capacity"] = (
            Decimal(blocks) * BLOCK_SIZE
        )

    # --------------------------------
    # COLOCAR TAREAS
    # --------------------------------

    # task_loads ya debería venir ordenado
    # por deadline
    for item in task_loads:

        remaining = item["weekly_hours_needed"]

        deadline = item["task"].due_date

        # Si está atrasada, la intentamos hacer
        # cuanto antes durante esta semana
        if deadline < today:
            eligible_days = days

        else:
            eligible_days = [
                day
                for day in days
                if day["date"] <= deadline
            ]

            # Deadline posterior a esta semana
            if not eligible_days:
                eligible_days = days

        while remaining > 0:

            possible_days = [
                day
                for day in eligible_days
                if day["used_hours"] < day["capacity"]
            ]

            if not possible_days:
                break

            # Día que menos carga tenga
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

            if assigned <= 0:
                break

            # Si ya existe esa tarea ese día,
            # acumulamos horas
            existing = next(
                (
                    task
                    for task in target_day["tasks"]
                    if task["task"].pk
                    == item["task"].pk
                ),
                None,
            )

            if existing:
                existing["hours"] += assigned

            else:
                target_day["tasks"].append({
                    "task": item["task"],
                    "hours": assigned,
                    "urgency": item.get(
                        "urgency",
                        "long_term",
                    ),
                    "urgency_label": item.get(
                        "urgency_label",
                        "",
                    ),
                })

            target_day["used_hours"] += assigned
            remaining -= assigned

        item["scheduled_hours"] = (
            item["weekly_hours_needed"]
            - remaining
        )

        item["unscheduled_hours"] = remaining

    return days