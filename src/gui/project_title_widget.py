"""Indicador compacto del documento activo (barra de herramientas)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from gui.app_chrome_styles import apply_project_title_styles
from i18n.json_translation import tr


class ProjectTitleWidget(QWidget):
    """
    Extremo derecho de la toolbar — patrón IDE:

    ● Nombre del show

    Solo lectura; renombrar desde Archivo → Renombrar show…
    La ruta del fichero se muestra en la barra de estado.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("ProjectTitleWidget")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._dirty_dot = QLabel("●")
        self._dirty_dot.setObjectName("ProjectDirtyDot")
        self._dirty_dot.setFixedWidth(14)
        self._dirty_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._show_name = QLabel()
        self._show_name.setObjectName("ProjectShowNameLabel")
        self._show_name.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._show_name.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(4)
        layout.addWidget(self._dirty_dot)
        layout.addWidget(self._show_name)

        apply_project_title_styles(self)
        self.set_state(show_name="", dirty=False, has_project=False)

    def set_state(
        self,
        *,
        show_name: str,
        dirty: bool,
        has_project: bool,
        file_path: str = "",
    ) -> None:
        if not has_project:
            self._show_name.setText(tr("project_none"))
            self._dirty_dot.setHidden(True)
            self.setToolTip(tr("project_none_hint"))
            return

        self._show_name.setText(show_name or tr("project_untitled_show"))
        self._dirty_dot.setHidden(not dirty)

        tooltip_lines = [self._show_name.text()]
        if file_path:
            tooltip_lines.append(file_path)
        else:
            tooltip_lines.append(tr("project_file_unsaved_hint"))
        if dirty:
            tooltip_lines.append(tr("project_dirty_hint"))
        self.setToolTip("\n".join(tooltip_lines))

    def recargar_textos(self) -> None:
        has_project = self._show_name.text() != tr("project_none")
        dirty = not self._dirty_dot.isHidden()
        show_name = "" if not has_project else self._show_name.text()
        file_path = ""
        tip = self.toolTip()
        if has_project and "\n" in tip:
            file_path = tip.split("\n", 1)[1].split("\n")[0]
            if file_path == tr("project_file_unsaved_hint"):
                file_path = ""
        self.set_state(
            show_name=show_name,
            dirty=dirty,
            has_project=has_project,
            file_path=file_path,
        )
