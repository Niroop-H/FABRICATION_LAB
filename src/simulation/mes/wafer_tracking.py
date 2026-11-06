"""Wafer and Lot Tracking Subsystem for Semiconductor Manufacturing Execution System (MES).

Aligned with Semiconductor Standards:
  - SEMI E87: Specification for Carrier Management (CMS)
  - SEMI E90: Specification for Substrate Tracking
  - SEMI E39: Object Services Standard: Concepts, Behavior, and Services (OSS)

Provides rigorous object models for 200mm cassettes/SMIF pods, 300mm FOUPs,
silicon substrate tracking, wafer genealogy, split/merge tracking, and process history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from src.simulation.mes.audit_log import AuditLog, EventTypes


class CarrierType(str, Enum):
    """Physical wafer carrier classification."""
    FOUP = "FOUP"          # Front Opening Unified Pod (300mm standard)
    CASSETTE = "CASSETTE"  # Open wafer cassette (150mm / 200mm standard)
    SMIF = "SMIF"          # Standard Mechanical Interface pod (sealed 200mm)


class CarrierState(str, Enum):
    """Carrier location state per SEMI E87."""
    AT_EQUIPMENT = "AT_EQUIPMENT"
    IN_STOCKER = "IN_STOCKER"
    IN_TRANSIT = "IN_TRANSIT"
    AT_LOAD_PORT = "AT_LOAD_PORT"


class LotState(str, Enum):
    """Lot manufacturing life-cycle state."""
    QUEUED = "QUEUED"
    ACTIVE = "ACTIVE"
    HOLD = "HOLD"
    COMPLETE = "COMPLETE"
    SCRAPPED = "SCRAPPED"


class WaferStatus(str, Enum):
    """Substrate process status per SEMI E90."""
    UNPROCESSED = "UNPROCESSED"
    IN_PROCESS = "IN_PROCESS"
    PROCESSED = "PROCESSED"
    MEASURED = "MEASURED"
    DEFECTIVE = "DEFECTIVE"
    SCRAPPED = "SCRAPPED"


@dataclass
class CarrierSlot:
    """Individual physical slot in a wafer carrier (1 to 25).

    Attributes:
        slot_number: Physical slot index (1 is typically bottom slot, 25 is top).
        occupied: Whether a wafer physically occupies this slot.
        wafer_id: Identifier of wafer residing in slot, if occupied.
    """

    slot_number: int
    occupied: bool = False
    wafer_id: Optional[str] = None


@dataclass
class WaferCarrier:
    """Wafer carrier vessel (FOUP, SMIF pod, or open cassette) per SEMI E87.

    Attributes:
        carrier_id: Unique RFID / barcode barcode carrier identifier (e.g. 'FOUP_300_042').
        carrier_type: FOUP, CASSETTE, or SMIF.
        capacity: Maximum wafer slot count (standard is 25).
        carrier_state: Location status (AT_EQUIPMENT, IN_STOCKER, IN_TRANSIT, AT_LOAD_PORT).
        current_location: Physical fab location string (e.g. 'STOCKER_BAY_04', 'LITHO_01_LP1').
        slots: Mapping of slot_number (1..capacity) to CarrierSlot.
    """

    carrier_id: str
    carrier_type: CarrierType
    capacity: int = 25
    carrier_state: CarrierState = CarrierState.IN_STOCKER
    current_location: str = "CENTRAL_STOCKER"
    slots: Dict[int, CarrierSlot] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize slot array if not provided."""
        if not self.slots:
            for i in range(1, self.capacity + 1):
                self.slots[i] = CarrierSlot(slot_number=i, occupied=False, wafer_id=None)

    @property
    def occupied_count(self) -> int:
        """Number of wafers currently in carrier."""
        return sum(1 for s in self.slots.values() if s.occupied)

    @property
    def empty_slots(self) -> List[int]:
        """List of empty slot indices."""
        return [num for num, s in sorted(self.slots.items()) if not s.occupied]

    @property
    def wafer_ids(self) -> List[str]:
        """List of all wafer IDs currently stored in carrier."""
        return [s.wafer_id for s in self.slots.values() if s.occupied and s.wafer_id is not None]

    def place_wafer(self, slot_number: int, wafer_id: str) -> None:
        """Place wafer into specific carrier slot."""
        if slot_number not in self.slots:
            raise ValueError(f"Slot {slot_number} outside carrier capacity {self.capacity}")
        if self.slots[slot_number].occupied:
            raise ValueError(
                f"Carrier {self.carrier_id} slot {slot_number} is already occupied by {self.slots[slot_number].wafer_id}"
            )
        self.slots[slot_number].occupied = True
        self.slots[slot_number].wafer_id = wafer_id

    def remove_wafer(self, slot_number: int) -> str:
        """Extract wafer from specific carrier slot."""
        if slot_number not in self.slots:
            raise ValueError(f"Slot {slot_number} outside carrier capacity {self.capacity}")
        if not self.slots[slot_number].occupied or self.slots[slot_number].wafer_id is None:
            raise ValueError(f"Carrier {self.carrier_id} slot {slot_number} is already empty")
        wid = self.slots[slot_number].wafer_id
        self.slots[slot_number].occupied = False
        self.slots[slot_number].wafer_id = None
        return wid


@dataclass
class WaferProcessHistoryEntry:
    """Historical processing or metrology record for an individual wafer."""
    step_id: str
    step_name: str
    equipment_id: str
    recipe_name: str
    start_time: str
    end_time: str
    operator_id: str
    metrology_data: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""


@dataclass
class WaferRecord:
    """Substrate entity tracking record per SEMI E90.

    Attributes:
        wafer_id: Laser-scribed alphanumeric wafer identifier (e.g. 'WFR_180_001_07').
        lot_id: Associated lot identifier.
        slot_number: Current slot inside carrier (1..25).
        diameter_mm: Substrate diameter (200.0 or 300.0 mm).
        substrate_type: Material description (e.g. 'p-type Si (100)', 'UTBB FD-SOI').
        carrier_id: Identifier of carrier currently housing wafer.
        equipment_id: Equipment tool currently processing or holding wafer (None if in carrier).
        status: Substrate status (UNPROCESSED, IN_PROCESS, PROCESSED, etc.).
        process_history: Chronological log of steps completed on this wafer.
    """

    wafer_id: str
    lot_id: str
    slot_number: int
    diameter_mm: float
    substrate_type: str
    carrier_id: Optional[str] = None
    equipment_id: Optional[str] = None
    status: WaferStatus = WaferStatus.UNPROCESSED
    process_history: List[WaferProcessHistoryEntry] = field(default_factory=list)


@dataclass
class LotRecord:
    """Production lot tracking record representing a batch of silicon wafers.

    Attributes:
        lot_id: Unique lot identifier (e.g. 'LOT_180_202611_A').
        product: Device or product code (e.g. 'MCU_180_AUTO', 'SOC_22FDSOI_AI').
        node: Technology node ('180nm', '130nm', '65nm', '22nm_fdsoi').
        priority: Priority ranking (1 = lowest, 100 = emergency / hot lot).
        wafer_list: Ordered list of wafer IDs belonging to this lot.
        current_step_index: Current 0-based index in the process route.
        current_step_id: Current process step identifier string.
        lot_state: Current state (QUEUED, ACTIVE, HOLD, COMPLETE, SCRAPPED).
        hold_codes: List of active hold reason codes (e.g. ['ENG_HOLD_METROLOGY', 'SPC_EXCURSION']).
        hold_reasons: Descriptive text explaining each hold code.
        creation_time: UTC timestamp string of lot release into fab.
        completion_time: UTC timestamp string when lot completed final step.
        carrier_id: Primary carrier ID assigned to transport this lot.
        parent_lot_id: Source lot ID if this lot was created from a split operation.
        split_children: List of child lot IDs created from splitting this lot.
    """

    lot_id: str
    product: str
    node: str
    priority: int = 50
    wafer_list: List[str] = field(default_factory=list)
    current_step_index: int = 0
    current_step_id: str = "STEP_010_INITIAL_CLEAN"
    lot_state: LotState = LotState.QUEUED
    hold_codes: List[str] = field(default_factory=list)
    hold_reasons: List[str] = field(default_factory=list)
    creation_time: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completion_time: Optional[str] = None
    carrier_id: Optional[str] = None
    parent_lot_id: Optional[str] = None
    split_children: List[str] = field(default_factory=list)


class WaferTrackingSystem:
    """Comprehensive SEMI E87/E90 Wafer and Lot Tracking System for MES.

    Maintains single-source-of-truth registry for:
      - All lots and their lifecycle states.
      - Physical substrate locations (wafer -> slot -> carrier -> equipment/stocker).
      - Substrate transfer validation (no double occupancy, valid slot indexing).
      - Complete wafer genealogy (splits, merges, step history).
    """

    def __init__(self, audit_log: Optional[AuditLog] = None) -> None:
        """Initialize tracking engine with optional audit log integration."""
        self.audit_log: Optional[AuditLog] = audit_log
        self.lots: Dict[str, LotRecord] = {}
        self.wafers: Dict[str, WaferRecord] = {}
        self.carriers: Dict[str, WaferCarrier] = {}

    def register_carrier(
        self,
        carrier_id: str,
        carrier_type: CarrierType,
        capacity: int = 25,
        location: str = "CENTRAL_STOCKER",
    ) -> WaferCarrier:
        """Register a new physical FOUP, SMIF, or cassette in the fab."""
        if carrier_id in self.carriers:
            raise ValueError(f"Carrier ID '{carrier_id}' is already registered")

        carrier = WaferCarrier(
            carrier_id=carrier_id,
            carrier_type=carrier_type,
            capacity=capacity,
            carrier_state=CarrierState.IN_STOCKER,
            current_location=location,
        )
        self.carriers[carrier_id] = carrier

        if self.audit_log:
            self.audit_log.append(
                event_type=EventTypes.CARRIER_MOVE,
                user_id="SYSTEM",
                description=f"Carrier {carrier_id} registered at {location}",
                details={"carrier_id": carrier_id, "type": carrier_type.value, "capacity": capacity},
            )
        return carrier

    def register_lot(
        self,
        lot_id: str,
        product: str,
        node: str,
        wafer_count: int = 25,
        priority: int = 50,
        carrier_id: Optional[str] = None,
        substrate_type: str = "p-type Si (100)",
        diameter_mm: float = 300.0,
        first_step_id: str = "STEP_010_INITIAL_CLEAN",
        user_id: str = "FAB_OPERATOR",
    ) -> LotRecord:
        """Create a new semiconductor production lot with constituent wafers.

        Args:
            lot_id: Unique lot designation.
            product: Device product code.
            node: Technology node name.
            wafer_count: Initial number of wafers (standard: 25).
            priority: Scheduling priority (1..100).
            carrier_id: Optional carrier to load wafers into immediately.
            substrate_type: Substrate material specification.
            diameter_mm: Wafer diameter (200.0 or 300.0 mm).
            first_step_id: Process flow starting step ID.
            user_id: ID of operator creating lot.

        Returns:
            Created LotRecord instance.
        """
        if lot_id in self.lots:
            raise ValueError(f"Lot '{lot_id}' is already registered")

        if wafer_count < 1 or wafer_count > 25:
            raise ValueError(f"Wafer count must be between 1 and 25, got: {wafer_count}")

        carrier: Optional[WaferCarrier] = None
        if carrier_id:
            if carrier_id not in self.carriers:
                raise ValueError(f"Carrier '{carrier_id}' does not exist")
            carrier = self.carriers[carrier_id]
            if len(carrier.empty_slots) < wafer_count:
                raise ValueError(
                    f"Carrier '{carrier_id}' has only {len(carrier.empty_slots)} empty slots, "
                    f"cannot accommodate {wafer_count} wafers"
                )

        wafer_ids: List[str] = []
        for idx in range(1, wafer_count + 1):
            w_id = f"{lot_id}_{idx:02d}"
            slot_num = idx
            w_carrier_id = carrier_id if carrier else None

            wafer = WaferRecord(
                wafer_id=w_id,
                lot_id=lot_id,
                slot_number=slot_num,
                diameter_mm=diameter_mm,
                substrate_type=substrate_type,
                carrier_id=w_carrier_id,
                equipment_id=None,
                status=WaferStatus.UNPROCESSED,
            )
            self.wafers[w_id] = wafer
            wafer_ids.append(w_id)

            if carrier:
                carrier.place_wafer(slot_num, w_id)

        lot = LotRecord(
            lot_id=lot_id,
            product=product,
            node=node,
            priority=priority,
            wafer_list=wafer_ids,
            current_step_index=0,
            current_step_id=first_step_id,
            lot_state=LotState.QUEUED,
            carrier_id=carrier_id,
        )
        self.lots[lot_id] = lot

        if self.audit_log:
            self.audit_log.append(
                event_type=EventTypes.LOT_CREATED,
                user_id=user_id,
                description=f"Lot {lot_id} registered with {wafer_count} wafers",
                lot_id=lot_id,
                details={
                    "product": product,
                    "node": node,
                    "wafer_count": wafer_count,
                    "carrier_id": carrier_id,
                },
            )

        return lot

    def move_carrier(
        self,
        carrier_id: str,
        new_location: str,
        new_state: CarrierState,
        user_id: str = "AGV_DISPATCHER",
    ) -> None:
        """Update carrier physical location and SEMI E87 state."""
        carrier = self.get_carrier(carrier_id)
        old_loc = carrier.current_location
        carrier.current_location = new_location
        carrier.carrier_state = new_state

        if self.audit_log:
            self.audit_log.append(
                event_type=EventTypes.CARRIER_MOVE,
                user_id=user_id,
                description=f"Carrier {carrier_id} moved from {old_loc} to {new_location} ({new_state.value})",
                details={"carrier_id": carrier_id, "from": old_loc, "to": new_location, "state": new_state.value},
            )

    def transfer_wafer_to_carrier(
        self,
        wafer_id: str,
        target_carrier_id: str,
        target_slot: int,
        user_id: str = "ROBOT_ARM",
    ) -> None:
        """Transfer wafer from its current position into a target carrier slot."""
        wafer = self.get_wafer(wafer_id)
        target_carrier = self.get_carrier(target_carrier_id)

        # Check if wafer is currently in another carrier
        old_carrier_id = wafer.carrier_id
        old_slot = wafer.slot_number
        if old_carrier_id and old_carrier_id in self.carriers:
            old_carrier = self.carriers[old_carrier_id]
            if old_carrier.slots.get(old_slot, None) and old_carrier.slots[old_slot].wafer_id == wafer_id:
                old_carrier.remove_wafer(old_slot)

        target_carrier.place_wafer(target_slot, wafer_id)
        wafer.carrier_id = target_carrier_id
        wafer.slot_number = target_slot

        if self.audit_log:
            self.audit_log.append(
                event_type=EventTypes.WAFER_TRANSFER,
                user_id=user_id,
                description=f"Wafer {wafer_id} transferred to carrier {target_carrier_id} slot {target_slot}",
                wafer_id=wafer_id,
                lot_id=wafer.lot_id,
                details={
                    "source_carrier": old_carrier_id,
                    "source_slot": old_slot,
                    "target_carrier": target_carrier_id,
                    "target_slot": target_slot,
                },
            )

    def record_process_step(
        self,
        wafer_id: str,
        step_id: str,
        step_name: str,
        equipment_id: str,
        recipe_name: str,
        start_time: str,
        end_time: str,
        operator_id: str,
        metrology_data: Optional[Dict[str, Any]] = None,
        notes: str = "",
    ) -> None:
        """Append a process execution record to an individual wafer's genealogy."""
        wafer = self.get_wafer(wafer_id)
        entry = WaferProcessHistoryEntry(
            step_id=step_id,
            step_name=step_name,
            equipment_id=equipment_id,
            recipe_name=recipe_name,
            start_time=start_time,
            end_time=end_time,
            operator_id=operator_id,
            metrology_data=metrology_data or {},
            notes=notes,
        )
        wafer.process_history.append(entry)
        wafer.status = WaferStatus.PROCESSED

    def hold_lot(
        self,
        lot_id: str,
        hold_code: str,
        reason: str,
        user_id: str = "QUALITY_ENGINEER",
    ) -> None:
        """Place lot on hold, preventing automatic dispatch."""
        lot = self.get_lot(lot_id)
        lot.lot_state = LotState.HOLD
        if hold_code not in lot.hold_codes:
            lot.hold_codes.append(hold_code)
            lot.hold_reasons.append(reason)

        if self.audit_log:
            self.audit_log.append(
                event_type=EventTypes.LOT_HOLD,
                user_id=user_id,
                description=f"Lot {lot_id} placed on HOLD: {hold_code} - {reason}",
                lot_id=lot_id,
                details={"hold_code": hold_code, "reason": reason},
            )

    def release_lot(
        self,
        lot_id: str,
        hold_code: str,
        user_id: str = "QUALITY_ENGINEER",
        comment: str = "Disposition approved",
    ) -> None:
        """Release lot from a specific hold code; restores ACTIVE state if all holds cleared."""
        lot = self.get_lot(lot_id)
        if hold_code in lot.hold_codes:
            idx = lot.hold_codes.index(hold_code)
            lot.hold_codes.pop(idx)
            lot.hold_reasons.pop(idx)

        if not lot.hold_codes:
            lot.lot_state = LotState.ACTIVE

        if self.audit_log:
            self.audit_log.append(
                event_type=EventTypes.LOT_RELEASE,
                user_id=user_id,
                description=f"Lot {lot_id} released from hold {hold_code}: {comment}",
                lot_id=lot_id,
                details={"cleared_hold_code": hold_code, "remaining_holds": list(lot.hold_codes)},
            )

    def split_lot(
        self,
        parent_lot_id: str,
        child_lot_id: str,
        split_wafer_ids: List[str],
        reason: str,
        user_id: str = "PROCESS_ENGINEER",
        child_carrier_id: Optional[str] = None,
    ) -> LotRecord:
        """Split a subset of wafers from a parent lot into a newly spawned child lot.

        Used for engineering splits, split-lot R&D experimentation, or rework flows.
        """
        parent = self.get_lot(parent_lot_id)
        if child_lot_id in self.lots:
            raise ValueError(f"Child lot ID '{child_lot_id}' already exists")

        # Validate wafers exist and belong to parent
        for w_id in split_wafer_ids:
            if w_id not in parent.wafer_list:
                raise ValueError(f"Wafer '{w_id}' is not in parent lot '{parent_lot_id}'")

        if len(split_wafer_ids) == len(parent.wafer_list):
            raise ValueError("Cannot split all wafers from parent lot; use lot transfer instead")

        # Remove wafers from parent
        for w_id in split_wafer_ids:
            parent.wafer_list.remove(w_id)
            wafer = self.wafers[w_id]
            wafer.lot_id = child_lot_id

        # Register child lot
        child_lot = LotRecord(
            lot_id=child_lot_id,
            product=parent.product,
            node=parent.node,
            priority=parent.priority,
            wafer_list=list(split_wafer_ids),
            current_step_index=parent.current_step_index,
            current_step_id=parent.current_step_id,
            lot_state=parent.lot_state,
            carrier_id=child_carrier_id,
            parent_lot_id=parent_lot_id,
        )
        self.lots[child_lot_id] = child_lot
        parent.split_children.append(child_lot_id)

        if self.audit_log:
            self.audit_log.append(
                event_type=EventTypes.LOT_SPLIT,
                user_id=user_id,
                description=f"Lot {parent_lot_id} split into child {child_lot_id} with {len(split_wafer_ids)} wafers: {reason}",
                lot_id=parent_lot_id,
                details={
                    "parent_lot": parent_lot_id,
                    "child_lot": child_lot_id,
                    "split_wafers": split_wafer_ids,
                    "parent_remaining_count": len(parent.wafer_list),
                    "reason": reason,
                },
            )

        return child_lot

    def merge_lots(
        self,
        surviving_lot_id: str,
        absorbed_lot_id: str,
        reason: str,
        user_id: str = "PROCESS_ENGINEER",
    ) -> LotRecord:
        """Merge an absorbed lot's wafers back into a surviving parent or peer lot."""
        surviving = self.get_lot(surviving_lot_id)
        absorbed = self.get_lot(absorbed_lot_id)

        if surviving.product != absorbed.product or surviving.node != absorbed.node:
            raise ValueError(
                f"Cannot merge incompatible lots: surviving ({surviving.product}/{surviving.node}) "
                f"vs absorbed ({absorbed.product}/{absorbed.node})"
            )

        total_wafers = len(surviving.wafer_list) + len(absorbed.wafer_list)
        if total_wafers > 25:
            raise ValueError(f"Merged wafer count ({total_wafers}) exceeds carrier maximum capacity of 25")

        for w_id in absorbed.wafer_list:
            surviving.wafer_list.append(w_id)
            wafer = self.wafers[w_id]
            wafer.lot_id = surviving_lot_id

        absorbed.wafer_list.clear()
        absorbed.lot_state = LotState.COMPLETE
        absorbed.completion_time = datetime.now(timezone.utc).isoformat()

        if self.audit_log:
            self.audit_log.append(
                event_type=EventTypes.LOT_MERGE,
                user_id=user_id,
                description=f"Lot {absorbed_lot_id} merged into {surviving_lot_id}: {reason}",
                lot_id=surviving_lot_id,
                details={
                    "surviving_lot": surviving_lot_id,
                    "absorbed_lot": absorbed_lot_id,
                    "total_wafers": len(surviving.wafer_list),
                    "reason": reason,
                },
            )

        return surviving

    def generate_wafer_genealogy(self, wafer_id: str) -> Dict[str, Any]:
        """Generate a complete genealogy report for a wafer (pedigree, lot ancestry, process trail)."""
        wafer = self.get_wafer(wafer_id)
        lot = self.get_lot(wafer.lot_id)

        # Trace split ancestry
        ancestry: List[str] = [lot.lot_id]
        curr = lot
        while curr.parent_lot_id and curr.parent_lot_id in self.lots:
            curr = self.lots[curr.parent_lot_id]
            ancestry.append(curr.lot_id)

        return {
            "wafer_id": wafer.wafer_id,
            "current_lot_id": wafer.lot_id,
            "lot_ancestry": ancestry,
            "substrate_type": wafer.substrate_type,
            "diameter_mm": wafer.diameter_mm,
            "current_carrier_id": wafer.carrier_id,
            "current_slot": wafer.slot_number,
            "current_status": wafer.status.value,
            "total_steps_executed": len(wafer.process_history),
            "process_history": [
                {
                    "step_id": h.step_id,
                    "step_name": h.step_name,
                    "equipment_id": h.equipment_id,
                    "recipe_name": h.recipe_name,
                    "start_time": h.start_time,
                    "end_time": h.end_time,
                    "operator_id": h.operator_id,
                    "metrology_data": h.metrology_data,
                    "notes": h.notes,
                }
                for h in wafer.process_history
            ],
        }

    def get_lot(self, lot_id: str) -> LotRecord:
        """Fetch lot by ID or raise KeyError."""
        if lot_id not in self.lots:
            raise KeyError(f"Lot '{lot_id}' not found in MES registry")
        return self.lots[lot_id]

    def get_wafer(self, wafer_id: str) -> WaferRecord:
        """Fetch wafer by ID or raise KeyError."""
        if wafer_id not in self.wafers:
            raise KeyError(f"Wafer '{wafer_id}' not found in MES registry")
        return self.wafers[wafer_id]

    def get_carrier(self, carrier_id: str) -> WaferCarrier:
        """Fetch carrier by ID or raise KeyError."""
        if carrier_id not in self.carriers:
            raise KeyError(f"Carrier '{carrier_id}' not found in MES registry")
        return self.carriers[carrier_id]
