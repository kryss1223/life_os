# Arquitectura actual de Life OS

## 1. Propósito de este documento

Este documento explica cómo está organizado el proyecto después de la refactorización, dónde vive cada responsabilidad y qué recorrido sigue una petición desde la URL hasta la plantilla.

No sustituye la documentación funcional:

- `COMPORTAMIENTO_ACTUAL.md` describe qué hace la aplicación.
- `DECISIONES_DE_PRODUCTO.md` recoge decisiones sobre horas, finalización e impactos.
- `HOJA_DE_RUTA.md` contiene las fases acordadas.
- `INVENTARIO_CSS.md` documenta la reorganización y limpieza de estilos.

## 2. Estado general

La aplicación continúa siendo un proyecto Django renderizado en servidor. Las pantallas HTML existentes y sus URLs públicas se han conservado, pero la lógica ya no está concentrada en un único archivo de views.

Estado de las fases:

- Planificación: lógica extraída y comportamiento documentado.
- Código legado: `legacy_views.py` eliminado.
- Modelos: validaciones e invariantes añadidas con compatibilidad para datos antiguos.
- Configuración: desarrollo y producción separados.
- CSS: estructura separada por capas y dominios; rediseño visual pendiente.
- API móvil: pendiente; todavía no existe `/api/v1/`.

La suite actual contiene 38 pruebas y debe mantenerse en verde durante los siguientes cambios.

## 3. Flujo de una petición

El recorrido normal de una petición es:

```text
URL
  -> life.views (fachada pública)
  -> life.view_modules.<dominio> (HTTP, formularios y redirecciones)
  -> selector / service / presenter
  -> plantilla HTML
```

Cada capa tiene una responsabilidad concreta:

- URL: define el contrato web y el nombre de la ruta.
- Fachada `life.views`: mantiene estables los imports históricos usados por `urls.py`.
- View de dominio: interpreta la petición HTTP y decide qué respuesta devolver.
- Selector: lee datos y aplica el alcance del usuario.
- Service: realiza cambios, reglas de negocio y operaciones transaccionales.
- Presenter: transforma datos en estructuras preparadas para mostrar.
- Template: representa el resultado; no debe decidir reglas de negocio.

## 4. Fachada de views y módulos HTTP

`life/views.py` ya no contiene implementaciones. Es una fachada que importa y publica las funciones de `life/view_modules/`. Esto permite conservar `views.dashboard`, `views.planning`, etc. sin mantener toda la lógica en un solo archivo.

Los módulos HTTP actuales son:

- `view_modules/auth.py`: registro.
- `view_modules/areas.py`: crear, editar, listar, mostrar y eliminar áreas.
- `view_modules/plans.py`: crear, editar y eliminar planes.
- `view_modules/tasks.py`: crear, editar y eliminar tareas e impactos.
- `view_modules/catalog.py`: listados y detalles de planes y tareas.
- `view_modules/dashboard.py`: página principal.
- `view_modules/analytics.py`: seguimiento semanal y estadísticas.
- `view_modules/planning.py`: planificación manual y automática.
- `view_modules/allocations.py`: crear, actualizar, mover y eliminar asignaciones semanales.

Las views deben seguir siendo pequeñas. Pueden validar un formulario, llamar a una operación y elegir una plantilla o redirección. No deben volver a contener consultas extensas, cálculos de calendario o escrituras coordinadas entre varios modelos.

## 5. Selectors: lectura de datos

Los selectors viven en `life/selectors/` y concentran consultas reutilizables:

- `areas.py`: áreas pertenecientes a un usuario.
- `plans.py`: planes accesibles por un usuario.
- `tasks.py`: tareas del usuario, incluyendo la compatibilidad con tareas antiguas sin propietario directo.
- `analytics.py`: datos de estadísticas y seguimiento.
- `dashboard.py`: consultas necesarias para el dashboard.
- `planning.py`: tareas elegibles y datos de planificación.

Regla principal: toda consulta sobre datos privados debe limitarse al usuario autenticado. Las views y services deben reutilizar estos selectors en lugar de repetir filtros de pertenencia.

Los selectors no deben guardar ni eliminar datos.

## 6. Services: escritura y reglas de negocio

Los services viven en `life/services/`:

- `areas.py`: operaciones destructivas o coordinadas sobre áreas.
- `tasks.py`: guardado de tareas con impactos, borrado y registro de horas reales.
- `allocations.py`: persistencia y modificación de asignaciones semanales.
- `planning.py`: procesamiento de planificación y coordinación de casos de uso.
- `weekly_planner.py`: algoritmo que construye la propuesta semanal.
- `data_audit.py`: detección de inconsistencias en datos históricos.

Las operaciones que modifican varios objetos deben vivir aquí y usar transacciones cuando sea necesario. Esta capa será reutilizable por la futura API móvil; no debe depender de templates ni de mensajes visuales.

## 7. Presenters y composición de páginas

Los presenters viven en `life/presenters/`:

- `catalog.py`: estructuras para listados y detalles.
- `dashboard.py`: métricas y representación del dashboard.
- `planning.py`: calendario anual, balance de áreas y calendario semanal guardado.

Un presenter puede calcular etiquetas, porcentajes y estructuras de visualización, pero no debe modificar la base de datos.

`life/page_contexts.py` sigue actuando como compositor de alto nivel para Dashboard y Planning. Es una pieza transitoria válida: reúne resultados de selectors y presenters para crear el contexto final. Si crece de nuevo, debe dividirse por página o convertirse en presenters específicos; no debe absorber reglas de escritura.

## 8. Planificación

La planificación está separada en varias piezas:

- `view_modules/planning.py`: petición GET/POST y respuesta HTML.
- `selectors/planning.py`: selección de tareas y semanas.
- `presenters/planning.py`: calendario anual, balance y representación semanal.
- `services/planning.py`: procesamiento del caso de uso.
- `services/weekly_planner.py`: generación de la propuesta automática.
- `services/allocations.py`: persistencia de asignaciones.
- `view_modules/allocations.py`: endpoints HTML para operaciones manuales.

El algoritmo actual asigna trabajo buscando días disponibles y equilibrando carga global. No garantiza repartir cada tarea uniformemente a lo largo de todos los días anteriores a su fecha límite. Ese comportamiento está documentado y su mejora queda como cambio funcional futuro, no como refactorización.

## 9. Modelos e invariantes

Los modelos principales están en `life/models.py`: `LifeArea`, `Plan`, `Task`, `TaskImpact`, `Week`, snapshots, seguimiento y asignaciones semanales.

Reglas incorporadas:

- `Task.completed_at` se establece al completar una tarea y se limpia si vuelve a un estado no completado.
- Una tarea no puede ser su propio padre.
- Se previenen ciclos en la jerarquía de tareas.
- Las relaciones padre-hija no deben mezclar usuarios.
- Un impacto no debe conectar una tarea con un plan de otro usuario.
- No debe repetirse el impacto de la misma tarea sobre el mismo plan durante la validación.
- No debe repetirse una semana del mismo usuario y fecha durante la validación.

`Task.user` es nullable por compatibilidad con datos históricos. Los selectors admiten el propietario directo y, para registros antiguos, pueden inferirlo a través de planes relacionados cuando la relación es inequívoca.

Las restricciones de compatibilidad no deben endurecerse en base de datos sin una migración de auditoría y reparación previa. Los datos existentes se pueden revisar con el comando `audit_life_data`.

## 10. Formularios

Los formularios Django siguen en `life/forms.py`.

Responsabilidades permitidas:

- Validación propia de campos.
- Configuración de widgets.
- Limitar querysets de campos según el usuario.
- Preparar datos validados para un service.

La escritura coordinada de una tarea y sus impactos se realiza mediante services. `TaskForm` limita las tareas padre usando `selectors.tasks.tasks_for_user`, evitando mostrar objetos de otros usuarios.

## 11. Configuración por entorno

La configuración está dividida en:

- `config/settings/base.py`: configuración común, idioma español y zona horaria `Europe/Madrid`.
- `config/settings/development.py`: desarrollo local, `DEBUG`, SQLite y almacenamiento estático directo.
- `config/settings/production.py`: PostgreSQL, WhiteNoise y opciones de seguridad.
- `config/settings/__init__.py`: selecciona producción cuando `DJANGO_ENV=production` o existe `RENDER`; en otro caso usa desarrollo.

Las variables esperadas están documentadas en `.env.example`. Producción exige al menos `SECRET_KEY` y `DATABASE_URL`.

## 12. Organización CSS actual

El antiguo `life/static/life/css/style.css` fue eliminado. Sus 6900 líneas se separaron por responsabilidad:

```text
css/
  theme.css
  components.css
  core/
    base.css
    layout.css
  components/
    forms.css
    cards.css
    progress.css
  pages/
    areas.css
    plans.css
    tasks.css
    dashboard.css
  planning.css
```

Significado de cada capa:

- `theme.css`: tokens canónicos de color, espacio, tipografía, forma y elevación para light/dark.
- `components.css`: mini UI kit y estados interactivos compartidos.
- `base.css`: reset y estilos básicos del documento.
- `layout.css`: layout mobile-first, header, navegación inferior, sidebar de escritorio y menú de ajustes.
- `components/`: reglas heredadas todavía necesarias durante la migración de pantallas.
- `pages/`: estilos de un dominio o pantalla.
- `planning.css`: dominio de planificación, que mantiene varias interfaces relacionadas.

El CSS está preparado para un rediseño, pero no se considera visualmente final. Se inició un inventario de selectores y se retiraron bloques antiguos de Áreas y Planes. La limpieza restante se pausó porque la siguiente etapa prevista es rediseñar la interfaz.

Los estilos inline restantes suelen transportar valores dinámicos como porcentajes o colores. Durante el rediseño se recomienda convertirlos en variables CSS cuando sea posible, por ejemplo `style="--progress: ..."`, sin trasladar cálculos funcionales al CSS.

## 13. Pruebas

Las pruebas están divididas por dominio en `life/tests/`:

- autenticación y rutas;
- asignaciones;
- áreas;
- catálogo;
- analítica;
- dashboard;
- planificación;
- modelos.

La suite se ejecuta con:

```powershell
python manage.py test life.tests
```

También debe ejecutarse:

```powershell
python manage.py check
```

Las pruebas actuales cubren comportamiento de backend y presencia de las hojas CSS principales. No sustituyen una revisión visual del responsive.

## 14. Cómo añadir una funcionalidad

### Caso de solo lectura

1. Añadir o reutilizar un selector.
2. Añadir un presenter si la salida requiere transformación.
3. Crear una view pequeña en el módulo del dominio.
4. Registrar la URL a través de la fachada `life.views` si es una pantalla HTML.
5. Añadir plantilla y prueba del dominio.

### Caso con escritura

1. Definir la regla e invariantes.
2. Implementar la operación en un service.
3. Reutilizar selectors para comprobar pertenencia.
4. Hacer que la view o futura API llame al service.
5. Probar el service y la capa HTTP por separado.

### Nueva pantalla

1. Reutilizar componentes existentes.
2. Crear CSS en `pages/<dominio>.css` si es específico.
3. No añadir reglas de página a `core`.
4. Evitar lógica de negocio en el template.

## 15. Dependencias permitidas

La dirección recomendada es:

```text
view -> selector
view -> service
view -> presenter
service -> selector / model
presenter -> selector result / model read-only
template <- context preparado
```

Dependencias a evitar:

- selector -> view;
- service -> template;
- model -> view;
- presenter -> escritura en base de datos;
- template -> reglas de negocio complejas;
- API futura -> duplicación de servicios existentes.

## 16. Trabajo pendiente

Prioridades actuales:

1. Rediseñar la interfaz sobre la nueva estructura CSS y completar el responsive real.
2. Crear `/api/v1/` reutilizando selectors, services y presenters independientes de HTML.
3. Definir autenticación móvil y contrato estable de errores.
4. Serializar áreas, planes, tareas, semanas y asignaciones.
5. Añadir pruebas de API independientes de templates.
6. Auditar y, cuando sea seguro, endurecer restricciones de base de datos para datos históricos.

La regla general para continuar es conservar el comportamiento documentado, mantener las views finas y evitar que una capa vuelva a asumir responsabilidades de las demás.
