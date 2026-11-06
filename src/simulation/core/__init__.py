"""Core Simulation Foundation for Semiconductor Fabrication Digital Twin.

Exports the fundamental physical, material, state, recipe, and routing primitives
governing the fab simulation environment:
  - units: Comprehensive semiconductor physical units system with ranges,
    uncertainties, and SEMI/NIST conversions.
  - state_machine: SEMI E10 equipment state machine with availability, MTBF,
    MTTR, and RAM calculations.
  - wafer: Physical wafer substrate, SOI buried oxide/device layer support,
    thin-film layer stack with Stoney stress/bow, and defect state.
  - recipe: SEMI E95 process recipes, parameter setpoints with tolerance bands,
    equipment hardware capability validation, and conditional branching.
  - process_route: End-to-end manufacturing routes, DAG step dependencies,
    quality hold points, and multi-node reference flows (180nm down to 22nm FD-SOI).
"""

from src.simulation.core.process_route import (
    CriticalSpec,
    ProcessNode,
    ProcessRoute,
    ProcessStep,
    ProcessStepCategory,
    RouteLibrary,
    StepSector,
)
from src.simulation.core.recipe import (
    BranchCondition,
    EquipmentCapabilities,
    ProcessType,
    Recipe,
    RecipeLibrary,
    RecipeParameter,
    RecipeStep,
)
from src.simulation.core.state_machine import (
    EquipmentEvent,
    EquipmentStateMachine,
    SemiE10Metrics,
    SemiE10State,
    SemiE10Substate,
    StateHistoryEntry,
    TransitionContext,
    TransitionRule,
)
from src.simulation.core.units import (
    PhysicalQuantity,
    UnitDimension,
    convert_value,
    duration,
    film_thickness,
    gas_flow,
    get_unit_dimension,
    implant_dose,
    ion_energy,
    length,
    litho_dose,
    normalize_unit,
    pressure,
    rf_power,
    rotation_speed,
    temperature,
    wafer_diameter,
    wafer_thickness,
)
from src.simulation.core.wafer import (
    CrystalOrientation,
    DopantType,
    Layer,
    LayerStack,
    MetrologyRecord,
    MetrologyResults,
    MetrologyType,
    ProcessHistory,
    ProcessStepRecord,
    SubstrateMaterial,
    Wafer,
    WaferID,
    WaferState,
    WaferSubstrate,
)

__all__ = [
    # Physical Units
    "PhysicalQuantity",
    "UnitDimension",
    "convert_value",
    "normalize_unit",
    "get_unit_dimension",
    "length",
    "wafer_diameter",
    "wafer_thickness",
    "film_thickness",
    "temperature",
    "pressure",
    "gas_flow",
    "rf_power",
    "implant_dose",
    "litho_dose",
    "ion_energy",
    "duration",
    "rotation_speed",
    # Equipment State Machine (SEMI E10)
    "SemiE10State",
    "SemiE10Substate",
    "EquipmentEvent",
    "TransitionContext",
    "StateHistoryEntry",
    "TransitionRule",
    "SemiE10Metrics",
    "EquipmentStateMachine",
    # Wafer Digital Twin
    "SubstrateMaterial",
    "CrystalOrientation",
    "DopantType",
    "MetrologyType",
    "WaferID",
    "WaferSubstrate",
    "Layer",
    "LayerStack",
    "WaferState",
    "ProcessStepRecord",
    "ProcessHistory",
    "MetrologyRecord",
    "MetrologyResults",
    "Wafer",
    # Recipe Management
    "ProcessType",
    "RecipeParameter",
    "BranchCondition",
    "RecipeStep",
    "EquipmentCapabilities",
    "Recipe",
    "RecipeLibrary",
    # Process Routes
    "ProcessNode",
    "ProcessStepCategory",
    "StepSector",
    "CriticalSpec",
    "ProcessStep",
    "ProcessRoute",
    "RouteLibrary",
]
