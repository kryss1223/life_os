# Decisiones de producto y migración

Este documento registra decisiones confirmadas durante la refactorización. Tienen prioridad sobre las ambigüedades recogidas en `COMPORTAMIENTO_ACTUAL.md`.

## 1. Horas reales y progreso temporal

- Las horas reales pueden superar las horas estimadas.
- Alcanzar las horas estimadas no completa automáticamente una tarea.
- El progreso visual calculado por horas continúa limitado a 100 %.
- Las horas reales conservan su valor completo aunque el progreso visual ya sea 100 %.
- Las horas estimadas representan una previsión, no un límite de trabajo permitido.

## 2. Impactos de tareas sobre planes

- Los impactos negativos son una función intencional del producto.
- Una tarea puede beneficiar a un plan y perjudicar a otro.
- El impacto permitido se mantiene entre -100 % y 100 %.
- Cuando una tarea se completa, su impacto se aplica al progreso de cada plan relacionado.
- El progreso persistido del plan continúa limitado al intervalo 0–100.
- No se exigirá que la suma de impactos de un plan sea exactamente 100.
- Sí se añadirá una restricción para impedir más de un impacto entre la misma tarea y el mismo plan.

## 3. Propiedad directa de tareas

Se acepta añadir un propietario directo a `Task` para simplificar permisos, consultas y la futura API móvil.

La migración deberá inferir el propietario desde los planes actuales. Si una tarea estuviera asociada a planes de usuarios diferentes, se tratará como conflicto de datos y no se elegirá un propietario silenciosamente.

## 4. Política para migraciones en producción

La base desplegada en Render contiene datos que deben preservarse. Las migraciones seguirán estas reglas:

1. No borrar ni recrear tablas con datos existentes.
2. No introducir de golpe campos obligatorios sin valor compatible.
3. Aplicar primero cambios aditivos y reversibles.
4. Auditar duplicados y relaciones conflictivas antes de añadir restricciones.
5. Crear migraciones de datos explícitas para normalizar registros existentes.
6. Detener la migración con un error descriptivo si aparecen datos ambiguos.
7. Añadir restricciones solo después de verificar los datos.
8. Probar la secuencia completa partiendo de una base con el esquema anterior.
9. Ejecutar una copia de seguridad de PostgreSQL en Render antes del despliegue.
10. No mezclar una migración delicada con cambios visuales o funcionales no relacionados.

## 5. Secuencia prevista para `Task.user`

La incorporación del propietario directo se realizará en varias fases:

1. Añadir `Task.user` permitiendo temporalmente valores nulos.
2. Rellenar el usuario cuando todos los planes relacionados pertenezcan al mismo propietario.
3. Detectar tareas sin plan o vinculadas a varios usuarios y generar un informe.
4. Resolver explícitamente esos casos antes de continuar.
5. Validar que no queda ninguna tarea sin propietario.
6. Convertir el campo en obligatorio.
7. Añadir índices y adaptar consultas, formularios y servicios.

No se asignará automáticamente el primer usuario encontrado cuando la propiedad sea ambigua.
