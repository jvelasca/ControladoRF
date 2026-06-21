# Sistema de Logging Profesional para la Aplicación

"""
logging.md
----------
Guía profesional para el sistema de logging centralizado del proyecto.

Propósito:
- Facilitar la depuración, trazabilidad y mantenimiento de la aplicación.
- Permitir el registro estructurado y flexible de eventos, errores y mensajes informativos.
- Garantizar la escalabilidad y la integración sencilla en todos los módulos.

Este sistema es obligatorio en todos los componentes y debe usarse siguiendo las recomendaciones de integración y buenas prácticas descritas a continuación.
"""

Este proyecto utiliza un sistema de logging centralizado, profesional y escalable, ubicado en `src/utils/logger.py`. El objetivo es facilitar la depuración, trazabilidad y mantenimiento de la aplicación, permitiendo registrar eventos, errores y mensajes informativos de forma estructurada y flexible.

## Características principales

- **Centralización:** Toda la configuración y uso de logs se gestiona desde un único módulo.
- **Modularidad:** Cada módulo puede obtener su propio logger mediante `get_logger(name)`.
- **Handlers por defecto:**
  - Archivo rotativo (`logs/app.log`, hasta 5 archivos de 2MB).
  - Consola (stdout/stderr).
- **Formato profesional:** Fecha, nivel, nombre del módulo y mensaje.
- **Extensible:** Puedes añadir más handlers (por ejemplo, logs por usuario, logs de eventos, etc.).
- **No dependencias de PyQt ni de rutas fijas en la lógica de la app.**

## Uso básico

### 1. Inicialización global (una vez al arrancar la app)

```python
from utils.logger import init_logging
init_logging()  # Puedes personalizar ruta, nombre de archivo, nivel, formato...
```

### 2. Obtener un logger en cualquier módulo

```python
from utils.logger import get_logger
logger = get_logger(__name__)
logger.info("Mensaje informativo")
logger.error("Mensaje de error")
```

### 3. Uso rápido para errores y mensajes globales

```python
from utils.logger import log_error, log_info, log_debug
log_info("Arrancando la aplicación...")
try:
	...
except Exception as e:
	log_error("Error crítico al iniciar", e)
```

## Recomendaciones de integración

- Llama a `init_logging()` al inicio del punto de entrada principal (por ejemplo, en el arranque de la GUI o del backend).
- Usa `get_logger(__name__)` en cada módulo para registrar mensajes específicos de ese componente.
- Utiliza los métodos rápidos (`log_error`, `log_info`, `log_debug`) para mensajes globales o de alto nivel.
- No acoples la lógica de logging a la interfaz gráfica ni a rutas absolutas.
- Si necesitas logs adicionales (por usuario, por sesión, etc.), añade nuevos handlers en `init_logging()`.

## Ejemplo de integración en la GUI

```python
from utils.logger import init_logging, get_logger
init_logging()
logger = get_logger(__name__)
logger.info("Iniciando ventana principal")
```

---

**Este sistema debe integrarse en todos los módulos nuevos para facilitar la depuración y el mantenimiento profesional del proyecto.**

---

## Log de alarmas Monitor (previsto — Fase M4)

Además del log general de aplicación (`logs/app.log`), el módulo **Monitor** tendrá un **subsistema de registro de alarmas** orientado al operador y al post-análisis del show:

| Aspecto | Log de aplicación (`utils/logger`) | Log de alarmas Monitor |
|---------|-----------------------------------|-------------------------|
| **Propósito** | Depuración, errores, trazas técnicas | Eventos RF: caídas, desviaciones, umbrales |
| **Persistencia** | Fichero rotativo `logs/app.log` | SQLite (`monitor_alarms`, etc.) + export |
| **Contenido** | Mensajes libres del desarrollador | Canal, frecuencia, severidad, medida, umbral, ack |
| **Audiencia** | Desarrollo / soporte | Operador de RF / producción |

El gestor de alarmas escribirá en ambos: eventos técnicos (fallo SDR) en `app.log`; incidencias de portadora en el log de alarmas.

Ver diseño completo en **`docs/monitor.md`** (secciones 6 y 9).
