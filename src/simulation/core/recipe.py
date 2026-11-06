"""Process Recipe Management System for Semiconductor Fab Digital Twin.

Provides a formal, physically validated recipe representation matching SEMI E95
and industry SECS/GEM standards. Manages multi-step tool execution sequences,
parameter setpoints with tolerances, ramp rates, equipment capability envelopes,
and conditional branching (e.g., optical emission spectroscopy / OES endpoint detection).

Key Classes:
  - RecipeParameter: Named physical setpoint with tolerance and permissible range.
  - BranchCondition: Logic rule for dynamic step branching upon sensor/endpoint triggers.
  - RecipeStep: Unit recipe operation with duration, setpoints, ramp limits, and branching.
  - Recipe: Fully structured multi-step process recipe.
  - EquipmentCapabilities: Tool operational envelope used for safety and physical validation.
  - RecipeLibrary: Fab-wide catalogue organized by process node and technology sector.

Standards References:
  - SEMI E95: Specification for Human Interface for Semiconductor Manufacturing Equipment
  - SEMI E30: Generic Model for Communications and Control of Manufacturing Equipment (GEM)
  - SEMI E40: Standard for Processing Management
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from .units import (
    PhysicalQuantity,
    duration,
    gas_flow,
    length,
    pressure,
    rf_power,
    temperature,
)

logger = logging.getLogger(__name__)


class ProcessType(str, Enum):
    """Semiconductor manufacturing process category."""
    DRY_ETCH = "DRY_ETCH"
    WET_ETCH = "WET_ETCH"
    ALD = "ALD"  # Atomic Layer Deposition
    PECVD = "PECVD"  # Plasma-Enhanced Chemical Vapor Deposition
    LPCVD = "LPCVD"  # Low-Pressure Chemical Vapor Deposition
    PVD_SPUTTER = "PVD_SPUTTER"  # Physical Vapor Deposition / Sputtering
    CMP = "CMP"  # Chemical Mechanical Planarization
    ION_IMPLANTATION = "ION_IMPLANTATION"
    RAPID_THERMAL_ANNEAL = "RAPID_THERMAL_ANNEAL"  # RTA / Spike Anneal / Flash Anneal
    PHOTOLITHOGRAPHY = "PHOTOLITHOGRAPHY"
    WET_CLEAN = "WET_CLEAN"


@dataclass
class RecipeParameter:
    """A single physical recipe setpoint parameter with tight fab tolerances.

    Attributes:
        name: Parameter name (e.g. 'Chamber Pressure', 'Source RF Power', 'Cl2 Gas Flow').
        setpoint: Target physical quantity.
        tolerance: Symmetrical or upper bound deviation allowed during steady-state.
        unit: Required unit symbol matching the physical dimension.
        valid_range: (min_value, max_value) allowed by recipe specification.
        description: Process description or chemical role.
    """

    name: str
    setpoint: PhysicalQuantity
    tolerance: PhysicalQuantity
    unit: str
    valid_range: Tuple[float, float]
    description: str = ""

    def __post_init__(self) -> None:
        # Re-check that setpoint unit aligns
        if self.setpoint.unit != self.unit:
            self.setpoint = self.setpoint.to_unit(self.unit)
        if self.tolerance.unit != self.unit:
            self.tolerance = self.tolerance.to_unit(self.unit)

        val = self.setpoint.value
        min_v, max_v = self.valid_range
        if not (min_v <= val <= max_v):
            raise ValueError(
                f"Parameter '{self.name}' setpoint {val} {self.unit} is outside "
                f"allowable recipe bounds [{min_v}, {max_v}] {self.unit}"
            )

    def is_within_tolerance(self, actual: PhysicalQuantity) -> bool:
        """Evaluate if an in-situ tool telemetry measurement is within recipe tolerance."""
        actual_conv = actual.to_unit(self.unit)
        delta = abs(actual_conv.value - self.setpoint.value)
        return delta <= self.tolerance.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "setpoint": self.setpoint.to_dict(),
            "tolerance": self.tolerance.to_dict(),
            "unit": self.unit,
            "valid_range": list(self.valid_range),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RecipeParameter:
        return cls(
            name=str(data["name"]),
            setpoint=PhysicalQuantity.from_dict(data["setpoint"]),
            tolerance=PhysicalQuantity.from_dict(data["tolerance"]),
            unit=str(data["unit"]),
            valid_range=(float(data["valid_range"][0]), float(data["valid_range"][1])),
            description=str(data.get("description", "")),
        )


@dataclass
class BranchCondition:
    """Conditional branching rule for smart recipes (e.g. in-situ endpoint detection).

    Attributes:
        signal_name: Sensor or state flag (e.g., 'OES_ENDPOINT_REACHED', 'LASER_INTERFEROMETRY_CYCLES').
        operator: Evaluation logic ('==', '>=', '<=', '>', '<', 'EXISTS').
        threshold: Optional reference value to compare against.
        target_step_on_true: Step number to transition to if condition evaluates True.
        target_step_on_false: Optional step number to jump to if False (None falls through to next step).
    """

    signal_name: str
    operator: str
    target_step_on_true: int
    threshold: Optional[PhysicalQuantity] = None
    target_step_on_false: Optional[int] = None

    def evaluate(self, telemetry_signals: Dict[str, Any]) -> Optional[int]:
        """Evaluate telemetry signal dict and return the next step_number or None to continue sequentially."""
        if self.signal_name not in telemetry_signals:
            return self.target_step_on_false

        actual_val = telemetry_signals[self.signal_name]
        is_true = False

        match self.operator:
            case "EXISTS":
                is_true = bool(actual_val)
            case "==":
                if self.threshold is not None and isinstance(actual_val, PhysicalQuantity):
                    is_true = (actual_val == self.threshold)
                else:
                    is_true = (actual_val == (self.threshold.value if self.threshold else True))
            case ">":
                if self.threshold is not None and isinstance(actual_val, PhysicalQuantity):
                    is_true = (actual_val > self.threshold)
                elif self.threshold is not None:
                    is_true = float(actual_val) > self.threshold.value
            case "<":
                if self.threshold is not None and isinstance(actual_val, PhysicalQuantity):
                    is_true = (actual_val < self.threshold)
                elif self.threshold is not None:
                    is_true = float(actual_val) < self.threshold.value
            case ">=":
                if self.threshold is not None and isinstance(actual_val, PhysicalQuantity):
                    is_true = (actual_val >= self.threshold)
                elif self.threshold is not None:
                    is_true = float(actual_val) >= self.threshold.value
            case "<=":
                if self.threshold is not None and isinstance(actual_val, PhysicalQuantity):
                    is_true = (actual_val <= self.threshold)
                elif self.threshold is not None:
                    is_true = float(actual_val) <= self.threshold.value
            case _:
                is_true = bool(actual_val)

        return self.target_step_on_true if is_true else self.target_step_on_false

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_name": self.signal_name,
            "operator": self.operator,
            "target_step_on_true": self.target_step_on_true,
            "threshold": self.threshold.to_dict() if self.threshold else None,
            "target_step_on_false": self.target_step_on_false,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BranchCondition:
        th = PhysicalQuantity.from_dict(data["threshold"]) if data.get("threshold") else None
        return cls(
            signal_name=str(data["signal_name"]),
            operator=str(data["operator"]),
            target_step_on_true=int(data["target_step_on_true"]),
            threshold=th,
            target_step_on_false=int(data["target_step_on_false"]) if data.get("target_step_on_false") is not None else None,
        )


@dataclass
class RecipeStep:
    """Individual operational phase of an equipment process recipe.

    Attributes:
        step_number: 1-indexed sequential execution number.
        name: Semantic step label (e.g. 'Stabilization', 'Strike', 'Main Etch', 'Overetch', 'Purge').
        duration: Step duration setting.
        setpoints: Dictionary mapping parameter name to RecipeParameter.
        ramp_rates: Dictionary mapping parameter name to rate of change (e.g. temp ramp degC/s).
        end_condition: Mechanism that terminates the step ('TIME_ELAPSED', 'OES_ENDPOINT', 'MANUAL').
        branch_condition: Optional dynamic branching rule based on endpoint detection.
    """

    step_number: int
    name: str
    duration: PhysicalQuantity
    setpoints: Dict[str, RecipeParameter] = field(default_factory=dict)
    ramp_rates: Dict[str, PhysicalQuantity] = field(default_factory=dict)
    end_condition: str = "TIME_ELAPSED"
    branch_condition: Optional[BranchCondition] = None

    def __post_init__(self) -> None:
        if self.step_number < 1:
            raise ValueError(f"step_number must be >= 1, got {self.step_number}")
        if self.duration.value < 0.0:
            raise ValueError(f"duration cannot be negative, got {self.duration.value}")

    def add_parameter(self, param: RecipeParameter) -> None:
        """Add or update a recipe parameter."""
        self.setpoints[param.name] = param

    def get_parameter(self, name: str) -> Optional[RecipeParameter]:
        """Fetch recipe parameter by name."""
        return self.setpoints.get(name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "name": self.name,
            "duration": self.duration.to_dict(),
            "setpoints": {k: v.to_dict() for k, v in self.setpoints.items()},
            "ramp_rates": {k: v.to_dict() for k, v in self.ramp_rates.items()},
            "end_condition": self.end_condition,
            "branch_condition": self.branch_condition.to_dict() if self.branch_condition else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RecipeStep:
        pts = {k: RecipeParameter.from_dict(v) for k, v in data.get("setpoints", {}).items()}
        ramps = {k: PhysicalQuantity.from_dict(v) for k, v in data.get("ramp_rates", {}).items()}
        bc = BranchCondition.from_dict(data["branch_condition"]) if data.get("branch_condition") else None
        return cls(
            step_number=int(data["step_number"]),
            name=str(data["name"]),
            duration=PhysicalQuantity.from_dict(data["duration"]),
            setpoints=pts,
            ramp_rates=ramps,
            end_condition=str(data.get("end_condition", "TIME_ELAPSED")),
            branch_condition=bc,
        )


@dataclass
class EquipmentCapabilities:
    """Physical operational envelope supported by a specific piece of fab equipment.

    Used by the simulator to validate recipes before dispatching them to tools.

    Attributes:
        tool_type: Equipment model or family (e.g. 'ICP_ETCHER_300MM', 'ALD_REACTOR').
        parameter_bounds: Map from parameter name to (min_allowed, max_allowed) PhysicalQuantity.
        max_ramp_rates: Map from parameter name to maximum permissible ramp rate.
        supported_gases: List of gas species plumbed to tool gas box (MFCs).
        max_steps: Maximum recipe step count allowed by tool PLC.
    """

    tool_type: str
    parameter_bounds: Dict[str, Tuple[PhysicalQuantity, PhysicalQuantity]] = field(default_factory=dict)
    max_ramp_rates: Dict[str, PhysicalQuantity] = field(default_factory=dict)
    supported_gases: List[str] = field(default_factory=list)
    max_steps: int = 50

    def validate_recipe(self, recipe: Recipe) -> List[str]:
        """Validate entire recipe against equipment hardware capabilities.

        Returns:
            List of violation descriptions (empty if recipe is fully compliant).
        """
        violations: List[str] = []

        if len(recipe.steps) > self.max_steps:
            violations.append(
                f"Recipe step count {len(recipe.steps)} exceeds equipment maximum {self.max_steps}"
            )

        for step in recipe.steps:
            for p_name, param in step.setpoints.items():
                if p_name in self.parameter_bounds:
                    b_min, b_max = self.parameter_bounds[p_name]
                    p_val_base = param.setpoint.to_unit(b_min.unit).value
                    if p_val_base < b_min.value or p_val_base > b_max.value:
                        violations.append(
                            f"Step {step.step_number} ({step.name}) parameter '{p_name}' "
                            f"value {param.setpoint.value} {param.unit} is outside equipment capability "
                            f"[{b_min.value}, {b_max.value}] {b_min.unit}"
                        )

            for r_name, ramp in step.ramp_rates.items():
                if r_name in self.max_ramp_rates:
                    max_ramp = self.max_ramp_rates[r_name]
                    ramp_conv = ramp.to_unit(max_ramp.unit)
                    if abs(ramp_conv.value) > max_ramp.value:
                        violations.append(
                            f"Step {step.step_number} ramp rate for '{r_name}' "
                            f"{ramp_conv.value} {max_ramp.unit} exceeds tool maximum {max_ramp.value} {max_ramp.unit}"
                        )

        return violations


@dataclass
class Recipe:
    """Full equipment process recipe specifying a multi-step manufacturing sequence.

    Attributes:
        recipe_id: Unique recipe ID (e.g. 'RCP-22FDSOI-GATE-ETCH').
        name: Human-readable recipe title.
        process_type: Category of unit process (DRY_ETCH, ALD, CMP, etc.).
        node: Target semiconductor node ('180nm', '130nm', '65nm', '22nm_FDSOI').
        version: Version revision string (e.g. '1.0.3').
        steps: Sequential list of RecipeSteps.
        chamber_type: Targeted chamber configuration (e.g. 'ICP_ETCH_CHAMBER').
        description: Process engineering notes.
        author: Engineer or group who qualified this recipe.
    """

    recipe_id: str
    name: str
    process_type: ProcessType
    node: str
    version: str = "1.0.0"
    steps: List[RecipeStep] = field(default_factory=list)
    chamber_type: str = "STANDARD"
    description: str = ""
    author: str = "Process Integration Engineer"

    def add_step(self, step: RecipeStep) -> None:
        """Append or replace step based on step_number."""
        self.steps.append(step)
        self.steps.sort(key=lambda s: s.step_number)

    def get_step(self, step_number: int) -> Optional[RecipeStep]:
        """Retrieve step by step_number."""
        for s in self.steps:
            if s.step_number == step_number:
                return s
        return None

    def total_duration(self) -> PhysicalQuantity:
        """Calculate total baseline duration of the recipe assuming sequential flow."""
        total_s = sum(s.duration.to_unit("s").value for s in self.steps)
        return duration(total_s, "s", source="Sum of recipe step durations")

    def validate(self) -> List[str]:
        """Perform internal consistency and integrity validation on recipe structure.

        Returns:
            List of validation errors found.
        """
        errors: List[str] = []
        if not self.steps:
            errors.append("Recipe contains no execution steps.")
            return errors

        step_nums: Set[int] = set()
        for idx, step in enumerate(self.steps):
            if step.step_number in step_nums:
                errors.append(f"Duplicate step_number {step.step_number} found at index {idx}.")
            step_nums.add(step.step_number)

            # Check branch condition targets
            if step.branch_condition is not None:
                bc = step.branch_condition
                if bc.target_step_on_true not in step_nums and bc.target_step_on_true > len(self.steps) + 1:
                    errors.append(
                        f"Step {step.step_number} branch true target {bc.target_step_on_true} "
                        f"does not correspond to a valid step."
                    )
                if bc.target_step_on_false is not None:
                    if bc.target_step_on_false not in step_nums and bc.target_step_on_false > len(self.steps) + 1:
                        errors.append(
                            f"Step {step.step_number} branch false target {bc.target_step_on_false} "
                            f"does not correspond to a valid step."
                        )

        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "name": self.name,
            "process_type": self.process_type.value,
            "node": self.node,
            "version": self.version,
            "steps": [s.to_dict() for s in self.steps],
            "chamber_type": self.chamber_type,
            "description": self.description,
            "author": self.author,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Recipe:
        steps = [RecipeStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            recipe_id=str(data["recipe_id"]),
            name=str(data["name"]),
            process_type=ProcessType(data["process_type"]),
            node=str(data["node"]),
            version=str(data.get("version", "1.0.0")),
            steps=steps,
            chamber_type=str(data.get("chamber_type", "STANDARD")),
            description=str(data.get("description", "")),
            author=str(data.get("author", "")),
        )

    def __repr__(self) -> str:
        return (
            f"Recipe(id={self.recipe_id!r}, type={self.process_type.value}, "
            f"node={self.node!r}, steps={len(self.steps)})"
        )

    def __str__(self) -> str:
        return (
            f"Recipe '{self.name}' [{self.recipe_id}] ({self.process_type.value} @ {self.node}) - "
            f"{len(self.steps)} steps, duration: {self.total_duration().value:.1f}s"
        )


class RecipeLibrary:
    """Catalog of production and engineering recipes indexed by node and process type."""

    def __init__(self) -> None:
        self._recipes: Dict[str, Recipe] = {}
        self._load_standard_reference_recipes()

    def register_recipe(self, recipe: Recipe) -> None:
        """Register a new or updated recipe into the fab library."""
        validation_errors = recipe.validate()
        if validation_errors:
            raise ValueError(f"Cannot register invalid recipe '{recipe.recipe_id}': {validation_errors}")
        self._recipes[recipe.recipe_id] = recipe

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        """Fetch recipe by ID."""
        return self._recipes.get(recipe_id)

    def find_recipes(
        self,
        node: Optional[str] = None,
        process_type: Optional[ProcessType] = None,
    ) -> List[Recipe]:
        """Query recipes matching process node and/or process type."""
        results: List[Recipe] = []
        for r in self._recipes.values():
            if node is not None and r.node.lower() != node.lower():
                continue
            if process_type is not None and r.process_type != process_type:
                continue
            results.append(r)
        return results

    def _load_standard_reference_recipes(self) -> None:
        """Initialize built-in baseline recipes for 22nm FD-SOI and legacy planar nodes."""
        # 1. 22nm FD-SOI High-k Metal Gate (HKMG) ALD HfO2 Deposition
        rcp_ald_hfo2 = Recipe(
            recipe_id="RCP-22FDSOI-ALD-HFO2",
            name="22nm FD-SOI HKMG HfO2 Gate Dielectric Atomic Layer Deposition",
            process_type=ProcessType.ALD,
            node="22nm_FDSOI",
            version="2.1.0",
            chamber_type="SINGLE_WAFER_ALD",
            description="Ultra-thin 1.8nm HfO2 deposition via TEMAH + H2O at 280 degC.",
            author="Gate Stack Integration Team",
        )
        # Step 1: Pre-heat and pump down
        rcp_ald_hfo2.add_step(RecipeStep(
            step_number=1,
            name="Substrate Thermal Stabilization & Base Vacuum",
            duration=duration(30.0, "s"),
            setpoints={
                "Chamber Pressure": RecipeParameter(
                    name="Chamber Pressure",
                    setpoint=pressure(0.5, "Torr"),
                    tolerance=pressure(0.05, "Torr"),
                    unit="Torr",
                    valid_range=(0.1, 5.0),
                ),
                "Chuck Temperature": RecipeParameter(
                    name="Chuck Temperature",
                    setpoint=temperature(280.0, "degC"),
                    tolerance=temperature(1.0, "degC"),
                    unit="degC",
                    valid_range=(200.0, 350.0),
                ),
                "N2 Carrier Flow": RecipeParameter(
                    name="N2 Carrier Flow",
                    setpoint=gas_flow(200.0, "sccm"),
                    tolerance=gas_flow(5.0, "sccm"),
                    unit="sccm",
                    valid_range=(50.0, 1000.0),
                ),
            },
        ))
        # Step 2: TEMAH Precursor Pulse
        rcp_ald_hfo2.add_step(RecipeStep(
            step_number=2,
            name="TEMAH Precursor Pulse",
            duration=duration(0.3, "s"),
            setpoints={
                "Chamber Pressure": RecipeParameter(
                    name="Chamber Pressure",
                    setpoint=pressure(1.0, "Torr"),
                    tolerance=pressure(0.1, "Torr"),
                    unit="Torr",
                    valid_range=(0.2, 5.0),
                ),
                "TEMAH Carrier N2 Flow": RecipeParameter(
                    name="TEMAH Carrier N2 Flow",
                    setpoint=gas_flow(50.0, "sccm"),
                    tolerance=gas_flow(2.0, "sccm"),
                    unit="sccm",
                    valid_range=(10.0, 200.0),
                ),
            },
        ))
        # Step 3: N2 Purge
        rcp_ald_hfo2.add_step(RecipeStep(
            step_number=3,
            name="Inert Gas N2 Purge",
            duration=duration(2.0, "s"),
            setpoints={
                "N2 Purge Flow": RecipeParameter(
                    name="N2 Purge Flow",
                    setpoint=gas_flow(400.0, "sccm"),
                    tolerance=gas_flow(10.0, "sccm"),
                    unit="sccm",
                    valid_range=(100.0, 1000.0),
                ),
            },
        ))
        # Step 4: H2O Oxidizer Pulse
        rcp_ald_hfo2.add_step(RecipeStep(
            step_number=4,
            name="H2O Oxidizer Pulse",
            duration=duration(0.2, "s"),
            setpoints={
                "H2O Vapor Flow": RecipeParameter(
                    name="H2O Vapor Flow",
                    setpoint=gas_flow(20.0, "sccm"),
                    tolerance=gas_flow(2.0, "sccm"),
                    unit="sccm",
                    valid_range=(5.0, 100.0),
                ),
            },
        ))
        # Step 5: Post-Purge with conditional branching on film thickness cycle count
        rcp_ald_hfo2.add_step(RecipeStep(
            step_number=5,
            name="Reaction Byproduct Purge",
            duration=duration(2.5, "s"),
            branch_condition=BranchCondition(
                signal_name="ALD_CYCLES_COMPLETED",
                operator="<",
                threshold=PhysicalQuantity(22.0, "count", (1.0, 100.0), 0.0, "Target 22 ALD cycles for 1.8nm HfO2"),
                target_step_on_true=2,  # Loop back to TEMAH pulse
                target_step_on_false=6,  # Continue to pump down
            ),
        ))
        # Step 6: Final Pump Down & Vent
        rcp_ald_hfo2.add_step(RecipeStep(
            step_number=6,
            name="Chamber Pump Down & Complete",
            duration=duration(15.0, "s"),
        ))
        self.register_recipe(rcp_ald_hfo2)

        # 2. 22nm FD-SOI Gate ICP Dry Etch Recipe
        rcp_gate_etch = Recipe(
            recipe_id="RCP-22FDSOI-GATE-ETCH",
            name="22nm FD-SOI TiN/PolySi Gate ICP Reactive Ion Etch",
            process_type=ProcessType.DRY_ETCH,
            node="22nm_FDSOI",
            version="1.5.0",
            chamber_type="ICP_ETCH_CHAMBER",
            description="High-selectivity gate electrode etch stopping on 1.8nm HfO2 and 6nm top Si.",
            author="Dry Plasma Etch Module",
        )
        rcp_gate_etch.add_step(RecipeStep(
            step_number=1,
            name="Gas Stabilization",
            duration=duration(10.0, "s"),
            setpoints={
                "Chamber Pressure": RecipeParameter(
                    name="Chamber Pressure",
                    setpoint=pressure(5.0, "mTorr"),
                    tolerance=pressure(0.2, "mTorr"),
                    unit="mTorr",
                    valid_range=(1.0, 50.0),
                ),
                "Cl2 Gas Flow": RecipeParameter(
                    name="Cl2 Gas Flow",
                    setpoint=gas_flow(120.0, "sccm"),
                    tolerance=gas_flow(2.0, "sccm"),
                    unit="sccm",
                    valid_range=(10.0, 300.0),
                ),
                "HBr Gas Flow": RecipeParameter(
                    name="HBr Gas Flow",
                    setpoint=gas_flow(80.0, "sccm"),
                    tolerance=gas_flow(2.0, "sccm"),
                    unit="sccm",
                    valid_range=(10.0, 200.0),
                ),
            },
        ))
        rcp_gate_etch.add_step(RecipeStep(
            step_number=2,
            name="RF Strike & Main Etch",
            duration=duration(25.0, "s"),
            end_condition="OES_ENDPOINT",
            setpoints={
                "Chamber Pressure": RecipeParameter(
                    name="Chamber Pressure",
                    setpoint=pressure(5.0, "mTorr"),
                    tolerance=pressure(0.2, "mTorr"),
                    unit="mTorr",
                    valid_range=(1.0, 50.0),
                ),
                "Source RF Power": RecipeParameter(
                    name="Source RF Power",
                    setpoint=rf_power(650.0, "W"),
                    tolerance=rf_power(10.0, "W"),
                    unit="W",
                    valid_range=(100.0, 2000.0),
                ),
                "Bias RF Power": RecipeParameter(
                    name="Bias RF Power",
                    setpoint=rf_power(85.0, "W"),
                    tolerance=rf_power(5.0, "W"),
                    unit="W",
                    valid_range=(10.0, 500.0),
                ),
            },
            branch_condition=BranchCondition(
                signal_name="OES_ENDPOINT_REACHED",
                operator="==",
                target_step_on_true=3,  # Proceed to overetch
                target_step_on_false=2,  # Keep etching
            ),
        ))
        rcp_gate_etch.add_step(RecipeStep(
            step_number=3,
            name="Selective Overetch",
            duration=duration(8.0, "s"),
            setpoints={
                "Chamber Pressure": RecipeParameter(
                    name="Chamber Pressure",
                    setpoint=pressure(8.0, "mTorr"),
                    tolerance=pressure(0.3, "mTorr"),
                    unit="mTorr",
                    valid_range=(1.0, 50.0),
                ),
                "Source RF Power": RecipeParameter(
                    name="Source RF Power",
                    setpoint=rf_power(400.0, "W"),
                    tolerance=rf_power(10.0, "W"),
                    unit="W",
                    valid_range=(100.0, 1500.0),
                ),
                "Bias RF Power": RecipeParameter(
                    name="Bias RF Power",
                    setpoint=rf_power(25.0, "W"),
                    tolerance=rf_power(2.0, "W"),
                    unit="W",
                    valid_range=(5.0, 100.0),
                ),
            },
        ))
        rcp_gate_etch.add_step(RecipeStep(
            step_number=4,
            name="Chamber De-chucking & Pump Out",
            duration=duration(12.0, "s"),
        ))
        self.register_recipe(rcp_gate_etch)
