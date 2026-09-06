# Design System de Life_OS

## Personalidad

**Life_OS = sofisticación lúdica.**

La interfaz debe sentirse clara, humana y positiva: superficies limpias, verde vivo, progreso visual, cards amables, animaciones suaves e ilustraciones ocasionales. No debe caer en una estética infantil ni en un dashboard empresarial frío.

## Fuente de verdad

- `life/static/life/css/theme.css`: tokens.
- `life/static/life/css/components.css`: UI kit.
- `life/static/life/css/core/base.css`: normalización y tipografía base.
- `life/static/life/css/core/layout.css`: layout responsive de la aplicación.
- `life/templates/life/base.html`: estructura, navegación y menú global.

No deben añadirse nuevos colores hexadecimales en CSS de página. Los estilos nuevos deben usar tokens como `--accent`, `--surface`, `--text`, `--border`, `--danger` o `--warning`.

Los aliases `--color-*` existen temporalmente para que las pantallas antiguas funcionen durante el rediseño. No deben utilizarse en componentes nuevos.

## Temas

El tema claro es el predeterminado. El oscuro se activa mediante `data-theme="dark"` en `<html>` y se persiste en `localStorage` con la clave `life-os-theme`.

## Tipografía

| Uso | Token | Tamaño |
|---|---|---|
| Título de página | `--font-page-title` | 28–32 px |
| Título de sección | `--font-section-title` | 20 px |
| Título de card | `--font-card-title` | 16 px |
| Cuerpo | `--font-body` | 14 px |
| Secundario | `--font-secondary` | 12 px |
| Caption | `--font-caption` | 11 px |

Nada funcional o importante debe mostrarse por debajo de 11 px.

## Componentes congelados

### Acciones

- `.ui-button` o `.button`: primaria.
- `.ui-button--secondary` o `.button-secondary`.
- `.ui-button--ghost` o `.button-ghost`.
- `.ui-button--danger` o `.button-danger`.
- `.icon-button`: acción solo con icono y área táctil mínima.

### Contenido

- `.ui-card`: card estándar.
- `.ui-card--interactive`: card clicable.
- `.ui-card--highlighted`: card destacada.
- `.ui-task-card`, `.ui-plan-card`, `.ui-area-card`: bases semánticas.
- `.metric-card`: métrica.
- `.ui-badge` con variantes `--active`, `--completed`, `--urgent`, `--pending` y `--focus`.
- `.ui-progress` / `.ui-progress__bar`.
- `.ui-progress-ring`, cuyo progreso se pasa mediante `--progress`.

### Formularios y selección

- `.ui-input`, `.ui-select` y `.form-control`.
- `.ui-slider`.
- `.ui-toggle` con `aria-pressed`.
- `.ui-week-selector`, `.ui-day-selector` y `.ui-selector-option`.

### Feedback

- `.ui-empty-state`.
- `.ui-toast`.
- `.ui-modal` y `.ui-modal__sheet`; en móvil actúa como bottom sheet y en escritorio como modal centrado.

### Navegación global

- `.app-header`: cabecera móvil.
- `.bottom-navigation`: navegación móvil con Inicio, Planning, Tareas, Planes y Áreas.
- `.desktop-sidebar`: la misma navegación expandida en escritorio.
- `.settings-menu`: Perfil, Ajustes, Notificaciones, Ayuda y soporte, Cerrar sesión y versión.

## Estados obligatorios

Los componentes interactivos deben contemplar:

- normal;
- `:hover` para puntero;
- `:active` como pressed móvil;
- `:focus-visible` para teclado;
- disabled mediante atributo o `.is-disabled`;
- seleccionado mediante `.is-selected`, `.is-active` o ARIA;
- error mediante `aria-invalid="true"` o `.is-error`.

## Layout mobile-first

Por debajo de 900 px:

- header fijo arriba;
- contenido con scroll central;
- navegación fija abajo;
- área táctil mínima de 44 px;
- una columna por defecto.

A partir de 900 px:

- desaparecen header y bottom navigation;
- aparece sidebar de 224 px;
- contenido centrado con máximo de 1200 px;
- la experiencia y la jerarquía de navegación siguen siendo las mismas.

## Regla para la Fase 2

Cada pantalla se rediseñará usando el kit antes de crear una clase nueva. Una clase específica de página solo se añade cuando no representa un patrón reutilizable. Django puede proporcionar datos y variables CSS dinámicas, pero no debe decidir colores o espaciados visuales.
