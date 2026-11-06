"""Base Framework for Semiconductor Equipment Human-Machine Interfaces (HMI).

Standards Compliance:
  - SEMI E95: Specification for Human Interface for Semiconductor Manufacturing Equipment
  - SEMI E10: Standard for Definition and Measurement of Equipment Reliability,
              Availability, and Maintainability (RAM)
  - SEMI S2: Environmental, Health, and Safety Guideline for Semiconductor Manufacturing Equipment
  - SEMI E30: Generic Model for Communications and Control of Manufacturing Equipment (GEM)

This module provides the architectural foundation for equipment HMIs in the virtual fab.
It defines standard widget primitives, screen tab navigation, multi-level role-based
access control (RBAC), and strict state machine mediation—ensuring all operator, engineering,
and maintenance commands pass through formal SEMI E10 state machines rather than mutating
tool physics directly.
"""

from __future__ import annotations

import logging
import math
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple, Union

from src.simulation.core.units import (
    PhysicalQuantity,
    convert_value,
    normalize_unit,
)
from src.simulation.equipment.base_equipment import (
    Alarm,
    AlarmSeverity,
    BaseEquipment,
    GEMControlState,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Authorization & Security Model (SEMI E95 Section 6.3)
# =============================================================================

class AuthorizationLevel(str, Enum):
    """User authorization levels for equipment HMI operation per SEMI E95.

    Hierarchical ordering: OPERATOR < ENGINEER < MAINTENANCE < ADMIN.
    """
    OPERATOR = "OPERATOR"
    ENGINEER = "ENGINEER"
    MAINTENANCE = "MAINTENANCE"
    ADMIN = "ADMIN"

    @property
    def rank(self) -> int:
        """Numeric rank for permission comparison."""
        ranks = {
            AuthorizationLevel.OPERATOR: 1,
            AuthorizationLevel.ENGINEER: 2,
            AuthorizationLevel.MAINTENANCE: 3,
            AuthorizationLevel.ADMIN: 4,
        }
        return ranks[self]

    def has_permission(self, required_level: AuthorizationLevel) -> bool:
        """Check if this authorization level satisfies or exceeds the required level."""
        return self.rank >= required_level.rank


# =============================================================================
# Navigation Tabs & Display Elements
# =============================================================================

class NavigationTab(str, Enum):
    """Standard SEMI E95 top-level equipment navigation tabs."""
    MAIN = "MAIN"
    RECIPE = "RECIPE"
    CHAMBER = "CHAMBER"
    ALARMS = "ALARMS"
    HISTORY = "HISTORY"
    MAINTENANCE = "MAINTENANCE"


class IndicatorColor(str, Enum):
    """Standard SEMI E95 indicator color palette."""
    GREEN = "#2ECC71"    # Normal / Productive / Ready
    YELLOW = "#F1C40F"   # Standby / Warning / Warm-up
    RED = "#E74C3C"      # Fault / Critical Alarm / EMO
    BLUE = "#3498DB"     # Engineering / Manual Mode
    GREY = "#7F8C8D"     # Offline / Disabled / Non-scheduled


class IndicatorState(str, Enum):
    """Subsystem physical condition states."""
    READY = "READY"
    WARNING = "WARNING"
    FAULT = "FAULT"
    OFFLINE = "OFFLINE"
    BUSY = "BUSY"

    @property
    def color(self) -> IndicatorColor:
        """Map condition state to SEMI standard color."""
        mapping = {
            IndicatorState.READY: IndicatorColor.GREEN,
            IndicatorState.WARNING: IndicatorColor.YELLOW,
            IndicatorState.FAULT: IndicatorColor.RED,
            IndicatorState.OFFLINE: IndicatorColor.GREY,
            IndicatorState.BUSY: IndicatorColor.BLUE,
        }
        return mapping[self]


@dataclass(frozen=True)
class WidgetPosition:
    """2D grid layout coordinate on the HMI panel screen."""
    x: int
    y: int

    def to_dict(self) -> Dict[str, int]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True)
class WidgetSize:
    """Widget dimensions in standard grid units."""
    width: int
    height: int

    def to_dict(self) -> Dict[str, int]:
        return {"width": self.width, "height": self.height}


# =============================================================================
# HMI Interaction Events
# =============================================================================

class HMIEventType(str, Enum):
    """Categorized user interaction event types."""
    BUTTON_PRESS = "BUTTON_PRESS"
    RECIPE_SELECT = "RECIPE_SELECT"
    PARAMETER_CHANGE = "PARAMETER_CHANGE"
    ALARM_ACK = "ALARM_ACK"
    ALARM_CLEAR = "ALARM_CLEAR"
    TAB_CHANGE = "TAB_CHANGE"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    MAINTENANCE_TRIGGER = "MAINTENANCE_TRIGGER"
    DIAGNOSTIC_EXEC = "DIAGNOSTIC_EXEC"


@dataclass(frozen=True)
class HMIEvent:
    """Encapsulates a user interaction originating from the HMI front-end.

    Attributes:
        event_type: Category of user action.
        panel_id: Identifier of source HMI panel.
        widget_id: ID of the interacting control or element.
        timestamp: Time of interaction (epoch seconds).
        authorization_level: Security level of interacting user.
        user_id: Operator/Engineer identifier.
        payload: Event parameters (e.g. selected recipe, changed value, alarm ID).
    """
    event_type: HMIEventType
    panel_id: str
    widget_id: str
    timestamp: float
    authorization_level: AuthorizationLevel
    user_id: str = "OP_DEFAULT"
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "panel_id": self.panel_id,
            "widget_id": self.widget_id,
            "timestamp": self.timestamp,
            "authorization_level": self.authorization_level.value,
            "user_id": self.user_id,
            "payload": dict(self.payload),
        }


# =============================================================================
# HMI Widgets Framework (SEMI E95 Compliant)
# =============================================================================

class HMIWidget(ABC):
    """Abstract base class for all SEMI E95 graphical interface components."""

    def __init__(
        self,
        widget_id: str,
        label: str,
        tab: NavigationTab,
        position: WidgetPosition,
        size: WidgetSize,
        visible: bool = True,
        enabled: bool = True,
        tooltip: str = "",
    ) -> None:
        self.widget_id = widget_id
        self.label = label
        self.tab = tab
        self.position = position
        self.size = size
        self.visible = visible
        self.enabled = enabled
        self.tooltip = tooltip

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize widget configuration and live telemetry to dictionary."""
        pass


class StatusIndicator(HMIWidget):
    """Visual LED/tile indicator representing subsystem readiness or alarm state."""

    def __init__(
        self,
        widget_id: str,
        label: str,
        tab: NavigationTab,
        position: WidgetPosition,
        size: WidgetSize = WidgetSize(2, 1),
        initial_state: IndicatorState = IndicatorState.READY,
        status_text: str = "Ready",
        tooltip: str = "",
    ) -> None:
        super().__init__(widget_id, label, tab, position, size, tooltip=tooltip)
        self.state = initial_state
        self.status_text = status_text

    def set_state(self, state: IndicatorState, text: Optional[str] = None) -> None:
        """Update indicator state and display label."""
        self.state = state
        if text is not None:
            self.status_text = text

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_type": "StatusIndicator",
            "widget_id": self.widget_id,
            "label": self.label,
            "tab": self.tab.value,
            "position": self.position.to_dict(),
            "size": self.size.to_dict(),
            "visible": self.visible,
            "enabled": self.enabled,
            "tooltip": self.tooltip,
            "state": self.state.value,
            "color": self.state.color.value,
            "status_text": self.status_text,
        }


class NumericDisplay(HMIWidget):
    """Precision numerical readout with engineering units, tolerances, and alarm bounds."""

    def __init__(
        self,
        widget_id: str,
        label: str,
        tab: NavigationTab,
        position: WidgetPosition,
        unit: str,
        size: WidgetSize = WidgetSize(2, 1),
        format_spec: str = "{:.2f}",
        initial_value: float = 0.0,
        warning_low: Optional[float] = None,
        warning_high: Optional[float] = None,
        fault_low: Optional[float] = None,
        fault_high: Optional[float] = None,
        history_len: int = 60,
        tooltip: str = "",
    ) -> None:
        super().__init__(widget_id, label, tab, position, size, tooltip=tooltip)
        self.unit = normalize_unit(unit)
        self.format_spec = format_spec
        self.value = initial_value
        self.warning_low = warning_low
        self.warning_high = warning_high
        self.fault_low = fault_low
        self.fault_high = fault_high
        self.history: Deque[Tuple[float, float]] = deque(maxlen=history_len)
        self.history.append((time.time(), initial_value))

    def update_value(self, new_val: Union[float, PhysicalQuantity], timestamp: Optional[float] = None) -> None:
        """Record a new numerical reading and timestamp into telemetry ring buffer."""
        t = timestamp if timestamp is not None else time.time()
        if isinstance(new_val, PhysicalQuantity):
            converted = new_val.to_unit(self.unit)
            val = converted.value
        else:
            val = float(new_val)
        self.value = val
        self.history.append((t, val))

    @property
    def alarm_state(self) -> IndicatorState:
        """Evaluate parameter against warning and fault bounds."""
        val = self.value
        if self.fault_low is not None and val < self.fault_low:
            return IndicatorState.FAULT
        if self.fault_high is not None and val > self.fault_high:
            return IndicatorState.FAULT
        if self.warning_low is not None and val < self.warning_low:
            return IndicatorState.WARNING
        if self.warning_high is not None and val > self.warning_high:
            return IndicatorState.WARNING
        return IndicatorState.READY

    def to_dict(self) -> Dict[str, Any]:
        formatted = self.format_spec.format(self.value)
        return {
            "widget_type": "NumericDisplay",
            "widget_id": self.widget_id,
            "label": self.label,
            "tab": self.tab.value,
            "position": self.position.to_dict(),
            "size": self.size.to_dict(),
            "visible": self.visible,
            "enabled": self.enabled,
            "tooltip": self.tooltip,
            "value": self.value,
            "formatted_value": f"{formatted} {self.unit}",
            "unit": self.unit,
            "alarm_state": self.alarm_state.value,
            "color": self.alarm_state.color.value,
            "limits": {
                "warning_low": self.warning_low,
                "warning_high": self.warning_high,
                "fault_low": self.fault_low,
                "fault_high": self.fault_high,
            },
            "recent_trend": list(self.history)[-10:],
        }


class TrendChart(HMIWidget):
    """Time-series telemetry plot tracking historical process parameters."""

    def __init__(
        self,
        widget_id: str,
        label: str,
        tab: NavigationTab,
        position: WidgetPosition,
        parameter_name: str,
        unit: str,
        size: WidgetSize = WidgetSize(6, 4),
        time_window_sec: float = 300.0,
        setpoint: Optional[float] = None,
        upper_limit: Optional[float] = None,
        lower_limit: Optional[float] = None,
        tooltip: str = "",
    ) -> None:
        super().__init__(widget_id, label, tab, position, size, tooltip=tooltip)
        self.parameter_name = parameter_name
        self.unit = normalize_unit(unit)
        self.time_window_sec = time_window_sec
        self.setpoint = setpoint
        self.upper_limit = upper_limit
        self.lower_limit = lower_limit
        self.data_points: Deque[Tuple[float, float]] = deque(maxlen=600)

    def add_point(self, value: float, timestamp: Optional[float] = None) -> None:
        """Add a time-series telemetry sample."""
        t = timestamp if timestamp is not None else time.time()
        self.data_points.append((t, float(value)))

    def clear(self) -> None:
        """Flush chart trend history."""
        self.data_points.clear()

    def to_dict(self) -> Dict[str, Any]:
        pts = list(self.data_points)
        return {
            "widget_type": "TrendChart",
            "widget_id": self.widget_id,
            "label": self.label,
            "tab": self.tab.value,
            "position": self.position.to_dict(),
            "size": self.size.to_dict(),
            "visible": self.visible,
            "enabled": self.enabled,
            "tooltip": self.tooltip,
            "parameter_name": self.parameter_name,
            "unit": self.unit,
            "time_window_sec": self.time_window_sec,
            "setpoint": self.setpoint,
            "upper_limit": self.upper_limit,
            "lower_limit": self.lower_limit,
            "point_count": len(pts),
            "points": pts,
        }


class RecipeSelector(HMIWidget):
    """Dropdown and recipe selection browser with process step inspector."""

    def __init__(
        self,
        widget_id: str,
        label: str,
        tab: NavigationTab,
        position: WidgetPosition,
        size: WidgetSize = WidgetSize(4, 4),
        recipes: Optional[List[Dict[str, Any]]] = None,
        selected_recipe_id: Optional[str] = None,
        tooltip: str = "Select qualified process recipe",
    ) -> None:
        super().__init__(widget_id, label, tab, position, size, tooltip=tooltip)
        self.recipes: List[Dict[str, Any]] = recipes or []
        self.selected_recipe_id: Optional[str] = selected_recipe_id

    def set_recipes(self, recipes: List[Dict[str, Any]]) -> None:
        """Update available recipe catalog."""
        self.recipes = list(recipes)

    def select_recipe(self, recipe_id: str) -> bool:
        """Select active recipe by ID."""
        for r in self.recipes:
            if r.get("recipe_id") == recipe_id or r.get("name") == recipe_id:
                self.selected_recipe_id = recipe_id
                return True
        return False

    def get_selected_recipe(self) -> Optional[Dict[str, Any]]:
        """Retrieve full details of currently selected recipe."""
        for r in self.recipes:
            if r.get("recipe_id") == self.selected_recipe_id or r.get("name") == self.selected_recipe_id:
                return r
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_type": "RecipeSelector",
            "widget_id": self.widget_id,
            "label": self.label,
            "tab": self.tab.value,
            "position": self.position.to_dict(),
            "size": self.size.to_dict(),
            "visible": self.visible,
            "enabled": self.enabled,
            "tooltip": self.tooltip,
            "recipe_count": len(self.recipes),
            "recipes": [
                {
                    "recipe_id": r.get("recipe_id", r.get("name", "RECIPE")),
                    "name": r.get("name", "Unnamed"),
                    "process_type": r.get("process_type", "PROCESS"),
                    "step_count": len(r.get("steps", [])),
                    "total_duration_sec": r.get("total_duration_sec", 0.0),
                    "last_modified": r.get("last_modified", "2026-01-01"),
                }
                for r in self.recipes
            ],
            "selected_recipe_id": self.selected_recipe_id,
            "selected_recipe_detail": self.get_selected_recipe(),
        }


class AlarmList(HMIWidget):
    """Interactive alarm annunciator grid displaying active faults and historical trips."""

    def __init__(
        self,
        widget_id: str,
        label: str,
        tab: NavigationTab,
        position: WidgetPosition,
        size: WidgetSize = WidgetSize(6, 4),
        tooltip: str = "Active equipment alarms per SEMI E95",
    ) -> None:
        super().__init__(widget_id, label, tab, position, size, tooltip=tooltip)
        self.active_alarms: List[Dict[str, Any]] = []
        self.alarm_history: List[Dict[str, Any]] = []

    def sync_alarms(self, active: List[Alarm], history: List[Alarm]) -> None:
        """Synchronize alarms with underlying tool hardware."""
        self.active_alarms = [a.to_dict() for a in active]
        self.alarm_history = [a.to_dict() for a in history][-50:]

    @property
    def highest_severity(self) -> Optional[AlarmSeverity]:
        """Determine highest severity among un-cleared active alarms."""
        if not self.active_alarms:
            return None
        severities = [AlarmSeverity(a["severity"]) for a in self.active_alarms]
        if AlarmSeverity.CRITICAL in severities:
            return AlarmSeverity.CRITICAL
        if AlarmSeverity.FAULT in severities:
            return AlarmSeverity.FAULT
        if AlarmSeverity.WARNING in severities:
            return AlarmSeverity.WARNING
        return AlarmSeverity.INFO

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_type": "AlarmList",
            "widget_id": self.widget_id,
            "label": self.label,
            "tab": self.tab.value,
            "position": self.position.to_dict(),
            "size": self.size.to_dict(),
            "visible": self.visible,
            "enabled": self.enabled,
            "tooltip": self.tooltip,
            "active_count": len(self.active_alarms),
            "active_alarms": self.active_alarms,
            "history_count": len(self.alarm_history),
            "recent_history": self.alarm_history[-10:],
            "highest_severity": self.highest_severity.value if self.highest_severity else None,
        }


class ButtonControl(HMIWidget):
    """Interactive push-button protected by role-based authorization."""

    def __init__(
        self,
        widget_id: str,
        label: str,
        tab: NavigationTab,
        position: WidgetPosition,
        action_name: str,
        size: WidgetSize = WidgetSize(2, 1),
        required_auth: AuthorizationLevel = AuthorizationLevel.OPERATOR,
        requires_confirmation: bool = False,
        button_style: str = "default",  # 'default', 'success', 'warning', 'danger'
        tooltip: str = "",
    ) -> None:
        super().__init__(widget_id, label, tab, position, size, tooltip=tooltip)
        self.action_name = action_name
        self.required_auth = required_auth
        self.requires_confirmation = requires_confirmation
        self.button_style = button_style

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_type": "ButtonControl",
            "widget_id": self.widget_id,
            "label": self.label,
            "tab": self.tab.value,
            "position": self.position.to_dict(),
            "size": self.size.to_dict(),
            "visible": self.visible,
            "enabled": self.enabled,
            "tooltip": self.tooltip,
            "action_name": self.action_name,
            "required_auth": self.required_auth.value,
            "requires_confirmation": self.requires_confirmation,
            "button_style": self.button_style,
        }


class GaugeDisplay(HMIWidget):
    """Analog circular dial gauge display with green, yellow, and red operating bands."""

    def __init__(
        self,
        widget_id: str,
        label: str,
        tab: NavigationTab,
        position: WidgetPosition,
        unit: str,
        min_value: float,
        max_value: float,
        size: WidgetSize = WidgetSize(3, 3),
        initial_value: float = 0.0,
        setpoint: Optional[float] = None,
        green_zone: Tuple[float, float] = (0.0, 100.0),
        yellow_zone: Optional[Tuple[float, float]] = None,
        red_zone: Optional[Tuple[float, float]] = None,
        tooltip: str = "",
    ) -> None:
        super().__init__(widget_id, label, tab, position, size, tooltip=tooltip)
        self.unit = normalize_unit(unit)
        self.min_value = float(min_value)
        self.max_value = float(max_value)
        self.value = float(initial_value)
        self.setpoint = float(setpoint) if setpoint is not None else None
        self.green_zone = green_zone
        self.yellow_zone = yellow_zone
        self.red_zone = red_zone

    def set_value(self, value: float) -> None:
        """Update dial indicator pointer position."""
        self.value = float(value)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_type": "GaugeDisplay",
            "widget_id": self.widget_id,
            "label": self.label,
            "tab": self.tab.value,
            "position": self.position.to_dict(),
            "size": self.size.to_dict(),
            "visible": self.visible,
            "enabled": self.enabled,
            "tooltip": self.tooltip,
            "value": self.value,
            "unit": self.unit,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "setpoint": self.setpoint,
            "green_zone": list(self.green_zone),
            "yellow_zone": list(self.yellow_zone) if self.yellow_zone else None,
            "red_zone": list(self.red_zone) if self.red_zone else None,
        }


class WaferMap(HMIWidget):
    """2D wafer spatial map rendering die grid, site metrology, and defect distributions."""

    def __init__(
        self,
        widget_id: str,
        label: str,
        tab: NavigationTab,
        position: WidgetPosition,
        size: WidgetSize = WidgetSize(4, 4),
        diameter_mm: float = 300.0,
        notch_orientation_deg: float = 0.0,
        edge_exclusion_mm: float = 3.0,
        die_pitch_x_mm: float = 20.0,
        die_pitch_y_mm: float = 20.0,
        tooltip: str = "2D Wafer Metrology and Defect Map",
    ) -> None:
        super().__init__(widget_id, label, tab, position, size, tooltip=tooltip)
        self.diameter_mm = diameter_mm
        self.notch_orientation_deg = notch_orientation_deg
        self.edge_exclusion_mm = edge_exclusion_mm
        self.die_pitch_x_mm = die_pitch_x_mm
        self.die_pitch_y_mm = die_pitch_y_mm
        # List of site dicts: {'site_id': str, 'x_mm': float, 'y_mm': float, 'value': float, 'unit': str, 'pass': bool}
        self.sites: List[Dict[str, Any]] = []
        # List of defect dicts: {'defect_id': int, 'x_mm': float, 'y_mm': float, 'size_um': float, 'type': str}
        self.defects: List[Dict[str, Any]] = []

    def set_sites(self, sites: List[Dict[str, Any]]) -> None:
        """Update inspection/metrology points."""
        self.sites = list(sites)

    def set_defects(self, defects: List[Dict[str, Any]]) -> None:
        """Update surface particle/defect coordinates."""
        self.defects = list(defects)

    def clear(self) -> None:
        """Clear map data."""
        self.sites.clear()
        self.defects.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_type": "WaferMap",
            "widget_id": self.widget_id,
            "label": self.label,
            "tab": self.tab.value,
            "position": self.position.to_dict(),
            "size": self.size.to_dict(),
            "visible": self.visible,
            "enabled": self.enabled,
            "tooltip": self.tooltip,
            "diameter_mm": self.diameter_mm,
            "notch_orientation_deg": self.notch_orientation_deg,
            "edge_exclusion_mm": self.edge_exclusion_mm,
            "site_count": len(self.sites),
            "defect_count": len(self.defects),
            "sites": self.sites,
            "defects": self.defects,
        }


# =============================================================================
# SEMI E95 Base HMIPanel
# =============================================================================

class HMIPanel:
    """Base class for all equipment Human-Machine Interface consoles.

    Adheres strictly to SEMI E95 specifications:
      - Standard 6-tab screen architecture: MAIN, RECIPE, CHAMBER, ALARMS, HISTORY, MAINTENANCE
      - Persistent Status Bar: tool state, active lot ID, wafer count, highest alarm indicator
      - State machine mediated control: interactions invoke state machine events or authorized
        hardware commands, preventing un-monitored variable mutations.
      - Role-based authorization validation.
    """

    def __init__(
        self,
        panel_id: str,
        equipment_reference: Optional[BaseEquipment] = None,
        initial_tab: NavigationTab = NavigationTab.MAIN,
        current_user_auth: AuthorizationLevel = AuthorizationLevel.OPERATOR,
        user_id: str = "OP_01",
    ) -> None:
        """Initialize the HMI Panel.

        Args:
            panel_id: Unique identifier (e.g. 'HMI_ETCH_01').
            equipment_reference: Associated physical equipment digital twin.
            initial_tab: Active navigation screen.
            current_user_auth: Authorization tier of currently logged-in user.
            user_id: Current user operator/engineer identifier.
        """
        self.panel_id = panel_id
        self.equipment = equipment_reference
        self.active_tab = initial_tab
        self.current_user_auth = current_user_auth
        self.user_id = user_id

        # Internal widget register: widget_id -> HMIWidget
        self._widgets: Dict[str, HMIWidget] = {}

        # Tracking lot / wafer metadata displayed in status bar
        self.active_lot_id: str = "IDLE_NO_LOT"
        self.active_wafer_id: Optional[str] = None
        self.wafers_processed_count: int = 0

    def add_widget(self, widget: HMIWidget) -> None:
        """Register a widget to the panel layout."""
        self._widgets[widget.widget_id] = widget

    def get_widget(self, widget_id: str) -> Optional[HMIWidget]:
        """Look up a widget by identifier."""
        return self._widgets.get(widget_id)

    def get_widgets_for_tab(self, tab: NavigationTab) -> List[HMIWidget]:
        """Return list of widgets assigned to the specified tab."""
        return [w for w in self._widgets.values() if w.tab == tab and w.visible]

    def set_active_tab(self, tab: NavigationTab) -> None:
        """Switch navigation tab."""
        self.active_tab = tab
        logger.debug("[%s] HMI tab switched to %s", self.panel_id, tab.value)

    def set_user(self, user_id: str, auth_level: AuthorizationLevel) -> None:
        """Update logged-in user and security rank."""
        self.user_id = user_id
        self.current_user_auth = auth_level
        logger.info("[%s] User logged in: %s (%s)", self.panel_id, user_id, auth_level.value)

    # -------------------------------------------------------------------------
    # SEMI E95 Status Bar
    # -------------------------------------------------------------------------

    def get_status_bar(self) -> Dict[str, Any]:
        """Construct the persistent SEMI E95 tool status bar payload.

        Displays:
          - Equipment ID, type, model
          - SEMI E10 current operational state and substate
          - SEMI E30 GEM control state
          - Active lot and wafer tracking
          - Highest active alarm severity indicator with color coding
        """
        eq_id = self.equipment.equipment_id if self.equipment else "STANDALONE_HMI"
        eq_type = self.equipment.equipment_type if self.equipment else "VIRTUAL_TOOL"

        if self.equipment:
            sm = self.equipment.state_machine
            current_state = sm.current_state.value
            current_substate = sm.current_substate.value
            state_code = sm.current_state.code
            gem_state = self.equipment.gem_control_state.value

            active_alarms = self.equipment.alarms
            if active_alarms:
                # Find worst severity
                severities = [a.severity for a in active_alarms]
                if AlarmSeverity.CRITICAL in severities:
                    highest_alarm = AlarmSeverity.CRITICAL.value
                    alarm_color = IndicatorColor.RED.value
                elif AlarmSeverity.FAULT in severities:
                    highest_alarm = AlarmSeverity.FAULT.value
                    alarm_color = IndicatorColor.RED.value
                elif AlarmSeverity.WARNING in severities:
                    highest_alarm = AlarmSeverity.WARNING.value
                    alarm_color = IndicatorColor.YELLOW.value
                else:
                    highest_alarm = AlarmSeverity.INFO.value
                    alarm_color = IndicatorColor.BLUE.value
            else:
                highest_alarm = "NONE"
                alarm_color = IndicatorColor.GREEN.value
        else:
            current_state = "2000_STANDBY"
            current_substate = "2200_NO_PRODUCT"
            state_code = 2000
            gem_state = GEMControlState.ONLINE_LOCAL.value
            highest_alarm = "NONE"
            alarm_color = IndicatorColor.GREEN.value

        # Derive SEMI state color
        if state_code == 1000:
            state_color = IndicatorColor.GREEN.value
        elif state_code == 2000:
            state_color = IndicatorColor.YELLOW.value
        elif state_code == 3000:
            state_color = IndicatorColor.BLUE.value
        elif state_code in (4000, 6000):
            state_color = IndicatorColor.GREY.value
        else:  # 5000 UNSCHEDULED DOWN
            state_color = IndicatorColor.RED.value

        return {
            "equipment_id": eq_id,
            "equipment_type": eq_type,
            "timestamp": time.time(),
            "semi_e10_state": current_state,
            "semi_e10_substate": current_substate,
            "state_color": state_color,
            "gem_control_state": gem_state,
            "active_lot_id": self.active_lot_id,
            "active_wafer_id": self.active_wafer_id or "NONE",
            "wafers_processed_count": self.wafers_processed_count,
            "highest_alarm": highest_alarm,
            "alarm_color": alarm_color,
            "logged_user_id": self.user_id,
            "logged_auth_level": self.current_user_auth.value,
            "active_tab": self.active_tab.value,
        }

    # -------------------------------------------------------------------------
    # State-Mediated Event Dispatcher
    # -------------------------------------------------------------------------

    def dispatch_event(self, event: HMIEvent) -> Dict[str, Any]:
        """Handle a front-end user interaction.

        Enforces:
          1. User authorization rank check against action/widget permission.
          2. Mediation strictly through the equipment state machine or
             SEMI E30 / SECS commands. No direct attribute mutations permitted.

        Args:
            event: The incoming user interaction event.

        Returns:
            Result dictionary indicating success, message, and updated panel state.
        """
        logger.info(
            "[%s] Processing HMI event: %s on widget '%s' by user %s (%s)",
            self.panel_id,
            event.event_type.value,
            event.widget_id,
            event.user_id,
            event.authorization_level.value,
        )

        # Tab changes are free to all logged users
        if event.event_type == HMIEventType.TAB_CHANGE:
            target_tab_str = event.payload.get("target_tab", "")
            try:
                new_tab = NavigationTab(target_tab_str)
                self.set_active_tab(new_tab)
                return {"success": True, "action": "TAB_CHANGE", "active_tab": new_tab.value}
            except ValueError:
                return {"success": False, "error": f"Invalid navigation tab '{target_tab_str}'"}

        # Lookup widget
        widget = self.get_widget(event.widget_id)
        if widget is not None and isinstance(widget, ButtonControl):
            # Check RBAC
            if not event.authorization_level.has_permission(widget.required_auth):
                err = (
                    f"Access Denied: Action '{widget.action_name}' requires "
                    f"authorization level {widget.required_auth.value}. User has {event.authorization_level.value}."
                )
                logger.warning("[%s] %s", self.panel_id, err)
                return {"success": False, "error": err, "code": "AUTH_DENIED"}

        # Route standard equipment operations
        if event.event_type == HMIEventType.EMERGENCY_STOP:
            # SEMI S2 Emergency Stop is accessible to EVERYONE
            if self.equipment is not None:
                reason = str(event.payload.get("reason", "Operator Emergency Stop Pressed"))
                self.equipment.emergency_stop(reason)
                return {"success": True, "action": "EMERGENCY_STOP", "message": "Emergency Stop Engaged"}
            return {"success": False, "error": "No physical equipment bound to HMI"}

        if event.event_type == HMIEventType.ALARM_ACK:
            alarm_id = str(event.payload.get("alarm_id", ""))
            if self.equipment is not None:
                ack_ok = self.equipment.acknowledge_alarm(alarm_id)
                return {"success": ack_ok, "alarm_id": alarm_id, "action": "ALARM_ACK"}
            return {"success": False, "error": "No physical equipment bound"}

        if event.event_type == HMIEventType.ALARM_CLEAR:
            alarm_id = str(event.payload.get("alarm_id", ""))
            if not event.authorization_level.has_permission(AuthorizationLevel.ENGINEER):
                return {"success": False, "error": "Clearing alarms requires ENGINEER permission"}
            if self.equipment is not None:
                clr_ok = self.equipment.clear_alarm(alarm_id)
                return {"success": clr_ok, "alarm_id": alarm_id, "action": "ALARM_CLEAR"}
            return {"success": False, "error": "No physical equipment bound"}

        if event.event_type == HMIEventType.RECIPE_SELECT:
            recipe_id = str(event.payload.get("recipe_id", ""))
            selector = self.get_widget(event.widget_id)
            if isinstance(selector, RecipeSelector):
                ok = selector.select_recipe(recipe_id)
                return {"success": ok, "recipe_id": recipe_id, "action": "RECIPE_SELECT"}
            return {"success": False, "error": f"Widget {event.widget_id} is not a RecipeSelector"}

        # Fallback to subclass-specific handler
        return self._handle_custom_event(event)

    def _handle_custom_event(self, event: HMIEvent) -> Dict[str, Any]:
        """Subclasses override this to handle process-specific button actions."""
        return {"success": True, "action": event.event_type.value, "detail": "Default event acknowledged"}

    # -------------------------------------------------------------------------
    # Telemetry Synchronization
    # -------------------------------------------------------------------------

    def update_telemetry(self) -> None:
        """Periodic sync hook to refresh widget values from hardware sensors."""
        if self.equipment is None:
            return

        # Synchronize alarms
        alarm_widget = None
        for w in self._widgets.values():
            if isinstance(w, AlarmList):
                w.sync_alarms(self.equipment.alarms, self.equipment.alarm_history)

        # Synchronize wafer counters
        if "total_wafers_processed" in self.equipment.maintenance_counters:
            curr, _ = self.equipment.maintenance_counters["total_wafers_processed"]
            self.wafers_processed_count = int(curr)

    def render(self) -> Dict[str, Any]:
        """Serialize complete HMI UI state for the presentation engine (Unity/Web)."""
        self.update_telemetry()
        widgets_data = [w.to_dict() for w in self._widgets.values()]
        return {
            "panel_id": self.panel_id,
            "status_bar": self.get_status_bar(),
            "active_tab": self.active_tab.value,
            "all_tabs": [t.value for t in NavigationTab],
            "widgets": widgets_data,
        }
