# Módulo resources

"""
README del módulo resources
--------------------------
Propósito: Centralizar y organizar todos los recursos estáticos de la aplicación (iconos, estilos, imágenes, etc.) de forma estructurada y coherente.

Premisas:
- Convenciones estrictas de nombres y organización por tema.
- Documentación de cualquier recurso especial o convención adicional.
- Pruebas de carga de recursos en la app antes de aceptar contribuciones.

Este módulo garantiza la coherencia visual y la mantenibilidad de los recursos gráficos.
"""

Este módulo contiene los recursos estáticos de la aplicación: iconos, estilos y otros archivos no Python.

## Estructura
- `icons/`: Iconos organizados por tema (`light/`, `dark/`).
- `styles/`: Hojas de estilo QSS para los temas visuales.
- Otros recursos estáticos.

## Convenciones
- Los iconos deben tener el mismo nombre en ambos temas (ej: `settings.png`, `workspaces.png`).
- Los estilos deben estar en archivos `.qss` y documentar el tema al que pertenecen.

## Ejemplo de uso en código
```python
from PyQt6.QtGui import QIcon
icon = QIcon("resources/icons/light/settings.png")
```
## Buenas prácticas
- Añade nuevos iconos en ambos temas.
- Usa nombres descriptivos y en minúsculas.
- Documenta cualquier recurso especial en este README.

## Checklist para contribuciones
- [ ] ¿El recurso está en la carpeta y tema correctos?
- [ ] ¿El nombre sigue la convención?
- [ ] ¿Se ha probado la carga del recurso en la app?
