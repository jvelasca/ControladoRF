"""Generación PDF del inventario RF."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Sequence

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen

from core.inventory_export import InventoryExportError, LIST_METADATA_FIELDS
from gui.inventory_export_labels import (
    PDF_DETAIL_SECTIONS,
    InventoryExportLabels,
    format_export_field,
)

PDF_TABLE_COLUMNS: Sequence[str] = (
    "channel_number",
    "channel_name",
    "model",
    "band",
    "frequency_mhz",
    "zone",
    "device_name",
    "device_type",
    "coordination_include",
    "coordination_active",
    "locked",
    "notes",
)

MARGIN = 36
ROW_HEIGHT = 20
HEADER_HEIGHT = 24
SECTION_GAP = 14
DETAIL_SECTION_GAP = 8
DETAIL_LINE_HEIGHT = 14
DETAIL_CHANNEL_GAP = 16


@dataclass
class _PdfContext:
    painter: QPainter
    writer: QPdfWriter
    labels: InventoryExportLabels
    page_width: int
    page_height: int
    content_width: float
    page_number: int = 1
    y: float = MARGIN

    @property
    def footer_reserve(self) -> float:
        return MARGIN + 18


def export_inventory_pdf(
    document: Mapping[str, Any],
    path: str,
    *,
    labels: InventoryExportLabels,
) -> None:
    writer = QPdfWriter(path)
    writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    writer.setPageOrientation(QPageLayout.Orientation.Landscape)
    writer.setResolution(96)
    writer.setTitle(labels.title)
    writer.setCreator("ControladoRF")

    painter = QPainter(writer)
    if not painter.isActive():
        painter.end()
        raise InventoryExportError("Could not start PDF painter")

    try:
        ctx = _PdfContext(
            painter=painter,
            writer=writer,
            labels=labels,
            page_width=writer.width(),
            page_height=writer.height(),
            content_width=writer.width() - 2 * MARGIN,
        )
        _render_summary_and_table(ctx, document)
        _render_channel_details(ctx, document)
        _draw_footer(ctx)
    finally:
        painter.end()


def _render_summary_and_table(ctx: _PdfContext, document: Mapping[str, Any]) -> None:
    fonts = _Fonts()
    project_name = str(document.get("project_name") or "—")
    exported_at = str(document.get("exported_at") or "—")
    lista = document.get("list") or {}
    channels = lista.get("channels") or []
    channel_count = int(lista.get("channel_count") or len(channels))

    ctx.painter.setFont(fonts.title)
    ctx.painter.setPen(QColor("#1E1E1E"))
    ctx.painter.drawText(
        QRectF(MARGIN, ctx.y, ctx.content_width, 28),
        Qt.AlignmentFlag.AlignLeft,
        ctx.labels.title,
    )
    ctx.y += 30

    ctx.painter.setFont(fonts.body)
    for line in (
        f"{ctx.labels.project_label}: {project_name}",
        f"{ctx.labels.exported_at_label}: {exported_at}",
        f"{ctx.labels.channel_count_label}: {channel_count}",
    ):
        ctx.painter.drawText(QRectF(MARGIN, ctx.y, ctx.content_width, 16), Qt.AlignmentFlag.AlignLeft, line)
        ctx.y += 16
    ctx.y += SECTION_GAP

    ctx.y = _draw_list_metadata(ctx, ctx.y, lista.get("metadata") or {}, fonts)
    ctx.y += SECTION_GAP

    ctx.painter.setFont(fonts.section)
    ctx.painter.drawText(
        QRectF(MARGIN, ctx.y, ctx.content_width, 18),
        Qt.AlignmentFlag.AlignLeft,
        ctx.labels.channels_title,
    )
    ctx.y += 22

    col_widths = _column_widths(ctx.content_width, PDF_TABLE_COLUMNS)
    ctx.y = _draw_table_header(ctx, ctx.y, col_widths, fonts.table_header)

    for row_index, channel in enumerate(channels):
        _ensure_space(ctx, ROW_HEIGHT, lambda: _draw_table_header(ctx, ctx.y, col_widths, fonts.table_header))
        bg = QColor("#F7F7F7") if row_index % 2 else QColor("#FFFFFF")
        ctx.painter.fillRect(QRectF(MARGIN, ctx.y, ctx.content_width, ROW_HEIGHT), bg)
        ctx.painter.setFont(fonts.table)
        ctx.painter.setPen(QColor("#1E1E1E"))
        x = MARGIN
        for col_index, field in enumerate(PDF_TABLE_COLUMNS):
            width = col_widths[col_index]
            text = format_export_field(field, channel.get(field), ctx.labels)
            rect = QRectF(x + 2, ctx.y + 2, width - 4, ROW_HEIGHT - 4)
            align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
            if field in ("channel_number", "frequency_mhz", "coordination_include", "coordination_active", "locked"):
                align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter
            ctx.painter.drawText(rect, align, text)
            x += width
        ctx.painter.setPen(QPen(QColor("#D0D0D0"), 1))
        ctx.painter.drawLine(int(MARGIN), int(ctx.y + ROW_HEIGHT), int(MARGIN + ctx.content_width), int(ctx.y + ROW_HEIGHT))
        ctx.y += ROW_HEIGHT


def _render_channel_details(ctx: _PdfContext, document: Mapping[str, Any]) -> None:
    channels = (document.get("list") or {}).get("channels") or []
    if not channels:
        return

    fonts = _Fonts()
    _start_new_page(ctx)
    ctx.painter.setFont(fonts.section)
    ctx.painter.setPen(QColor("#1E1E1E"))
    ctx.painter.drawText(
        QRectF(MARGIN, ctx.y, ctx.content_width, 20),
        Qt.AlignmentFlag.AlignLeft,
        ctx.labels.channel_details_title,
    )
    ctx.y += 24

    for index, channel in enumerate(channels, start=1):
        block_height = _estimate_channel_block_height()
        _ensure_space(ctx, block_height + DETAIL_CHANNEL_GAP)

        number = channel.get("channel_number")
        name = str(channel.get("channel_name") or "").strip() or "—"
        heading = f"{index}. "
        if number not in (None, ""):
            heading += f"#{number} · "
        heading += name

        ctx.painter.setFont(fonts.channel_title)
        ctx.painter.setPen(QColor("#0078D4"))
        ctx.painter.drawText(QRectF(MARGIN, ctx.y, ctx.content_width, 18), Qt.AlignmentFlag.AlignLeft, heading)
        ctx.y += 20

        box_top = ctx.y
        ctx.y += 6
        for section_key, fields in PDF_DETAIL_SECTIONS:
            ctx.painter.setFont(fonts.detail_section)
            ctx.painter.setPen(QColor("#1E1E1E"))
            section_title = ctx.labels.section_titles.get(section_key, section_key)
            ctx.painter.drawText(
                QRectF(MARGIN + 8, ctx.y, ctx.content_width - 16, 16),
                Qt.AlignmentFlag.AlignLeft,
                section_title,
            )
            ctx.y += 18
            ctx.y = _draw_property_grid(ctx, channel, fields, fonts)
            ctx.y += DETAIL_SECTION_GAP

        box_height = ctx.y - box_top + 4
        ctx.painter.setPen(QPen(QColor("#CCCEDB"), 1))
        ctx.painter.setBrush(Qt.BrushStyle.NoBrush)
        ctx.painter.drawRoundedRect(QRectF(MARGIN, box_top, ctx.content_width, box_height), 4, 4)
        ctx.y = box_top + box_height + DETAIL_CHANNEL_GAP


def _draw_property_grid(
    ctx: _PdfContext,
    channel: Dict[str, Any],
    fields: Sequence[str],
    fonts: _Fonts,
) -> float:
    label_width = ctx.content_width * 0.24
    value_width = ctx.content_width * 0.22
    column_gap = ctx.content_width * 0.04
    x_positions = (
        MARGIN + 8,
        MARGIN + 8 + label_width + value_width + column_gap,
    )
    y = ctx.y
    row = 0
    for field in fields:
        col = row % 2
        if col == 0 and row > 0:
            y += DETAIL_LINE_HEIGHT + 2
        x_label = x_positions[col]
        x_value = x_label + label_width
        label = ctx.labels.field_labels.get(field, field)
        value = format_export_field(field, channel.get(field), ctx.labels)
        ctx.painter.setFont(fonts.detail_label)
        ctx.painter.setPen(QColor("#666666"))
        ctx.painter.drawText(
            QRectF(x_label, y, label_width - 4, DETAIL_LINE_HEIGHT),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            f"{label}:",
        )
        ctx.painter.setFont(fonts.detail_value)
        ctx.painter.setPen(QColor("#1E1E1E"))
        ctx.painter.drawText(
            QRectF(x_value, y, value_width - 4, DETAIL_LINE_HEIGHT * 2),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            value,
        )
        if col == 1:
            y += DETAIL_LINE_HEIGHT + 2
        row += 1
    if row % 2 == 1:
        y += DETAIL_LINE_HEIGHT + 2
    return y


def _estimate_channel_block_height() -> float:
    rows = sum(max(1, (len(fields) + 1) // 2) for _, fields in PDF_DETAIL_SECTIONS)
    return 20 + 6 + len(PDF_DETAIL_SECTIONS) * 18 + rows * (DETAIL_LINE_HEIGHT + 2) + 8


def _ensure_space(ctx: _PdfContext, needed: float, on_continue=None) -> None:
    if ctx.y + needed <= ctx.page_height - ctx.footer_reserve:
        return
    _start_new_page(ctx)
    if on_continue:
        on_continue()


def _start_new_page(ctx: _PdfContext) -> None:
    _draw_footer(ctx)
    ctx.writer.newPage()
    ctx.page_number += 1
    ctx.y = MARGIN


def _draw_list_metadata(
    ctx: _PdfContext,
    y: float,
    metadata: Mapping[str, Any],
    fonts: _Fonts,
) -> float:
    ctx.painter.setFont(fonts.section)
    ctx.painter.setPen(QColor("#1E1E1E"))
    ctx.painter.drawText(
        QRectF(MARGIN, y, ctx.content_width, 18),
        Qt.AlignmentFlag.AlignLeft,
        ctx.labels.list_metadata_title,
    )
    y += 20
    ctx.painter.setFont(fonts.body)
    for field in LIST_METADATA_FIELDS:
        label = ctx.labels.field_labels.get(field, field)
        value = format_export_field(field, metadata.get(field), ctx.labels)
        ctx.painter.drawText(
            QRectF(MARGIN, y, ctx.content_width, 16),
            Qt.AlignmentFlag.AlignLeft,
            f"{label}: {value}",
        )
        y += 16
    ctx.y = y
    return y


def _draw_table_header(ctx: _PdfContext, y: float, col_widths: List[float], font: QFont) -> float:
    content_width = sum(col_widths)
    ctx.painter.fillRect(QRectF(MARGIN, y, content_width, HEADER_HEIGHT), QColor("#ECECEC"))
    ctx.painter.setFont(font)
    ctx.painter.setPen(QColor("#1E1E1E"))
    x = MARGIN
    for col_index, field in enumerate(PDF_TABLE_COLUMNS):
        width = col_widths[col_index]
        label = ctx.labels.field_labels.get(field, field)
        rect = QRectF(x + 2, y + 4, width - 4, HEADER_HEIGHT - 6)
        ctx.painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
        x += width
    ctx.painter.setPen(QPen(QColor("#808080"), 1))
    ctx.painter.drawRect(QRectF(MARGIN, y, content_width, HEADER_HEIGHT))
    ctx.y = y + HEADER_HEIGHT
    return ctx.y


def _draw_footer(ctx: _PdfContext) -> None:
    ctx.painter.setFont(QFont("Segoe UI", 8))
    ctx.painter.setPen(QColor("#666666"))
    footer = ctx.labels.page_label.format(page=ctx.page_number)
    ctx.painter.drawText(
        QRectF(MARGIN, ctx.page_height - MARGIN, ctx.page_width - 2 * MARGIN, 16),
        Qt.AlignmentFlag.AlignRight,
        footer,
    )


def _column_widths(content_width: float, fields: Sequence[str]) -> List[float]:
    weights = {
        "channel_number": 0.7,
        "channel_name": 1.4,
        "model": 1.1,
        "band": 0.8,
        "frequency_mhz": 1.0,
        "zone": 1.0,
        "device_name": 1.2,
        "device_type": 1.0,
        "coordination_include": 0.7,
        "coordination_active": 0.7,
        "locked": 0.6,
        "notes": 1.8,
    }
    total = sum(weights.get(field, 1.0) for field in fields)
    return [content_width * weights.get(field, 1.0) / total for field in fields]


@dataclass
class _Fonts:
    title: QFont = QFont("Segoe UI", 16, QFont.Weight.Bold)
    section: QFont = QFont("Segoe UI", 11, QFont.Weight.DemiBold)
    body: QFont = QFont("Segoe UI", 9)
    table_header: QFont = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
    table: QFont = QFont("Segoe UI", 8)
    channel_title: QFont = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
    detail_section: QFont = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
    detail_label: QFont = QFont("Segoe UI", 8)
    detail_value: QFont = QFont("Segoe UI", 8)
