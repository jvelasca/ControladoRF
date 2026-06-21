# Arquitectura del proyecto

"""
Resumen arquitectónico
----------------------
Este documento define la arquitectura de referencia para este proyecto basado en una plantilla PyQt6 generica creada por mi, estableciendo las bases para un desarrollo profesional, mantenible y escalable.

Incluye:
- Principios de diseño y desarrollo (modularidad, tipado fuerte, encapsulamiento, validación, desacoplamiento, documentación y pruebas).
- Patrón arquitectónico Modelo-Vista-Controlador (MVC) y su aplicación práctica.
- Estructura de carpetas y responsabilidades de cada módulo.
- Convenciones clave para temas, internacionalización, persistencia y gestión de workspaces.
- Decisiones técnicas y recomendaciones de estilo.

Este documento debe ser consultado y actualizado en cada cambio relevante de la arquitectura.
"""

## Principios clave de diseño y desarrollo

- **Modularidad estricta:** Cada módulo debe tener una única responsabilidad y exponer solo interfaces públicas claras. No debe haber dependencias circulares ni acoplamientos innecesarios.
- **Encapsulamiento:** La lógica interna de cada módulo debe estar protegida y no ser accesible desde otros módulos. Usar clases, métodos y atributos privados siempre que sea posible.
- **Tipado fuerte:** Todo el código debe usar anotaciones de tipo (type hints) en funciones, métodos y modelos. Los modelos de datos deben implementarse preferentemente con dataclasses.
- **Validación y seguridad:** Todos los datos de entrada y salida deben validarse rigurosamente. Se debe manejar cualquier posible error o excepción de forma robusta y registrar los errores críticos.
- **Pruebas y mantenibilidad:** Cada módulo debe contar con pruebas unitarias y de integración. El código debe estar documentado con docstrings claros y actualizados.
- **Desacoplamiento de la UI:** La lógica de negocio y la gestión de datos deben residir en servicios o controladores independientes, nunca en la interfaz gráfica.
- **Comunicación entre módulos:** Usar interfaces, eventos o señales para la comunicación entre módulos, evitando dependencias directas. Uso de getters y setters para acceder a datos de otros módulos, nunca acceso directo a atributos.
- **Documentación exhaustiva:** Toda premisa, decisión arquitectónica y convención debe estar documentada en los archivos de docs y en los docstrings.
- Internacionalización, accesibilidad y experiencia de usuario profesional.
- Control de versiones con Git y flujos de trabajo colaborativos.
- UI modular: componentes reutilizables y autocontenidos.

## Patrón arquitectónico

La aplicación sigue el patrón Modelo-Vista-Controlador (MVC):
- **Modelo:** Gestiona los datos, lógica de negocio y persistencia.
- **Vista:** Interfaz gráfica (PyQt6), desacoplada de la lógica.
- **Controlador:** Orquesta la comunicación entre modelo y vista, y gestiona los eventos de usuario.

## Estructura de carpetas y módulos

- src/core: lógica de negocio reutilizable
- src/gui: interfaz PyQt basada en QDockWidget para paneles acoplables, con persistencia de layout por workspace
- src/workspace: gestión de workspaces
- src/db: acceso a base de datos
- src/utils: utilidades generales
- src/i18n: internacionalización (gestión de idiomas y traducciones de la UI, con recarga dinámica por workspace)
- src/resources/icons/light y src/resources/icons/dark: iconos PNG opcionales para modo claro y oscuro del SO (mismos nombres).
- src/resources/styles: documentación de estilos (la apariencia de paneles está en `src/gui/panel_styles.py`)
- src/resources: recursos estáticos
- src/tests: pruebas (nota: la carpeta real de tests unitarios es `tests/` en la raíz del proyecto)

### Convención de iconos
- `get_app_icon("nombre")` elige PNG en `icons/light/` o `icons/dark/` según `icon_mode()` (modo del SO).
- Si no hay PNG, usa iconos estándar Qt (`QStyle.StandardPixmap`), visibles en claro y oscuro.
- Para iconos personalizados, añadir el mismo nombre en `light/` y `dark/`.
- Ver `src/resources/icons/README.md` y `src/gui/icon_utils.py`.

## Convenciones clave

- **No hay selector de tema**: la apariencia sigue el modo claro u oscuro del sistema operativo (`apply_system_appearance()`).
- Menú **Ver → Reiniciar paneles** restaura el layout por defecto de los docks y lo persiste en el workspace activo.
- Los **paneles acoplables** adaptan colores con `is_dark_mode()` y paletas VS en `gui/panel_styles.py`.
- La persistencia del layout se guarda al cerrar la app en el workspace activo.
- Por workspace solo se persiste **idioma** y estado de UI (layout, tablas, etc.), no el tema visual.

## Base de datos (SQLite)

- Módulo: `src/db/` — conexión, transacciones y migraciones versionadas.
- Fichero: `src/workspace/data/app.db` (junto a `workspaces.json`).
- Arranque: `AppLifecycle` conecta y ejecuta `ensure_migrations()`, crea `ApplicationServices`.
- Cierre: `Database.close()` en `on_shutdown`.
- Sin ORM ni repositorios de dominio en fase 1; ver `docs/db.md`.
- La GUI consume datos de dominio vía `core.ApplicationServices`, no repositorios directos.

## Capa core

- Módulo: `src/core/` — validaciones y reglas de negocio.
- Contenedor: `ApplicationServices.from_database_service(...)`.
- Ejemplo: `ItemService` (nombres únicos, longitudes máximas).
- Ver `docs/core.md`.

## Persistencia y workspaces

- En cada workspace se guarda toda la configuración de la aplicación, incluyendo:
  - Dimensiones y posición de todas las ventanas.
  - Configuración de columnas de tablas (anchos, orden, visibilidad, etc).
  - Preferencias de usuario, idioma, layout, etc.
  - Cualquier otro parámetro relevante para la experiencia del usuario.
- Al cambiar de workspace, toda la app se adapta al contexto y preferencias guardadas.
- La gestión y restauración de estos parámetros debe ser responsabilidad de cada componente de la UI, usando siempre el workspace activo proporcionado por WorkspaceController.

## Flujo de activación de workspace

- Solo puede haber un workspace activo a la vez.
- Al activar un workspace desde la UI, se debe refrescar la tabla para que solo una fila muestre 'Sí' en la columna 'Activo'.
- Tras activar, la ventana principal debe actualizar la barra de estado y restaurar la configuración (ej: geometría).
- La activación se realiza siempre a través del WorkspaceController, que notifica a todos los observadores.
- Este flujo garantiza coherencia visual y lógica en toda la app.

## Premisas y filosofía de workspaces

- Modularidad, robustez y autonomía de cada módulo.
- Comunicación mediante interfaces y eventos, nunca por detalles internos.
- Documentación exhaustiva y mantenida en cada cambio relevante.

## Decisiones técnicas

- Uso de Python 3.10+ y PyQt6.
- Tests con pytest y estructura de carpetas separada.
- Internacionalización mediante archivos de idioma y soporte UTF-8.
- Logger centralizado para errores críticos.
- Automatización de tests y CI recomendada.

## Preguntas abiertas y mejoras iniciales

- se prevé integración con servicios externos o APIs
- Despliegue PyInstaller.
- Estilos PEP8 y formateo automático con black, por ser el estándar profesional y ampliamente adoptado en la comunidad Python.
- Soporte multiplataforma completo (Windows, Linux, macOS).
- Las rutas, dependencias y scripts deben ser compatibles y documentarse las particularidades de cada plataforma. 
- Se deben usar entornos virtuales y pruebas automáticas en CI para garantizar la compatibilidad.

---

Para dudas o sugerencias, consulta la documentación principal o contacta con los responsables del proyecto.
