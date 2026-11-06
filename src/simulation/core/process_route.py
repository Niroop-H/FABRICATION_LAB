"""Manufacturing Process Route Architecture for Semiconductor Fab Digital Twin.

Models the end-to-end process sequence (traveller/route) required to fabricate
integrated circuits across nodes from 180nm down to 22nm FD-SOI.

Key Components:
  - ProcessNode: Enum of supported fab technological nodes (180nm, 130nm, 65nm, 22nm FD-SOI).
  - ProcessStepCategory / StepSector: Functional fab modules (LITHO, ETCH, DEPOSITION, CMP, etc.).
  - CriticalSpec: Statistical Process Control (SPC) tolerance band limits.
  - ProcessStep: Individual route unit with recipe link, specs, dependencies, parallel branches, and hold points.
  - ProcessRoute: Validated Directed Acyclic Graph (DAG) and sequence of manufacturing operations.
  - RouteLibrary: Pre-configured, fully qualified industrial process routes per node.

Standards References:
  - SEMI E10: Standard for Definition and Measurement of Equipment Reliability, Availability, and Maintainability
  - SEMI E40: Standard for Processing Management
  - SEMI E87: Specification for Carrier Management (CMS)
  - SEMI E90: Specification for Substrate Tracking
  - SEMI E95: Specification for Human Interface for Semiconductor Manufacturing Equipment
  - ITRS / IRDS: International Technology Roadmap for Devices and Systems
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .units import (
    PhysicalQuantity,
    duration,
    film_thickness,
    length,
    temperature,
)

logger = logging.getLogger(__name__)


class ProcessNode(str, Enum):
    """Semiconductor manufacturing technology nodes."""
    NM_180 = "180nm"
    NM_130 = "130nm"
    NM_65 = "65nm"
    NM_22_FDSOI = "22nm_FDSOI"


class ProcessStepCategory(str, Enum):
    """Broad category of semiconductor unit processes."""
    CLEAN = "CLEAN"
    OXIDATION = "OXIDATION"
    DIFFUSION = "DIFFUSION"
    ION_IMPLANT = "ION_IMPLANT"
    LITHOGRAPHY = "LITHOGRAPHY"
    ETCH = "ETCH"
    STRIP = "STRIP"
    THIN_FILM_DEPOSITION = "THIN_FILM_DEPOSITION"  # CVD, ALD, PVD
    CMP = "CMP"  # Chemical Mechanical Planarization
    ANNEAL = "ANNEAL"  # RTA, Spike, Laser
    METROLOGY = "METROLOGY"
    INSPECTION = "INSPECTION"
    TEST = "TEST"  # WAT, CP


# Alias for compatibility
StepSector = ProcessStepCategory


@dataclass(frozen=True)
class CriticalSpec:
    """Statistical Process Control (SPC) or Engineering specification limits for a process metric.

    Attributes:
        metric_name: Name of measured property (e.g., 'film_thickness', 'critical_dimension').
        target: Target nominal physical quantity.
        lsl: Lower Specification Limit (engineering hard boundary).
        usl: Upper Specification Limit (engineering hard boundary).
        lcl: Lower Control Limit (+/- 3-sigma SPC statistical limit).
        ucl: Upper Control Limit (+/- 3-sigma SPC statistical limit).
    """

    metric_name: str
    target: PhysicalQuantity
    lsl: PhysicalQuantity
    usl: PhysicalQuantity
    lcl: Optional[PhysicalQuantity] = None
    ucl: Optional[PhysicalQuantity] = None

    def __post_init__(self) -> None:
        """Validate specification limit hierarchy."""
        if self.lsl.value > self.usl.value:
            raise ValueError(
                f"LSL ({self.lsl.value}) cannot exceed USL ({self.usl.value}) for {self.metric_name}"
            )
        if self.target.value < self.lsl.value or self.target.value > self.usl.value:
            raise ValueError(
                f"Target ({self.target.value}) must lie between LSL and USL for {self.metric_name}"
            )
        if self.lcl is not None and self.ucl is not None:
            if self.lcl.value > self.ucl.value:
                raise ValueError(
                    f"LCL ({self.lcl.value}) cannot exceed UCL ({self.ucl.value}) for {self.metric_name}"
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "target": self.target.to_dict(),
            "lsl": self.lsl.to_dict(),
            "usl": self.usl.to_dict(),
            "lcl": self.lcl.to_dict() if self.lcl else None,
            "ucl": self.ucl.to_dict() if self.ucl else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CriticalSpec:
        lcl_val = PhysicalQuantity.from_dict(data["lcl"]) if data.get("lcl") else None
        ucl_val = PhysicalQuantity.from_dict(data["ucl"]) if data.get("ucl") else None
        return cls(
            metric_name=str(data["metric_name"]),
            target=PhysicalQuantity.from_dict(data["target"]),
            lsl=PhysicalQuantity.from_dict(data["lsl"]),
            usl=PhysicalQuantity.from_dict(data["usl"]),
            lcl=lcl_val,
            ucl=ucl_val,
        )


@dataclass
class ProcessStep:
    """Individual unit process step in a wafer fabrication route.

    Attributes:
        step_number: Sequential step index (e.g. 10, 20, 30...).
        step_id: Unique string identifier (e.g. 'FD22_GATE_ETCH_080').
        name: Human-readable step name.
        category: Unit process category enum (ProcessStepCategory).
        equipment_type: SEMI equipment classification required for processing.
        recipe_reference: Equipment recipe ID or file name.
        specifications: Target physical parameters (e.g., target thickness, CD).
        critical_specs: Dict of critical quality metric specifications.
        dependencies: List of prerequisite step_numbers that must be completed.
        can_run_parallel_with: List of step_numbers that may execute concurrently.
        is_hold_point: Quality gate / SPC hold point requiring sign-off.
        metrology_required: Flag indicating inline metrology inspection is mandatory.
        estimated_duration: Expected step duration as PhysicalQuantity.
        estimated_duration_min: Typical run time in minutes (convenience float property).
        safety_hazards: List of environmental or equipment safety considerations.
        description: Detailed engineering description.
    """

    step_number: int
    step_id: str
    name: str
    category: ProcessStepCategory = ProcessStepCategory.THIN_FILM_DEPOSITION
    equipment_type: str = "GENERIC_TOOL"
    recipe_reference: str = "DEFAULT_RECIPE"
    specifications: Dict[str, PhysicalQuantity] = field(default_factory=dict)
    critical_specs: Dict[str, CriticalSpec] = field(default_factory=dict)
    dependencies: List[int] = field(default_factory=list)
    can_run_parallel_with: List[int] = field(default_factory=list)
    is_hold_point: bool = False
    metrology_required: bool = False
    estimated_duration: PhysicalQuantity = field(
        default_factory=lambda: duration(1800.0, "s", source="Standard Batch Process Duration")
    )
    estimated_duration_min: float = 30.0
    safety_hazards: List[str] = field(default_factory=list)
    description: str = ""

    def __post_init__(self) -> None:
        if self.step_number <= 0:
            raise ValueError(f"step_number must be positive, got {self.step_number}")
        if not self.step_id.strip():
            raise ValueError("step_id cannot be empty")

        # Keep duration fields in sync
        if self.estimated_duration is not None:
            self.estimated_duration_min = self.estimated_duration.to_unit("min").value
        elif self.estimated_duration_min > 0:
            self.estimated_duration = duration(self.estimated_duration_min * 60.0, "s")

    @property
    def recipe_name(self) -> str:
        """Alias for recipe_reference."""
        return self.recipe_reference

    @property
    def sector(self) -> ProcessStepCategory:
        """Alias for category."""
        return self.category

    @property
    def parameters(self) -> Dict[str, PhysicalQuantity]:
        """Alias returning specifications dict for backward compatibility."""
        return self.specifications

    def get_parameter(self, param_name: str) -> Optional[PhysicalQuantity]:
        """Retrieve a specific parameter or specification by name."""
        return self.specifications.get(param_name)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize step metadata to standard dictionary format."""
        return {
            "step_number": self.step_number,
            "step_id": self.step_id,
            "name": self.name,
            "category": self.category.value,
            "equipment_type": self.equipment_type,
            "recipe_reference": self.recipe_reference,
            "recipe_name": self.recipe_reference,
            "specifications": {k: v.to_dict() for k, v in self.specifications.items()},
            "critical_specs": {k: v.to_dict() for k, v in self.critical_specs.items()},
            "dependencies": list(self.dependencies),
            "can_run_parallel_with": list(self.can_run_parallel_with),
            "is_hold_point": self.is_hold_point,
            "metrology_required": self.metrology_required,
            "estimated_duration": self.estimated_duration.to_dict(),
            "estimated_duration_min": self.estimated_duration_min,
            "safety_hazards": list(self.safety_hazards),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProcessStep:
        specs = {k: PhysicalQuantity.from_dict(v) for k, v in data.get("specifications", {}).items()}
        # Also parse legacy parameters if specifications was empty
        if not specs and "parameters" in data:
            specs = {k: PhysicalQuantity.from_dict(v) for k, v in data["parameters"].items()}

        crit = {k: CriticalSpec.from_dict(v) for k, v in data.get("critical_specs", {}).items()}
        cat = ProcessStepCategory(data.get("category", ProcessStepCategory.THIN_FILM_DEPOSITION.value))
        rcp = str(data.get("recipe_reference") or data.get("recipe_name", "DEFAULT_RECIPE"))
        dur = (
            PhysicalQuantity.from_dict(data["estimated_duration"])
            if "estimated_duration" in data
            else duration(float(data.get("estimated_duration_min", 30.0)) * 60.0, "s")
        )

        return cls(
            step_number=int(data["step_number"]),
            step_id=str(data["step_id"]),
            name=str(data["name"]),
            category=cat,
            equipment_type=str(data.get("equipment_type", "GENERIC_TOOL")),
            recipe_reference=rcp,
            specifications=specs,
            critical_specs=crit,
            dependencies=[int(d) for d in data.get("dependencies", [])],
            can_run_parallel_with=[int(p) for p in data.get("can_run_parallel_with", [])],
            is_hold_point=bool(data.get("is_hold_point", False)),
            metrology_required=bool(data.get("metrology_required", False)),
            estimated_duration=dur,
            estimated_duration_min=float(data.get("estimated_duration_min", dur.to_unit("min").value)),
            safety_hazards=list(data.get("safety_hazards", [])),
            description=str(data.get("description", "")),
        )


@dataclass
class ProcessRoute:
    """Complete fabrication sequence representing an entire technology flow.

    Attributes:
        route_id: Unique route identifier (e.g. 'ROUTE_22FDSOI_FEOL').
        name: Human-readable route title.
        process_node: ProcessNode enum (e.g. NM_22_FDSOI, NM_65, NM_180).
        technology_node: Node string representation.
        wafer_diameter_mm: Standard wafer diameter (200.0 or 300.0 mm).
        wafer_type: Starting substrate description.
        steps: Chronologically ordered list of unit process steps.
        description: Engineering overview of the route.
        version: Route revision string.
        mask_layers: Total number of lithography mask levels.
        metal_layers: Number of interconnect metal layers.
    """

    route_id: str
    name: str
    process_node: ProcessNode = ProcessNode.NM_22_FDSOI
    technology_node: str = "22nm_FDSOI"
    wafer_diameter_mm: float = 300.0
    wafer_type: str = "300mm SOI Wafer"
    steps: List[ProcessStep] = field(default_factory=list)
    description: str = ""
    version: str = "1.0.0"
    mask_layers: int = 24
    metal_layers: int = 6

    def __post_init__(self) -> None:
        """Validate step numbers order and harmonize node fields."""
        if isinstance(self.process_node, str):
            try:
                self.process_node = ProcessNode(self.process_node)
            except ValueError:
                # Map raw strings
                for node in ProcessNode:
                    if node.value.lower() == self.process_node.lower():
                        self.process_node = node
                        break
        self.technology_node = self.process_node.value
        self.steps.sort(key=lambda s: s.step_number)

    def add_step(self, step: ProcessStep) -> None:
        """Add a step and sort sequence by step_number."""
        self.steps.append(step)
        self.steps.sort(key=lambda s: s.step_number)

    @property
    def total_steps(self) -> int:
        """Total number of process steps in route."""
        return len(self.steps)

    def get_step(self, step_number: int) -> Optional[ProcessStep]:
        """Fetch step by sequence number."""
        for step in self.steps:
            if step.step_number == step_number:
                return step
        return None

    def get_step_by_number(self, step_number: int) -> Optional[ProcessStep]:
        """Locate process step by its sequence number (alias for get_step)."""
        return self.get_step(step_number)

    def get_step_by_id(self, step_id: str) -> Optional[ProcessStep]:
        """Locate process step by its unique step identifier."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def get_step_index(self, step_id: str) -> int:
        """Get 0-based index of step in the sequence."""
        for idx, step in enumerate(self.steps):
            if step.step_id == step_id:
                return idx
        raise ValueError(f"Step ID '{step_id}' not found in route '{self.route_id}'")

    def get_hold_points(self) -> List[ProcessStep]:
        """Return all steps flagged as QA / metrology hold points."""
        return [s for s in self.steps if s.is_hold_point]

    def total_cycle_time(self) -> PhysicalQuantity:
        """Calculate total raw process cycle time as PhysicalQuantity."""
        total_s = sum(s.estimated_duration.to_unit("s").value for s in self.steps)
        return duration(total_s, "s", source="Sum of all route step cycle times")

    def total_cycle_time_estimate_hours(self) -> float:
        """Calculate nominal raw process cycle time in hours (excluding queue/wait time)."""
        return self.total_cycle_time().to_unit("hr").value

    def get_steps_by_equipment(self, equipment_type: str) -> List[ProcessStep]:
        """Return all steps performed on a given equipment type."""
        return [step for step in self.steps if step.equipment_type == equipment_type]

    def validate_route(self) -> List[str]:
        """Validate DAG dependencies, step ordering, and duplicate step numbers.

        Returns:
            List of validation errors found (empty if route is valid).
        """
        errors: List[str] = []
        if not self.steps:
            errors.append("ProcessRoute contains no steps.")
            return errors

        step_numbers: Set[int] = set()
        step_ids: Set[str] = set()

        for idx, step in enumerate(self.steps):
            if step.step_number in step_numbers:
                errors.append(f"Duplicate step_number {step.step_number} found at index {idx}.")
            step_numbers.add(step.step_number)

            if step.step_id in step_ids:
                errors.append(f"Duplicate step_id '{step.step_id}' found at index {idx}.")
            step_ids.add(step.step_id)

            # Validate dependencies: dependencies must reference existing strictly prior steps
            for dep in step.dependencies:
                if dep not in step_numbers or dep >= step.step_number:
                    errors.append(
                        f"Step {step.step_number} ({step.step_id}) has invalid dependency on step {dep}. "
                        "Dependencies must point to strictly prior steps."
                    )

            # Validate parallel steps
            for par in step.can_run_parallel_with:
                if par == step.step_number:
                    errors.append(f"Step {step.step_number} cannot run parallel with itself.")

        return errors

    def get_eligible_steps(
        self,
        completed_step_numbers: Set[int],
    ) -> List[ProcessStep]:
        """Evaluate DAG dependencies and return all steps currently eligible to execute.

        Args:
            completed_step_numbers: Set of step numbers already successfully executed.

        Returns:
            List of executable ProcessSteps whose dependencies are satisfied.
        """
        eligible: List[ProcessStep] = []
        for step in self.steps:
            if step.step_number in completed_step_numbers:
                continue

            deps_satisfied = True
            for dep in step.dependencies:
                if dep not in completed_step_numbers:
                    deps_satisfied = False
                    break

            if deps_satisfied:
                eligible.append(step)

        return eligible

    def to_dict(self) -> Dict[str, Any]:
        """Serialize route to standard dictionary."""
        return {
            "route_id": self.route_id,
            "name": self.name,
            "process_node": self.process_node.value,
            "technology_node": self.technology_node,
            "wafer_diameter_mm": self.wafer_diameter_mm,
            "wafer_type": self.wafer_type,
            "version": self.version,
            "steps": [s.to_dict() for s in self.steps],
            "description": self.description,
            "mask_layers": self.mask_layers,
            "metal_layers": self.metal_layers,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProcessRoute:
        """Reconstruct ProcessRoute from dictionary representation."""
        steps = [ProcessStep.from_dict(s) for s in data.get("steps", [])]
        node_str = data.get("process_node") or data.get("technology_node", ProcessNode.NM_22_FDSOI.value)
        try:
            node = ProcessNode(node_str)
        except ValueError:
            node = ProcessNode.NM_22_FDSOI

        return cls(
            route_id=str(data["route_id"]),
            name=str(data["name"]),
            process_node=node,
            technology_node=node.value,
            wafer_diameter_mm=float(data.get("wafer_diameter_mm", 300.0)),
            wafer_type=str(data.get("wafer_type", "Standard Wafer")),
            version=str(data.get("version", "1.0.0")),
            steps=steps,
            description=str(data.get("description", "")),
            mask_layers=int(data.get("mask_layers", 24)),
            metal_layers=int(data.get("metal_layers", 6)),
        )

    def __repr__(self) -> str:
        return (
            f"ProcessRoute(id={self.route_id!r}, node={self.process_node.value}, "
            f"steps={len(self.steps)})"
        )

    def __str__(self) -> str:
        return (
            f"Process Route '{self.name}' [{self.route_id}] ({self.process_node.value}) - "
            f"{len(self.steps)} steps, {len(self.get_hold_points())} hold points"
        )


class RouteLibrary:
    """Central repository of factory process routes for all supported semiconductor nodes."""

    def __init__(self) -> None:
        self._routes: Dict[str, ProcessRoute] = {}
        self._load_standard_routes()

    def register_route(self, route: ProcessRoute) -> None:
        """Register a new or modified route with automated DAG validation."""
        errors = route.validate_route()
        if errors:
            raise ValueError(f"Cannot register invalid route '{route.route_id}': {errors}")
        self._routes[route.route_id] = route

    def get_route(self, route_id: str) -> Optional[ProcessRoute]:
        """Fetch route by identifier."""
        return self._routes.get(route_id)

    def get_routes_by_node(self, node: ProcessNode) -> List[ProcessRoute]:
        """Fetch all routes qualified for a specific process node."""
        return [r for r in self._routes.values() if r.process_node == node]

    def _load_standard_routes(self) -> None:
        """Load industrial reference routes for 22nm FD-SOI, 65nm, and 180nm nodes."""
        # 1. 22nm FD-SOI Front-End-Of-Line (FEOL) Full Process Route
        r22 = ProcessRoute(
            route_id="ROUTE-22FDSOI-FEOL-FLOW",
            name="22nm FD-SOI Front-End-of-Line (FEOL) Fabrication Route",
            process_node=ProcessNode.NM_22_FDSOI,
            technology_node=ProcessNode.NM_22_FDSOI.value,
            wafer_diameter_mm=300.0,
            wafer_type="300mm SmartCut™ SOI Wafer (20nm BOX / 6nm UTB Si)",
            version="3.0.0",
            mask_layers=28,
            metal_layers=8,
            description=(
                "Complete 22nm FD-SOI FEOL integration flow featuring SmartCut™ SOI substrate, "
                "Shallow Trench Isolation (STI), High-k Metal Gate (HKMG) ALD HfO2, dual-workfunction "
                "metal gates, raised source/drain epitaxy, and NiPt salicide."
            ),
        )

        # Step 10: Incoming Substrate Inspection
        r22.add_step(ProcessStep(
            step_number=10,
            step_id="FD22_SUB_INSPECT_010",
            name="Incoming 300mm SOI Wafer Inspection",
            category=ProcessStepCategory.METROLOGY,
            equipment_type="OPTICAL_INSPECTOR_300MM",
            recipe_reference="RCP-22FDSOI-SUB-INSPECT",
            specifications={
                "BOX Thickness Target": film_thickness(20.0, "nm", 0.5),
                "Top Si Device Layer Target": film_thickness(6.0, "nm", 0.2),
            },
            dependencies=[],
            is_hold_point=True,
            metrology_required=True,
            estimated_duration=duration(1200.0, "s"),
            description="Verify ultra-thin body top silicon (6nm) and buried oxide (20nm) uniformity.",
        ))

        # Step 20: Pad Oxide & SiN Hardmask Deposition
        r22.add_step(ProcessStep(
            step_number=20,
            step_id="FD22_PAD_DEP_020",
            name="Pad Oxide Thermal Growth & LPCVD SiN Hardmask",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="THERMAL_FURNACE_300MM",
            recipe_reference="RCP-22FDSOI-PAD-OX-SIN",
            specifications={
                "Pad Oxide Thickness": film_thickness(3.0, "nm", 0.2),
                "SiN Hardmask Thickness": film_thickness(60.0, "nm", 1.5),
            },
            dependencies=[10],
            is_hold_point=False,
            metrology_required=True,
            estimated_duration=duration(5400.0, "s"),
            description="Grow 3nm screen pad oxide and deposit 60nm Si3N4 hardmask.",
        ))

        # Step 30: STI Lithography & Etch
        r22.add_step(ProcessStep(
            step_number=30,
            step_id="FD22_STI_ETCH_030",
            name="STI Trench Lithography and ICP Reactive Ion Etch",
            category=ProcessStepCategory.ETCH,
            equipment_type="ICP_ETCHER_300MM",
            recipe_reference="RCP-22FDSOI-STI-ETCH",
            specifications={
                "STI Depth": length(120.0, "nm", (100.0, 150.0), 2.0),
                "STI Trench CD": length(30.0, "nm", (20.0, 50.0), 1.0),
            },
            dependencies=[20],
            is_hold_point=False,
            metrology_required=True,
            estimated_duration=duration(3600.0, "s"),
            description="Etch shallow isolation trenches stopping inside the handle substrate.",
        ))

        # Step 40: STI Fill & CMP Planarization
        r22.add_step(ProcessStep(
            step_number=40,
            step_id="FD22_STI_CMP_040",
            name="STI HDP-CVD Oxide Fill & CMP Planarization",
            category=ProcessStepCategory.CMP,
            equipment_type="CMP_POLISHER_300MM",
            recipe_reference="RCP-22FDSOI-STI-CMP",
            specifications={
                "Remaining SiN Thickness": film_thickness(45.0, "nm", 2.0),
                "Oxide Dishing": length(3.0, "nm", (0.0, 10.0), 0.5),
            },
            dependencies=[30],
            is_hold_point=True,
            metrology_required=True,
            estimated_duration=duration(4200.0, "s"),
            description="High-density plasma oxide trench gap fill and planarization stopping on SiN.",
        ))

        # Step 50: Nitride Strip & Well/Back-Gate Implantation
        r22.add_step(ProcessStep(
            step_number=50,
            step_id="FD22_BACKGATE_IMPLANT_050",
            name="Hot Phosphoric Acid SiN Strip & Back-Gate Well Implant",
            category=ProcessStepCategory.ION_IMPLANT,
            equipment_type="HIGH_ENERGY_IMPLANTER_300MM",
            recipe_reference="RCP-22FDSOI-WELL-IMPLANT",
            specifications={
                "Back-Gate Well Dose": PhysicalQuantity(2e13, "ions/cm^2", (1e12, 1e15), 1e12, "Well Doping"),
            },
            dependencies=[40],
            is_hold_point=False,
            metrology_required=False,
            estimated_duration=duration(3600.0, "s"),
            description="Implant phosphorus / boron below BOX layer for threshold voltage back-bias tuning.",
        ))

        # Step 60: HKMG High-k ALD HfO2 Deposition
        r22.add_step(ProcessStep(
            step_number=60,
            step_id="FD22_HKMG_ALD_060",
            name="High-k Gate Dielectric ALD (1.8nm HfO2)",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="ALD_REACTOR_300MM",
            recipe_reference="RCP-22FDSOI-ALD-HFO2",
            specifications={
                "HfO2 Film Thickness": film_thickness(1.8, "nm", 0.05),
                "EOT Target": film_thickness(0.85, "nm", 0.03),
            },
            dependencies=[50],
            is_hold_point=True,
            metrology_required=True,
            estimated_duration=duration(2700.0, "s"),
            description="Deposit ultra-thin 1.8nm HfO2 high-k dielectric on pristine 6nm silicon channel.",
        ))

        # Step 70: Workfunction Metal & PolySi Gate Stack Deposition
        r22.add_step(ProcessStep(
            step_number=70,
            step_id="FD22_GATE_STACK_070",
            name="TiN/TaN Metal Gate Sputter & PolySi Cap Deposition",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="CLUSTER_PVD_LPCVD_300MM",
            recipe_reference="RCP-22FDSOI-PVD-TIN",
            specifications={
                "TiN Gate Thickness": film_thickness(4.0, "nm", 0.2),
                "PolySi Cap Thickness": film_thickness(45.0, "nm", 1.0),
            },
            dependencies=[60],
            is_hold_point=False,
            metrology_required=True,
            estimated_duration=duration(3600.0, "s"),
            description="Deposit TiN metal gate workfunction layer followed by protective polysilicon cap.",
        ))

        # Step 80: Gate Patterning & ICP Reactive Ion Etch
        r22.add_step(ProcessStep(
            step_number=80,
            step_id="FD22_GATE_ETCH_080",
            name="ArF Immersion Gate Lithography & ICP Plasma Etch",
            category=ProcessStepCategory.ETCH,
            equipment_type="ICP_ETCHER_300MM",
            recipe_reference="RCP-22FDSOI-GATE-ETCH",
            specifications={
                "Gate Critical Dimension (CD)": length(20.0, "nm", (15.0, 25.0), 0.5),
            },
            dependencies=[70],
            is_hold_point=True,
            metrology_required=True,
            estimated_duration=duration(4800.0, "s"),
            description="Critical 22nm gate etch stopping cleanly on 1.8nm HfO2 and 6nm silicon body.",
        ))

        # Step 90: Raised Source/Drain (RSD) Epitaxy
        r22.add_step(ProcessStep(
            step_number=90,
            step_id="FD22_RSD_EPI_090",
            name="Raised Source/Drain (RSD) In-Situ Doped Epitaxy",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="UHVCVD_EPI_REACTOR_300MM",
            recipe_reference="RCP-22FDSOI-EPI-RSD",
            specifications={
                "RSD Facet Thickness": film_thickness(18.0, "nm", 0.5),
            },
            dependencies=[80],
            is_hold_point=False,
            metrology_required=True,
            estimated_duration=duration(5400.0, "s"),
            description="Grow selective SiGe (pMOS) and Si:P (nMOS) raised contacts on 6nm thin silicon.",
        ))

        # Step 100: Rapid Thermal Spike Anneal
        r22.add_step(ProcessStep(
            step_number=100,
            step_id="FD22_SPIKE_ANNEAL_100",
            name="Ultra-Shallow Junction Rapid Thermal Spike Anneal",
            category=ProcessStepCategory.ANNEAL,
            equipment_type="RTA_CHAMBER_300MM",
            recipe_reference="RCP-22FDSOI-RTA-SPIKE",
            specifications={
                "Peak Temperature Target": temperature(1050.0, "degC", (1020.0, 1080.0), 2.0),
            },
            dependencies=[90],
            is_hold_point=False,
            metrology_required=False,
            estimated_duration=duration(1800.0, "s"),
            description="1050 degC spike anneal with millisecond dwell to activate dopants without diffusion.",
        ))

        # Step 110: NiPt Salicide Formation
        r22.add_step(ProcessStep(
            step_number=110,
            step_id="FD22_SALICIDE_110",
            name="Self-Aligned Nickel-Platinum Silicide (NiPtSi)",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="CLUSTER_PVD_RTA_300MM",
            recipe_reference="RCP-22FDSOI-NIPT-SALICIDE",
            specifications={
                "NiPt Thickness Target": film_thickness(7.0, "nm", 0.3),
                "Sheet Resistance Target": PhysicalQuantity(12.0, "ohm/sq", (5.0, 25.0), 0.5, "Rs Salicide"),
            },
            dependencies=[100],
            is_hold_point=True,
            metrology_required=True,
            estimated_duration=duration(3600.0, "s"),
            description="Deposit 7nm Ni-Pt alloy and two-step anneal to form low-resistance silicide contacts.",
        ))
        self.register_route(r22)

        # 2. 65nm Standard Planar CMOS FEOL Route
        r65 = ProcessRoute(
            route_id="ROUTE-65NM-FEOL-FLOW",
            name="65nm Standard Planar CMOS FEOL Fabrication Route",
            process_node=ProcessNode.NM_65,
            technology_node=ProcessNode.NM_65.value,
            wafer_diameter_mm=300.0,
            wafer_type="300mm Monocrystalline Bulk Silicon",
            version="1.2.0",
            description="Standard 65nm planar CMOS front-end route on bulk 300mm silicon.",
        )
        r65.add_step(ProcessStep(
            step_number=10,
            step_id="CMOS65_SUB_INSPECT_010",
            name="Incoming 300mm Bulk Silicon Inspection",
            category=ProcessStepCategory.METROLOGY,
            equipment_type="OPTICAL_INSPECTOR_300MM",
            recipe_reference="RCP-65NM-SUB-INSPECT",
            dependencies=[],
            is_hold_point=True,
            metrology_required=True,
        ))
        r65.add_step(ProcessStep(
            step_number=20,
            step_id="CMOS65_STI_TRENCH_020",
            name="STI Isolation Trench Etch",
            category=ProcessStepCategory.ETCH,
            equipment_type="ICP_ETCHER_300MM",
            recipe_reference="RCP-65NM-STI-ETCH",
            specifications={"STI Depth": length(300.0, "nm", (280.0, 320.0), 5.0)},
            dependencies=[10],
        ))
        r65.add_step(ProcessStep(
            step_number=30,
            step_id="CMOS65_GATE_OX_030",
            name="Thermal Gate Oxidation (SiON 1.4nm)",
            category=ProcessStepCategory.OXIDATION,
            equipment_type="THERMAL_FURNACE_300MM",
            recipe_reference="RCP-65NM-GATE-SION",
            specifications={"SiON Thickness": film_thickness(1.4, "nm", 0.05)},
            dependencies=[20],
            is_hold_point=True,
            metrology_required=True,
        ))
        r65.add_step(ProcessStep(
            step_number=40,
            step_id="CMOS65_POLY_GATE_040",
            name="Polysilicon Gate Deposition & Etch (65nm CD)",
            category=ProcessStepCategory.ETCH,
            equipment_type="ICP_ETCHER_300MM",
            recipe_reference="RCP-65NM-POLY-ETCH",
            specifications={"Gate CD": length(60.0, "nm", (55.0, 65.0), 1.0)},
            dependencies=[30],
            is_hold_point=True,
            metrology_required=True,
        ))
        self.register_route(r65)

        # 3. 180nm Planar CMOS Route
        r180 = ProcessRoute(
            route_id="ROUTE-180NM-CMOS-FLOW",
            name="180nm Planar CMOS Fabrication Route",
            process_node=ProcessNode.NM_180,
            technology_node=ProcessNode.NM_180.value,
            wafer_diameter_mm=200.0,
            wafer_type="200mm Monocrystalline Bulk Silicon",
            version="1.0.0",
            description="Mature 180nm planar CMOS fabrication flow on 200mm bulk wafers.",
        )
        r180.add_step(ProcessStep(
            step_number=10,
            step_id="CMOS180_PAD_OX_010",
            name="Pad Oxidation & LOCOS / STI Masking",
            category=ProcessStepCategory.OXIDATION,
            equipment_type="HORIZONTAL_FURNACE_200MM",
            recipe_reference="RCP-180NM-PAD-OX",
            specifications={"Pad Oxide": film_thickness(15.0, "nm", 1.0)},
            dependencies=[],
        ))
        r180.add_step(ProcessStep(
            step_number=20,
            step_id="CMOS180_GATE_DEP_020",
            name="Gate Oxidation (3.5nm SiO2) & PolySi Gate Deposition",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="LPCVD_FURNACE_200MM",
            recipe_reference="RCP-180NM-GATE-OX",
            specifications={"Gate Oxide": film_thickness(3.5, "nm", 0.1)},
            dependencies=[10],
            is_hold_point=True,
            metrology_required=True,
        ))
        self.register_route(r180)
