# Iconos

Iconografía **monocromática unificada** vía `gui/icon_utils.py` (glyphs Qt estándar).

## Uso

```python
from gui.icon_utils import get_app_icon, ICON_SIZE_MENU

action.setIcon(get_app_icon("settings", ICON_SIZE_MENU))
```

## Registro de nombres

| Clave | Uso |
|-------|-----|
| `settings` | Configuración |
| `workspaces` | Gestión de workspaces |
| `exit` / `close` | Cerrar / salir |
| `about` | Acerca de |
| `language` | Idioma |
| `panel1` / `panel2` / `panel3` | Paneles dock |
| `new` / `import` / `export` / `duplicate` / `delete` / `activate` | Acciones workspace |

Los iconos siguen la paleta claro/oscuro activa (sin colores fijos).

## Logo de la aplicación (Acerca de…)

Coloque **`brand.png`** (recomendado), **`logo.png`** o **`app.png`** en esta carpeta para sustituir el icono `.ico` en la ventana **Acerca de…** y como icono de ventana. Tamaño recomendado: **256×256** px o superior (PNG con transparencia).

Si no hay PNG, se usa `ico.ico` o un icono generado con las iniciales «RF».

Las carpetas `light/` y `dark/` están reservadas para overrides opcionales futuros; por defecto no se usan.
