"""Abstract Base Class and Core Interfaces for Semiconductor Fabrication Equipment.

Standards Compliance:
  - SEMI E10: Standard for Definition and Measurement of Equipment Reliability,
    Availability, and Maintainability (RAM)
  - SEMI E30: Generic Model for Communications and Control of Manufacturing Equipment (GEM)
  - SEMI E5: SEMI Equipment Communications Standard 2 (SECS-II)
  - SEMI S2: Environmental, Health, and Safety Guideline for Semiconductor Manufacturing Equipment
  - SEMI E95: Specification for Human Interface for Semiconductor Manufacturing Equipment

This module provides the abstract base class `BaseEquipment` that models physical wafer
processing tools in a 300mm/200mm cleanroom fab. It coordinates hardware interlocks,
active alarms, PM maintenance counters, SECS/GEM communication and control states,
and process chamber lifecycles.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.simulation.core.state_machine import EquipmentState, EquipmentStateMachine
from src.simulation.core.units import (
    PhysicalQuantity,
    pressure,
    temperature,
    duration,
)

logger = logging.getLogger(__name__)


class GEMCommState(str, Enum):
    """SEMI E30 GEM Communication States."""
    DISABLED = "DISABLED"
    NOT_COMMUNICATING = "NOT_COMMUNICATING"
    COMMUNICATING = "COMMUNICATING"


class GEMControlState(str, Enum):
    """SEMI E30 GEM Control States."""
    EQUIPMENT_OFFLINE = "EQUIPMENT_OFFLINE"
    ATTEMPT_ONLINE = "ATTEMPT_ONLINE"
    HOST_OFFLINE = "HOST_OFFLINE"
    ONLINE_LOCAL = "ONLINE_LOCAL"
    ONLINE_REMOTE = "ONLINE_REMOTE"


class GEMProcessingState(str, Enum):
    """SEMI E30 GEM Process States for Chamber/Tool."""
    IDLE = "IDLE"
    SETUP = "SETUP"
    READY = "READY"
    EXECUTING = "EXECUTING"
    PAUSE = "PAUSE"


class AlarmSeverity(str, Enum):
    """SEMI E95 / SEMI S2 Alarm Severity Levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    FAULT = "FAULT"
    CRITICAL = "CRITICAL"


class ChamberState(str, Enum):
    """Operational physical status of a process chamber."""
    ATMOSPHERIC = "ATMOSPHERIC"
    PUMPING_DOWN = "PUMPING_DOWN"
    HIGH_VACUUM = "HIGH_VACUUM"
    PROCESSING = "PROCESSING"
    PURGING = "PURGING"
    VENTING = "VENTING"
    MAINTENANCE = "MAINTENANCE"


@dataclass
class Alarm:
    """Equipment Alarm representation per SEMI E30 / SEMI E95.

    Attributes:
        alarm_id: Unique alarm identifier (e.g. 'ALM_VAC_001').
        name: Short human-readable alarm name.
        severity: Alarm severity level.
        timestamp: Time alarm was triggered (epoch seconds).
        description: Detailed physical root cause description.
        source: Hardware subsystem originating the alarm.
        acknowledged: True if operator or host has acknowledged the alarm.
        cleared: True if alarm condition has cleared.
        clear_timestamp: Timestamp when cleared.
    """

    alarm_id: str
    name: str
    severity: AlarmSeverity
    timestamp: float
    description: str
    source: str = "Hardware Subsystem"
    acknowledged: bool = False
    cleared: bool = False
    clear_timestamp: Optional[float] = None

    def acknowledge(self) -> None:
        """Mark alarm as acknowledged."""
        self.acknowledged = True

    def clear(self, timestamp: Optional[float] = None) -> None:
        """Clear active alarm condition."""
        self.cleared = True
        self.clear_timestamp = timestamp if timestamp is not None else time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert alarm record to dictionary."""
        return {
            "alarm_id": self.alarm_id,
            "name": self.name,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "description": self.description,
            "source": self.source,
            "acknowledged": self.acknowledged,
            "cleared": self.cleared,
            "clear_timestamp": self.clear_timestamp,
        }


@dataclass
class SafetyInterlock:
    """Hardware Safety Interlock adhering to SEMI S2 safety standards.

    Physical operations (plasma strike, high voltage, toxic gas flow, heating)
    are strictly inhibited if any required interlock is tripped.

    Attributes:
        interlock_id: Unique interlock code (e.g. 'INTLK_DOOR_CLOSED').
        name: Name of the safety circuit or switch.
        description: Safety rationale and circuit function.
        is_tripped: True if unsafe condition is detected (circuit open/alarm).
        trip_reason: Text explaining why interlock was tripped.
        auto_reset: Whether interlock auto-resets when normal condition resumes.
    """

    interlock_id: str
    name: str
    description: str
    is_tripped: bool = False
    trip_reason: str = ""
    auto_reset: bool = False

    def trip(self, reason: str) -> None:
        """Trip safety interlock and record reason."""
        self.is_tripped = True
        self.trip_reason = reason
        logger.error("SAFETY INTERLOCK TRIPPED [%s - %s]: %s", self.interlock_id, self.name, reason)

    def reset(self, force: bool = False) -> bool:
        """Attempt to reset the interlock."""
        if not self.is_tripped:
            return True
        if self.auto_reset or force:
            self.is_tripped = False
            self.trip_reason = ""
            logger.info("Safety interlock reset: [%s - %s]", self.interlock_id, self.name)
            return True
        logger.warning("Interlock [%s] requires manual safety inspection to reset.", self.interlock_id)
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Convert interlock state to dictionary."""
        return {
            "interlock_id": self.interlock_id,
            "name": self.name,
            "description": self.description,
            "is_tripped": self.is_tripped,
            "trip_reason": self.trip_reason,
            "auto_reset": self.auto_reset,
        }


@dataclass
class MaintenanceCounter:
    """Preventive Maintenance (PM) and Wear Counter tracking.

    Attributes:
        name: Counter name (e.g., 'processed_wafers', 'rf_on_hours', 'source_filament_hours').
        current: Current accumulated metric value.
        limit: Threshold value at which PM service is mandatory.
        unit: Physical unit symbol ('count', 'hr', 'sccm*s', 'mTorr*hr').
        pm_action: Required maintenance procedure when limit is reached.
        last_serviced_timestamp: Epoch timestamp of last reset/PM.
    """

    name: str
    current: float
    limit: float
    unit: str
    pm_action: str
    last_serviced_timestamp: float = field(default_factory=time.time)

    def increment(self, amount: float = 1.0) -> None:
        """Increment counter by specified amount."""
        if amount < 0.0:
            raise ValueError(f"Increment must be non-negative, got {amount}")
        self.current += amount

    def is_due(self) -> bool:
        """Return True if counter has reached or exceeded PM limit."""
        return self.current >= self.limit

    def reset(self, timestamp: Optional[float] = None) -> None:
        """Reset counter upon PM completion."""
        self.current = 0.0
        self.last_serviced_timestamp = timestamp if timestamp is not None else time.time()

    def to_tuple(self) -> Tuple[float, float]:
        """Return (current, limit) tuple."""
        return (self.current, self.limit)

    def to_dict(self) -> Dict[str, Any]:
        """Convert counter to dictionary."""
        return {
            "name": self.name,
            "current": self.current,
            "limit": self.limit,
            "unit": self.unit,
            "pm_action": self.pm_action,
            "is_due": self.is_due(),
            "last_serviced_timestamp": self.last_serviced_timestamp,
        }


@dataclass
class ProcessChamber:
    """Physical process chamber representation within semiconductor equipment.

    Attributes:
        chamber_id: Chamber identifier (e.g. 'CH1', 'PM_A').
        name: Descriptive chamber name.
        volume_liters: Chamber internal vacuum volume (Liters).
        base_pressure_torr: Ultimate base vacuum achievable (Torr).
        current_pressure_torr: Current measured chamber pressure (Torr).
        current_temperature_c: Measured chamber wall or chuck temperature (°C).
        state: Operational physical state.
        telemetry: Additional live physical sensors.
    """

    chamber_id: str
    name: str
    volume_liters: float = 25.0
    base_pressure_torr: float = 1e-6
    current_pressure_torr: float = 760.0
    current_temperature_c: float = 20.0
    state: ChamberState = ChamberState.ATMOSPHERIC
    telemetry: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize chamber state."""
        return {
            "chamber_id": self.chamber_id,
            "name": self.name,
            "volume_liters": self.volume_liters,
            "base_pressure_torr": self.base_pressure_torr,
            "current_pressure_torr": self.current_pressure_torr,
            "current_temperature_c": self.current_temperature_c,
            "state": self.state.value,
            "telemetry": dict(self.telemetry),
        }


@dataclass
class Wafer:
    """Generic semiconductor wafer substrate for processing.

    Attributes:
        wafer_id: Unique wafer scribe ID (e.g. 'W-1049-01').
        lot_id: Production lot identifier.
        slot: Carrier slot number (1-25).
        diameter_mm: Wafer diameter (150, 200, 300 mm).
        notch_orientation_deg: Wafer notch/flat angle (0.0 to 360.0°).
        layers: List of deposited/etched film layer dictionaries.
        defect_count: Surface particle / defect count.
        process_history: List of completed process step records.
    """

    wafer_id: str
    lot_id: str = "LOT_DEFAULT"
    slot: int = 1
    diameter_mm: int = 300
    notch_orientation_deg: float = 0.0
    layers: List[Dict[str, Any]] = field(default_factory=list)
    defect_count: int = 0
    process_history: List[Dict[str, Any]] = field(default_factory=list)

    def add_layer(self, layer_type: str, material: str, thickness_nm: float, **kwargs: Any) -> None:
        """Add a layer on top of wafer film stack."""
        layer = {
            "layer_type": layer_type,
            "material": material,
            "thickness_nm": thickness_nm,
            "timestamp": time.time(),
            **kwargs,
        }
        self.layers.append(layer)

    def get_top_layer(self) -> Optional[Dict[str, Any]]:
        """Return the top-most active film layer."""
        if not self.layers:
            return None
        return self.layers[-1]

    def record_step(self, tool_id: str, recipe_name: str, step_details: Dict[str, Any]) -> None:
        """Append a process execution record to wafer history."""
        self.process_history.append({
            "tool_id": tool_id,
            "recipe_name": recipe_name,
            "timestamp": time.time(),
            "details": step_details,
        })


class BaseEquipment(ABC):
    """Abstract Base Class for semiconductor manufacturing tools.

    Provides core services common to all fab tools:
      - SEMI E10 state machine management and RAM time accounting.
      - SEMI E30 SECS/GEM communications and control state logic.
      - Hardware safety interlocks and pre-operation interlock validation.
      - Alarm management: raise, acknowledge, clear, and severity filtering.
      - Maintenance counter monitoring with automatic PM due detection.
      - Chamber management and process execution lifecycle.
    """

    def __init__(
        self,
        equipment_id: str,
        equipment_type: str,
        manufacturer: str,
        model: str,
        supported_wafer_diameters: Optional[List[int]] = None,
        initial_time: Optional[float] = None,
    ) -> None:
        """Initialize the base equipment instance.

        Args:
            equipment_id: Unique tool tag (e.g. 'ETCH_01', 'OX_FURN_02').
            equipment_type: Category ('PLASMA_ETCH', 'OXIDATION_FURNACE', 'CVD', 'LITHO', 'ION_IMPLANT').
            manufacturer: Equipment maker (e.g. 'Lam Research', 'Applied Materials', 'ASML', 'TEL').
            model: Hardware model identifier.
            supported_wafer_diameters: Supported wafer sizes in mm (default [300]).
            initial_time: Simulation epoch start timestamp.
        """
        self.equipment_id = equipment_id
        self.equipment_type = equipment_type
        self.manufacturer = manufacturer
        self.model = model
        self.supported_wafer_diameters = supported_wafer_diameters or [300]

        self._lock = threading.RLock()
        self.sim_time = initial_time if initial_time is not None else time.time()

        # SEMI E10 State Machine
        self.state_machine = EquipmentStateMachine(
            equipment_id=self.equipment_id,
            initial_timestamp=self.sim_time,
        )

        # SEMI E30 GEM Communications & Control States
        self.gem_comm_state = GEMCommState.COMMUNICATING
        self.gem_control_state = GEMControlState.ONLINE_REMOTE
        self.gem_processing_state = GEMProcessingState.IDLE

        # Hardware safety interlocks: code -> SafetyInterlock
        self._interlocks: Dict[str, SafetyInterlock] = {}

        # Alarms: Active alarms list and complete alarm history
        self._active_alarms: List[Alarm] = []
        self._alarm_history: List[Alarm] = []

        # Process chambers
        self._process_chambers: List[ProcessChamber] = []

        # Maintenance Counters: name -> MaintenanceCounter
        self._maintenance_counters: Dict[str, MaintenanceCounter] = {}

        # Standard baseline maintenance counters
        self.add_maintenance_counter(
            name="total_wafers_processed",
            limit=5000.0,
            unit="count",
            pm_action="Chamber dry clean / focus ring inspection",
        )
        self.add_maintenance_counter(
            name="operating_hours",
            limit=1000.0,
            unit="hr",
            pm_action="Exhaust line inspection & pump oil change",
        )

        # Install common hardware interlocks
        self.add_interlock(
            interlock_id="INTLK_EMO",
            name="Emergency Off (EMO) Circuit",
            description="SEMI S2 Emergency Off button loop",
            auto_reset=False,
        )
        self.add_interlock(
            interlock_id="INTLK_EXHAUST",
            name="Facility Toxic Exhaust Flow",
            description="Differential pressure sensor in facility exhaust duct",
            auto_reset=True,
        )
        self.add_interlock(
            interlock_id="INTLK_COOLING_WATER",
            name="Process Cooling Water (PCW) Flow",
            description="Flow switch on return cooling circuit",
            auto_reset=True,
        )

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def interlocks(self) -> List[SafetyInterlock]:
        """Return list of all registered safety interlocks."""
        with self._lock:
            return list(self._interlocks.values())

    @property
    def alarms(self) -> List[Alarm]:
        """Return list of currently active un-cleared alarms."""
        with self._lock:
            return [a for a in self._active_alarms if not a.cleared]

    @property
    def alarm_history(self) -> List[Alarm]:
        """Return historical record of all alarms."""
        with self._lock:
            return list(self._alarm_history)

    @property
    def process_chambers(self) -> List[ProcessChamber]:
        """Return list of associated process chambers."""
        with self._lock:
            return list(self._process_chambers)

    @property
    def maintenance_counters(self) -> Dict[str, Tuple[float, float]]:
        """Return dictionary mapping counter name to (current, limit) tuple."""
        with self._lock:
            return {name: c.to_tuple() for name, c in self._maintenance_counters.items()}

    # -------------------------------------------------------------------------
    # Interlock Management
    # -------------------------------------------------------------------------

    def add_interlock(
        self,
        interlock_id: str,
        name: str,
        description: str,
        auto_reset: bool = False,
    ) -> SafetyInterlock:
        """Register a new safety interlock into the safety subsystem."""
        with self._lock:
            interlock = SafetyInterlock(
                interlock_id=interlock_id,
                name=name,
                description=description,
                auto_reset=auto_reset,
            )
            self._interlocks[interlock_id] = interlock
            return interlock

    def trip_interlock(self, interlock_id: str, reason: str) -> None:
        """Trip a designated safety interlock and abort active operations."""
        with self._lock:
            if interlock_id not in self._interlocks:
                raise KeyError(f"Interlock '{interlock_id}' is not registered.")
            interlock = self._interlocks[interlock_id]
            interlock.trip(reason)

            # Raise critical alarm
            self.raise_alarm(
                alarm_id=f"ALM_{interlock_id}",
                name=f"Safety Interlock Tripped: {interlock.name}",
                severity=AlarmSeverity.CRITICAL,
                description=f"Hardware safety circuit tripped: {reason}",
                source="Safety Interlock Controller",
            )

    def reset_interlock(self, interlock_id: str, force: bool = False) -> bool:
        """Reset a tripped safety interlock."""
        with self._lock:
            if interlock_id not in self._interlocks:
                raise KeyError(f"Interlock '{interlock_id}' is not registered.")
            return self._interlocks[interlock_id].reset(force=force)

    def check_interlocks(self) -> Tuple[bool, List[str]]:
        """Verify that all safety interlocks are healthy prior to an operation.

        Returns:
            Tuple of (all_healthy: bool, list_of_tripped_reasons: list[str]).
        """
        with self._lock:
            tripped_reasons: List[str] = []
            for itlk in self._interlocks.values():
                if itlk.is_tripped:
                    tripped_reasons.append(f"[{itlk.interlock_id}] {itlk.name}: {itlk.trip_reason}")
            return (len(tripped_reasons) == 0, tripped_reasons)

    # -------------------------------------------------------------------------
    # Alarm Management
    # -------------------------------------------------------------------------

    def raise_alarm(
        self,
        alarm_id: str,
        name: str,
        severity: AlarmSeverity,
        description: str,
        source: str = "Hardware Subsystem",
    ) -> Alarm:
        """Raise a new equipment alarm.

        Args:
            alarm_id: Unique alarm ID code.
            name: Concise title of the alarm condition.
            severity: INFO, WARNING, FAULT, or CRITICAL.
            description: Technical detail of the excursion or failure.
            source: Subsystem that reported the failure.

        Returns:
            The created Alarm instance.
        """
        with self._lock:
            alarm = Alarm(
                alarm_id=alarm_id,
                name=name,
                severity=severity,
                timestamp=self.sim_time,
                description=description,
                source=source,
            )
            self._active_alarms.append(alarm)
            self._alarm_history.append(alarm)

            logger.warning(
                "ALARM RAISED [%s] %s (%s): %s",
                severity.value,
                name,
                alarm_id,
                description,
            )

            # Fault and Critical alarms trigger state machine transitions
            if severity in (AlarmSeverity.FAULT, AlarmSeverity.CRITICAL):
                try:
                    self.state_machine.trigger(
                        event="ALARM_TRIP",
                        timestamp=self.sim_time,
                        payload={"alarm_id": alarm_id, "reason": description},
                    )
                except Exception as exc:
                    logger.debug("State transition on alarm ignored: %s", exc)

            return alarm

    def acknowledge_alarm(self, alarm_id: str) -> bool:
        """Acknowledge an active alarm by ID."""
        with self._lock:
            for alarm in self._active_alarms:
                if alarm.alarm_id == alarm_id and not alarm.acknowledged:
                    alarm.acknowledge()
                    logger.info("Alarm acknowledged: %s", alarm_id)
                    return True
            return False

    def clear_alarm(self, alarm_id: str) -> bool:
        """Clear an active alarm condition."""
        with self._lock:
            for alarm in self._active_alarms:
                if alarm.alarm_id == alarm_id and not alarm.cleared:
                    alarm.clear(timestamp=self.sim_time)
                    logger.info("Alarm cleared: %s", alarm_id)

                    # If no remaining fault or critical alarms, attempt clear state transition
                    fault_count = sum(
                        1
                        for a in self._active_alarms
                        if not a.cleared and a.severity in (AlarmSeverity.FAULT, AlarmSeverity.CRITICAL)
                    )
                    if fault_count == 0:
                        try:
                            self.state_machine.trigger(
                                event="CLEAR_ALARM",
                                timestamp=self.sim_time,
                                payload={"cleared_alarm": alarm_id},
                            )
                        except Exception:
                            pass
                    return True
            return False

    def get_active_alarms(self, min_severity: Optional[AlarmSeverity] = None) -> List[Alarm]:
        """Return list of active un-cleared alarms, optionally filtered by min severity."""
        with self._lock:
            active = [a for a in self._active_alarms if not a.cleared]
            if min_severity is None:
                return active
            severity_order = {
                AlarmSeverity.INFO: 0,
                AlarmSeverity.WARNING: 1,
                AlarmSeverity.FAULT: 2,
                AlarmSeverity.CRITICAL: 3,
            }
            threshold = severity_order[min_severity]
            return [a for a in active if severity_order[a.severity] >= threshold]

    # -------------------------------------------------------------------------
    # Maintenance Tracking
    # -------------------------------------------------------------------------

    def add_maintenance_counter(
        self,
        name: str,
        limit: float,
        unit: str,
        pm_action: str,
        initial_value: float = 0.0,
    ) -> MaintenanceCounter:
        """Add a preventive maintenance counter to the equipment."""
        with self._lock:
            counter = MaintenanceCounter(
                name=name,
                current=initial_value,
                limit=limit,
                unit=unit,
                pm_action=pm_action,
                last_serviced_timestamp=self.sim_time,
            )
            self._maintenance_counters[name] = counter
            return counter

    def record_wafer_processed(self, count: int = 1) -> None:
        """Increment processed wafer counter and check PM thresholds."""
        with self._lock:
            if "total_wafers_processed" in self._maintenance_counters:
                ctr = self._maintenance_counters["total_wafers_processed"]
                ctr.increment(count)
                if ctr.is_due():
                    self.raise_alarm(
                        alarm_id="ALM_PM_WAFER_COUNT",
                        name="PM Required: Wafer Threshold Exceeded",
                        severity=AlarmSeverity.WARNING,
                        description=f"{ctr.name} reached {ctr.current}/{ctr.limit}. Action: {ctr.pm_action}",
                        source="Maintenance Manager",
                    )

    def record_rf_hours(self, hours: float) -> None:
        """Accumulate RF plasma hours and check cathode/source maintenance."""
        with self._lock:
            counter_name = "rf_on_hours"
            if counter_name not in self._maintenance_counters:
                self.add_maintenance_counter(
                    name=counter_name,
                    limit=200.0,
                    unit="hr",
                    pm_action="Inspect and replace RF match coil / focus ring",
                )
            ctr = self._maintenance_counters[counter_name]
            ctr.increment(hours)
            if ctr.is_due():
                self.raise_alarm(
                    alarm_id="ALM_PM_RF_HOURS",
                    name="PM Required: RF On-Time Limit",
                    severity=AlarmSeverity.WARNING,
                    description=f"RF hours reached {ctr.current:.1f}/{ctr.limit:.1f} hr. Action: {ctr.pm_action}",
                    source="RF Generator Maintenance Subsystem",
                )

    def check_maintenance_status(self) -> Dict[str, Dict[str, Any]]:
        """Return status dictionary of all maintenance counters."""
        with self._lock:
            return {name: c.to_dict() for name, c in self._maintenance_counters.items()}

    def reset_maintenance_counter(self, name: str) -> None:
        """Reset a maintenance counter following service."""
        with self._lock:
            if name not in self._maintenance_counters:
                raise KeyError(f"Counter '{name}' not found.")
            self._maintenance_counters[name].reset(timestamp=self.sim_time)
            logger.info("Maintenance counter '%s' reset successfully.", name)

    # -------------------------------------------------------------------------
    # Chamber Registration
    # -------------------------------------------------------------------------

    def add_chamber(self, chamber: ProcessChamber) -> None:
        """Register a process chamber to this equipment."""
        with self._lock:
            self._process_chambers.append(chamber)

    # -------------------------------------------------------------------------
    # SECS/GEM Interface Hooks
    # -------------------------------------------------------------------------

    def set_gem_control_state(self, state: GEMControlState) -> None:
        """Set GEM Control State (SEMI E30)."""
        with self._lock:
            prev = self.gem_control_state
            self.gem_control_state = state
            logger.info("[%s] GEM Control State changed: %s -> %s", self.equipment_id, prev.value, state.value)

    def set_gem_processing_state(self, state: GEMProcessingState) -> None:
        """Set GEM Processing State (SEMI E30)."""
        with self._lock:
            prev = self.gem_processing_state
            self.gem_processing_state = state
            logger.info("[%s] GEM Processing State changed: %s -> %s", self.equipment_id, prev.value, state.value)

    # -------------------------------------------------------------------------
    # Abstract Equipment Lifecycle Methods
    # -------------------------------------------------------------------------

    @abstractmethod
    def initialize(self) -> bool:
        """Perform hardware self-tests, sensor calibration, and tool startup.

        Returns:
            True if tool successfully transitions to STANDBY state.
        """
        pass

    @abstractmethod
    def process_wafer(self, wafer: Wafer, recipe: Any) -> Any:
        """Execute a process recipe on the specified wafer.

        Args:
            wafer: Target silicon wafer.
            recipe: Process recipe container.

        Returns:
            Process result containing telemetry and physical modifications.
        """
        pass

    @abstractmethod
    def abort(self, reason: str) -> bool:
        """Safely interrupt the current operation, extinguish plasma/heaters, and vent/purge.

        Args:
            reason: Operator or supervisory abort reason.

        Returns:
            True if safely aborted.
        """
        pass

    @abstractmethod
    def emergency_stop(self, reason: str) -> None:
        """Execute an immediate SEMI S2 Emergency Stop (EMO).

        Instantly closes toxic gas valves, de-energizes RF and high voltages,
        and halts all robot movements without waiting for recipe steps.

        Args:
            reason: Root safety justification.
        """
        pass
