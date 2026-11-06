# Standards Traceability Matrix
# Silicon Fabrication Lab Digital Twin
# ====================================
#
# This file maps every modeled behavior, parameter, and interface
# to its governing standard, revision, and specific clause.

"""
Standards Traceability Matrix for the Semiconductor Fabrication Digital Twin.

Every modeled equipment behavior, HMI element, safety interlock, and process
parameter must trace to a governing standard or validated engineering reference.

IMPORTANT: This matrix documents our *intended* alignment with industry standards.
Full compliance requires access to the published standard documents and formal
conformance testing. This simulator implements *representative* behaviors based
on publicly available standard descriptions and industry practice.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class StandardBody(Enum):
    """Standards development organizations."""
    SEMI = "SEMI (Semiconductor Equipment and Materials International)"
    ISO = "ISO (International Organization for Standardization)"
    IEC = "IEC (International Electrotechnical Commission)"
    NFPA = "NFPA (National Fire Protection Association)"
    OSHA = "OSHA (Occupational Safety and Health Administration)"


class ComplianceLevel(Enum):
    """Level of compliance with a standard."""
    FULL = "Full implementation of applicable clauses"
    PARTIAL = "Selected clauses implemented; limitations documented"
    REFERENCE = "Used as design reference; not claiming compliance"
    PLANNED = "Planned for future implementation"


@dataclass(frozen=True)
class StandardReference:
    """Reference to a specific standard and its application in the simulator."""
    standard_id: str
    title: str
    body: StandardBody
    revision: str
    applicable_clauses: list[str]
    application_in_simulator: str
    compliance_level: ComplianceLevel
    limitations: str
    notes: str = ""


# ============================================================================
# SEMI Equipment Communication Standards
# ============================================================================

SEMI_E5 = StandardReference(
    standard_id="SEMI E5",
    title="SEMI Equipment Communications Standard 2 Message Content (SECS-II)",
    body=StandardBody.SEMI,
    revision="SEMI E5-0720",
    applicable_clauses=["All stream/function definitions", "Data item formats"],
    application_in_simulator=(
        "Message encoding/decoding for equipment-host communication. "
        "Defines the data structure format used in all SECS messages."
    ),
    compliance_level=ComplianceLevel.REFERENCE,
    limitations=(
        "Simulator implements commonly used stream/function pairs. "
        "Full SECS-II message catalog is extensive; only production-relevant "
        "messages are implemented."
    ),
)

SEMI_E30 = StandardReference(
    standard_id="SEMI E30",
    title="Generic Model for Communications and Control of Manufacturing Equipment (GEM)",
    body=StandardBody.SEMI,
    revision="SEMI E30-1120",
    applicable_clauses=[
        "Section 7: Communication State Model",
        "Section 8: Control State Model",
        "Section 9: Process State Model",
        "Section 10: Equipment Constants",
        "Section 11: Status Variables",
        "Section 12: Data Variables",
        "Section 13: Collection Events",
        "Section 14: Alarm Management",
        "Section 15: Remote Control",
        "Section 16: Recipe Management",
    ],
    application_in_simulator=(
        "Core equipment behavioral model. All simulated equipment implements "
        "GEM state machines (Communication, Control, Process states), "
        "event reporting, alarm management, and recipe handling."
    ),
    compliance_level=ComplianceLevel.PARTIAL,
    limitations=(
        "Implements core GEM capabilities. Advanced features like spooling, "
        "dynamic event report configuration, and equipment terminal services "
        "may be simplified."
    ),
)

SEMI_E37 = StandardReference(
    standard_id="SEMI E37",
    title="High-Speed SECS Message Services (HSMS)",
    body=StandardBody.SEMI,
    revision="SEMI E37.1-0720",
    applicable_clauses=[
        "Section 6: HSMS Message Format",
        "Section 7: Connection State Machine",
        "Section 8: Session State Machine",
        "Section 9: Timer definitions (T3, T5, T6, T7, T8)",
    ],
    application_in_simulator=(
        "TCP/IP transport layer for equipment-host communication. "
        "Simulator implements HSMS-SS (Single Session) server mode "
        "with all defined timers and connection management."
    ),
    compliance_level=ComplianceLevel.PARTIAL,
    limitations=(
        "Single-session mode only. Multi-session HSMS-GS not implemented. "
        "Timer values are configurable but default to common industry values."
    ),
)

SEMI_E40 = StandardReference(
    standard_id="SEMI E40",
    title="Standard for Processing Management",
    body=StandardBody.SEMI,
    revision="SEMI E40-0720",
    applicable_clauses=[
        "Section 7: Process Job State Model",
        "Section 8: Process Job Services",
    ],
    application_in_simulator=(
        "Process Job management on equipment. Governs how recipes are bound "
        "to wafer lots and executed in process chambers. Implements the full "
        "Process Job state machine including error states."
    ),
    compliance_level=ComplianceLevel.PARTIAL,
    limitations=(
        "Core PJ states implemented. Advanced multi-recipe interleaving "
        "and some edge-case state transitions may be simplified."
    ),
)

SEMI_E87 = StandardReference(
    standard_id="SEMI E87",
    title="Specification for Carrier Management (CMS)",
    body=StandardBody.SEMI,
    revision="SEMI E87-0720",
    applicable_clauses=[
        "Section 7: Load Port Transfer State Model",
        "Section 8: Carrier Object State Models",
        "Section 9: Slot Map Verification",
        "Section 10: Carrier ID Verification",
    ],
    application_in_simulator=(
        "FOUP/cassette carrier management at load ports. Simulates carrier "
        "arrival, clamping, door opening, slot mapping, and wafer access. "
        "Differentiates between FOUP (300mm) and cassette/SMIF (200mm) workflows."
    ),
    compliance_level=ComplianceLevel.PARTIAL,
    limitations=(
        "Implements standard carrier management flows. AMHS OHT handshake "
        "(SEMI E84) is simplified. RF-tag reading is simulated."
    ),
)

SEMI_E90 = StandardReference(
    standard_id="SEMI E90",
    title="Specification for Substrate Tracking",
    body=StandardBody.SEMI,
    revision="SEMI E90-0720",
    applicable_clauses=[
        "Section 7: Substrate Location Model",
        "Section 8: Substrate Processing State",
        "Section 9: Substrate Transport State",
    ],
    application_in_simulator=(
        "Individual wafer tracking through all equipment locations. "
        "Tracks wafer position (load port slot, robot arm, loadlock, "
        "process chamber) and processing state throughout the tool."
    ),
    compliance_level=ComplianceLevel.PARTIAL,
    limitations=(
        "Core substrate tracking implemented. Some complex multi-chamber "
        "scheduling optimizations may be simplified."
    ),
)

SEMI_E94 = StandardReference(
    standard_id="SEMI E94",
    title="Specification for Control Job Management",
    body=StandardBody.SEMI,
    revision="SEMI E94-0720",
    applicable_clauses=[
        "Section 7: Control Job State Model",
        "Section 8: Control Job Services",
    ],
    application_in_simulator=(
        "Highest-level automation object. Control Jobs bundle Process Jobs "
        "across carriers, governing lot-level throughput and scheduling. "
        "Implements CJ state machine and host interaction."
    ),
    compliance_level=ComplianceLevel.PARTIAL,
    limitations="Core CJ management implemented. Advanced queuing strategies simplified.",
)

SEMI_E95 = StandardReference(
    standard_id="SEMI E95",
    title="Specification for Human Interface for Semiconductor Manufacturing Equipment",
    body=StandardBody.SEMI,
    revision="SEMI E95-1122 (check for 2026 revision)",
    applicable_clauses=[
        "Section 7: Screen Layout Architecture",
        "Section 8: Navigation Panel",
        "Section 9: Status Display",
        "Section 10: Alarm Display",
        "Section 11: Color Coding Standards",
    ],
    application_in_simulator=(
        "HMI design reference for equipment operator consoles. "
        "All simulated equipment GUIs follow E95 screen zoning: "
        "title panel, navigation panel, work area, status bar. "
        "Standard color coding for equipment states and alarms."
    ),
    compliance_level=ComplianceLevel.REFERENCE,
    limitations=(
        "Used as design reference for HMI layout and interaction patterns. "
        "Actual OEM screens are proprietary; our HMIs are representative "
        "industry-style interfaces following E95 principles."
    ),
    notes=(
        "SEMI reported a revision to E95 in August 2026. Check published "
        "revision status before claiming compliance with specific revision."
    ),
)

SEMI_E10 = StandardReference(
    standard_id="SEMI E10",
    title="Standard for Definition and Measurement of Equipment Reliability, "
          "Availability, and Maintainability (RAM)",
    body=StandardBody.SEMI,
    revision="SEMI E10-0814",
    applicable_clauses=[
        "Section 5: Equipment State Definitions",
        "Section 6: Time Category Definitions",
    ],
    application_in_simulator=(
        "Equipment state definitions for RAM tracking. Defines six major "
        "equipment states: PRODUCTIVE, STANDBY, ENGINEERING, SCHEDULED_DOWN, "
        "UNSCHEDULED_DOWN, NON_SCHEDULED. Used as the basis for our equipment "
        "state machine model."
    ),
    compliance_level=ComplianceLevel.PARTIAL,
    limitations=(
        "State definitions implemented. Full RAM calculation methodology "
        "(OEE, availability formulas) partially implemented."
    ),
)

SEMI_E187 = StandardReference(
    standard_id="SEMI E187",
    title="Specification for Cybersecurity of Fab Equipment",
    body=StandardBody.SEMI,
    revision="SEMI E187-0222",
    applicable_clauses=[
        "Section 6: Operating System Security",
        "Section 7: Network Security",
        "Section 8: Endpoint Protection",
        "Section 9: Access Control",
    ],
    application_in_simulator=(
        "Cybersecurity reference for equipment communication architecture. "
        "Informs our network isolation design, access control model, and "
        "secure integration architecture for production-connected mode."
    ),
    compliance_level=ComplianceLevel.REFERENCE,
    limitations=(
        "Used as architectural reference. Full cybersecurity compliance "
        "requires infrastructure-level implementation beyond the simulator."
    ),
)

# ============================================================================
# SEMI Safety Standards
# ============================================================================

SEMI_S2 = StandardReference(
    standard_id="SEMI S2",
    title="Environmental, Health, and Safety Guideline for Semiconductor "
          "Manufacturing Equipment",
    body=StandardBody.SEMI,
    revision="SEMI S2-0716",
    applicable_clauses=[
        "Section 6: Electrical Safety",
        "Section 7: Mechanical Safety",
        "Section 8: Chemical Safety",
        "Section 9: Fire Safety",
        "Section 10: Radiation Safety",
        "Section 11: Ergonomics",
        "Section 12: EMO (Emergency Off)",
    ],
    application_in_simulator=(
        "Primary safety reference for equipment interlock design. "
        "All simulated equipment implements EMO behavior, chemical "
        "interlocks, vacuum interlocks, RF radiation interlocks, "
        "and exhaust flow interlocks per S2 principles."
    ),
    compliance_level=ComplianceLevel.REFERENCE,
    limitations=(
        "Safety behaviors are modeled for training purposes. "
        "Real equipment safety requires hardware interlocks that "
        "cannot be overridden by software."
    ),
)

SEMI_S8 = StandardReference(
    standard_id="SEMI S8",
    title="Safety Guidelines for Ergonomics Engineering of Semiconductor "
          "Manufacturing Equipment",
    body=StandardBody.SEMI,
    revision="SEMI S8-0712",
    applicable_clauses=[
        "Section 6: Physical Access",
        "Section 7: Load Port Heights",
        "Section 8: Lifting Limits",
        "Section 9: Maintenance Access Envelopes",
    ],
    application_in_simulator=(
        "Ergonomics reference for physical equipment dimensions and "
        "operator interaction zones. Informs 3D model proportions, "
        "load port heights (900mm ± 10mm), and maintenance access."
    ),
    compliance_level=ComplianceLevel.REFERENCE,
    limitations="Used for dimensional accuracy in 3D models.",
)

SEMI_S10 = StandardReference(
    standard_id="SEMI S10",
    title="Safety Guideline for Risk Assessment and Risk Evaluation Process",
    body=StandardBody.SEMI,
    revision="SEMI S10-0307",
    applicable_clauses=[
        "Section 5: Risk Assessment Methodology",
        "Section 6: Hazard Identification",
    ],
    application_in_simulator=(
        "Risk assessment framework for equipment hazard identification. "
        "Used to design training scenarios that teach risk assessment "
        "and hazard recognition skills."
    ),
    compliance_level=ComplianceLevel.REFERENCE,
    limitations="Framework reference for training scenario design.",
)

# ============================================================================
# ISO Standards
# ============================================================================

ISO_14644_1 = StandardReference(
    standard_id="ISO 14644-1",
    title="Cleanrooms and associated controlled environments — "
          "Part 1: Classification of air cleanliness by particle concentration",
    body=StandardBody.ISO,
    revision="ISO 14644-1:2015",
    applicable_clauses=[
        "Section 3: Classification levels (ISO 1 through ISO 9)",
        "Annex A: Particle concentration formula",
        "Annex B: Particle size thresholds",
    ],
    application_in_simulator=(
        "Cleanroom classification system. Defines particle count limits "
        "for each ISO class. Used in cleanroom environment simulation: "
        "ISO 5 for process bays, ISO 1 for FOUP/mini-environments, "
        "ISO 6-7 for service chases. "
        "Formula: Cn = 10^N × (0.1/D)^2.08 "
        "where N=class, D=particle size in μm, Cn=particles/m³."
    ),
    compliance_level=ComplianceLevel.PARTIAL,
    limitations=(
        "Particle count model is simplified. Real cleanroom qualification "
        "requires extensive air sampling per ISO 14644-3."
    ),
)

# ============================================================================
# Complete Registry
# ============================================================================

STANDARDS_REGISTRY: dict[str, StandardReference] = {
    "SEMI E5": SEMI_E5,
    "SEMI E10": SEMI_E10,
    "SEMI E30": SEMI_E30,
    "SEMI E37": SEMI_E37,
    "SEMI E40": SEMI_E40,
    "SEMI E87": SEMI_E87,
    "SEMI E90": SEMI_E90,
    "SEMI E94": SEMI_E94,
    "SEMI E95": SEMI_E95,
    "SEMI E187": SEMI_E187,
    "SEMI S2": SEMI_S2,
    "SEMI S8": SEMI_S8,
    "SEMI S10": SEMI_S10,
    "ISO 14644-1": ISO_14644_1,
}


def get_applicable_standards(domain: str) -> list[StandardReference]:
    """Get all standards applicable to a given domain.
    
    Args:
        domain: One of 'equipment', 'safety', 'communication', 'hmi',
                'cleanroom', 'carrier', 'wafer_tracking', 'cybersecurity'.
    
    Returns:
        List of applicable StandardReference objects.
    """
    domain_map: dict[str, list[str]] = {
        "equipment": ["SEMI E10", "SEMI E30", "SEMI E40", "SEMI S2"],
        "safety": ["SEMI S2", "SEMI S8", "SEMI S10"],
        "communication": ["SEMI E5", "SEMI E30", "SEMI E37"],
        "hmi": ["SEMI E95", "SEMI S8"],
        "cleanroom": ["ISO 14644-1"],
        "carrier": ["SEMI E87", "SEMI E84"],
        "wafer_tracking": ["SEMI E87", "SEMI E90"],
        "process_job": ["SEMI E40", "SEMI E94"],
        "cybersecurity": ["SEMI E187"],
    }
    
    standard_ids = domain_map.get(domain, [])
    return [STANDARDS_REGISTRY[sid] for sid in standard_ids if sid in STANDARDS_REGISTRY]
