"""Modelos de supervisión de inventario RF (Monitor M2).

Incluye presets v2, referencia nominal ``ChannelReferenceCapture`` y settings
de dwell/ack. Persistencia en ``project.modules.monitor.supervision``.

Ver ``docs/monitor_supervision_premisas.md``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

SupervisionLogTrigger = Literal["manual", "play", "auto"]
SupervisionRecStartMode = Literal["manual", "play"]
AckMode = Literal["manual", "auto_reset"]
BandwidthSource = Literal["device_type", "manual"]
ThresholdMode = Literal["noise_relative", "nominal_delta"]
AlarmSeverity = Literal["critica", "menor", "aviso", "comentario"]
AlarmPhase = Literal["active", "latched", "cleared"]

SUPERVISION_VERSION = 2


@dataclass
class SupervisionRules:
    """Umbrales relativos al piso de ruido (estilo scan thresholds Workbench)."""

    warning_above_noise_db: float = 6.0
    critical_above_noise_db: float = 3.0
    carrier_loss_margin_db: float = 2.0
    debounce_ms: int = 500
    digital_metrics_enabled: bool = True
    mer_warning_db: float = 22.0
    mer_critical_db: float = 14.0
    digital_debounce_ms: int = 1500

    def to_dict(self) -> Dict[str, Any]:
        return {
            "warning_above_noise_db": self.warning_above_noise_db,
            "critical_above_noise_db": self.critical_above_noise_db,
            "carrier_loss_margin_db": self.carrier_loss_margin_db,
            "debounce_ms": self.debounce_ms,
            "digital_metrics_enabled": self.digital_metrics_enabled,
            "mer_warning_db": self.mer_warning_db,
            "mer_critical_db": self.mer_critical_db,
            "digital_debounce_ms": self.digital_debounce_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> SupervisionRules:
        raw = data or {}
        return cls(
            warning_above_noise_db=float(raw.get("warning_above_noise_db", 6.0)),
            critical_above_noise_db=float(raw.get("critical_above_noise_db", 3.0)),
            carrier_loss_margin_db=float(raw.get("carrier_loss_margin_db", 2.0)),
            debounce_ms=int(raw.get("debounce_ms", 500)),
            digital_metrics_enabled=bool(raw.get("digital_metrics_enabled", True)),
            mer_warning_db=float(raw.get("mer_warning_db", 22.0)),
            mer_critical_db=float(raw.get("mer_critical_db", 14.0)),
            digital_debounce_ms=int(raw.get("digital_debounce_ms", 1500)),
        )


@dataclass
class SupervisionSettings:
    log_trigger: SupervisionLogTrigger = "manual"
    rec_start_mode: SupervisionRecStartMode = "manual"
    log_directory: str = ""
    log_export_directory: str = ""
    warning_ack_mode: AckMode = "manual"
    warning_auto_reset_sec: int = 0
    critical_ack_mode: AckMode = "manual"
    critical_auto_reset_sec: int = 0
    show_inventory_on_spectrum: bool = True
    tree_group_mode: str = "zone"
    dwell_tuning_ms: int = 900
    dwell_restore_ms: int = 80
    dwell_periodic_interval_s: float = 60.0
    dwell_snr_recheck_interval_s: float = 12.0
    dwell_min_global_gap_s: float = 4.0
    alarm_window_geometry_b64: str = ""
    alarm_window_expanded_groups: List[str] = field(default_factory=list)
    alarm_window_scroll: int = 0
    alarm_window_visible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "log_trigger": self.log_trigger,
            "warning_ack_mode": self.warning_ack_mode,
            "warning_auto_reset_sec": self.warning_auto_reset_sec,
            "critical_ack_mode": self.critical_ack_mode,
            "critical_auto_reset_sec": self.critical_auto_reset_sec,
            "show_inventory_on_spectrum": self.show_inventory_on_spectrum,
            "tree_group_mode": self.tree_group_mode,
            "dwell_tuning_ms": int(self.dwell_tuning_ms),
            "dwell_restore_ms": int(self.dwell_restore_ms),
            "dwell_periodic_interval_s": float(self.dwell_periodic_interval_s),
            "dwell_snr_recheck_interval_s": float(self.dwell_snr_recheck_interval_s),
            "dwell_min_global_gap_s": float(self.dwell_min_global_gap_s),
            "alarm_window": {
                "geometry_b64": self.alarm_window_geometry_b64,
                "expanded_groups": list(self.alarm_window_expanded_groups),
                "scroll": int(self.alarm_window_scroll),
                "visible": bool(self.alarm_window_visible),
            },
        }
        if self.log_directory:
            payload["log_directory"] = self.log_directory
        if self.log_export_directory:
            payload["log_export_directory"] = self.log_export_directory
        if self.rec_start_mode != "manual":
            payload["rec_start_mode"] = self.rec_start_mode
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> SupervisionSettings:
        raw = data or {}
        log_trigger = str(raw.get("log_trigger") or "play")
        if log_trigger not in ("manual", "play", "auto"):
            log_trigger = "play"
        rec_start_mode = str(raw.get("rec_start_mode") or "manual")
        if rec_start_mode not in ("manual", "play"):
            rec_start_mode = "manual"
        alarm_raw = raw.get("alarm_window") if isinstance(raw.get("alarm_window"), dict) else {}
        expanded_raw = alarm_raw.get("expanded_groups") or []
        expanded_groups = [str(key) for key in expanded_raw if key]
        return cls(
            log_trigger=log_trigger,  # type: ignore[arg-type]
            rec_start_mode=rec_start_mode,  # type: ignore[arg-type]
            log_directory=str(raw.get("log_directory") or ""),
            log_export_directory=str(raw.get("log_export_directory") or ""),
            warning_ack_mode=_parse_ack_mode(raw.get("warning_ack_mode"), "manual"),
            warning_auto_reset_sec=max(0, int(raw.get("warning_auto_reset_sec", 0))),
            critical_ack_mode=_parse_ack_mode(raw.get("critical_ack_mode"), "manual"),
            critical_auto_reset_sec=max(0, int(raw.get("critical_auto_reset_sec", 0))),
            show_inventory_on_spectrum=bool(raw.get("show_inventory_on_spectrum", True)),
            tree_group_mode=_parse_tree_group_mode(raw.get("tree_group_mode")),
            dwell_tuning_ms=max(200, int(raw.get("dwell_tuning_ms", 900))),
            dwell_restore_ms=max(20, int(raw.get("dwell_restore_ms", 80))),
            dwell_periodic_interval_s=max(15.0, float(raw.get("dwell_periodic_interval_s", 60.0))),
            dwell_snr_recheck_interval_s=max(5.0, float(raw.get("dwell_snr_recheck_interval_s", 12.0))),
            dwell_min_global_gap_s=max(1.0, float(raw.get("dwell_min_global_gap_s", 4.0))),
            alarm_window_geometry_b64=str(alarm_raw.get("geometry_b64") or ""),
            alarm_window_expanded_groups=expanded_groups,
            alarm_window_scroll=max(0, int(alarm_raw.get("scroll", 0))),
            alarm_window_visible=bool(alarm_raw.get("visible", False)),
        )


def _parse_tree_group_mode(value: Any) -> str:
    from core.monitor.supervision.supervision_tree import SUPERVISION_TREE_GROUP_MODES

    mode = str(value or "zone")
    return mode if mode in SUPERVISION_TREE_GROUP_MODES else "zone"


def _parse_ack_mode(value: Any, default: AckMode) -> AckMode:
    mode = str(value or default)
    return mode if mode in ("manual", "auto_reset") else default


@dataclass
class ChannelReferenceCapture:
    """Nivel nominal memorizado en el aire (referencia de supervisión)."""

    snr_above_noise_db: Optional[float] = None
    carrier_dbm: Optional[float] = None
    mer_db: Optional[float] = None
    sync_ok: Optional[bool] = None
    captured_at_iso: str = ""

    def is_valid(self) -> bool:
        return self.snr_above_noise_db is not None or self.carrier_dbm is not None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if self.snr_above_noise_db is not None:
            payload["snr_above_noise_db"] = float(self.snr_above_noise_db)
        if self.carrier_dbm is not None:
            payload["carrier_dbm"] = float(self.carrier_dbm)
        if self.mer_db is not None:
            payload["mer_db"] = float(self.mer_db)
        if self.sync_ok is not None:
            payload["sync_ok"] = bool(self.sync_ok)
        if self.captured_at_iso:
            payload["captured_at_iso"] = self.captured_at_iso
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> ChannelReferenceCapture:
        raw = data or {}
        snr = raw.get("snr_above_noise_db")
        carrier = raw.get("carrier_dbm")
        mer = raw.get("mer_db")
        sync = raw.get("sync_ok")
        return cls(
            snr_above_noise_db=float(snr) if snr is not None else None,
            carrier_dbm=float(carrier) if carrier is not None else None,
            mer_db=float(mer) if mer is not None else None,
            sync_ok=bool(sync) if sync is not None else None,
            captured_at_iso=str(raw.get("captured_at_iso") or ""),
        )


@dataclass
class SupervisionTarget:
    channel_key: str
    enabled: bool = True
    bandwidth_hz: float = 200_000.0
    bandwidth_source: BandwidthSource = "device_type"
    preset_id: str = ""
    check_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    threshold_mode: str = ""
    reference: ChannelReferenceCapture = field(default_factory=ChannelReferenceCapture)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "channel_key": self.channel_key,
            "enabled": self.enabled,
            "bandwidth_hz": self.bandwidth_hz,
            "bandwidth_source": self.bandwidth_source,
        }
        if self.preset_id:
            payload["preset_id"] = self.preset_id
        if self.check_overrides:
            payload["check_overrides"] = {
                str(key): dict(value)
                for key, value in self.check_overrides.items()
                if isinstance(value, dict) and key
            }
        if self.threshold_mode:
            payload["threshold_mode"] = self.threshold_mode
        ref = self.reference.to_dict()
        if ref:
            payload["reference"] = ref
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SupervisionTarget:
        source = str(data.get("bandwidth_source") or "device_type")
        if source not in ("device_type", "manual"):
            source = "device_type"
        overrides_raw = data.get("check_overrides") or {}
        check_overrides: Dict[str, Dict[str, Any]] = {}
        if isinstance(overrides_raw, dict):
            for key, value in overrides_raw.items():
                if key and isinstance(value, dict):
                    check_overrides[str(key)] = dict(value)
        mode = str(data.get("threshold_mode") or "")
        if mode not in ("noise_relative", "nominal_delta"):
            mode = ""
        return cls(
            channel_key=str(data.get("channel_key") or ""),
            enabled=bool(data.get("enabled", True)),
            bandwidth_hz=max(1.0, float(data.get("bandwidth_hz", 200_000.0))),
            bandwidth_source=source,  # type: ignore[arg-type]
            preset_id=str(data.get("preset_id") or ""),
            check_overrides=check_overrides,
            threshold_mode=mode,
            reference=ChannelReferenceCapture.from_dict(
                data.get("reference") if isinstance(data.get("reference"), dict) else None
            ),
        )


@dataclass
class SupervisionState:
    version: int = SUPERVISION_VERSION
    settings: SupervisionSettings = field(default_factory=SupervisionSettings)
    rules: SupervisionRules = field(default_factory=SupervisionRules)
    rule_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    targets: List[SupervisionTarget] = field(default_factory=list)
    default_preset_id: str = "alarm_normal_fm"
    active_alarm_preset_id: str = "alarm_normal_fm"
    user_presets: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        overrides = {
            str(key): dict(value)
            for key, value in self.rule_overrides.items()
            if isinstance(value, dict) and key
        }
        payload: Dict[str, Any] = {
            "version": self.version,
            "settings": self.settings.to_dict(),
            "rules": self.rules.to_dict(),
            "default_preset_id": self.default_preset_id,
            "active_alarm_preset_id": self.active_alarm_preset_id,
            "targets": [target.to_dict() for target in self.targets],
        }
        if overrides:
            payload["rule_overrides"] = overrides
        if self.user_presets:
            payload["user_presets"] = {
                str(key): dict(value)
                for key, value in self.user_presets.items()
                if isinstance(value, dict) and key
            }
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> SupervisionState:
        raw = data or {}
        targets_raw = raw.get("targets") or []
        targets = [
            SupervisionTarget.from_dict(item)
            for item in targets_raw
            if isinstance(item, dict) and item.get("channel_key")
        ]
        overrides_raw = raw.get("rule_overrides") or {}
        rule_overrides: Dict[str, Dict[str, Any]] = {}
        if isinstance(overrides_raw, dict):
            for key, value in overrides_raw.items():
                if key and isinstance(value, dict):
                    rule_overrides[str(key)] = dict(value)
        user_presets_raw = raw.get("user_presets") or {}
        user_presets: Dict[str, Dict[str, Any]] = {}
        if isinstance(user_presets_raw, dict):
            for key, value in user_presets_raw.items():
                if key and isinstance(value, dict):
                    user_presets[str(key)] = dict(value)
        version = int(raw.get("version", 1))
        from core.monitor.supervision.alarm_presets import PRESET_ALARM_NORMAL_FM, normalize_alarm_preset_id

        default_preset = normalize_alarm_preset_id(
            str(raw.get("default_preset_id") or PRESET_ALARM_NORMAL_FM)
        )
        active_preset = normalize_alarm_preset_id(
            str(raw.get("active_alarm_preset_id") or default_preset or PRESET_ALARM_NORMAL_FM)
        )
        return cls(
            version=max(version, SUPERVISION_VERSION) if version >= 1 else SUPERVISION_VERSION,
            settings=SupervisionSettings.from_dict(raw.get("settings")),
            rules=SupervisionRules.from_dict(raw.get("rules")),
            rule_overrides=rule_overrides,
            targets=targets,
            default_preset_id=default_preset,
            active_alarm_preset_id=active_preset,
            user_presets=user_presets,
        )


@dataclass(frozen=True)
class ResolvedSupervisionTarget:
    """Canal listo para medición / dibujo en espectro."""

    channel_key: str
    enabled: bool
    frequency_hz: float
    bandwidth_hz: float
    label: str
    color: str
    device_type: str
    band: str = ""
    zone: str = ""

    @property
    def half_bandwidth_hz(self) -> float:
        return max(self.bandwidth_hz, 1.0) * 0.5


@dataclass
class AlarmSummaryCounts:
    ok: int = 0
    warning_active: int = 0
    warning_latched: int = 0
    critical_active: int = 0
    critical_latched: int = 0


@dataclass(frozen=True)
class SupervisionChannelMetrics:
    """Últimas métricas conocidas por canal (árbol de supervisión)."""

    channel_key: str
    snr_db: Optional[float] = None
    mer_db: Optional[float] = None
    sync_ok: Optional[bool] = None
    digital_mode: str = "none"  # none | snr_only | snr_and_mer


@dataclass(frozen=True)
class AlarmDisplayRow:
    """Fila estructurada para tabla de alarmas activas."""

    channel_key: str
    label: str
    frequency_mhz: float
    severity: str
    phase: str
    snr_db: Optional[float] = None
    carrier_dbm: Optional[float] = None
    noise_dbm: Optional[float] = None
    message: str = ""
    can_ack: bool = True
    acknowledged: bool = False
