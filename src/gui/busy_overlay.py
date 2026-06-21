"""Indicador de espera modal para operaciones largas en la GUI."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QProgressDialog, QWidget


@contextmanager
def busy_dialog(
    parent: Optional[QWidget],
    *,
    title: str,
    message: str,
) -> Iterator[QProgressDialog]:
    """
    Muestra un diálogo indeterminado (barra animada) mientras dura el bloque `with`.

    Evita la sensación de que la aplicación se ha colgado durante importaciones
    o sincronizaciones pesadas en el hilo principal.
    """
    dialog = QProgressDialog(message, "", 0, 0, parent)
    dialog.setWindowTitle(title)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(0)
    dialog.setCancelButton(None)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    dialog.setMinimumWidth(360)
    dialog.show()
    QApplication.processEvents()
    try:
        yield dialog
    finally:
        dialog.close()
        QApplication.processEvents()
