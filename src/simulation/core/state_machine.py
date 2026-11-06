"""SEMI E10 Compliant Equipment State Machine for Semiconductor Digital Twin.

Implements the standard SEMI E10 specification for equipment reliability,
availability, and maintainability (RAM). Tracks 6 basic states:
  - 1000 PRODUCTIVE: Equipment is performing its intended manufacturing function.
  - 2000 STANDBY: Equipment is ready to operate, but waiting for WIP, operator, or instructions.
  - 3000 ENGINEERING: Equipment is operational but executing process/equipment engineering or qualification.
  - 4000 SCHEDULED_DOWN: Equipment is undergoing planned maintenance, cleans, or conversions.
  - 5000 UNSCHEDULED_DOWN: Equipment has incurred an unscheduled failure, fault, or process excursion.
  - 6000 NON_SCHEDULED: Equipment is unpowered, training, or awaiting site qualification.

Features:
  - Strict hierarchical State and Sub-state validation per SEMI E10.
  - Guard conditions and pre/post transition hooks.
  - High-precision timestamped transition history logging.
  - SEMI E10 operational metrics calculation (Availability, MTBF, MTTR, OEE).
  - Thread-safe state transitions and queries.
  - Full dictionary serialization / deserialization.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SemiE10State(str, Enum):
    """SEMI E10 Six Basic Equipment States with numeric code references."""
    PRODUCTIVE = "1000_PRODUCTIVE"
    STANDBY = "2000_STANDBY"
    ENGINEERING = "3000_ENGINEERING"
    SCHEDULED_DOWN = "4000_SCHEDULED_DOWN"
    UNSCHEDULED_DOWN = "5000_UNSCHEDULED_DOWN"
    NON_SCHEDULED = "6000_NON_SCHEDULED"

    @property
    def code(self) -> int:
        """Return the SEMI E10 4-digit numeric state code."""
        return int(self.value.split("_")[0])

    @property
    def display_name(self) -> str:
        """Return human-readable state name."""
        return self.value.split("_", 1)[1]


class SemiE10Substate(str, Enum):
    """SEMI E10 Standard Sub-states with associated parent states."""

    # 1000 PRODUCTIVE Sub-states
    REGULAR_RUN = "1100_REGULAR_RUN"
    WORK_FOR_THIRD_PARTIES = "1200_WORK_FOR_THIRD_PARTIES"
    REWORK = "1300_REWORK"
    ENGINEERING_RUNS = "1400_ENGINEERING_RUNS"

    # 2000 STANDBY Sub-states
    NO_OPERATOR = "2100_NO_OPERATOR"
    NO_PRODUCT = "2200_NO_PRODUCT"
    NO_SUPPORT = "2300_NO_SUPPORT"
    WARM_UP = "2400_WARM_UP"

    # 3000 ENGINEERING Sub-states
    PROCESS_ENGINEERING = "3100_PROCESS_ENGINEERING"
    EQUIPMENT_ENGINEERING = "3200_EQUIPMENT_ENGINEERING"
    SOFTWARE_TESTING = "3300_SOFTWARE_TESTING"

    # 4000 SCHEDULED DOWN Sub-states
    PREVENTIVE_MAINTENANCE = "4100_PREVENTIVE_MAINTENANCE"
    PERIODIC_CLEAN = "4200_PERIODIC_CLEAN"
    SETUP_CHANGEOVER = "4300_SETUP_CHANGEOVER"
    FACILITY_SCHEDULED = "4400_FACILITY_SCHEDULED"

    # 5000 UNSCHEDULED DOWN Sub-states
    EQUIPMENT_FAULT = "5100_EQUIPMENT_FAULT"
    PROCESS_EXCURSION = "5200_PROCESS_EXCURSION"
    FACILITY_FAILURE = "5300_FACILITY_FAILURE"
    WAITING_FOR_PARTS = "5400_WAITING_FOR_PARTS"
    WAITING_FOR_MAINTENANCE = "5500_WAITING_FOR_MAINTENANCE"

    # 6000 NON-SCHEDULED Sub-states
    OFFLINE_IDLE = "6100_OFFLINE_IDLE"
    TRAINING = "6200_TRAINING"
    INSTALLATION_QUAL = "6300_INSTALLATION_QUAL"

    @property
    def code(self) -> int:
        """Return the SEMI E10 sub-state code."""
        return int(self.value.split("_")[0])

    @property
    def display_name(self) -> str:
        """Return human-readable sub-state name."""
        return self.value.split("_", 1)[1]

    @property
    def parent_state(self) -> SemiE10State:
        """Derive the SEMI E10 parent state from the substate code."""
        state_code = (self.code // 1000) * 1000
        for state in SemiE10State:
            if state.code == state_code:
                return state
        raise ValueError(f"Unmapped parent state for substate: {self.value}")


# Mapping for fast validation of state-to-substate relationships
_VALID_SUBSTATES_PER_STATE: Dict[SemiE10State, Set[SemiE10Substate]] = {
    SemiE10State.PRODUCTIVE: {
        SemiE10Substate.REGULAR_RUN,
        SemiE10Substate.WORK_FOR_THIRD_PARTIES,
        SemiE10Substate.REWORK,
        SemiE10Substate.ENGINEERING_RUNS,
    },
    SemiE10State.STANDBY: {
        SemiE10Substate.NO_OPERATOR,
        SemiE10Substate.NO_PRODUCT,
        SemiE10Substate.NO_SUPPORT,
        SemiE10Substate.WARM_UP,
    },
    SemiE10State.ENGINEERING: {
        SemiE10Substate.PROCESS_ENGINEERING,
        SemiE10Substate.EQUIPMENT_ENGINEERING,
        SemiE10Substate.SOFTWARE_TESTING,
    },
    SemiE10State.SCHEDULED_DOWN: {
        SemiE10Substate.PREVENTIVE_MAINTENANCE,
        SemiE10Substate.PERIODIC_CLEAN,
        SemiE10Substate.SETUP_CHANGEOVER,
        SemiE10Substate.FACILITY_SCHEDULED,
    },
    SemiE10State.UNSCHEDULED_DOWN: {
        SemiE10Substate.EQUIPMENT_FAULT,
        SemiE10Substate.PROCESS_EXCURSION,
        SemiE10Substate.FACILITY_FAILURE,
        SemiE10Substate.WAITING_FOR_PARTS,
        SemiE10Substate.WAITING_FOR_MAINTENANCE,
    },
    SemiE10State.NON_SCHEDULED: {
        SemiE10Substate.OFFLINE_IDLE,
        SemiE10Substate.TRAINING,
        SemiE10Substate.INSTALLATION_QUAL,
    },
}


class EquipmentEvent(str, Enum):
    """Standardized factory equipment events triggering state transitions."""
    START_RUN = "START_RUN"
    COMPLETE_RUN = "COMPLETE_RUN"
    ABORT_RUN = "ABORT_RUN"
    WIP_ARRIVED = "WIP_ARRIVED"
    WIP_DEPLETED = "WIP_DEPLETED"
    OPERATOR_ABSENT = "OPERATOR_ABSENT"
    OPERATOR_AVAILABLE = "OPERATOR_AVAILABLE"
    START_WARMUP = "START_WARMUP"
    WARMUP_COMPLETE = "WARMUP_COMPLETE"
    START_ENG_TEST = "START_ENG_TEST"
    COMPLETE_ENG_TEST = "COMPLETE_ENG_TEST"
    SCHEDULE_PM = "SCHEDULE_PM"
    COMPLETE_PM = "COMPLETE_PM"
    START_CLEAN = "START_CLEAN"
    COMPLETE_CLEAN = "COMPLETE_CLEAN"
    ALARM_TRIP = "ALARM_TRIP"
    EXCURSION_DETECTED = "EXCURSION_DETECTED"
    CLEAR_ALARM = "CLEAR_ALARM"
    FACILITY_FAILURE = "FACILITY_FAILURE"
    FACILITY_RESTORED = "FACILITY_RESTORED"
    ORDER_PARTS = "ORDER_PARTS"
    PARTS_RECEIVED = "PARTS_RECEIVED"
    SHUTDOWN_TOOL = "SHUTDOWN_TOOL"
    POWER_ON_TOOL = "POWER_ON_TOOL"
    START_TRAINING = "START_TRAINING"
    END_TRAINING = "END_TRAINING"


@dataclass(frozen=True)
class TransitionContext:
    """Contextual metadata passed to guard conditions and transition callbacks.

    Attributes:
        equipment_id: Unique hardware identifier of the equipment.
        event: Triggering event name.
        from_state: Pre-transition state.
        from_substate: Pre-transition sub-state.
        to_state: Target state.
        to_substate: Target sub-state.
        timestamp: Simulation or epoch timestamp (seconds).
        payload: Event parameters (e.g. lot_id, alarm_code, reason).
    """

    equipment_id: str
    event: str
    from_state: SemiE10State
    from_substate: SemiE10Substate
    to_state: SemiE10State
    to_substate: SemiE10Substate
    timestamp: float
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StateHistoryEntry:
    """Historical record of an equipment state transition.

    Attributes:
        timestamp: Transition time (seconds).
        from_state: Pre-transition state.
        from_substate: Pre-transition sub-state.
        to_state: New state entered.
        to_substate: New sub-state entered.
        event: Event name that triggered transition.
        reason: Justification or operator comment.
        duration_in_prev_state: Seconds spent in the previous state.
        metadata: Associated contextual payload.
    """

    timestamp: float
    from_state: SemiE10State
    from_substate: SemiE10Substate
    to_state: SemiE10State
    to_substate: SemiE10Substate
    event: str
    reason: str
    duration_in_prev_state: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize history entry to dictionary."""
        return {
            "timestamp": self.timestamp,
            "from_state": self.from_state.value,
            "from_substate": self.from_substate.value,
            "to_state": self.to_state.value,
            "to_substate": self.to_substate.value,
            "event": self.event,
            "reason": self.reason,
            "duration_in_prev_state": self.duration_in_prev_state,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StateHistoryEntry:
        """Deserialize history entry from dictionary."""
        return cls(
            timestamp=float(data["timestamp"]),
            from_state=SemiE10State(data["from_state"]),
            from_substate=SemiE10Substate(data["from_substate"]),
            to_state=SemiE10State(data["to_state"]),
            to_substate=SemiE10Substate(data["to_substate"]),
            event=str(data["event"]),
            reason=str(data.get("reason", "")),
            duration_in_prev_state=float(data["duration_in_prev_state"]),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class TransitionRule:
    """Definition of an allowed transition within the SEMI E10 state machine.

    Attributes:
        event: Triggering event symbol or string.
        source_state: Source state or None if wildcard (*).
        source_substate: Source sub-state or None if wildcard.
        target_state: Resulting state.
        target_substate: Resulting sub-state.
        guard: Optional callable evaluating (context) -> bool.
        before_transition: Optional callback executed before state mutation.
        after_transition: Optional callback executed after state mutation.
    """

    event: str
    source_state: Optional[SemiE10State]
    source_substate: Optional[SemiE10Substate]
    target_state: SemiE10State
    target_substate: SemiE10Substate
    guard: Optional[Callable[[TransitionContext], bool]] = None
    before_transition: Optional[Callable[[TransitionContext], None]] = None
    after_transition: Optional[Callable[[TransitionContext], None]] = None


@dataclass
class SemiE10Metrics:
    """Reliability, Availability, and Maintainability (RAM) metrics defined in SEMI E10."""
    total_time_hours: float
    productive_hours: float
    standby_hours: float
    engineering_hours: float
    scheduled_down_hours: float
    unscheduled_down_hours: float
    non_scheduled_hours: float
    failure_count: int
    repair_count: int
    availability: float  # (Total - SchedDown - UnschedDown) / Total
    operational_availability: float  # Productive / (Total - NonScheduled)
    mean_time_between_failures_hours: float  # Productive_hours / Failure_count
    mean_time_to_repair_hours: float  # UnschedDown_hours / Repair_count

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_time_hours": round(self.total_time_hours, 3),
            "productive_hours": round(self.productive_hours, 3),
            "standby_hours": round(self.standby_hours, 3),
            "engineering_hours": round(self.engineering_hours, 3),
            "scheduled_down_hours": round(self.scheduled_down_hours, 3),
            "unscheduled_down_hours": round(self.unscheduled_down_hours, 3),
            "non_scheduled_hours": round(self.non_scheduled_hours, 3),
            "failure_count": self.failure_count,
            "repair_count": self.repair_count,
            "availability": round(self.availability, 4),
            "operational_availability": round(self.operational_availability, 4),
            "mean_time_between_failures_hours": round(self.mean_time_between_failures_hours, 3),
            "mean_time_to_repair_hours": round(self.mean_time_to_repair_hours, 3),
        }


class EquipmentStateMachine:
    """Thread-safe SEMI E10 Equipment State Machine for semiconductor tools.

    Manages states, transitions, guard evaluations, callbacks, and history
    logging with SEMI E10 compliance.
    """

    def __init__(
        self,
        equipment_id: str,
        initial_state: SemiE10State = SemiE10State.STANDBY,
        initial_substate: SemiE10Substate = SemiE10Substate.NO_PRODUCT,
        initial_timestamp: Optional[float] = None,
    ) -> None:
        """Initialize the state machine with equipment ID and initial state.

        Args:
            equipment_id: Equipment identifier (e.g. 'ETCH_ICP_01').
            initial_state: Starting SEMI E10 state.
            initial_substate: Starting SEMI E10 sub-state.
            initial_timestamp: Simulation epoch start time (defaults to time.time()).
        """
        self.equipment_id = equipment_id
        self._lock = threading.RLock()
        self._current_time = initial_timestamp if initial_timestamp is not None else time.time()

        self._validate_substate(initial_state, initial_substate)
        self._current_state = initial_state
        self._current_substate = initial_substate
        self._state_entry_time = self._current_time

        self._history: List[StateHistoryEntry] = []
        self._transitions: List[TransitionRule] = []
        self._listeners: List[Callable[[StateHistoryEntry], None]] = []

        # Setup standard SEMI E10 transition rules
        self._install_default_transitions()

    @staticmethod
    def _validate_substate(state: SemiE10State, substate: SemiE10Substate) -> None:
        """Verify that substate is canonically owned by state."""
        valid_substates = _VALID_SUBSTATES_PER_STATE.get(state, set())
        if substate not in valid_substates:
            raise ValueError(
                f"Substate '{substate.value}' is not a valid child of state '{state.value}'. "
                f"Valid children are: {[s.value for s in valid_substates]}"
            )

    @property
    def current_state(self) -> SemiE10State:
        """Return the current SEMI E10 state under thread lock."""
        with self._lock:
            return self._current_state

    @property
    def current_substate(self) -> SemiE10Substate:
        """Return the current SEMI E10 substate under thread lock."""
        with self._lock:
            return self._current_substate

    @property
    def state_entry_time(self) -> float:
        """Return timestamp when current state was entered."""
        with self._lock:
            return self._state_entry_time

    @property
    def history(self) -> List[StateHistoryEntry]:
        """Return a copy of the state transition history."""
        with self._lock:
            return list(self._history)

    def register_transition(self, rule: TransitionRule) -> None:
        """Add an explicit transition rule to the machine."""
        with self._lock:
            self._validate_substate(rule.target_state, rule.target_substate)
            self._transitions.append(rule)

    def add_listener(self, listener: Callable[[StateHistoryEntry], None]) -> None:
        """Register a callback invoked immediately after every state change."""
        with self._lock:
            self._listeners.append(listener)

    def can_trigger(
        self,
        event: Union[EquipmentEvent, str],
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Evaluate if an event can be triggered from the current state."""
        event_str = event.value if isinstance(event, EquipmentEvent) else str(event)
        payload_data = payload or {}

        with self._lock:
            for rule in self._transitions:
                if rule.event != event_str:
                    continue
                if rule.source_state is not None and rule.source_state != self._current_state:
                    continue
                if rule.source_substate is not None and rule.source_substate != self._current_substate:
                    continue

                if rule.guard is not None:
                    context = TransitionContext(
                        equipment_id=self.equipment_id,
                        event=event_str,
                        from_state=self._current_state,
                        from_substate=self._current_substate,
                        to_state=rule.target_state,
                        to_substate=rule.target_substate,
                        timestamp=self._current_time,
                        payload=payload_data,
                    )
                    try:
                        if not rule.guard(context):
                            continue
                    except Exception as exc:
                        logger.warning("Guard evaluation failed for %s: %s", event_str, exc)
                        continue
                return True
            return False

    def trigger(
        self,
        event: Union[EquipmentEvent, str],
        reason: str = "",
        payload: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None,
    ) -> bool:
        """Trigger a state transition via event.

        Args:
            event: Event symbol or name.
            reason: Operator note or cause description.
            payload: Optional metadata dictionary.
            timestamp: Simulation or physical time in seconds.

        Returns:
            True if transition succeeded, False if no valid transition was found.
        """
        event_str = event.value if isinstance(event, EquipmentEvent) else str(event)
        payload_data = payload or {}

        with self._lock:
            cur_time = timestamp if timestamp is not None else time.time()
            if cur_time < self._state_entry_time:
                # Monotonic clock protection in simulation
                cur_time = self._state_entry_time

            for rule in self._transitions:
                if rule.event != event_str:
                    continue
                if rule.source_state is not None and rule.source_state != self._current_state:
                    continue
                if rule.source_substate is not None and rule.source_substate != self._current_substate:
                    continue

                context = TransitionContext(
                    equipment_id=self.equipment_id,
                    event=event_str,
                    from_state=self._current_state,
                    from_substate=self._current_substate,
                    to_state=rule.target_state,
                    to_substate=rule.target_substate,
                    timestamp=cur_time,
                    payload=payload_data,
                )

                if rule.guard is not None:
                    try:
                        if not rule.guard(context):
                            continue
                    except Exception as exc:
                        logger.warning("Guard execution error for %s on %s: %s", event_str, self.equipment_id, exc)
                        continue

                # Execute pre-transition callback
                if rule.before_transition is not None:
                    try:
                        rule.before_transition(context)
                    except Exception as exc:
                        logger.error("Pre-transition hook error on %s: %s", self.equipment_id, exc)

                duration_in_prev = max(0.0, cur_time - self._state_entry_time)
                history_entry = StateHistoryEntry(
                    timestamp=cur_time,
                    from_state=self._current_state,
                    from_substate=self._current_substate,
                    to_state=rule.target_state,
                    to_substate=rule.target_substate,
                    event=event_str,
                    reason=reason,
                    duration_in_prev_state=duration_in_prev,
                    metadata=payload_data,
                )

                # Mutate State
                self._current_state = rule.target_state
                self._current_substate = rule.target_substate
                self._state_entry_time = cur_time
                self._current_time = cur_time
                self._history.append(history_entry)

                # Execute post-transition callback
                if rule.after_transition is not None:
                    try:
                        rule.after_transition(context)
                    except Exception as exc:
                        logger.error("Post-transition hook error on %s: %s", self.equipment_id, exc)

                # Notify listeners
                for listener in self._listeners:
                    try:
                        listener(history_entry)
                    except Exception as exc:
                        logger.error("State change listener error on %s: %s", self.equipment_id, exc)

                return True

            logger.debug(
                "No matching transition found on %s for event '%s' from state %s / %s",
                self.equipment_id,
                event_str,
                self._current_state.value,
                self._current_substate.value,
            )
            return False

    def force_state(
        self,
        new_state: SemiE10State,
        new_substate: SemiE10Substate,
        reason: str,
        timestamp: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Directly force equipment into a specific SEMI E10 state (operator/supervisor override).

        Args:
            new_state: Target SEMI E10 State.
            new_substate: Target SEMI E10 Sub-state.
            reason: Mandatory reason for supervisor forced state change.
            timestamp: Timestamp in seconds.
            metadata: Associated contextual data.
        """
        with self._lock:
            self._validate_substate(new_state, new_substate)
            cur_time = timestamp if timestamp is not None else time.time()
            if cur_time < self._state_entry_time:
                cur_time = self._state_entry_time

            duration_in_prev = max(0.0, cur_time - self._state_entry_time)
            entry = StateHistoryEntry(
                timestamp=cur_time,
                from_state=self._current_state,
                from_substate=self._current_substate,
                to_state=new_state,
                to_substate=new_substate,
                event="FORCED_OVERRIDE",
                reason=reason,
                duration_in_prev_state=duration_in_prev,
                metadata=metadata or {},
            )

            self._current_state = new_state
            self._current_substate = new_substate
            self._state_entry_time = cur_time
            self._current_time = cur_time
            self._history.append(entry)

            for listener in self._listeners:
                try:
                    listener(entry)
                except Exception as exc:
                    logger.error("Listener error during forced state on %s: %s", self.equipment_id, exc)

    def get_time_in_current_state(self, current_time: Optional[float] = None) -> float:
        """Return duration in seconds spent in the current state."""
        with self._lock:
            now = current_time if current_time is not None else time.time()
            return max(0.0, now - self._state_entry_time)

    def calculate_metrics(
        self,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> SemiE10Metrics:
        """Compute SEMI E10 RAM metrics over an observation window.

        Args:
            start_time: Window start epoch seconds. Defaults to first history entry or entry time.
            end_time: Window end epoch seconds. Defaults to current simulation time.

        Returns:
            SemiE10Metrics object with availability, MTBF, MTTR, and state breakdowns.
        """
        with self._lock:
            now = end_time if end_time is not None else max(self._current_time, time.time())
            earliest = (
                self._history[0].timestamp if self._history else self._state_entry_time
            )
            t_start = start_time if start_time is not None else earliest
            if now <= t_start:
                total_duration = 0.001
            else:
                total_duration = now - t_start

            # State duration accumulator in seconds
            state_times: Dict[SemiE10State, float] = {s: 0.0 for s in SemiE10State}
            failure_count = 0
            repair_count = 0

            # Reconstruct timeline from history
            cursor = t_start
            current_iter_state = self._history[0].from_state if self._history else self._current_state

            for entry in self._history:
                if entry.timestamp < t_start:
                    current_iter_state = entry.to_state
                    continue
                if entry.timestamp > now:
                    break

                dt = entry.timestamp - cursor
                if dt > 0:
                    state_times[current_iter_state] += dt

                # Track failure occurrences (transitions into UNSCHEDULED_DOWN)
                if (
                    entry.to_state == SemiE10State.UNSCHEDULED_DOWN
                    and entry.from_state != SemiE10State.UNSCHEDULED_DOWN
                ):
                    failure_count += 1

                # Track repairs (transitions from UNSCHEDULED_DOWN back to STANDBY/PRODUCTIVE)
                if (
                    entry.from_state == SemiE10State.UNSCHEDULED_DOWN
                    and entry.to_state != SemiE10State.UNSCHEDULED_DOWN
                ):
                    repair_count += 1

                cursor = entry.timestamp
                current_iter_state = entry.to_state

            # Tail interval from cursor to end_time
            if cursor < now:
                state_times[self._current_state] += now - cursor

            prod_s = state_times[SemiE10State.PRODUCTIVE]
            stdby_s = state_times[SemiE10State.STANDBY]
            eng_s = state_times[SemiE10State.ENGINEERING]
            sched_down_s = state_times[SemiE10State.SCHEDULED_DOWN]
            unsched_down_s = state_times[SemiE10State.UNSCHEDULED_DOWN]
            non_sched_s = state_times[SemiE10State.NON_SCHEDULED]

            total_h = total_duration / 3600.0
            prod_h = prod_s / 3600.0
            stdby_h = stdby_s / 3600.0
            eng_h = eng_s / 3600.0
            sched_down_h = sched_down_s / 3600.0
            unsched_down_h = unsched_down_s / 3600.0
            non_sched_h = non_sched_s / 3600.0

            # SEMI E10 Availability: (Total - SchedDown - UnschedDown) / Total
            denom_avail = total_h if total_h > 0 else 1.0
            availability = (total_h - sched_down_h - unsched_down_h) / denom_avail
            availability = max(0.0, min(1.0, availability))

            # Operational Availability: Productive / (Total - NonScheduled)
            ops_denom = total_h - non_sched_h
            if ops_denom > 0:
                ops_avail = max(0.0, min(1.0, prod_h / ops_denom))
            else:
                ops_avail = 1.0

            # MTBF = Productive Time / Failures
            mtbf = (prod_h / failure_count) if failure_count > 0 else prod_h

            # MTTR = Unscheduled Down Time / Repairs
            mttr = (unsched_down_h / repair_count) if repair_count > 0 else unsched_down_h

            return SemiE10Metrics(
                total_time_hours=total_h,
                productive_hours=prod_h,
                standby_hours=stdby_h,
                engineering_hours=eng_h,
                scheduled_down_hours=sched_down_h,
                unscheduled_down_hours=unsched_down_h,
                non_scheduled_hours=non_sched_h,
                failure_count=failure_count,
                repair_count=repair_count,
                availability=availability,
                operational_availability=ops_avail,
                mean_time_between_failures_hours=mtbf,
                mean_time_to_repair_hours=mttr,
            )

    def _install_default_transitions(self) -> None:
        """Populate standard SEMI E10 factory equipment transition matrix."""
        # 1. STANDBY <-> PRODUCTIVE
        self.register_transition(TransitionRule(
            event=EquipmentEvent.START_RUN.value,
            source_state=SemiE10State.STANDBY,
            source_substate=None,
            target_state=SemiE10State.PRODUCTIVE,
            target_substate=SemiE10Substate.REGULAR_RUN,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.COMPLETE_RUN.value,
            source_state=SemiE10State.PRODUCTIVE,
            source_substate=None,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.NO_PRODUCT,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.ABORT_RUN.value,
            source_state=SemiE10State.PRODUCTIVE,
            source_substate=None,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.NO_PRODUCT,
        ))

        # 2. STANDBY Sub-state transitions
        self.register_transition(TransitionRule(
            event=EquipmentEvent.WIP_ARRIVED.value,
            source_state=SemiE10State.STANDBY,
            source_substate=SemiE10Substate.NO_PRODUCT,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.WARM_UP,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.WARMUP_COMPLETE.value,
            source_state=SemiE10State.STANDBY,
            source_substate=SemiE10Substate.WARM_UP,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.NO_PRODUCT,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.OPERATOR_ABSENT.value,
            source_state=SemiE10State.STANDBY,
            source_substate=None,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.NO_OPERATOR,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.OPERATOR_AVAILABLE.value,
            source_state=SemiE10State.STANDBY,
            source_substate=SemiE10Substate.NO_OPERATOR,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.NO_PRODUCT,
        ))

        # 3. ENGINEERING
        self.register_transition(TransitionRule(
            event=EquipmentEvent.START_ENG_TEST.value,
            source_state=SemiE10State.STANDBY,
            source_substate=None,
            target_state=SemiE10State.ENGINEERING,
            target_substate=SemiE10Substate.PROCESS_ENGINEERING,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.COMPLETE_ENG_TEST.value,
            source_state=SemiE10State.ENGINEERING,
            source_substate=None,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.NO_PRODUCT,
        ))

        # 4. SCHEDULED DOWN
        self.register_transition(TransitionRule(
            event=EquipmentEvent.SCHEDULE_PM.value,
            source_state=SemiE10State.STANDBY,
            source_substate=None,
            target_state=SemiE10State.SCHEDULED_DOWN,
            target_substate=SemiE10Substate.PREVENTIVE_MAINTENANCE,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.COMPLETE_PM.value,
            source_state=SemiE10State.SCHEDULED_DOWN,
            source_substate=SemiE10Substate.PREVENTIVE_MAINTENANCE,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.WARM_UP,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.START_CLEAN.value,
            source_state=SemiE10State.STANDBY,
            source_substate=None,
            target_state=SemiE10State.SCHEDULED_DOWN,
            target_substate=SemiE10Substate.PERIODIC_CLEAN,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.COMPLETE_CLEAN.value,
            source_state=SemiE10State.SCHEDULED_DOWN,
            source_substate=SemiE10Substate.PERIODIC_CLEAN,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.WARM_UP,
        ))

        # 5. UNSCHEDULED DOWN (Can trigger from PRODUCTIVE, STANDBY, ENGINEERING)
        for src in (SemiE10State.PRODUCTIVE, SemiE10State.STANDBY, SemiE10State.ENGINEERING):
            self.register_transition(TransitionRule(
                event=EquipmentEvent.ALARM_TRIP.value,
                source_state=src,
                source_substate=None,
                target_state=SemiE10State.UNSCHEDULED_DOWN,
                target_substate=SemiE10Substate.EQUIPMENT_FAULT,
            ))
            self.register_transition(TransitionRule(
                event=EquipmentEvent.EXCURSION_DETECTED.value,
                source_state=src,
                source_substate=None,
                target_state=SemiE10State.UNSCHEDULED_DOWN,
                target_substate=SemiE10Substate.PROCESS_EXCURSION,
            ))
            self.register_transition(TransitionRule(
                event=EquipmentEvent.FACILITY_FAILURE.value,
                source_state=src,
                source_substate=None,
                target_state=SemiE10State.UNSCHEDULED_DOWN,
                target_substate=SemiE10Substate.FACILITY_FAILURE,
            ))

        self.register_transition(TransitionRule(
            event=EquipmentEvent.CLEAR_ALARM.value,
            source_state=SemiE10State.UNSCHEDULED_DOWN,
            source_substate=None,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.WARM_UP,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.FACILITY_RESTORED.value,
            source_state=SemiE10State.UNSCHEDULED_DOWN,
            source_substate=SemiE10Substate.FACILITY_FAILURE,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.WARM_UP,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.ORDER_PARTS.value,
            source_state=SemiE10State.UNSCHEDULED_DOWN,
            source_substate=SemiE10Substate.EQUIPMENT_FAULT,
            target_state=SemiE10State.UNSCHEDULED_DOWN,
            target_substate=SemiE10Substate.WAITING_FOR_PARTS,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.PARTS_RECEIVED.value,
            source_state=SemiE10State.UNSCHEDULED_DOWN,
            source_substate=SemiE10Substate.WAITING_FOR_PARTS,
            target_state=SemiE10State.UNSCHEDULED_DOWN,
            target_substate=SemiE10Substate.WAITING_FOR_MAINTENANCE,
        ))

        # 6. NON-SCHEDULED
        self.register_transition(TransitionRule(
            event=EquipmentEvent.SHUTDOWN_TOOL.value,
            source_state=SemiE10State.STANDBY,
            source_substate=None,
            target_state=SemiE10State.NON_SCHEDULED,
            target_substate=SemiE10Substate.OFFLINE_IDLE,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.POWER_ON_TOOL.value,
            source_state=SemiE10State.NON_SCHEDULED,
            source_substate=SemiE10Substate.OFFLINE_IDLE,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.WARM_UP,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.START_TRAINING.value,
            source_state=SemiE10State.STANDBY,
            source_substate=None,
            target_state=SemiE10State.NON_SCHEDULED,
            target_substate=SemiE10Substate.TRAINING,
        ))
        self.register_transition(TransitionRule(
            event=EquipmentEvent.END_TRAINING.value,
            source_state=SemiE10State.NON_SCHEDULED,
            source_substate=SemiE10Substate.TRAINING,
            target_state=SemiE10State.STANDBY,
            target_substate=SemiE10Substate.NO_PRODUCT,
        ))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state machine and history to dictionary."""
        with self._lock:
            return {
                "equipment_id": self.equipment_id,
                "current_state": self._current_state.value,
                "current_substate": self._current_substate.value,
                "state_entry_time": self._state_entry_time,
                "history": [entry.to_dict() for entry in self._history],
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EquipmentStateMachine:
        """Reconstruct state machine from dictionary representation."""
        sm = cls(
            equipment_id=str(data["equipment_id"]),
            initial_state=SemiE10State(data["current_state"]),
            initial_substate=SemiE10Substate(data["current_substate"]),
            initial_timestamp=float(data["state_entry_time"]),
        )
        if "history" in data:
            sm._history = [StateHistoryEntry.from_dict(h) for h in data["history"]]
        return sm

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"EquipmentStateMachine(equipment_id={self.equipment_id!r}, "
                f"state={self._current_state.name}, substate={self._current_substate.name})"
            )

    def __str__(self) -> str:
        with self._lock:
            return (
                f"[{self.equipment_id}] {self._current_state.display_name} / "
                f"{self._current_substate.display_name} "
                f"(active for {self.get_time_in_current_state():.1f}s)"
            )


# Alias for backward/SEMI compatibility
EquipmentState = SemiE10State

