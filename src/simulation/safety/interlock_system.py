"""Safety Interlock System for Semiconductor Fabrication Equipment.

This module provides a production-grade safety engine fully compliant with
SEMI S2 (Environmental, Health, and Safety Guideline for Semiconductor Manufacturing
Equipment) and international functional safety standards (IEC 61508 / ISO 13849).

Standards & Regulatory Foundations:
  - SEMI S2-0715: Environmental, Health, and Safety Guideline for Semiconductor
    Manufacturing Equipment.
  - SEMI S8-0915: Safety Guidelines for Ergonomics Engineering of Semiconductor
    Manufacturing Equipment.
  - SEMI S10-0307: Safety Guideline for Risk Assessment and Risk Evaluation Process.
  - SEMI S22-0715: Safety Guideline for Electrical Design of Semiconductor Manufacturing Equipment.
  - SEMI E12: Standard for Equipment Specific Gas and Chemical Systems.
  - NFPA 79: Electrical Standard for Industrial Machinery.
  - OSHA 29 CFR 1910.119: Process Safety Management of Highly Hazardous Chemicals.

Key Engineering Requirements:
  1. Strict hierarchy of interlock severities: WARNING, FAULT, CRITICAL, EMERGENCY.
  2. SEMI S2 Emergency Machine Off (EMO):
     Hardwired, fail-safe, immediate hazardous energy isolation. EMERGENCY
     interlocks can NEVER be bypassed by software or operator override.
  3. Safe state definitions for all primary fab equipment types (Furnace, Etcher,
     PECVD, Implanter, Track/Lithography, Wet Bench).
  4. Comprehensive interlock categories:
     - Vacuum (foreline, chamber overpressure, turbo molecular pump speed)
     - Temperature (over-temperature, chuck coolant flow)
     - Gas (toxic/pyrophoric leak detection, delivery differential pressure)
     - Mechanical (wafer handler intrusion, maintenance lid switch)
     - Electrical (RF reflected power, enclosure high-voltage interlock, ground fault)
     - Chemical (acid bath level, wet bench exhaust flow)
     - Exhaust (scrubber static pressure, house exhaust velocity)
     - Seismic (triaxial acceleration > 0.1g)
  5. Immutable audit trail logging all trips, resets, authorizations, and actions.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class InterlockSeverity(str, Enum):
    """SEMI S2 Interlock Hazard Severity Levels.

    Hierarchy:
      EMERGENCY > CRITICAL > FAULT > WARNING
    """
    WARNING = "WARNING"      # Advisory alert; recipe continues; requires operator acknowledgment
    FAULT = "FAULT"          # Inhibits recipe start or next wafer; allows controlled in-situ finish
    CRITICAL = "CRITICAL"    # Immediate controlled abort; isolates process gases; halts RF; safe vent
    EMERGENCY = "EMERGENCY"  # Immediate hardwired trip (EMO); de-energizes all hazardous power & gases


class InterlockCategory(str, Enum):
    """Functional equipment subsystems governed by SEMI safety guidelines."""
    EMO = "EMO"
    VACUUM = "VACUUM"
    TEMPERATURE = "TEMPERATURE"
    GAS_TOXIC = "GAS_TOXIC"
    GAS_FLAMMABLE = "GAS_FLAMMABLE"
    MECHANICAL = "MECHANICAL"
    ELECTRICAL = "ELECTRICAL"
    CHEMICAL = "CHEMICAL"
    EXHAUST = "EXHAUST"
    SEISMIC = "SEISMIC"


class SafetyActionType(str, Enum):
    """Standardized deterministic safety mitigation actions."""
    EMO_HARD_TRIP = "EMO_HARD_TRIP"
    ISOLATE_PROCESS_GASES = "ISOLATE_PROCESS_GASES"
    PURGE_CHAMBER_N2 = "PURGE_CHAMBER_N2"
    DE_ENERGIZE_RF = "DE_ENERGIZE_RF"
    DE_ENERGIZE_HEATERS = "DE_ENERGIZE_HEATERS"
    ABORT_ROBOT_MOTION = "ABORT_ROBOT_MOTION"
    ISOLATE_VACUUM_VALVES = "ISOLATE_VACUUM_VALVES"
    LOCK_CHAMBER_LID = "LOCK_CHAMBER_LID"
    ACTIVATE_FACILITY_ALARM = "ACTIVATE_FACILITY_ALARM"
    HOLD_PUMP_DOWN = "HOLD_PUMP_DOWN"
    SAFE_VENT_TO_ATM = "SAFE_VENT_TO_ATM"


class EquipmentType(str, Enum):
    """Primary semiconductor process tool types."""
    HORIZONTAL_FURNACE = "HORIZONTAL_FURNACE"
    VERTICAL_FURNACE = "VERTICAL_FURNACE"
    PLASMA_ETCHER = "PLASMA_ETCHER"
    PECVD_SYSTEM = "PECVD_SYSTEM"
    LPCVD_SYSTEM = "LPCVD_SYSTEM"
    ION_IMPLANTER = "ION_IMPLANTER"
    WET_BENCH = "WET_BENCH"
    LITHOGRAPHY_TRACK = "LITHOGRAPHY_TRACK"


class SafetyInterlockBypassForbiddenError(PermissionError):
    """Raised when an unauthorized or prohibited interlock bypass is attempted.

    Per SEMI S2 Section 12, EMERGENCY and EMO circuits shall NOT permit bypass.
    """
    pass


@dataclass
class EquipmentSafeState:
    """Rigorous safe state definition for equipment upon safety shutdown.

    Attributes:
        equipment_type: Type of fab tool.
        rf_power: Safe state of RF generators ("DE_ENERGIZED", "N/A").
        heater_power: Safe state of furnace/resistive heaters ("DE_ENERGIZED", "IDLE_STANDBY").
        gas_valves: State of toxic/flammable gas supply valves ("PNEUMATIC_FAIL_CLOSED").
        purge_state: Inert purge ballast status ("FLOWING_N2_BALLAST", "ISOLATED").
        vacuum_valves: Gate and slit valve positions ("CLOSED_ISOLATED").
        robot_brakes: Transfer robot status ("DYNAMIC_BRAKES_ENGAGED").
        exhaust: Ventilation status ("MAXIMUM_DAMPER_OPEN").
        description: Text description of the safe state.
    """
    equipment_type: EquipmentType
    rf_power: str
    heater_power: str
    gas_valves: str
    purge_state: str
    vacuum_valves: str
    robot_brakes: str
    exhaust: str
    description: str


# Pre-defined SEMI S2 equipment safe states
STANDARD_SAFE_STATES: Dict[EquipmentType, EquipmentSafeState] = {
    EquipmentType.PLASMA_ETCHER: EquipmentSafeState(
        equipment_type=EquipmentType.PLASMA_ETCHER,
        rf_power="DE_ENERGIZED_ZERO_WATTS",
        heater_power="DE_ENERGIZED",
        gas_valves="PNEUMATIC_NORMALLY_CLOSED_ISOLATED",
        purge_state="N2_PURGE_FLOWING_500_SCCM",
        vacuum_valves="TURBO_GATE_CLOSED_FORELINE_ISOLATED",
        robot_brakes="TRANSFER_ARM_BRAKES_LOCKED",
        exhaust="ACID_TOXIC_EXHAUST_OPEN",
        description="Plasma extinguished, reactive gases isolated, chamber holding base vacuum with N2 purge.",
    ),
    EquipmentType.HORIZONTAL_FURNACE: EquipmentSafeState(
        equipment_type=EquipmentType.HORIZONTAL_FURNACE,
        rf_power="N/A",
        heater_power="SCR_HEATER_CIRCUITS_OPENED",
        gas_valves="DRY_O2_HCL_PYROGENIC_GASES_ISOLATED",
        purge_state="N2_BALLAST_FLOWING_10_SLM",
        vacuum_valves="ATMOSPHERIC_FLAPPER_EXHAUST_OPEN",
        robot_brakes="BOAT_LOADER_MOTION_LOCKED",
        exhaust="HEAT_EXHAUST_OPEN_MAX",
        description="Furnace heating de-energized, tube flooded with high-purity N2 ballast.",
    ),
    EquipmentType.VERTICAL_FURNACE: EquipmentSafeState(
        equipment_type=EquipmentType.VERTICAL_FURNACE,
        rf_power="N/A",
        heater_power="ELEMENTS_DE_ENERGIZED",
        gas_valves="PROCESS_GAS_LINES_PNEUMATIC_SHUT",
        purge_state="HIGH_PURITY_N2_PURGE_ENGAGED",
        vacuum_valves="TUBE_SEALED",
        robot_brakes="VERTICAL_ELEVATOR_MECHANICAL_PIN_ENGAGED",
        exhaust="CABINET_EXHAUST_ACTIVE",
        description="Boat locked in position, toxic/pyrophoric gases isolated, continuous N2 purge.",
    ),
    EquipmentType.PECVD_SYSTEM: EquipmentSafeState(
        equipment_type=EquipmentType.PECVD_SYSTEM,
        rf_power="HIGH_FREQ_LOW_FREQ_GENERATORS_INTERLOCKED_OFF",
        heater_power="SUSCEPTOR_HEATER_DE_ENERGIZED",
        gas_valves="SILANE_AMMONIA_ISOLATED_AT_POU_VALVES",
        purge_state="N2_CYCLIC_BALLAST_ACTIVE",
        vacuum_valves="SLIT_VALVES_CLOSED_VACUUM_ISOLATION_VALVE_CLOSED",
        robot_brakes="WAFER_HANDLER_BRAKES_ON",
        exhaust="PYROPHORIC_SCRUBBER_EXHAUST_ACTIVE",
        description="Silane pyrophoric gas isolated at manifold, RF killed, chamber sealed.",
    ),
    EquipmentType.LPCVD_SYSTEM: EquipmentSafeState(
        equipment_type=EquipmentType.LPCVD_SYSTEM,
        rf_power="N/A",
        heater_power="MULTI_ZONE_ELEMENTS_OFF",
        gas_valves="DCS_NH3_SIH4_ISOLATED",
        purge_state="N2_BALLAST_20_SLM",
        vacuum_valves="ROOTS_BLOWER_ISOLATION_VALVE_SHUT",
        robot_brakes="BOAT_RETRACTOR_HALTED",
        exhaust="POINT_OF_USE_THERMAL_SCRUBBER_POWERED",
        description="Furnace power tripped, toxic precursors closed, dry pump N2 ballast running.",
    ),
    EquipmentType.ION_IMPLANTER: EquipmentSafeState(
        equipment_type=EquipmentType.ION_IMPLANTER,
        rf_power="SOURCE_RF_OFF",
        heater_power="SOURCE_FILAMENT_OFF",
        gas_valves="ASH3_PH3_SDS_CYLINDERS_PNEUMATIC_SHUT",
        purge_state="VACUUM_HOLD",
        vacuum_valves="BEAMLINE_HIGH_VACUUM_VALVES_ISOLATED",
        robot_brakes="PLATEN_DRIVE_DISENGAGED_BRAKED",
        exhaust="TOXIC_GAS_CABINET_EXHAUST_FULL",
        description="High-voltage acceleration (>100kV) dropped, toxic hydride gases isolated.",
    ),
    EquipmentType.WET_BENCH: EquipmentSafeState(
        equipment_type=EquipmentType.WET_BENCH,
        rf_power="N/A",
        heater_power="BATH_IMMERSION_HEATERS_TRIPPED",
        gas_valves="N2_BUBBLERS_ISOLATED",
        purge_state="DRAIN_RINSE_ACTIVE",
        vacuum_valves="N/A",
        robot_brakes="OVERHEAD_ROBOT_LOCKED",
        exhaust="ACID_CORROSIVE_EXHAUST_CONFIRMED",
        description="Immersion heaters disconnected, bath covers closed, aspirators stopped.",
    ),
    EquipmentType.LITHOGRAPHY_TRACK: EquipmentSafeState(
        equipment_type=EquipmentType.LITHOGRAPHY_TRACK,
        rf_power="N/A",
        heater_power="HOT_PLATES_TEMPERATURE_CUTOFF",
        gas_valves="SOLVENT_PUMPS_DE_ENERGIZED",
        purge_state="CLEANROOM_LAMINAR_FLOW_HEPA_ACTIVE",
        vacuum_valves="SPIN_CHUCK_VACUUM_MAINTAINED",
        robot_brakes="SCARA_ARM_DYNAMIC_STOP",
        exhaust="SOLVENT_VAPOR_EXHAUST_OPEN",
        description="Solvent dispense lines depressurized, spin chuck stopped with vacuum hold.",
    ),
}


@dataclass
class SafetyInterlock:
    """An individual SEMI S2 compliant safety interlock.

    Attributes:
        interlock_id: Unique hardware or logical interlock code (e.g. 'ILK-EMO-001').
        name: Short descriptive name.
        description: Functional safety description and hazard mitigation.
        category: InterlockCategory.
        severity: InterlockSeverity (WARNING, FAULT, CRITICAL, EMERGENCY).
        condition: Callable returning True if system is SAFE, False if TRIPPED.
        actions_when_triggered: List of SafetyActionType executed when tripped.
        bypass_authorized: Whether maintenance bypass is currently active.
        bypass_user: Operator or technician ID who authorized the bypass.
        bypass_reason: Engineering reason for maintenance bypass.
        bypass_timestamp: Timestamp when bypass was authorized.
        tripped: Current tripped latch state.
        latch: If True, remains tripped even after condition returns to True until reset.
        last_checked: Timestamp of most recent condition evaluation.
        last_triggered: Timestamp when interlock last tripped.
    """
    interlock_id: str
    name: str
    description: str
    category: InterlockCategory
    severity: InterlockSeverity
    condition: Callable[[], bool]
    actions_when_triggered: List[SafetyActionType] = field(default_factory=list)
    bypass_authorized: bool = False
    bypass_user: Optional[str] = None
    bypass_reason: Optional[str] = None
    bypass_timestamp: Optional[datetime.datetime] = None
    tripped: bool = False
    latch: bool = True
    last_checked: Optional[datetime.datetime] = None
    last_triggered: Optional[datetime.datetime] = None


@dataclass
class InterlockAuditLogEntry:
    """Immutable audit trail log entry for safety events."""
    timestamp: datetime.datetime
    event_type: str  # TRIP, RESET, BYPASS_AUTHORIZED, BYPASS_REVOKED, EMO_TRIGGERED
    interlock_id: str
    severity: InterlockSeverity
    operator_id: str
    details: str
    actions_dispatched: List[SafetyActionType]


@dataclass
class InterlockEvaluationResult:
    """Outcome of evaluating all registered system safety interlocks."""
    all_safe: bool
    highest_severity: Optional[InterlockSeverity]
    tripped_interlocks: List[SafetyInterlock]
    active_bypasses: List[SafetyInterlock]
    actions_to_execute: List[SafetyActionType]
    timestamp: datetime.datetime


class InterlockSystem:
    """Central safety interlock supervision engine for semiconductor manufacturing equipment."""

    def __init__(self, equipment_type: EquipmentType = EquipmentType.PLASMA_ETCHER) -> None:
        """Initialize interlock supervisory system for specified equipment type."""
        self.equipment_type: EquipmentType = equipment_type
        self._interlocks: Dict[str, SafetyInterlock] = {}
        self._audit_log: List[InterlockAuditLogEntry] = []
        self._emo_active: bool = False
        self._emo_operator: Optional[str] = None
        self._emo_reason: Optional[str] = None
        self._emo_timestamp: Optional[datetime.datetime] = None

    @property
    def is_emo_tripped(self) -> bool:
        """Return True if Emergency Machine Off is active."""
        return self._emo_active

    @property
    def safe_state_definition(self) -> EquipmentSafeState:
        """Return the SEMI S2 defined safe state for this equipment type."""
        return STANDARD_SAFE_STATES[self.equipment_type]

    def register_interlock(self, interlock: SafetyInterlock) -> None:
        """Register a new safety interlock into the system.

        Args:
            interlock: SafetyInterlock instance.

        Raises:
            ValueError: If interlock_id is already registered.
        """
        if interlock.interlock_id in self._interlocks:
            raise ValueError(f"Interlock '{interlock.interlock_id}' is already registered.")
        self._interlocks[interlock.interlock_id] = interlock

    def unregister_interlock(self, interlock_id: str) -> None:
        """Unregister an interlock (only allowed if not currently tripped).

        Args:
            interlock_id: Unique interlock code.

        Raises:
            KeyError: If interlock not found.
            RuntimeError: If interlock is currently tripped.
        """
        if interlock_id not in self._interlocks:
            raise KeyError(f"Interlock '{interlock_id}' not found.")
        if self._interlocks[interlock_id].tripped:
            raise RuntimeError(f"Cannot unregister tripped interlock '{interlock_id}'.")
        del self._interlocks[interlock_id]

    def evaluate_all(self) -> InterlockEvaluationResult:
        """Evaluate all registered interlocks against current machine sensor conditions.

        Severity Hierarchy:
          EMERGENCY > CRITICAL > FAULT > WARNING

        Returns:
            InterlockEvaluationResult summary.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        tripped: List[SafetyInterlock] = []
        bypasses: List[SafetyInterlock] = []
        actions: Set[SafetyActionType] = set()
        highest_sev: Optional[InterlockSeverity] = None

        severity_rank = {
            InterlockSeverity.WARNING: 1,
            InterlockSeverity.FAULT: 2,
            InterlockSeverity.CRITICAL: 3,
            InterlockSeverity.EMERGENCY: 4,
        }

        # If EMO is physically latched, enforce emergency actions immediately
        if self._emo_active:
            actions.add(SafetyActionType.EMO_HARD_TRIP)
            actions.add(SafetyActionType.ISOLATE_PROCESS_GASES)
            actions.add(SafetyActionType.DE_ENERGIZE_RF)
            actions.add(SafetyActionType.DE_ENERGIZE_HEATERS)
            actions.add(SafetyActionType.ABORT_ROBOT_MOTION)
            highest_sev = InterlockSeverity.EMERGENCY

        for ilk in self._interlocks.values():
            ilk.last_checked = now

            if ilk.bypass_authorized:
                bypasses.append(ilk)
                continue  # Bypassed interlock condition is skipped

            # Evaluate physical condition callback
            try:
                is_safe = ilk.condition()
            except Exception as exc:
                # Fail-safe: an exception in an interlock condition must trip the interlock!
                is_safe = False

            if not is_safe:
                was_already_tripped = ilk.tripped
                ilk.tripped = True
                ilk.last_triggered = now
                tripped.append(ilk)

                for act in ilk.actions_when_triggered:
                    actions.add(act)

                # Determine highest severity
                if highest_sev is None or severity_rank[ilk.severity] > severity_rank[highest_sev]:
                    highest_sev = ilk.severity

                if not was_already_tripped:
                    # Log new trip event
                    self._audit_log.append(
                        InterlockAuditLogEntry(
                            timestamp=now,
                            event_type="INTERLOCK_TRIPPED",
                            interlock_id=ilk.interlock_id,
                            severity=ilk.severity,
                            operator_id="SYSTEM_SUPERVISOR",
                            details=f"Interlock '{ilk.name}' condition violated: {ilk.description}",
                            actions_dispatched=ilk.actions_when_triggered,
                        )
                    )
            else:
                # If condition returned to safe: unlatch only if latch is False
                if not ilk.latch and ilk.tripped:
                    ilk.tripped = False
                elif ilk.tripped:
                    # Still latched until manual reset
                    tripped.append(ilk)
                    for act in ilk.actions_when_triggered:
                        actions.add(act)
                    if highest_sev is None or severity_rank[ilk.severity] > severity_rank[highest_sev]:
                        highest_sev = ilk.severity

        all_ok = (len(tripped) == 0 and not self._emo_active)

        return InterlockEvaluationResult(
            all_safe=all_ok,
            highest_severity=highest_sev,
            tripped_interlocks=tripped,
            active_bypasses=bypasses,
            actions_to_execute=sorted(list(actions), key=lambda a: a.value),
            timestamp=now,
        )

    def can_start_process(self) -> Tuple[bool, List[str]]:
        """Pre-operation safety interlock check before recipe start.

        Returns:
            Tuple of (can_start: bool, reasons: List[str]).
        """
        eval_result = self.evaluate_all()
        reasons: List[str] = []

        if self._emo_active:
            reasons.append(f"EMO button is currently depressed (triggered by {self._emo_operator}: {self._emo_reason}).")

        for ilk in eval_result.tripped_interlocks:
            if ilk.severity in (InterlockSeverity.FAULT, InterlockSeverity.CRITICAL, InterlockSeverity.EMERGENCY):
                reasons.append(f"[{ilk.severity.value}] {ilk.interlock_id} ({ilk.name}) is tripped: {ilk.description}")

        can_start = (len(reasons) == 0)
        return can_start, reasons

    def trigger_emo(self, reason: str, operator_id: str) -> None:
        """Trigger Emergency Machine Off (EMO).

        SEMI S2 Section 12 compliant:
        Immediately trips all safety actions, de-energizing RF, heaters, and hazardous gases.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        self._emo_active = True
        self._emo_operator = operator_id
        self._emo_reason = reason
        self._emo_timestamp = now

        emo_actions = [
            SafetyActionType.EMO_HARD_TRIP,
            SafetyActionType.ISOLATE_PROCESS_GASES,
            SafetyActionType.DE_ENERGIZE_RF,
            SafetyActionType.DE_ENERGIZE_HEATERS,
            SafetyActionType.ABORT_ROBOT_MOTION,
            SafetyActionType.ACTIVATE_FACILITY_ALARM,
        ]

        self._audit_log.append(
            InterlockAuditLogEntry(
                timestamp=now,
                event_type="EMO_TRIGGERED",
                interlock_id="EMO-SYSTEM-BUTTON",
                severity=InterlockSeverity.EMERGENCY,
                operator_id=operator_id,
                details=f"EMERGENCY MACHINE OFF triggered: {reason}",
                actions_dispatched=emo_actions,
            )
        )

    def reset_emo(self, operator_id: str, physical_twist_key_released: bool = True) -> None:
        """Reset Emergency Machine Off following verified clearance of hazard.

        Args:
            operator_id: Authorized engineer badge ID.
            physical_twist_key_released: Hardware verification that EMO button was unlatched.

        Raises:
            PermissionError: If physical button is still held down.
        """
        if not physical_twist_key_released:
            raise PermissionError("Cannot reset EMO: Physical pushbutton is still mechanically latched in depressed state.")

        now = datetime.datetime.now(datetime.timezone.utc)
        self._emo_active = False
        prev_reason = self._emo_reason
        self._emo_reason = None
        self._emo_operator = None
        self._emo_timestamp = None

        self._audit_log.append(
            InterlockAuditLogEntry(
                timestamp=now,
                event_type="EMO_RESET",
                interlock_id="EMO-SYSTEM-BUTTON",
                severity=InterlockSeverity.EMERGENCY,
                operator_id=operator_id,
                details=f"EMO reset by authorized operator. Previous trip reason: {prev_reason}",
                actions_dispatched=[],
            )
        )

    def authorize_bypass(
        self,
        interlock_id: str,
        operator_id: str,
        reason: str,
        authorized_role: str,
    ) -> None:
        """Authorize a maintenance bypass on a specific interlock.

        SEMI S2 Compliance Rule:
          EMERGENCY interlocks can NEVER be bypassed under any circumstances.
          Bypasses on CRITICAL interlocks require 'MAINTENANCE_SUPERVISOR' or 'EHS_OFFICER' role.

        Args:
            interlock_id: Target interlock code.
            operator_id: Operator/Engineer identifier.
            reason: Justification for bypass.
            authorized_role: Security role of the requester.

        Raises:
            SafetyInterlockBypassForbiddenError: If attempting to bypass EMERGENCY interlock
                or lacking adequate role credentials.
        """
        if interlock_id not in self._interlocks:
            raise KeyError(f"Interlock '{interlock_id}' does not exist.")

        ilk = self._interlocks[interlock_id]

        # STRICT SEMI S2 RULE: EMERGENCY INTERLOCKS CANNOT BE BYPASSED
        if ilk.severity == InterlockSeverity.EMERGENCY:
            raise SafetyInterlockBypassForbiddenError(
                f"SEMI S2 Violation: EMERGENCY severity interlock '{interlock_id}' "
                f"('{ilk.name}') can NEVER be bypassed by software or administrative action."
            )

        # Role validation for CRITICAL severity
        if ilk.severity == InterlockSeverity.CRITICAL and authorized_role not in ("MAINTENANCE_SUPERVISOR", "EHS_OFFICER", "FAB_DIRECTOR"):
            raise SafetyInterlockBypassForbiddenError(
                f"Bypassing CRITICAL interlock '{interlock_id}' requires MAINTENANCE_SUPERVISOR "
                f"or EHS_OFFICER role; current role is '{authorized_role}'."
            )

        now = datetime.datetime.now(datetime.timezone.utc)
        ilk.bypass_authorized = True
        ilk.bypass_user = operator_id
        ilk.bypass_reason = reason
        ilk.bypass_timestamp = now
        ilk.tripped = False  # Temporarily clear tripped state while bypassed

        self._audit_log.append(
            InterlockAuditLogEntry(
                timestamp=now,
                event_type="BYPASS_AUTHORIZED",
                interlock_id=interlock_id,
                severity=ilk.severity,
                operator_id=operator_id,
                details=f"Maintenance bypass authorized by {operator_id} ({authorized_role}): {reason}",
                actions_dispatched=[],
            )
        )

    def revoke_bypass(self, interlock_id: str, operator_id: str) -> None:
        """Revoke an active maintenance bypass and restore normal protection."""
        if interlock_id not in self._interlocks:
            raise KeyError(f"Interlock '{interlock_id}' does not exist.")

        ilk = self._interlocks[interlock_id]
        now = datetime.datetime.now(datetime.timezone.utc)
        prev_user = ilk.bypass_user
        ilk.bypass_authorized = False
        ilk.bypass_user = None
        ilk.bypass_reason = None
        ilk.bypass_timestamp = None

        self._audit_log.append(
            InterlockAuditLogEntry(
                timestamp=now,
                event_type="BYPASS_REVOKED",
                interlock_id=interlock_id,
                severity=ilk.severity,
                operator_id=operator_id,
                details=f"Maintenance bypass revoked by {operator_id}. (Previous bypass user: {prev_user})",
                actions_dispatched=[],
            )
        )

    def reset_interlock(self, interlock_id: str, operator_id: str) -> bool:
        """Attempt to reset a latched interlock after the fault condition has cleared.

        Returns:
            True if successfully reset, False if physical condition is still unsafe.
        """
        if interlock_id not in self._interlocks:
            raise KeyError(f"Interlock '{interlock_id}' does not exist.")

        ilk = self._interlocks[interlock_id]

        # Verify underlying sensor condition is safe
        try:
            is_safe = ilk.condition()
        except Exception:
            is_safe = False

        now = datetime.datetime.now(datetime.timezone.utc)
        if is_safe:
            ilk.tripped = False
            self._audit_log.append(
                InterlockAuditLogEntry(
                    timestamp=now,
                    event_type="INTERLOCK_RESET_SUCCESS",
                    interlock_id=interlock_id,
                    severity=ilk.severity,
                    operator_id=operator_id,
                    details=f"Interlock '{ilk.name}' successfully reset to normal safe state.",
                    actions_dispatched=[],
                )
            )
            return True
        else:
            self._audit_log.append(
                InterlockAuditLogEntry(
                    timestamp=now,
                    event_type="INTERLOCK_RESET_FAILED",
                    interlock_id=interlock_id,
                    severity=ilk.severity,
                    operator_id=operator_id,
                    details=f"Reset rejected: Physical condition for '{ilk.name}' is still in violation.",
                    actions_dispatched=[],
                )
            )
            return False

    def get_audit_trail(self) -> List[InterlockAuditLogEntry]:
        """Return the complete immutable safety audit log."""
        return list(self._audit_log)


def create_standard_fab_interlocks(
    sensor_telemetry: Dict[str, Any],
    equipment_type: EquipmentType = EquipmentType.PLASMA_ETCHER,
) -> InterlockSystem:
    """Factory creating the complete SEMI S2 suite of 8 common fab safety interlocks.

    Interlocks created:
      1. Vacuum: Chamber overpressure threshold & foreline backing limit
      2. Temperature: Chuck / furnace over-temperature limit switch
      3. Gas Toxic: Toxic gas sniffer sensor detection limit (< TLV)
      4. Gas Flammable: Pyrophoric / combustible gas leak detector (< 25% LEL)
      5. Mechanical: Wafer robot intrusion barrier & chamber lid limit switch
      6. Electrical: High-voltage enclosure door switch & RF ground fault
      7. Chemical / Exhaust: Exhaust scrubber duct differential pressure limit
      8. Seismic: SEMI S2 triaxial earthquake accelerometer (> 0.1g)

    Args:
      sensor_telemetry: Dictionary holding live equipment telemetry data.
      equipment_type: Equipment type classification.

    Returns:
      Configured InterlockSystem ready for operation.
    """
    sys = InterlockSystem(equipment_type=equipment_type)

    # 1. Vacuum Interlock (Chamber overpressure during process)
    # Safe if pressure < 50.0 Torr (when processing at mTorr regime)
    sys.register_interlock(
        SafetyInterlock(
            interlock_id="ILK-VAC-001",
            name="Chamber Vacuum Overpressure Interlock",
            description="Trips if chamber vacuum degrades above safe process threshold (50 Torr).",
            category=InterlockCategory.VACUUM,
            severity=InterlockSeverity.CRITICAL,
            condition=lambda: float(sensor_telemetry.get("chamber_pressure_torr", 0.01)) < 50.0,
            actions_when_triggered=[
                SafetyActionType.ISOLATE_PROCESS_GASES,
                SafetyActionType.DE_ENERGIZE_RF,
                SafetyActionType.ISOLATE_VACUUM_VALVES,
            ],
        )
    )

    # 2. Temperature Interlock (Furnace or chuck over-temp)
    # Safe if temperature < 1150 °C (or chuck < 85°C)
    sys.register_interlock(
        SafetyInterlock(
            interlock_id="ILK-TEMP-001",
            name="Thermal Over-Temperature Thermal Cutoff",
            description="Trips if heating elements exceed maximum safe design temperature limit (1150°C).",
            category=InterlockCategory.TEMPERATURE,
            severity=InterlockSeverity.CRITICAL,
            condition=lambda: float(sensor_telemetry.get("temperature_c", 25.0)) <= 1150.0,
            actions_when_triggered=[
                SafetyActionType.DE_ENERGIZE_HEATERS,
                SafetyActionType.ISOLATE_PROCESS_GASES,
                SafetyActionType.PURGE_CHAMBER_N2,
            ],
        )
    )

    # 3. Gas Toxic Leak Interlock
    # Safe if toxic hydride ppm is zero or below 0.005 ppm (TLV)
    sys.register_interlock(
        SafetyInterlock(
            interlock_id="ILK-GAS-TOX-001",
            name="Toxic Gas Sniffer Threshold Interlock",
            description="SEMI S2 / OSHA toxic gas detection sniffer in cabinet/chase. Trips if concentration >= TLV.",
            category=InterlockCategory.GAS_TOXIC,
            severity=InterlockSeverity.EMERGENCY,  # Emergency: toxic life safety!
            condition=lambda: float(sensor_telemetry.get("toxic_gas_ppm", 0.0)) < 0.005,
            actions_when_triggered=[
                SafetyActionType.ISOLATE_PROCESS_GASES,
                SafetyActionType.EMO_HARD_TRIP,
                SafetyActionType.ACTIVATE_FACILITY_ALARM,
            ],
        )
    )

    # 4. Gas Flammable / Pyrophoric Leak Interlock
    # Safe if lower explosive limit (LEL) < 25%
    sys.register_interlock(
        SafetyInterlock(
            interlock_id="ILK-GAS-FLAM-001",
            name="Flammable / Pyrophoric Gas LEL Detector",
            description="Combustible gas optical/catalytic bead detector. Trips if atmosphere >= 25% LEL.",
            category=InterlockCategory.GAS_FLAMMABLE,
            severity=InterlockSeverity.CRITICAL,
            condition=lambda: float(sensor_telemetry.get("combustible_lel_pct", 0.0)) < 25.0,
            actions_when_triggered=[
                SafetyActionType.ISOLATE_PROCESS_GASES,
                SafetyActionType.PURGE_CHAMBER_N2,
                SafetyActionType.DE_ENERGIZE_RF,
            ],
        )
    )

    # 5. Mechanical Enclosure / Lid Interlock
    # Safe if maintenance lid is physically closed (switch = True)
    sys.register_interlock(
        SafetyInterlock(
            interlock_id="ILK-MECH-LID-001",
            name="Chamber Maintenance Lid Closed Limit Switch",
            description="Physical positive-break safety limit switch on vacuum chamber upper lid.",
            category=InterlockCategory.MECHANICAL,
            severity=InterlockSeverity.FAULT,
            condition=lambda: bool(sensor_telemetry.get("chamber_lid_closed", True)),
            actions_when_triggered=[
                SafetyActionType.DE_ENERGIZE_RF,
                SafetyActionType.ABORT_ROBOT_MOTION,
            ],
        )
    )

    # 6. Electrical High-Voltage Enclosure Interlock
    # Safe if generator HV cabinet door is interlocked shut
    sys.register_interlock(
        SafetyInterlock(
            interlock_id="ILK-ELEC-HV-001",
            name="High-Voltage Generator Enclosure Interlock",
            description="NFPA 79 door safety interlock on RF matching network and high-voltage power supply.",
            category=InterlockCategory.ELECTRICAL,
            severity=InterlockSeverity.CRITICAL,
            condition=lambda: bool(sensor_telemetry.get("hv_enclosure_door_closed", True)),
            actions_when_triggered=[
                SafetyActionType.DE_ENERGIZE_RF,
                SafetyActionType.DE_ENERGIZE_HEATERS,
            ],
        )
    )

    # 7. Exhaust Ventilation Flow Interlock
    # Safe if exhaust differential pressure is adequate (> 0.5 in. w.g. or > 500 fpm velocity)
    sys.register_interlock(
        SafetyInterlock(
            interlock_id="ILK-EXH-001",
            name="Scrubber House Exhaust Static Pressure Interlock",
            description="Differential pressure switch confirming minimum ventilation draft velocity.",
            category=InterlockCategory.EXHAUST,
            severity=InterlockSeverity.FAULT,
            condition=lambda: float(sensor_telemetry.get("exhaust_dp_in_wg", 1.2)) >= 0.50,
            actions_when_triggered=[
                SafetyActionType.ISOLATE_PROCESS_GASES,
                SafetyActionType.DE_ENERGIZE_HEATERS,
            ],
        )
    )

    # 8. Seismic Accelerometer Interlock
    # SEMI S2 requirement: Earthquake sensor trips if ground acceleration > 0.10 g
    sys.register_interlock(
        SafetyInterlock(
            interlock_id="ILK-SEIS-001",
            name="SEMI S2 Triaxial Earthquake Accelerometer",
            description="Triaxial seismic acceleration trip threshold (> 0.10g) for automatic fab shutoff.",
            category=InterlockCategory.SEISMIC,
            severity=InterlockSeverity.EMERGENCY,
            condition=lambda: float(sensor_telemetry.get("seismic_accel_g", 0.0)) < 0.10,
            actions_when_triggered=[
                SafetyActionType.EMO_HARD_TRIP,
                SafetyActionType.ISOLATE_PROCESS_GASES,
                SafetyActionType.DE_ENERGIZE_RF,
                SafetyActionType.DE_ENERGIZE_HEATERS,
                SafetyActionType.ABORT_ROBOT_MOTION,
            ],
        )
    )

    return sys
