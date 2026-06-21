# Proyecto plantilla PyQt6

"""
README general del proyecto
--------------------------
Plantilla profesional para aplicaciones de escritorio en Python con PyQt6, diseñada para máxima modularidad, mantenibilidad y escalabilidad.

Premisas clave:
- Modularidad estricta y separación de responsabilidades.
- Tipado fuerte y uso de dataclasses en todos los modelos y funciones públicas.
- Encapsulamiento y protección de la lógica interna de cada módulo.
- Comunicación desacoplada entre componentes mediante interfaces, señales o eventos.
- Documentación exhaustiva y tests automáticos para toda funcionalidad.

Esta plantilla sigue el patrón Modelo-Vista-Controlador (MVC) y sirve como base para proyectos empresariales o personales que requieran calidad profesional, internacionalización y soporte multiplataforma.
"""

## Principios arquitectónicos clave

- **Modularidad estricta:** Cada módulo debe tener una única responsabilidad y exponer solo interfaces públicas claras. No debe haber dependencias circulares ni acoplamientos innecesarios.
- **Encapsulamiento:** La lógica interna de cada módulo debe estar protegida y no ser accesible desde otros módulos. Usar clases, métodos y atributos privados siempre que sea posible. Evitar el acceso directo a atributos; usar métodos públicos y privados (getters/setters).
- **Tipado fuerte:** Todo el código debe usar anotaciones de tipo (type hints) en funciones, métodos y modelos. Los modelos de datos deben implementarse preferentemente con dataclasses.
- **Separación de responsabilidades:** La lógica de negocio, la persistencia, la UI y las utilidades deben estar en módulos independientes y comunicarse solo mediante interfaces, eventos o señales.
- **Comunicación desacoplada:** Usar interfaces, eventos o señales para la comunicación entre módulos, evitando dependencias directas.

Estructura base para aplicaciones de escritorio en PyQt6 siguiendo el patrón Modelo-Vista-Controlador (MVC).

## Descripción

Esta plantilla proporciona una estructura modular y escalable para el desarrollo de aplicaciones de escritorio profesionales en Python con PyQt6.

## Estructura del proyecto

- src/core: lógica de negocio reutilizable
- src/gui: interfaz PyQt con paneles acoplables (QDockWidget) y persistencia de layout por workspace
- src/workspace: gestión de workspaces
- src/db: acceso a base de datos
- src/utils: utilidades generales
- src/i18n: internacionalización (gestión de idiomas y traducciones de la UI mediante ficheros JSON y función tr)
- src/resources/icons/light y src/resources/icons/dark: iconos PNG opcionales según modo claro/oscuro del SO.

## Gestión de iconos

- `get_app_icon("nombre")` elige automáticamente la carpeta `light/` o `dark/` según el modo del SO.
- Si no hay PNG, usa iconos estándar Qt (`QStyle`), visibles en claro y oscuro.
- Para iconos personalizados, añadir el mismo nombre en `light/` y `dark/`.
- Ver detalles y convenciones en `src/resources/icons/README.md` y `src/gui/icon_utils.py`.

## Requisitos

- Python 3.10+
- PyQt6
- pytest
- Recomendado: entorno virtual (venv)

## Instalación rápida

1. Clona el repositorio.
2. Crea y activa un entorno virtual:
   ```
   python -m venv venv
   source venv/bin/activate  # o .\venv\Scripts\activate en Windows
   ```
3. Instala dependencias:
   ```
   pip install -r requirements.txt
   ```
4. Ejecuta la aplicación:
   ```
   python src/main.py
   ```

## Gestión de dependencias y despliegue

- Todas las dependencias deben estar en requirements.txt.
- Usa siempre entorno virtual para aislar el proyecto.
- Para crear un ejecutable, se recomienda usar PyInstaller o herramientas similares.

## Tests y CI

- Ejecuta los tests con:
  ```
  PYTHONPATH=src python -m pytest tests
  PYTHONPATH=src python -m pytest tests_gui
  ```
  En PowerShell:
  ```
  $env:PYTHONPATH="src"; python -m pytest tests
  $env:PYTHONPATH="src"; python -m pytest tests_gui
  ```
- Se recomienda integrar CI (GitHub Actions, GitLab CI, etc.) para automatizar pruebas y calidad.

## Buenas prácticas y recomendaciones

- Separa claramente la lógica de negocio, persistencia, UI y utilidades en módulos independientes.
- Cada clase debe tener una única responsabilidad.
- Usa interfaces (como WorkspaceAware) para contratos entre módulos.
- Uso obligatorio de anotaciones de tipo (type hints) y dataclasses en todos los modelos y funciones públicas.
- Encapsula la lógica interna de cada clase y módulo; evita el acceso directo a atributos y usa siempre métodos públicos/privados (getters y setters).
- Añade docstrings claros y detallados a todas las clases y métodos públicos.
- Explica el propósito, argumentos y valores de retorno.
- Documenta contratos de interfaces y ejemplos de uso cuando sea relevante.
- Marca todos los textos traducibles usando la función `tr("clave")` de `i18n/json_translation.py` (no uses `self.tr()` de Qt).
- Para cambiar el idioma en caliente, usa `apply_language()` de `i18n/translation_utils.py`.
- Añade o edita las claves en los ficheros JSON de idioma (`es.json`, `en.json`, etc.) para cada nuevo texto.
- Para añadir un idioma, crea un nuevo fichero JSON siguiendo la estructura de los existentes.

- Maneja excepciones en puntos críticos y nunca dejes que una excepción no controlada rompa el flujo principal.
- Añade tests unitarios y de integración para toda nueva funcionalidad.
- Cubre casos límite y errores esperados (por ejemplo, restauración con config corrupto o incompleto).
- Mantén los textos de UI en español y codificados en UTF-8.
- Usa archivos de idioma para la internacionalización.
- Antes de hacer un merge, ejecuta todos los tests y asegúrate de que pasan.
- Revisa que la documentación y los type hints estén completos.
- Si modificas workspaces, mantén coherencia entre `WorkspaceController`, diálogos GUI y `workspaces.json`.
- Verifica que los métodos save_state y restore_state de los componentes aware usen siempre los atributos correctos y estén alineados con la arquitectura.
- Si detectas errores de atributo en logs, revisa y corrige los nombres de propiedades y su uso en toda la app.

## Referencias

- Consulta `docs/arquitectura_APP.md` para arquitectura CONTROLADORF, módulos y proyecto `.crf`.
- Consulta `docs/arquitectura_gral.md` para principios y convenciones de la plantilla.
- Consulta `docs/gui.md` para UI, apariencia adaptativa al SO y workspaces.
- Consulta `docs/db.md` para la capa SQLite.
- Consulta `docs/core.md` para servicios de negocio.
- Consulta `docs/import_workbench.md` e `docs/inventario_edicion.md` para inventario RF.
- Consulta **`docs/monitor.md`** para el módulo Monitor (SDR, espectro, supervisión y alarmas).
- Consulta **`docs/rf_engine/00_README.md`** para la arquitectura RF v1.0 (refactorización equipos SDR).
- Consulta **`docs/ayuda.md`** (es) / **`docs/help.md`** (en) para el manual de usuario (menú Ayuda).
- Consulta **`docs/monitor_supervision_ayuda.md`** (es) / **`docs/monitor_supervision_help.md`** (en) para supervisión RF.
- Consulta **`docs/distribucion_w11.md`** para generar el paquete ZIP de distribución Windows 11.
