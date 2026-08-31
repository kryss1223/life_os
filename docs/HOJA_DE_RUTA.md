# Hoja de ruta de Life OS

Esta es la secuencia acordada para convertir el prototipo actual en una base mantenible y preparada para clientes web y móvil.

## 1. Terminar la pantalla de planificación

- Extraer el calendario anual.
- Extraer la comparación entre importancia y tiempo.
- Extraer la construcción del calendario semanal.
- Separar el procesamiento del formulario automático.
- Trasladar `planning` fuera de `legacy_views.py`.

## 2. Eliminar definitivamente el código legado

- Retirar las funciones antiguas que ya estén reemplazadas.
- Limpiar imports duplicados y dependencias obsoletas.
- Confirmar que `legacy_views.py` queda sin responsabilidades.
- Eliminar `legacy_views.py`.
- Dividir las pruebas actuales por dominio.

## 3. Mejorar el modelo de datos

- Garantizar una semana única por usuario y fecha.
- Garantizar un impacto único por tarea y plan.
- Mantener `completed_at` sincronizado con el estado de la tarea.
- Validar que las relaciones no mezclen usuarios.
- Prevenir ciclos entre tareas padre e hijas.
- Crear migraciones de datos seguras para la base desplegada en Render.
- Añadir pruebas de migraciones, modelos y servicios.

Las decisiones sobre horas e impactos se definen en `DECISIONES_DE_PRODUCTO.md`.

## 4. Reorganizar la configuración

- Configurar idioma español.
- Configurar la zona horaria de Madrid.
- Extraer secretos y valores variables al entorno.
- Separar desarrollo y producción.
- Limpiar valores duplicados y opciones obsoletas.

## 5. Refactorizar CSS

- Inventariar reglas y componentes realmente utilizados.
- Definir tokens de color, espaciado, tipografía, radios y sombras.
- Separar base, layout, componentes y páginas.
- Eliminar duplicados y sobrescrituras accidentales progresivamente.
- Implementar una adaptación responsive consistente.

## 6. Preparar la aplicación móvil

- Crear una API versionada bajo `/api/v1/`.
- Definir autenticación para clientes móviles.
- Serializar áreas, planes, tareas, semanas y asignaciones.
- Exponer planificación manual y automática mediante servicios existentes.
- Definir respuestas y errores estables.
- Añadir pruebas independientes de las plantillas HTML.

## Criterio de avance

Cada fase debe conservar las pruebas anteriores, añadir cobertura para las reglas extraídas y actualizar la documentación cuando cambie una decisión funcional.
