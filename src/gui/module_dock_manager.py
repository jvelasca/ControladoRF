"""Reexport del gestor de pestañas (sustituye el modelo QDockWidget global)."""
from gui.module_tab_manager import ModuleDockManager, ModuleTabManager

__all__ = ["ModuleDockManager", "ModuleTabManager"]
