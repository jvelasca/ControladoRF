# Módulo db — fase 2

Capa genérica de persistencia relacional con **SQLite**.

## Componentes

| Módulo | Rol |
|--------|-----|
| `settings.py` | Parámetros persistidos |
| `connection.py` | Conexión y transacciones |
| `maintenance.py` | Integridad, VACUUM, backup |
| `service.py` | Orquestación + `service.items` |
| `models/item.py` | Entidad de ejemplo `Item` |
| `repositories/base.py` | `BaseRepository[T]` — CRUD común |
| `repositories/item_repository.py` | CRUD de `items` |
| `migration.py` | Esquema versionado (001–003) |

## Repositorios (fase 2)

```python
from db import DatabaseService

service.startup()
item = service.items.create("Nombre", "Descripción")
items = service.items.search_by_name("Nom")
service.items.delete(item.id)
```

Extender: crear modelo + repositorio que herede de `BaseRepository`, añadir migración en `migration.py`.

## Tests

```powershell
.\scripts\run_db_tests.ps1
```

O manualmente:

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/db -v
python scripts/test_db_repositories.py
```

Documentación: `docs/db.md`.
