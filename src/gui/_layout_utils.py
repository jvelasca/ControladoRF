"""Utilidades de disposición de paneles por módulo."""


def restaurar_paneles_por_defecto(main_window) -> None:
    manager = getattr(main_window, "_module_tab_manager", None) or getattr(
        main_window, "_module_dock_manager", None
    )
    if manager is not None:
        manager.reset_active_module_layout()
