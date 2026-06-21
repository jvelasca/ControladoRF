"""Acordeón estilo QToolBox nativo — cabeceras siempre visibles, contenido ajustado."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QStyleOptionToolBox,
    QStylePainter,
    QVBoxLayout,
    QWidget,
)


def _tab_position(index: int, count: int) -> QStyleOptionToolBox.TabPosition:
    if count <= 1:
        return QStyleOptionToolBox.TabPosition.OnlyOneTab
    if index == 0:
        return QStyleOptionToolBox.TabPosition.Beginning
    if index == count - 1:
        return QStyleOptionToolBox.TabPosition.End
    return QStyleOptionToolBox.TabPosition.Middle


def _selected_position(index: int, current: int) -> QStyleOptionToolBox.SelectedPosition:
    if current < 0:
        return QStyleOptionToolBox.SelectedPosition.NotAdjacent
    if index == current - 1:
        return QStyleOptionToolBox.SelectedPosition.NextIsSelected
    if index == current + 1:
        return QStyleOptionToolBox.SelectedPosition.PreviousIsSelected
    return QStyleOptionToolBox.SelectedPosition.NotAdjacent


class MonitorAccordionHeader(QAbstractButton):
    """Cabecera con pintado nativo CE_ToolBoxTab (misma apariencia que QToolBox)."""

    def __init__(
        self,
        text: str,
        *,
        index: int,
        count: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._index = index
        self._count = count
        self._current_index = 0
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(28)

    def set_tab_context(self, *, index: int, count: int, current_index: int) -> None:
        self._index = index
        self._count = count
        self._current_index = current_index
        self.update()

    def sizeHint(self):
        opt = self._style_option()
        fm = opt.fontMetrics
        height = max(fm.height() + 12, 28)
        return QSize(max(self.width(), 120), height)

    def paintEvent(self, _event) -> None:
        painter = QStylePainter(self)
        opt = self._style_option()
        painter.drawControl(QStyle.ControlElement.CE_ToolBoxTabShape, opt)
        painter.drawControl(QStyle.ControlElement.CE_ToolBoxTabLabel, opt)

    def _style_option(self) -> QStyleOptionToolBox:
        opt = QStyleOptionToolBox()
        opt.initFrom(self)
        opt.text = self.text()
        opt.icon = self.icon()
        opt.position = _tab_position(self._index, self._count)
        opt.selectedPosition = _selected_position(self._index, self._current_index)
        opt.state = QStyle.StateFlag.State_Enabled
        if self.isChecked():
            opt.state |= QStyle.StateFlag.State_On | QStyle.StateFlag.State_Open
        else:
            opt.state |= QStyle.StateFlag.State_Off
        if self.underMouse():
            opt.state |= QStyle.StateFlag.State_MouseOver
        if self.hasFocus():
            opt.state |= QStyle.StateFlag.State_HasFocus
        return opt


class _AccordionSection(QWidget):
    """Una fila del acordeón: cabecera + cuerpo opcional debajo."""

    activated = pyqtSignal(int)

    def __init__(
        self,
        index: int,
        title: str,
        content: QWidget,
        *,
        scrollable: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._index = index
        self._scrollable = scrollable
        self._expanded = False

        self._header = MonitorAccordionHeader(title, index=index, count=1, parent=self)
        self._header.clicked.connect(self._on_header_clicked)

        self._body = QFrame(self)
        self._body.setObjectName("MonitorAccordionBody")
        self._body.setFrameShape(QFrame.Shape.NoFrame)
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        if scrollable:
            self._scroll = QScrollArea(self._body)
            self._scroll.setWidgetResizable(True)
            self._scroll.setFrameShape(QFrame.Shape.NoFrame)
            self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._scroll.setWidget(content)
            self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            body_layout.addWidget(self._scroll)
        else:
            self._scroll = None
            content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            body_layout.addWidget(content)

        self._body.setVisible(False)
        self._body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header)
        layout.addWidget(self._body)

    @property
    def header(self) -> MonitorAccordionHeader:
        return self._header

    @property
    def scrollable(self) -> bool:
        return self._scrollable

    def is_expanded(self) -> bool:
        return self._expanded

    def set_title(self, title: str) -> None:
        self._header.setText(title)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._header.setChecked(expanded)
        self._body.setVisible(expanded)
        if expanded and not self._scrollable:
            self._body.adjustSize()
        elif not expanded and self._scroll is not None:
            self._clear_scroll_height()
        self.updateGeometry()

    def content_natural_height(self, width: int | None = None) -> int:
        if not self._expanded:
            return 0
        if self._scroll is None:
            return self._body.sizeHint().height()
        inner = self._scroll.widget()
        if inner is None:
            return 120
        measure_w = max((width or self._body.width()) - 8, 120)
        old_min_w, old_max_w = inner.minimumWidth(), inner.maximumWidth()
        inner.setMinimumWidth(measure_w)
        inner.setMaximumWidth(measure_w)
        layout = inner.layout()
        if layout is not None:
            layout.activate()
        inner.adjustSize()
        inner_h = inner.heightForWidth(measure_w)
        if inner_h <= 0:
            inner_h = inner.sizeHint().height()
        inner.setMinimumWidth(old_min_w)
        inner.setMaximumWidth(old_max_w)
        return max(inner_h, inner.minimumSizeHint().height(), 1)

    def set_body_viewport(self, height: int) -> None:
        """Fija el alto del cuerpo: natural si cabe; scroll si el contenido es más alto."""
        if self._scroll is None:
            return
        height = max(height, 80)
        natural = self.content_natural_height(max(self._body.width(), 120))
        self._scroll.setMinimumHeight(0)
        self._scroll.setMaximumHeight(16777215)
        if natural <= height:
            self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self._scroll.setFixedHeight(natural)
        else:
            self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self._scroll.setFixedHeight(height)

    def _clear_scroll_height(self) -> None:
        if self._scroll is None:
            return
        self._scroll.setMinimumHeight(0)
        self._scroll.setMaximumHeight(16777215)
        self._scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def header_height_hint(self) -> int:
        return max(self._header.sizeHint().height(), self._header.minimumHeight())

    def body_height_hint(self) -> int:
        if not self._expanded:
            return 0
        if self._scroll is not None:
            return self._scroll.height()
        return self._body.sizeHint().height()

    def _on_header_clicked(self) -> None:
        self.activated.emit(self._index)


class MonitorConfigAccordion(QWidget):
    """Acordeón vertical: todas las cabeceras visibles; una sección abierta a la vez."""

    currentChanged = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sections: list[_AccordionSection] = []
        self._current_index = -1
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def count(self) -> int:
        return len(self._sections)

    def currentIndex(self) -> int:
        return self._current_index

    def widget(self, index: int) -> QWidget | None:
        if index < 0 or index >= len(self._sections):
            return None
        section = self._sections[index]
        if section._scroll is not None:
            return section._scroll.widget()
        body_layout = section._body.layout()
        if body_layout is not None and body_layout.count() > 0:
            item = body_layout.itemAt(0)
            if item is not None:
                return item.widget()
        return None

    def addSection(self, content: QWidget, title: str, *, scrollable: bool = False) -> None:
        index = len(self._sections)
        section = _AccordionSection(
            index,
            title,
            content,
            scrollable=scrollable,
            parent=self,
        )
        section.activated.connect(self._on_section_activated)
        self._sections.append(section)
        self._layout.addWidget(section)
        self._refresh_tab_context()
        if self._current_index < 0:
            self.setCurrentIndex(0)

    def setItemText(self, index: int, title: str) -> None:
        if 0 <= index < len(self._sections):
            self._sections[index].set_title(title)

    def setCurrentIndex(self, index: int) -> None:
        if index < 0 or index >= len(self._sections):
            return
        if index == self._current_index:
            return
        previous = self._current_index
        self._current_index = index
        for i, section in enumerate(self._sections):
            section.set_expanded(i == index)
        self._refresh_tab_context()
        self.update_viewport()
        if previous != index:
            self.currentChanged.emit(index)

    def collapseAll(self) -> None:
        if self._current_index < 0:
            return
        previous = self._current_index
        self._current_index = -1
        for section in self._sections:
            section.set_expanded(False)
        self._refresh_tab_context()
        self.updateGeometry()
        if previous >= 0:
            self.currentChanged.emit(-1)

    def headers_height_hint(self) -> int:
        return sum(section.header_height_hint() for section in self._sections)

    def update_viewport(self, available_height: int | None = None) -> None:
        if self._current_index < 0:
            for section in self._sections:
                if section._scroll is not None:
                    section._clear_scroll_height()
            self.updateGeometry()
            return
        if available_height is not None:
            height = available_height
        else:
            parent = self.parentWidget()
            height = parent.height() if parent is not None else 480

        headers_h = self.headers_height_hint()
        margins = 12
        body_budget = max(80, height - headers_h - margins)

        for section in self._sections:
            if section.is_expanded() and section.scrollable:
                section.set_body_viewport(body_budget)

        self.updateGeometry()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.update_viewport(self._viewport_height())

    def _viewport_height(self) -> int:
        parent = self.parentWidget()
        if parent is not None and parent.height() > 0:
            return parent.height()
        return max(self.height(), 320)

    def _on_section_activated(self, index: int) -> None:
        if index == self._current_index:
            self.collapseAll()
            return
        self.setCurrentIndex(index)

    def _refresh_tab_context(self) -> None:
        count = len(self._sections)
        for i, section in enumerate(self._sections):
            section.header.set_tab_context(
                index=i,
                count=count,
                current_index=self._current_index,
            )
