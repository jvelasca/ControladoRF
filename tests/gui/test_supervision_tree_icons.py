"""Tests iconos árbol supervisión."""
from __future__ import annotations

import sys

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_supervision_tree_icon_cache(qapp):
    from gui.monitor.monitor_supervision_tree_icons import supervision_tree_icon

    icon_ok = supervision_tree_icon("microphone", "ok")
    icon_crit = supervision_tree_icon("microphone", "critical_pending")
    icon_comment = supervision_tree_icon("microphone", "comentario")
    assert not icon_ok.isNull()
    assert not icon_crit.isNull()
    assert not icon_comment.isNull()
    assert icon_ok.cacheKey() != icon_crit.cacheKey()
    assert icon_comment.cacheKey() != icon_ok.cacheKey()


def test_supervision_tree_icon_blink_dim(qapp):
    from gui.monitor.monitor_supervision_tree_icons import supervision_tree_icon

    bright = supervision_tree_icon("microphone", "critical_pending", blink_dim=False)
    dim = supervision_tree_icon("microphone", "critical_pending", blink_dim=True)
    assert bright.cacheKey() != dim.cacheKey()
