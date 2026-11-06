"""Dispatch and Scheduling Subsystem for Semiconductor Manufacturing Execution System (MES).

Implements standard fab lot dispatch heuristics, dynamic queueing, recipe qualification,
SEMI E10 equipment state verification, and fab throughput accounting.

Standards References:
  - SEMI E10: Standard for Definition and Measurement of Equipment Reliability,
    Availability, and Maintainability (RAM)
  - SEMI E30: Generic Model for Communications and Control of Manufacturing Equipment (GEM)
  - SEMI E87: Specification for Carrier Management (CMS)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from src.simulation.core.process_route import ProcessRoute, ProcessStep
from src.simulation.mes.audit_log import AuditLog, EventTypes
from src.simulation.mes.wafer_tracking import (
    CarrierState,
    LotRecord,
    LotState,
    WaferTrackingSystem,
)


class DispatchRule(str, Enum):
    """Lot dispatch heuristics commonly deployed in automated semiconductor wafer fabs."""
    FIFO = "FIFO"                         # First-In, First-Out (by queue arrival time)
    PRIORITY = "PRIORITY"                 # Highest lot priority first (e.g. Hot Lot / Expedite)
    DUE_DATE = "DUE_DATE"                 # Earliest Due Date (EDD)
    CRITICAL_RATIO = "CRITICAL_RATIO"     # (Due Date - Current Time) / Remaining Process Time
    SPT = "SPT"                           # Shortest Processing Time first


class SEMIEquipmentState(str, Enum):
    """Equipment operational states defined by SEMI Standard E10."""
    PRD = "PRD"  # Productive: Regular production or engineering run underway
    SBY = "SBY"  # Standby: Unoccupied, idle, and fully operational
    ENG = "ENG"  # Engineering: R&D experimentation, golden wafer test
    SDT = "SDT"  # Scheduled Downtime: Preventive maintenance, routine cleaning
    UDT = "UDT"  # Unscheduled Downtime: Fault, interlock trip, breakdown
    NST = "NST"  # Non-Scheduled Time: Tool powered down, plant idle


@dataclass
class QueueItem:
    """An individual production lot waiting in an equipment buffer queue.

    Attributes:
        lot_id: Semiconductor lot identifier.
        arrival_time: Timestamp when lot arrived at queue buffer.
        due_date: Target shipment or completion timestamp.
        remaining_process_time_min: Estimated remaining total cycle time in fab (minutes).
        current_step_duration_min: Duration of the step to be run on this equipment (minutes).
        recipe_name: Recipe to be executed for this lot.
    """

    lot_id: str
    arrival_time: float
    due_date: float
    remaining_process_time_min: float
    current_step_duration_min: float
    recipe_name: str


@dataclass
class EquipmentProfile:
    """Tool capability and live status model per SEMI E10.

    Attributes:
        equipment_id: Unique tool identifier (e.g. 'FURNACE_DIFF_01').
        equipment_type: Equipment classification matching process route step.
        state: Current SEMI E10 operational state.
        qualified_recipes: Set of qualified recipe names tool is authorized to run.
        current_lot_id: Lot currently undergoing active processing in chamber.
        current_recipe: Active executing recipe name.
        load_ports: Total number of load port docks (typically 2 to 4).
        total_productive_seconds: Total logged seconds in PRD state.
        total_standby_seconds: Total logged seconds in SBY state.
        total_downtime_seconds: Total logged seconds in SDT/UDT states.
    """

    equipment_id: str
    equipment_type: str
    state: SEMIEquipmentState = SEMIEquipmentState.SBY
    qualified_recipes: Set[str] = field(default_factory=set)
    current_lot_id: Optional[str] = None
    current_recipe: Optional[str] = None
    load_ports: int = 2
    total_productive_seconds: float = 0.0
    total_standby_seconds: float = 0.0
    total_downtime_seconds: float = 0.0


class EquipmentQueue:
    """Managed queue of lots waiting at an equipment group or load port."""

    def __init__(self, equipment_id: str, default_rule: DispatchRule = DispatchRule.PRIORITY) -> None:
        """Initialize empty queue for equipment tool."""
        self.equipment_id: str = equipment_id
        self.active_rule: DispatchRule = default_rule
        self._items: List[QueueItem] = []

    def __len__(self) -> int:
        """Return number of lots in queue."""
        return len(self._items)

    @property
    def is_empty(self) -> bool:
        """True if no lots are waiting in queue."""
        return len(self._items) == 0

    def enqueue(
        self,
        lot_id: str,
        arrival_time: float,
        due_date: float,
        remaining_process_time_min: float,
        current_step_duration_min: float,
        recipe_name: str,
    ) -> None:
        """Enqueue a new lot waiting for processing."""
        item = QueueItem(
            lot_id=lot_id,
            arrival_time=arrival_time,
            due_date=due_date,
            remaining_process_time_min=remaining_process_time_min,
            current_step_duration_min=current_step_duration_min,
            recipe_name=recipe_name,
        )
        self._items.append(item)

    def remove(self, lot_id: str) -> Optional[QueueItem]:
        """Remove a lot by ID from queue."""
        for idx, it in enumerate(self._items):
            if it.lot_id == lot_id:
                return self._items.pop(idx)
        return None

    def get_ranked_lots(
        self,
        current_sim_time: float,
        lot_lookup: Callable[[str], LotRecord],
        rule: Optional[DispatchRule] = None,
    ) -> List[QueueItem]:
        """Sort waiting lots according to the designated dispatch heuristic."""
        active_rule = rule or self.active_rule
        items_copy = list(self._items)

        match active_rule:
            case DispatchRule.FIFO:
                # Sort ascending by arrival time
                items_copy.sort(key=lambda item: item.arrival_time)

            case DispatchRule.PRIORITY:
                # Sort descending by lot priority, secondary ascending by arrival
                def priority_key(item: QueueItem) -> Tuple[int, float]:
                    try:
                        lot = lot_lookup(item.lot_id)
                        prio = lot.priority
                    except KeyError:
                        prio = 50
                    return (-prio, item.arrival_time)

                items_copy.sort(key=priority_key)

            case DispatchRule.DUE_DATE:
                # Earliest due date first
                items_copy.sort(key=lambda item: item.due_date)

            case DispatchRule.CRITICAL_RATIO:
                # Critical ratio = (due_date - current_time) / remaining_time
                # Lower CR indicates highest urgency (< 1.0 is behind schedule)
                def cr_key(item: QueueItem) -> float:
                    rem = max(1.0, item.remaining_process_time_min * 60.0)
                    time_remaining = item.due_date - current_sim_time
                    return time_remaining / rem

                items_copy.sort(key=cr_key)

            case DispatchRule.SPT:
                # Shortest current step duration first
                items_copy.sort(key=lambda item: item.current_step_duration_min)

        return items_copy


class Dispatcher:
    """Automated Manufacturing Execution Dispatch Engine.

    Manages:
      - Equipment availability and state transitions (SEMI E10).
      - Step routing (identifying tools qualified for each process step).
      - Recipe qualification enforcement (preventing wrong recipe execution).
      - Heuristic lot selection from equipment queues.
      - Real-time throughput (wafers/hr, lots/hr, utilization).
    """

    def __init__(
        self,
        tracking_system: WaferTrackingSystem,
        audit_log: Optional[AuditLog] = None,
    ) -> None:
        """Initialize dispatcher linked to MES tracking and audit."""
        self.tracking_system: WaferTrackingSystem = tracking_system
        self.audit_log: Optional[AuditLog] = audit_log

        self.equipment: Dict[str, EquipmentProfile] = {}
        self.queues: Dict[str, EquipmentQueue] = {}
        self.routes: Dict[str, ProcessRoute] = {}

        # Throughput counters
        self.total_completed_lots: int = 0
        self.total_completed_wafers: int = 0
        self.simulation_start_time: float = 0.0

    def register_equipment(
        self,
        equipment_id: str,
        equipment_type: str,
        qualified_recipes: Optional[Set[str]] = None,
        load_ports: int = 2,
    ) -> EquipmentProfile:
        """Register equipment tool in dispatcher."""
        if equipment_id in self.equipment:
            raise ValueError(f"Equipment '{equipment_id}' is already registered")

        prof = EquipmentProfile(
            equipment_id=equipment_id,
            equipment_type=equipment_type,
            state=SEMIEquipmentState.SBY,
            qualified_recipes=set(qualified_recipes or []),
            load_ports=load_ports,
        )
        self.equipment[equipment_id] = prof
        self.queues[equipment_id] = EquipmentQueue(equipment_id)
        return prof

    def qualify_recipe(self, equipment_id: str, recipe_name: str) -> None:
        """Add a recipe to an equipment's qualified recipe registry."""
        eq = self.get_equipment(equipment_id)
        eq.qualified_recipes.add(recipe_name)

        if self.audit_log:
            self.audit_log.append(
                event_type=EventTypes.RECIPE_DOWNLOAD,
                user_id="PROCESS_ENGINEER",
                description=f"Recipe '{recipe_name}' qualified on {equipment_id}",
                equipment_id=equipment_id,
                details={"recipe_name": recipe_name},
            )

    def register_route(self, route: ProcessRoute) -> None:
        """Register process technology route for step routing."""
        self.routes[route.route_id] = route

    def set_equipment_state(
        self,
        equipment_id: str,
        new_state: SEMIEquipmentState,
        user_id: str = "SYSTEM",
        reason: str = "",
    ) -> None:
        """Transition equipment state according to SEMI E10."""
        eq = self.get_equipment(equipment_id)
        old_state = eq.state
        eq.state = new_state

        if self.audit_log:
            ev_type = EventTypes.MAINTENANCE if new_state in (SEMIEquipmentState.SDT, SEMIEquipmentState.UDT) else EventTypes.OPERATOR_ACTION
            self.audit_log.append(
                event_type=ev_type,
                user_id=user_id,
                description=f"Equipment {equipment_id} state changed from {old_state.value} to {new_state.value}: {reason}",
                equipment_id=equipment_id,
                details={"from": old_state.value, "to": new_state.value, "reason": reason},
            )

    def find_capable_equipment(self, equipment_type: str) -> List[str]:
        """Locate all equipment IDs that match required equipment type."""
        return [
            eq_id
            for eq_id, prof in self.equipment.items()
            if prof.equipment_type == equipment_type
        ]

    def is_recipe_qualified(self, equipment_id: str, recipe_name: str) -> bool:
        """Verify whether an equipment tool is qualified to run a specified recipe."""
        eq = self.get_equipment(equipment_id)
        # Empty set can be treated as open prototype or strictly unqualified.
        # Semiconductor best-practice is explicit qualification:
        return recipe_name in eq.qualified_recipes

    def route_lot_to_queue(
        self,
        lot_id: str,
        current_sim_time: float,
        due_date: float,
        route_id: str,
    ) -> str:
        """Route lot to the optimal waiting queue based on its current process step."""
        lot = self.tracking_system.get_lot(lot_id)
        if route_id not in self.routes:
            raise KeyError(f"Route '{route_id}' not found")
        route = self.routes[route_id]

        current_step = route.steps[lot.current_step_index]
        capable_tools = self.find_capable_equipment(current_step.equipment_type)

        if not capable_tools:
            raise RuntimeError(
                f"No equipment in fab matches step requirement '{current_step.equipment_type}' "
                f"for step {current_step.step_id}"
            )

        # Select tool with shortest queue length and recipe qualification
        best_tool: Optional[str] = None
        min_queue_len = float("inf")

        for tool_id in capable_tools:
            prof = self.equipment[tool_id]
            # Prioritize qualified tools
            is_qual = self.is_recipe_qualified(tool_id, current_step.recipe_name)
            q_len = len(self.queues[tool_id])
            score = q_len + (0 if is_qual else 100)
            if score < min_queue_len:
                min_queue_len = score
                best_tool = tool_id

        selected_tool = best_tool or capable_tools[0]

        # Calculate remaining total cycle time
        remaining_time = sum(
            s.estimated_duration_min
            for s in route.steps[lot.current_step_index:]
        )

        self.queues[selected_tool].enqueue(
            lot_id=lot_id,
            arrival_time=current_sim_time,
            due_date=due_date,
            remaining_process_time_min=remaining_time,
            current_step_duration_min=current_step.estimated_duration_min,
            recipe_name=current_step.recipe_name,
        )

        # Update carrier state if applicable
        if lot.carrier_id and lot.carrier_id in self.tracking_system.carriers:
            self.tracking_system.move_carrier(
                lot.carrier_id,
                new_location=f"{selected_tool}_LOAD_PORT",
                new_state=CarrierState.AT_LOAD_PORT,
                user_id="DISPATCHER",
            )

        return selected_tool

    def select_next_lot(
        self,
        equipment_id: str,
        current_sim_time: float,
        rule: Optional[DispatchRule] = None,
    ) -> Optional[LotRecord]:
        """Select next eligible lot from queue, enforcing tool availability and recipe qualification.

        Returns:
            LotRecord if an eligible lot is ready, or None.
        """
        eq = self.get_equipment(equipment_id)
        if eq.state != SEMIEquipmentState.SBY:
            return None  # Tool not in Standby (idle and ready)

        queue = self.queues[equipment_id]
        if queue.is_empty:
            return None

        ranked_items = queue.get_ranked_lots(
            current_sim_time=current_sim_time,
            lot_lookup=self.tracking_system.get_lot,
            rule=rule,
        )

        for item in ranked_items:
            lot = self.tracking_system.get_lot(item.lot_id)
            # Skip lots on hold or scrapped
            if lot.lot_state in (LotState.HOLD, LotState.SCRAPPED, LotState.COMPLETE):
                continue

            # Recipe qualification check
            if not self.is_recipe_qualified(equipment_id, item.recipe_name):
                # Try next ranked lot
                continue

            # Eligible lot found!
            return lot

        return None

    def dispatch_lot(
        self,
        equipment_id: str,
        lot_id: str,
        current_sim_time: float,
        user_id: str = "MES_AUTO_DISPATCH",
    ) -> None:
        """Formally dispatch a lot onto equipment for process execution."""
        eq = self.get_equipment(equipment_id)
        lot = self.tracking_system.get_lot(lot_id)

        # Dequeue
        self.queues[equipment_id].remove(lot_id)

        # Update equipment state
        eq.state = SEMIEquipmentState.PRD
        eq.current_lot_id = lot_id
        eq.current_recipe = lot.current_step_id

        # Update lot state
        lot.lot_state = LotState.ACTIVE

        # Update carrier location to equipment
        if lot.carrier_id and lot.carrier_id in self.tracking_system.carriers:
            self.tracking_system.move_carrier(
                carrier_id=lot.carrier_id,
                new_location=equipment_id,
                new_state=CarrierState.AT_EQUIPMENT,
                user_id=user_id,
            )

        if self.audit_log:
            self.audit_log.append(
                event_type=EventTypes.PROCESS_START,
                user_id=user_id,
                description=f"Lot {lot_id} dispatched onto {equipment_id} for {lot.current_step_id}",
                equipment_id=equipment_id,
                lot_id=lot_id,
                details={
                    "current_step": lot.current_step_id,
                    "wafer_count": len(lot.wafer_list),
                    "sim_time": current_sim_time,
                },
            )

    def complete_processing(
        self,
        equipment_id: str,
        lot_id: str,
        route_id: str,
        execution_duration_sec: float,
        current_sim_time: float,
        user_id: str = "MES_AUTO_DISPATCH",
    ) -> None:
        """Complete step execution, advance lot step pointer, and restore tool to SBY."""
        eq = self.get_equipment(equipment_id)
        lot = self.tracking_system.get_lot(lot_id)
        route = self.routes[route_id]

        eq.state = SEMIEquipmentState.SBY
        eq.current_lot_id = None
        eq.current_recipe = None
        eq.total_productive_seconds += execution_duration_sec

        # Advance step pointer
        lot.current_step_index += 1
        if lot.current_step_index >= route.total_steps:
            lot.lot_state = LotState.COMPLETE
            lot.completion_time = datetime.now(timezone.utc).isoformat()
            self.total_completed_lots += 1
            self.total_completed_wafers += len(lot.wafer_list)
        else:
            lot.current_step_id = route.steps[lot.current_step_index].step_id
            lot.lot_state = LotState.QUEUED

        if self.audit_log:
            self.audit_log.append(
                event_type=EventTypes.PROCESS_END,
                user_id=user_id,
                description=f"Lot {lot_id} completed step on {equipment_id}",
                equipment_id=equipment_id,
                lot_id=lot_id,
                details={
                    "advanced_to_step": lot.current_step_id,
                    "is_completed": lot.lot_state == LotState.COMPLETE,
                    "duration_sec": execution_duration_sec,
                },
            )

    def calculate_throughput(self, total_elapsed_hours: float) -> Dict[str, float]:
        """Compute fab and tool-level throughput statistics."""
        hours = max(1e-4, total_elapsed_hours)
        wafers_per_hr = self.total_completed_wafers / hours
        lots_per_hr = self.total_completed_lots / hours

        eq_utilizations: Dict[str, float] = {}
        for eq_id, prof in self.equipment.items():
            total_sec = prof.total_productive_seconds + prof.total_standby_seconds + prof.total_downtime_seconds
            util = (prof.total_productive_seconds / max(1.0, total_sec)) * 100.0
            eq_utilizations[f"{eq_id}_utilization_pct"] = round(util, 2)

        return {
            "completed_lots": float(self.total_completed_lots),
            "completed_wafers": float(self.total_completed_wafers),
            "throughput_wafers_per_hour": round(wafers_per_hr, 2),
            "throughput_lots_per_hour": round(lots_per_hr, 2),
            **eq_utilizations,
        }

    def get_equipment(self, equipment_id: str) -> EquipmentProfile:
        """Fetch equipment profile by ID or raise KeyError."""
        if equipment_id not in self.equipment:
            raise KeyError(f"Equipment '{equipment_id}' not registered in dispatcher")
        return self.equipment[equipment_id]
