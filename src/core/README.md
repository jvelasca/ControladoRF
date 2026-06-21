# Módulo core — fase 3

Lógica de negocio desacoplada de **PyQt6**. Orquesta reglas de dominio sobre repositorios `db/`.

## Estructura

```
src/core/
  __init__.py
  app_services.py      # ApplicationServices — contenedor DI
  exceptions.py        # ValidationError, DuplicateNameError
  services/
    item_service.py    # Reglas de negocio sobre items
```

## Flujo

```
GUI / AppLifecycle
       ↓
ApplicationServices
       ↓
ItemService (validación, reglas)
       ↓
ItemRepository (persistencia)
```

La GUI **no** debe llamar a repositorios directamente; use `app_services.items`.

## ItemService — reglas de dominio

| Regla | Detalle |
|-------|---------|
| Nombre obligatorio | Tras normalizar espacios |
| Longitud máxima | 100 caracteres (nombre), 500 (descripción) |
| Nombre único | Case insensitive |
| Búsqueda vacía | Devuelve listado completo ordenado |

## Uso

```python
from core import ApplicationServices

services = ApplicationServices.from_database_service(database_service)
item = services.items.create_item("Nombre", "Descripción")
services.items.delete_item(item.id)
```

## Tests

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/core -v
python scripts/test_core_services.py
```

O suite completa backend:

```powershell
.\scripts\run_db_tests.ps1
```

Documentación: `docs/core.md`.
