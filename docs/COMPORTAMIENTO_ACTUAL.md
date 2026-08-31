# Life OS: comportamiento funcional actual

Este documento describe lo que la aplicación hace **a fecha de 31 de agosto de 2026**, según el código existente. No define todavía el producto ideal. Su objetivo es servir como contrato de referencia durante la refactorización.

## 1. Propósito observado

Life OS permite a cada usuario organizar su vida en cuatro niveles relacionados:

1. **Áreas de vida**, con importancia, satisfacción y dedicación semanal deseada.
2. **Planes**, que representan objetivos dentro de un área.
3. **Tareas**, que pueden contribuir a uno o varios planes.
4. **Semanas y asignaciones**, que colocan horas de tareas en días concretos.

El sistema combina seguimiento subjetivo (satisfacción), progreso por objetivos y planificación temporal.

## 2. Usuarios y aislamiento de datos

- Un área pertenece directamente a un usuario.
- Los planes pertenecen al usuario de forma indirecta, a través de su área.
- Las tareas pertenecen de forma indirecta a los usuarios de sus planes.
- Una semana pertenece directamente a un usuario.
- Las asignaciones pertenecen indirectamente al usuario de su semana.
- Las pantallas funcionales requieren autenticación.
- Las consultas y operaciones refactorizadas impiden acceder a áreas, planes, tareas y asignaciones de otros usuarios.

### Ambigüedad importante

Una tarea puede estar vinculada a planes de varias áreas y el modelo no impide que esos planes sean de usuarios diferentes. La interfaz actual filtra los planes disponibles y evita crear normalmente esa situación, pero la base de datos no la prohíbe.

## 3. Áreas de vida

Cada área contiene:

- nombre y descripción;
- importancia entre 0 y 100, con valor inicial 50;
- satisfacción actual entre 0 y 100, inicialmente 50;
- satisfacción deseada entre 0 y 100, inicialmente 80;
- horas objetivo por semana, inicialmente 0.

### Cálculos

- `gap = satisfacción deseada - satisfacción actual`.
- `priority_score = gap × importancia`.
- El progreso del área es la media ponderada del progreso de sus planes no cancelados:

  `suma(importancia del plan × progreso del plan) / suma(importancias)`.

- Si la suma de importancias es cero, el progreso del área es cero.
- El cálculo no excluye planes en estado idea, pausado o completado; solamente excluye cancelados.

### Eliminación

Al eliminar un área se eliminan en cascada sus planes e impactos. Las tareas que, como consecuencia, se quedan sin ningún plan también se eliminan. Si una tarea todavía pertenece a otro plan, se conserva.

## 4. Planes

Un plan siempre pertenece a un área y contiene:

- nombre y descripción;
- importancia entre 0 y 100;
- horas estimadas;
- progreso entre 0 y 100;
- fechas opcionales de inicio y objetivo;
- estado: idea, activo, pausado, completado o cancelado.

El estado inicial es **activo** y el progreso inicial es cero.

### Progreso de un plan

El progreso no depende de las horas realizadas. Se calcula sumando el porcentaje de impacto de todas sus tareas cuyo estado sea `COMPLETED`:

`progreso = suma(impacto de tareas completadas)`.

El resultado se limita al intervalo 0–100. Por tanto:

- una tarea incompleta no aporta progreso;
- una tarea completada puede aportar impacto positivo o negativo;
- varias tareas pueden superar 100, pero el valor guardado queda en 100;
- una suma negativa queda guardada como 0;
- marcar manualmente un plan como completado no fuerza su progreso a 100.

El progreso se recalcula al guardar una tarea desde los flujos actuales, al modificar sus impactos y al eliminarla.

## 5. Tareas e impactos

Una tarea contiene:

- nombre y descripción;
- tarea padre opcional;
- horas estimadas y horas reales;
- fecha límite opcional;
- estado: pendiente, en progreso, completada o cancelada;
- fecha de finalización opcional (`completed_at`).

Una tarea se relaciona con uno o varios planes mediante un **impacto**, cuyo porcentaje permitido está entre -100 y 100.

### Significado operativo del impacto

Actualmente el impacto solo determina cuánto progresa un plan cuando la tarea está completada. No afecta directamente a:

- las horas estimadas;
- la prioridad del planificador;
- la satisfacción del área;
- el reparto de tiempo semanal.

Una misma tarea puede aportar porcentajes diferentes a varios planes. Al completarse, aporta simultáneamente a todos ellos.

### Jerarquía de tareas

- Una tarea puede tener una tarea padre.
- Al borrar la tarea padre, sus subtareas se borran en cascada.
- La jerarquía no interviene en el progreso ni en el planificador.
- La interfaz refactorizada solo ofrece como padre tareas del usuario y excluye la propia tarea.
- No existe todavía una validación de ciclos indirectos, por ejemplo A → B → A.

### Registro de horas

Desde el detalle de una tarea se pueden sumar horas reales positivas. Las horas se acumulan; no sustituyen el total existente. Un valor vacío, inválido, cero o negativo no modifica la tarea.

El código no marca automáticamente la tarea como completada cuando las horas reales alcanzan las estimadas.

## 6. Semanas y seguimiento

Una semana contiene:

- usuario y fecha de inicio;
- horas disponibles opcionales;
- satisfacción general inicial y final opcionales;
- notas;
- modo de planificación.

Los modos son:

- `PASSIVE`: sin planificación fijada;
- `MANUAL`: contiene asignaciones añadidas manualmente;
- `OPTIMIZED`: calendario generado y guardado por el planificador.

También existen dos modelos históricos:

- `LifeAreaSnapshot`: satisfacción inicial/final, horas y notas de un área en una semana.
- `WeeklyTracking`: horas y progreso inicial/final de un plan en una semana.

Ambos exponen el cambio como valor final menos valor inicial. En el comportamiento visible actual se consultan, pero no se ha localizado un flujo completo que cree y cierre automáticamente estos registros.

## 7. Planificación semanal automática

Solo entran en la propuesta automática las tareas que:

- pertenecen a algún plan del usuario;
- tienen fecha límite;
- no están completadas ni canceladas;
- tienen horas estimadas mayores que cero;
- aún tienen horas pendientes (`estimadas - reales > 0`).

### Necesidad semanal

Para cada tarea:

- `horas restantes = max(0, estimadas - reales)`;
- `semanas restantes = max(1, redondeo hacia arriba de días restantes / 7)`;
- `horas semanales necesarias = horas restantes / semanas restantes`.

Una tarea vencida necesita, idealmente, todas sus horas restantes durante la semana planificada.

### Urgencia

- hasta 7 días: urgente;
- de 8 a 28 días: próxima;
- más de 28 días: largo plazo;
- fecha pasada: vencida y urgente.

La urgencia sirve principalmente para etiquetar y ordenar visualmente. El reparto proporcional de capacidad no asigna un peso adicional por urgencia.

### Sobrecarga y reparto

- Si la necesidad total cabe en las horas disponibles, cada tarea recibe su necesidad ideal.
- Si no cabe, todas las tareas seleccionadas se reducen con el mismo factor proporcional:

  `factor = horas disponibles / necesidad total`.

- El calendario trabaja en bloques mínimos de 0,5 horas.
- Los redondeos sobrantes favorecen primero a las tareas cuya fracción estaba más cerca del siguiente bloque; la fecha límite actúa como desempate.

### Distribución entre días

- La capacidad semanal se distribuye de forma aproximadamente uniforme entre los días habilitados.
- Por defecto sábado y domingo están excluidos.
- Nunca se asignan bloques a días pasados.
- Una tarea con fecha dentro de la semana solo se coloca hasta su fecha límite.
- Una tarea vencida puede colocarse en cualquier día disponible.
- Cada bloque se coloca en el día elegible menos cargado; en empate gana el día anterior.

### Guardar una propuesta

Al guardar el plan optimizado:

1. se crea o recupera la semana;
2. se guardan sus horas disponibles;
3. el modo pasa a `OPTIMIZED`;
4. se eliminan **todas** las asignaciones existentes de esa semana;
5. se crean las asignaciones de la nueva propuesta.

Esto significa que guardar una optimización reemplaza también las asignaciones manuales previas de esa semana.

## 8. Planificación manual

- Se puede añadir una tarea abierta a una fecha con un mínimo de 0,5 horas.
- Si ya existe la misma tarea el mismo día, las horas se suman.
- Al añadir la primera asignación manual a una semana pasiva, el modo cambia a `MANUAL`.
- Una asignación solo puede moverse dentro de su propia semana.
- Si se mueve sobre otra asignación de la misma tarea y día, ambas se fusionan.
- Al actualizar una asignación, las horas menores de 0,5 se elevan a 0,5.
- Eliminar una asignación no cambia automáticamente el modo de la semana.

## 9. Dashboard, listados y estadísticas

El dashboard muestra una síntesis de:

- áreas y satisfacción media;
- planes activos y visibles;
- tareas abiertas y próximas fechas límite;
- foco basado en el primer plan activo ordenado por importancia y fecha;
- capacidad semanal disponible, asignada y libre;
- distribución del tiempo por áreas;
- calendario de la semana actual.

La pantalla de planificación también compara:

- porcentaje de importancia de cada área sobre la importancia total;
- porcentaje de horas objetivo del área sobre las horas objetivo totales.

La diferencia se clasifica como:

- menos de -5 puntos: poco tiempo;
- más de 5 puntos: mucho tiempo;
- entre ambos límites: equilibrado.

Las estadísticas cuentan áreas, planes activos y tareas completadas, calculan satisfacción media y suman las horas objetivo semanales.

## 10. Comportamientos dudosos o incompletos detectados

Estos puntos describen el código actual y deberán decidirse antes de tratarlos como reglas definitivas:

1. `completed_at` existe, pero no se actualiza automáticamente al cambiar el estado de una tarea.
2. El modelo permite impactos duplicados para la misma combinación tarea–plan porque no existe una restricción única explícita.
3. Una tarea puede quedar asociada a planes de usuarios diferentes mediante operaciones fuera de la interfaz.
4. Guardar un plan optimizado borra el calendario manual de esa semana.
5. La urgencia no da prioridad adicional cuando falta capacidad; todas las tareas se reducen proporcionalmente.
6. El progreso de un plan depende del estado completado y del impacto, no del esfuerzo realizado.
7. El progreso de un área puede incluir planes pausados, ideas y completados.
8. Las horas reales pueden superar las estimadas sin límite.
9. No existe una restricción única de una semana por usuario y fecha de inicio.
10. Algunas consultas históricas usan nombres como `week_start` directamente en modelos que realmente guardan una relación `week`; esas pantallas necesitan pruebas específicas.
11. La configuración usa UTC e idioma inglés aunque la interfaz está escrita en español.
12. El calendario anual usa nombres de meses dependientes del locale del servidor.

## 11. Contrato para la refactorización

Hasta que se tome una decisión funcional distinta, la refactorización debe:

- conservar estas fórmulas y estados;
- mantener las URLs y formularios visibles;
- mantener el aislamiento entre usuarios;
- no cambiar silenciosamente los criterios de selección del planificador;
- cubrir con pruebas cada regla antes de mover o reemplazar su implementación;
- registrar como decisión explícita cualquier cambio respecto a este documento.

Las decisiones ya confirmadas se registran en `DECISIONES_DE_PRODUCTO.md`. En particular, las horas reales pueden superar las estimadas y los impactos negativos son intencionales.
