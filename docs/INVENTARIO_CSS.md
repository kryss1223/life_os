# Inventario CSS

## Alcance

El inventario cruza las clases definidas en las hojas CSS con las referencias presentes en plantillas, parciales, scripts embebidos y código Python.

Una clase sin coincidencia literal no se considera automáticamente eliminable. Django puede construir clases dinámicas, por ejemplo `status-{{ task.status }}`, y algunas variantes se aplican mediante datos calculados.

## Estado inicial

- 13 hojas CSS.
- 409 clases CSS únicas.
- 347 clases con una referencia literal en el proyecto.
- 62 clases sin coincidencia literal directa.
- 16 atributos `style` en las plantillas, usados principalmente para porcentajes, progreso y colores dinámicos.
- No hay archivos JavaScript externos; la interacción existente vive en scripts embebidos en las plantillas.

## Clasificación inicial

### Dinámicas: conservar

- Estados de tareas: `task-status-*`.
- Variantes del dashboard: `dash-pill-*`.
- Estados y tonos construidos desde valores de modelos o presentadores.

### Legado confirmado y eliminado

- Antiguo detalle de área: `.area-detail-header`, `.plans-grid`, `.plan-card`, `.plans-empty-state` e historial asociado.
- Motivo: ninguna de estas clases aparece en `life_area_detail.html` ni en otros HTML, scripts o código Python.
- Resultado: 453 líneas retiradas de `pages/areas.css`.
- Detalle antiguo de Plan: cabecera `.plan-detail-hero`, progreso `.plan-main-progress` y tarjetas `.plan-task-card`.
- Se conservaron `.plan-metrics`, seguimiento semanal y `TASK DASHBOARD`, porque la versión moderna los reutiliza.
- Resultado: 256 líneas de reglas antiguas y sus ajustes responsive huérfanos retirados de `pages/plans.css`.

### Pendiente de revisión manual

- Planning antiguo: conviven calendario anual, planificador guardado y propuesta automática; se revisará por subbloques.
- Estilos inline: se trasladarán cuando el valor pueda expresarse con una variable CSS sin perder datos dinámicos.

## Criterio de eliminación

Un bloque se elimina únicamente cuando todos sus selectores están ausentes de plantillas, parciales, scripts y generadores de clases del backend, y no actúa como base de una variante todavía utilizada.
