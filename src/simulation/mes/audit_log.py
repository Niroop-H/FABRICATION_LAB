"""Audit and Event Logging Subsystem for Semiconductor Manufacturing Execution System (MES).

This module implements an immutable, append-only, tamper-evident audit logging system
designed to satisfy regulatory compliance standards:
  - FDA 21 CFR Part 11 (Electronic Records, Electronic Signatures, Audit Trails)
  - SEMI E95: Specification for Human Interface for Semiconductor Manufacturing Equipment
  - SEMI E30: Generic Model for Communications and Control of Manufacturing Equipment (GEM)

Every state transition, operator action, recipe modification, alarm trigger, and lot/wafer
movement is recorded with cryptographic chaining (SHA-256) to ensure data integrity.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union


class EventTypes(str, Enum):
    """Categorization of audit log events across fab operations and equipment states."""
    # Process execution
    PROCESS_START = "PROCESS_START"
    PROCESS_END = "PROCESS_END"
    RECIPE_DOWNLOAD = "RECIPE_DOWNLOAD"
    RECIPE_CHANGE = "RECIPE_CHANGE"
    CALIBRATION = "CALIBRATION"

    # Safety and equipment alarms
    ALARM = "ALARM"
    INTERLOCK = "INTERLOCK"
    MAINTENANCE = "MAINTENANCE"
    EMERGENCY_STOP = "EMERGENCY_STOP"

    # Human interaction
    OPERATOR_ACTION = "OPERATOR_ACTION"
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    CONFIG_CHANGE = "CONFIG_CHANGE"

    # Lot & Wafer Tracking
    LOT_CREATED = "LOT_CREATED"
    LOT_HOLD = "LOT_HOLD"
    LOT_RELEASE = "LOT_RELEASE"
    LOT_SPLIT = "LOT_SPLIT"
    LOT_MERGE = "LOT_MERGE"
    LOT_SCRAP = "LOT_SCRAP"
    LOT_COMPLETE = "LOT_COMPLETE"
    CARRIER_MOVE = "CARRIER_MOVE"
    WAFER_TRANSFER = "WAFER_TRANSFER"

    # Quality and Metrology
    METROLOGY_OUT_OF_SPEC = "METROLOGY_OUT_OF_SPEC"
    SPC_VIOLATION = "SPC_VIOLATION"


@dataclass(frozen=True)
class AuditEvent:
    """Tamper-evident audit event record in the MES system.

    Attributes:
        event_id: Unique sequential integer index.
        timestamp: ISO 8601 UTC timestamp string.
        event_type: Event classification from EventTypes enum.
        user_id: ID of operator, engineer, or automated system account triggering the event.
        equipment_id: Equipment identifier, if applicable (e.g. 'FURNACE_01', 'SCANNER_02').
        lot_id: Semiconductor lot identifier, if applicable (e.g. 'LOT_180_001').
        wafer_id: Specific wafer ID, if event pertains to a single substrate.
        description: Concise textual description of the action or state change.
        details: Structured dictionary containing telemetry, setpoints, or before/after state.
        previous_hash: SHA-256 digest of the immediately preceding event in the log.
        hash: SHA-256 digest of this event's canonical fields, anchoring the chain.
    """

    event_id: int
    timestamp: str
    event_type: EventTypes
    user_id: str
    equipment_id: Optional[str]
    lot_id: Optional[str]
    wafer_id: Optional[str]
    description: str
    details: Dict[str, Any] = field(default_factory=dict)
    previous_hash: str = "0" * 64
    hash: str = ""

    def calculate_hash(self) -> str:
        """Compute cryptographic SHA-256 hash across all immutable attributes."""
        # Canonical string representation for deterministic hashing
        payload = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "user_id": self.user_id,
            "equipment_id": self.equipment_id,
            "lot_id": self.lot_id,
            "wafer_id": self.wafer_id,
            "description": self.description,
            "details": self.details,
            "previous_hash": self.previous_hash,
        }
        serialized = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to JSON-serializable dictionary."""
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d


class AuditLog:
    """Append-only, cryptographically verified audit log store.

    Guarantees:
      - Append-only semantics: records cannot be overwritten or deleted.
      - Integrity checking: linear SHA-256 hash chain ensures any tampering or record deletion is detected.
      - Rich multi-field search and query interface.
      - Standard JSON and CSV compliance export.
    """

    GENESIS_HASH: str = "0" * 64

    def __init__(self, log_name: str = "FAB_PRIMARY_MES_AUDIT_LOG") -> None:
        """Initialize empty audit log with genesis state."""
        self.log_name: str = log_name
        self._events: List[AuditEvent] = []
        self._last_hash: str = self.GENESIS_HASH
        self._next_id: int = 1

    def append(
        self,
        event_type: Union[EventTypes, str],
        user_id: str,
        description: str,
        equipment_id: Optional[str] = None,
        lot_id: Optional[str] = None,
        wafer_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> AuditEvent:
        """Record a new immutable audit entry in the log.

        Args:
            event_type: Event category.
            user_id: ID of operator, engineer, or system agent.
            description: Summary of the logged action or event.
            equipment_id: Optional associated equipment ID.
            lot_id: Optional associated lot ID.
            wafer_id: Optional associated wafer ID.
            details: Optional dictionary with process metrics or state data.
            timestamp: Optional specific datetime; defaults to current UTC time.

        Returns:
            The newly created and cryptographically signed AuditEvent.
        """
        if isinstance(event_type, str):
            event_type = EventTypes(event_type)

        now_utc = timestamp or datetime.now(timezone.utc)
        iso_timestamp = now_utc.isoformat()

        details_dict = details or {}
        prev_hash = self._last_hash
        event_id = self._next_id

        # Temporary event to compute hash
        temp_event = AuditEvent(
            event_id=event_id,
            timestamp=iso_timestamp,
            event_type=event_type,
            user_id=user_id,
            equipment_id=equipment_id,
            lot_id=lot_id,
            wafer_id=wafer_id,
            description=description,
            details=details_dict,
            previous_hash=prev_hash,
            hash="",
        )
        calculated_hash = temp_event.calculate_hash()

        # Final record with confirmed hash
        sealed_event = AuditEvent(
            event_id=event_id,
            timestamp=iso_timestamp,
            event_type=event_type,
            user_id=user_id,
            equipment_id=equipment_id,
            lot_id=lot_id,
            wafer_id=wafer_id,
            description=description,
            details=details_dict,
            previous_hash=prev_hash,
            hash=calculated_hash,
        )

        self._events.append(sealed_event)
        self._last_hash = calculated_hash
        self._next_id += 1

        return sealed_event

    def __len__(self) -> int:
        """Return total count of recorded audit events."""
        return len(self._events)

    def __iter__(self) -> Iterator[AuditEvent]:
        """Iterate over all audit events chronologically."""
        return iter(self._events)

    def get_event(self, event_id: int) -> Optional[AuditEvent]:
        """Fetch event by 1-based index."""
        if 1 <= event_id <= len(self._events):
            return self._events[event_id - 1]
        return None

    def query(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_type: Optional[Union[EventTypes, str]] = None,
        user_id: Optional[str] = None,
        equipment_id: Optional[str] = None,
        lot_id: Optional[str] = None,
        wafer_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[AuditEvent]:
        """Query audit log with multi-field filtering criteria.

        Args:
            start_time: Filter events occurred at or after this UTC datetime.
            end_time: Filter events occurred at or before this UTC datetime.
            event_type: Specific EventTypes category.
            user_id: Filter by actor ID.
            equipment_id: Filter by equipment tool ID.
            lot_id: Filter by lot ID.
            wafer_id: Filter by wafer ID.
            limit: Maximum number of events to return.

        Returns:
            List of matching AuditEvent records.
        """
        if isinstance(event_type, str):
            event_type = EventTypes(event_type)

        results: List[AuditEvent] = []
        for event in self._events:
            ev_dt = datetime.fromisoformat(event.timestamp)
            if start_time is not None and ev_dt < start_time:
                continue
            if end_time is not None and ev_dt > end_time:
                continue
            if event_type is not None and event.event_type != event_type:
                continue
            if user_id is not None and event.user_id != user_id:
                continue
            if equipment_id is not None and event.equipment_id != equipment_id:
                continue
            if lot_id is not None and event.lot_id != lot_id:
                continue
            if wafer_id is not None and event.wafer_id != wafer_id:
                continue

            results.append(event)
            if limit is not None and len(results) >= limit:
                break

        return results

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """Verify complete cryptographic chain to confirm zero tampering or omissions.

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str]).
        """
        expected_prev = self.GENESIS_HASH

        for idx, event in enumerate(self._events, start=1):
            if event.event_id != idx:
                return False, f"Sequence error: expected ID {idx}, found {event.event_id}"

            if event.previous_hash != expected_prev:
                return (
                    False,
                    f"Hash break at event {idx}: expected previous_hash {expected_prev[:12]}..., "
                    f"found {event.previous_hash[:12]}...",
                )

            recalculated = event.calculate_hash()
            if recalculated != event.hash:
                return (
                    False,
                    f"Content corruption at event {idx}: hash {event.hash[:12]}... "
                    f"does not match recalculation {recalculated[:12]}...",
                )

            expected_prev = event.hash

        return True, None

    def export_to_json(self, file_path: Optional[Union[str, Path]] = None) -> str:
        """Export audit trail to formatted JSON string or file.

        Args:
            file_path: Optional destination file path.

        Returns:
            Formatted JSON string.
        """
        data = {
            "log_name": self.log_name,
            "export_time": datetime.now(timezone.utc).isoformat(),
            "total_events": len(self._events),
            "integrity_verified": self.verify_integrity()[0],
            "events": [event.to_dict() for event in self._events],
        }
        json_str = json.dumps(data, indent=2, default=str)
        if file_path:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json_str, encoding="utf-8")
        return json_str

    def export_to_csv(self, file_path: Optional[Union[str, Path]] = None) -> str:
        """Export audit trail to standard CSV format.

        Args:
            file_path: Optional destination file path.

        Returns:
            CSV content as string.
        """
        output = StringIO()
        fieldnames = [
            "event_id",
            "timestamp",
            "event_type",
            "user_id",
            "equipment_id",
            "lot_id",
            "wafer_id",
            "description",
            "details",
            "previous_hash",
            "hash",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for event in self._events:
            row = event.to_dict()
            row["details"] = json.dumps(row["details"], default=str)
            writer.writerow(row)

        csv_str = output.getvalue()
        if file_path:
            p = Path(file_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(csv_str, encoding="utf-8")
        return csv_str
