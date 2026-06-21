"""
Arranque principal de la aplicación PyQt6.
"""
import sys
from pathlib import Path

# Garantiza imports desde src/ al depurar con F5 (Cursor/VS Code/Visual Studio)
_SRC_DIR = Path(__file__).resolve().parent
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from app_lifecycle import AppLifecycle


def main() -> None:
    """Punto de entrada principal de la aplicación."""
    lifecycle = AppLifecycle()
    sys.exit(lifecycle.start())


if __name__ == "__main__":
    main()
