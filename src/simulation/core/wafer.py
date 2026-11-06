"""Digital Wafer Representation for Semiconductor Fab Digital Twin.

Represents the physical, structural, and chemical state of a silicon or SOI wafer
as it progresses through fab unit processes (litho, etch, deposition, CMP, implant).

Key Components:
  - WaferID: Identification per SEMI T7 / M12 standard.
  - WaferSubstrate: Substrate physics (material, crystal orientation, diameter,
    thickness, dopants, resistivity, and SOI BOX / device layer parameters).
  - Layer / LayerStack: High-fidelity thin-film material stack with physical
    thickness, deposition mechanism, optical constants, and Stoney equation stress.
  - WaferState: Dynamic surface condition tracking (particles, defectivity,
    thermal profile, metal contamination, bow, warpage, and TTV).
  - ProcessHistory: Chronological provenance of tools, recipes, run parameters.
  - MetrologyResults: In-line metrology measurements (CD-SEM, ellipsometry,
    four-point probe, defect inspection, and site wafer maps).

Standards References:
  - SEMI M1: Specifications for Polished Single Crystal Silicon Wafers
  - SEMI T7: Specification for Back Surface Marking of Double-Side Polished Wafers
  - SEMI M12: Specification for Serial Alphanumeric Marking of Wafers
  - Stoney, G.G. (1909): The Tension of Metallic Films Deposited by Electrolysis
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from .units import (
    PhysicalQuantity,
    film_thickness,
    length,
    temperature,
    wafer_diameter,
    wafer_thickness,
)


class SubstrateMaterial(str, Enum):
    """Substrate material types used across planar CMOS and advanced nodes."""
    BULK_SILICON = "BULK_SILICON"
    SOI_FDSOI = "SOI_FDSOI"  # Fully Depleted Silicon-On-Insulator (e.g. 22nm FD-SOI)
    SOI_PDSOI = "SOI_PDSOI"  # Partially Depleted SOI
    SILICON_GERMANIUM = "SILICON_GERMANIUM"  # SiGe virtual substrates
    GALLIUM_NITRIDE = "GALLIUM_NITRIDE"  # GaN on Si / SiC
    SILICON_CARBIDE = "SILICON_CARBIDE"  # 4H/6H SiC power substrates


class CrystalOrientation(str, Enum):
    """Wafer crystallographic orientation."""
    ORIENTATION_100 = "<100>"
    ORIENTATION_110 = "<110>"
    ORIENTATION_111 = "<111>"


class DopantType(str, Enum):
    """Substrate background dopant impurity."""
    P_BORON = "P_BORON"
    N_PHOSPHORUS = "N_PHOSPHORUS"
    N_ARSENIC = "N_ARSENIC"
    N_ANTIMONY = "N_ANTIMONY"
    INTRINSIC = "INTRINSIC"


class MetrologyType(str, Enum):
    """Standard in-line fab metrology inspection methods."""
    CD_SEM = "CD_SEM"  # Critical Dimension Scanning Electron Microscopy
    ELLIPSOMETRY = "ELLIPSOMETRY"  # Spectroscopic Ellipsometry (film thickness, n, k)
    FOUR_POINT_PROBE = "FOUR_POINT_PROBE"  # Sheet resistance / Rs mapping
    DEFECT_INSPECTION = "DEFECT_INSPECTION"  # Brightfield/darkfield optical surface inspection
    XRR = "XRR"  # X-Ray Reflectivity (density, ultra-thin film thickness)
    XRD = "XRD"  # X-Ray Diffraction (crystal strain, phase)
    INTERFEROMETRY = "INTERFEROMETRY"  # Wafer bow, warp, TTV, flatness


@dataclass(frozen=True)
class WaferID:
    """Unique digital identifier for a physical wafer.

    Attributes:
        lot_id: Production lot identifier (e.g. 'LOT-22FD-001').
        wafer_number: Cassette slot / wafer index (1 to 25 per SEMI E1).
        laser_mark: Back-surface or notch SEMI T7 / M12 standard alphanumeric/2D code.
        substrate_description: Summary string of base substrate.
    """

    lot_id: str
    wafer_number: int
    laser_mark: str
    substrate_description: str = "Standard 300mm Monocrystalline Silicon"

    def __post_init__(self) -> None:
        if not (1 <= self.wafer_number <= 25):
            raise ValueError(f"wafer_number must be between 1 and 25, got {self.wafer_number}")
        if not self.lot_id.strip():
            raise ValueError("lot_id cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lot_id": self.lot_id,
            "wafer_number": self.wafer_number,
            "laser_mark": self.laser_mark,
            "substrate_description": self.substrate_description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WaferID:
        return cls(
            lot_id=str(data["lot_id"]),
            wafer_number=int(data["wafer_number"]),
            laser_mark=str(data["laser_mark"]),
            substrate_description=str(data.get("substrate_description", "")),
        )


@dataclass
class WaferSubstrate:
    """Physical substrate specifications compliant with SEMI M1.

    Includes explicit support for advanced Silicon-on-Insulator (SOI) wafers,
    specifically 22nm FD-SOI with Ultra-Thin Body (UTB) and Buried Oxide (BOX).

    Attributes:
        material: Base material (Si, SOI_FDSOI, etc.).
        orientation: Crystal plane orientation (<100>, <110>, <111>).
        diameter: Nominal wafer diameter (e.g. 300 mm).
        thickness: Bulk wafer thickness (e.g. 775 μm).
        resistivity: Bulk substrate resistivity in ohm*cm.
        dopant_type: Impurity dopant.
        dopant_concentration: Background doping concentration in cm^-3.
        notch_or_flat: Orientation fiducial ('NOTCH' for >=200mm, 'FLAT' for <=150mm).
        is_soi: Flag indicating whether substrate is SOI.
        box_thickness: Buried Oxide thickness (e.g., 20.0 nm for 22nm FD-SOI).
        device_layer_thickness: Ultra-thin top silicon film thickness (e.g. 6.0 nm for 22nm FD-SOI).
        box_material: Buried dielectric material (typically 'SiO2').
    """

    material: SubstrateMaterial = SubstrateMaterial.BULK_SILICON
    orientation: CrystalOrientation = CrystalOrientation.ORIENTATION_100
    diameter: PhysicalQuantity = field(default_factory=wafer_diameter)
    thickness: PhysicalQuantity = field(default_factory=wafer_thickness)
    resistivity: PhysicalQuantity = field(
        default_factory=lambda: PhysicalQuantity(
            value=10.0,
            unit="ohm*cm",
            valid_range=(0.0001, 100000.0),
            uncertainty=0.5,
            source="SEMI M1 Wafer Resistivity Spec",
        )
    )
    dopant_type: DopantType = DopantType.P_BORON
    dopant_concentration: PhysicalQuantity = field(
        default_factory=lambda: PhysicalQuantity(
            value=1.5e15,
            unit="count",
            valid_range=(1e11, 1e21),
            uncertainty=1e14,
            source="Substrate Crystal Growth Ingot Specification",
        )
    )
    notch_or_flat: str = "NOTCH"
    is_soi: bool = False
    box_thickness: Optional[PhysicalQuantity] = None
    device_layer_thickness: Optional[PhysicalQuantity] = None
    box_material: str = "SiO2"

    def __post_init__(self) -> None:
        if self.is_soi or self.material in (SubstrateMaterial.SOI_FDSOI, SubstrateMaterial.SOI_PDSOI):
            self.is_soi = True
            if self.box_thickness is None:
                # Default 20.0 nm Buried Oxide for 22nm FD-SOI
                self.box_thickness = PhysicalQuantity(
                    value=20.0,
                    unit="nm",
                    valid_range=(5.0, 500.0),
                    uncertainty=0.5,
                    source="22nm FD-SOI SmartCut™ Ingot Specification",
                )
            if self.device_layer_thickness is None:
                # Default 6.0 nm Ultra-Thin Body Silicon for 22nm FD-SOI
                self.device_layer_thickness = PhysicalQuantity(
                    value=6.0,
                    unit="nm",
                    valid_range=(2.0, 100.0),
                    uncertainty=0.2,
                    source="22nm FD-SOI Ultra-Thin Silicon Film Metrology",
                )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "material": self.material.value,
            "orientation": self.orientation.value,
            "diameter": self.diameter.to_dict(),
            "thickness": self.thickness.to_dict(),
            "resistivity": self.resistivity.to_dict(),
            "dopant_type": self.dopant_type.value,
            "dopant_concentration": self.dopant_concentration.to_dict(),
            "notch_or_flat": self.notch_or_flat,
            "is_soi": self.is_soi,
            "box_thickness": self.box_thickness.to_dict() if self.box_thickness else None,
            "device_layer_thickness": self.device_layer_thickness.to_dict() if self.device_layer_thickness else None,
            "box_material": self.box_material,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WaferSubstrate:
        box_th = PhysicalQuantity.from_dict(data["box_thickness"]) if data.get("box_thickness") else None
        dev_th = PhysicalQuantity.from_dict(data["device_layer_thickness"]) if data.get("device_layer_thickness") else None
        return cls(
            material=SubstrateMaterial(data["material"]),
            orientation=CrystalOrientation(data["orientation"]),
            diameter=PhysicalQuantity.from_dict(data["diameter"]),
            thickness=PhysicalQuantity.from_dict(data["thickness"]),
            resistivity=PhysicalQuantity.from_dict(data["resistivity"]),
            dopant_type=DopantType(data["dopant_type"]),
            dopant_concentration=PhysicalQuantity.from_dict(data["dopant_concentration"]),
            notch_or_flat=str(data.get("notch_or_flat", "NOTCH")),
            is_soi=bool(data.get("is_soi", False)),
            box_thickness=box_th,
            device_layer_thickness=dev_th,
            box_material=str(data.get("box_material", "SiO2")),
        )


@dataclass
class Layer:
    """Individual thin film deposited, grown, or coated on the wafer surface.

    Attributes:
        layer_id: Unique layer tracking string.
        name: Common fab name (e.g. 'Pad Oxide', 'HfO2 High-k Gate Dielectric').
        material: Chemical/material designation ('SiO2', 'Si3N4', 'HfO2', 'TiN', 'Cu').
        thickness: Physical thickness of the layer.
        deposition_method: Deposition/growth technique (ALD, PECVD, LPCVD, Thermal, Sputter, Spin).
        process_step_id: ID of the process route step that formed this layer.
        stress_mpa: Intrinsic film stress (+ tensile, - compressive).
        refractive_index: Optical refractive index n at 633 nm.
        extinction_coefficient: Optical extinction coefficient k at 633 nm.
        is_patterned: Whether this layer has undergone litho/etch patterning.
        pattern_cd: Critical dimension if patterned (nm).
    """

    layer_id: str
    name: str
    material: str
    thickness: PhysicalQuantity
    deposition_method: str = "ALD"
    process_step_id: str = "INIT_000"
    stress_mpa: PhysicalQuantity = field(
        default_factory=lambda: PhysicalQuantity(
            value=0.0,
            unit="MPa",
            valid_range=(-5000.0, 5000.0),
            uncertainty=10.0,
            source="Film Stress Metrology (FSM)",
        )
    )
    refractive_index: Optional[float] = 1.46  # Default SiO2
    extinction_coefficient: Optional[float] = 0.0
    is_patterned: bool = False
    pattern_cd: Optional[PhysicalQuantity] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "name": self.name,
            "material": self.material,
            "thickness": self.thickness.to_dict(),
            "deposition_method": self.deposition_method,
            "process_step_id": self.process_step_id,
            "stress_mpa": self.stress_mpa.to_dict(),
            "refractive_index": self.refractive_index,
            "extinction_coefficient": self.extinction_coefficient,
            "is_patterned": self.is_patterned,
            "pattern_cd": self.pattern_cd.to_dict() if self.pattern_cd else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Layer:
        cd = PhysicalQuantity.from_dict(data["pattern_cd"]) if data.get("pattern_cd") else None
        return cls(
            layer_id=str(data["layer_id"]),
            name=str(data["name"]),
            material=str(data["material"]),
            thickness=PhysicalQuantity.from_dict(data["thickness"]),
            deposition_method=str(data.get("deposition_method", "ALD")),
            process_step_id=str(data.get("process_step_id", "")),
            stress_mpa=PhysicalQuantity.from_dict(data["stress_mpa"]),
            refractive_index=data.get("refractive_index"),
            extinction_coefficient=data.get("extinction_coefficient"),
            is_patterned=bool(data.get("is_patterned", False)),
            pattern_cd=cd,
        )


@dataclass
class LayerStack:
    """Ordered stack of thin-film layers grown or deposited on the wafer substrate.

    Index 0 is the interface immediately contacting the substrate; the last
    element is the outermost front-side surface layer.
    """

    layers: List[Layer] = field(default_factory=list)

    def add_layer(self, layer: Layer) -> None:
        """Deposit or grow a new layer on top of the current stack."""
        self.layers.append(layer)

    def get_top_layer(self) -> Optional[Layer]:
        """Return the outermost surface layer, or None if stack is bare."""
        return self.layers[-1] if self.layers else None

    def remove_top_layer(self) -> Optional[Layer]:
        """Strip or lift-off the outermost layer (e.g. photoresist strip)."""
        return self.layers.pop() if self.layers else None

    def etch_top_layer(self, depth: PhysicalQuantity) -> Tuple[Optional[Layer], PhysicalQuantity]:
        """Etch into the top layer by a specified depth.

        Args:
            depth: Etch thickness to remove.

        Returns:
            Tuple of (remaining top layer or None, actual removed thickness).
        """
        if not self.layers:
            zero_th = PhysicalQuantity(0.0, "nm", (0.0, 1000.0), 0.0, "Etch Zero")
            return None, zero_th

        top = self.layers[-1]
        top_th_nm = top.thickness.to_unit("nm").value
        depth_nm = depth.to_unit("nm").value

        if depth_nm >= top_th_nm:
            # Entire layer etched through
            removed = self.layers.pop()
            return None, removed.thickness
        else:
            # Partial etch
            remaining_nm = top_th_nm - depth_nm
            new_th = film_thickness(remaining_nm, "nm", uncertainty=top.thickness.uncertainty)
            top.thickness = new_th
            removed_th = film_thickness(depth_nm, "nm", uncertainty=depth.uncertainty)
            return top, removed_th

    def find_layer(self, name_or_id: str) -> Optional[Layer]:
        """Search stack for a layer matching layer_id or name."""
        for layer in reversed(self.layers):
            if layer.layer_id == name_or_id or layer.name.lower() == name_or_id.lower():
                return layer
        return None

    def get_total_thickness(self) -> PhysicalQuantity:
        """Calculate cumulative thickness of all layers in the stack."""
        if not self.layers:
            return film_thickness(0.0, "nm", uncertainty=0.0)
        tot_nm = sum(layer.thickness.to_unit("nm").value for layer in self.layers)
        combined_unc = math.sqrt(sum(layer.thickness.to_unit("nm").uncertainty ** 2 for layer in self.layers))
        return PhysicalQuantity(
            value=tot_nm,
            unit="nm",
            valid_range=(0.0, 1e7),
            uncertainty=combined_unc,
            source="Cumulative Layer Stack Metrology",
        )

    def calculate_stoney_bow_change(
        self,
        substrate_thickness: PhysicalQuantity,
        wafer_radius: PhysicalQuantity,
    ) -> PhysicalQuantity:
        """Calculate wafer bow deflection induced by thin film stack using Stoney's Equation.

        Stoney's equation for circular wafer:
          delta_bow = 3 * (1 - nu_s) * R_w^2 * sum(sigma_f * t_f) / (E_s * t_s^2)
        For Si (100): Biaxial modulus E_s / (1 - nu_s) ≈ 180.5 GPa = 180,500 MPa.

        Args:
            substrate_thickness: Wafer thickness t_s (typically ~775 um).
            wafer_radius: Wafer radius R_w (e.g. 150 mm = 0.15 m).

        Returns:
            Calculated bow change in micrometers (um).
        """
        # Biaxial modulus for Si <100> in MPa
        biaxial_modulus_si_mpa = 180500.0

        ts_m = substrate_thickness.to_unit("m").value
        rw_m = wafer_radius.to_unit("m").value

        # Cumulative film force: sum(sigma_i * t_i) in MPa * m
        sum_sigma_t = 0.0
        for l in self.layers:
            sigma_mpa = l.stress_mpa.to_unit("MPa").value
            tf_m = l.thickness.to_unit("m").value
            sum_sigma_t += sigma_mpa * tf_m

        if ts_m <= 0.0:
            return PhysicalQuantity(0.0, "um", (-500.0, 500.0), 0.0, "Stoney Bow")

        # Stoney bow deflection in meters
        # delta_bow = (3.0 * rw_m^2 * sum_sigma_t) / (biaxial_modulus_si_mpa * ts_m^2)
        delta_bow_m = (3.0 * (rw_m ** 2) * sum_sigma_t) / (biaxial_modulus_si_mpa * (ts_m ** 2))
        delta_bow_um = delta_bow_m * 1e6

        return PhysicalQuantity(
            value=delta_bow_um,
            unit="um",
            valid_range=(-500.0, 500.0),
            uncertainty=abs(delta_bow_um * 0.05) + 0.1,
            source="Stoney Equation Film Stress Model",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"layers": [layer.to_dict() for layer in self.layers]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LayerStack:
        layers = [Layer.from_dict(l) for l in data.get("layers", [])]
        return cls(layers=layers)


@dataclass
class WaferState:
    """Dynamic operational and contamination state of the wafer.

    Tracks defect count, particles, geometric warpage/bow, metallic contamination,
    and process integrity flags.

    Attributes:
        particle_count: Detected particles >= 0.05 μm on front surface.
        defect_count: Pattern defects (shorts, opens, bridging, CD excursions).
        warpage: Wafer warpage across entire surface (peak-to-valley in μm).
        bow: Center-to-reference-plane displacement in μm (+ convex, - concave).
        total_thickness_variation: TTV (difference between max and min thickness in μm).
        stress: Global substrate residual stress in MPa.
        contamination_levels: Surface metallic contamination in atoms/cm^2 (e.g. Fe, Cu, Ni, Cr).
        temperature: Current wafer bulk temperature in degC.
        location: Current fab location (FOUP slot, loadlock, chuck ID).
        is_scrapped: Scrap status flag.
        scrap_reason: Explanation if scrapped.
    """

    particle_count: int = 0
    defect_count: int = 0
    warpage: PhysicalQuantity = field(
        default_factory=lambda: PhysicalQuantity(
            value=12.0,
            unit="um",
            valid_range=(0.0, 250.0),
            uncertainty=0.5,
            source="SEMI M1 Wafer Flatness Specification",
        )
    )
    bow: PhysicalQuantity = field(
        default_factory=lambda: PhysicalQuantity(
            value=2.0,
            unit="um",
            valid_range=(-150.0, 150.0),
            uncertainty=0.3,
            source="SEMI M1 Wafer Bow Spec",
        )
    )
    total_thickness_variation: PhysicalQuantity = field(
        default_factory=lambda: PhysicalQuantity(
            value=1.5,
            unit="um",
            valid_range=(0.0, 50.0),
            uncertainty=0.1,
            source="SEMI M1 TTV Specification",
        )
    )
    stress: PhysicalQuantity = field(
        default_factory=lambda: PhysicalQuantity(
            value=0.0,
            unit="MPa",
            valid_range=(-1000.0, 1000.0),
            uncertainty=2.0,
            source="Wafer Substrate Stress Sensor",
        )
    )
    contamination_levels: Dict[str, PhysicalQuantity] = field(default_factory=dict)
    temperature: PhysicalQuantity = field(default_factory=lambda: temperature(25.0, "degC"))
    location: str = "FOUP_01_SLOT_01"
    is_scrapped: bool = False
    scrap_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.contamination_levels:
            # Default baseline cleanroom levels (< 1e10 atoms/cm^2 per ITRS guidelines)
            self.contamination_levels = {
                "Fe": PhysicalQuantity(1e9, "ions/cm^2", (0.0, 1e14), 1e8, "TXRF Surface Metal Spec"),
                "Cu": PhysicalQuantity(5e8, "ions/cm^2", (0.0, 1e14), 5e7, "TXRF Surface Metal Spec"),
                "Ni": PhysicalQuantity(2e8, "ions/cm^2", (0.0, 1e14), 2e7, "TXRF Surface Metal Spec"),
                "Na": PhysicalQuantity(5e9, "ions/cm^2", (0.0, 1e14), 5e8, "TXRF Surface Metal Spec"),
            }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "particle_count": self.particle_count,
            "defect_count": self.defect_count,
            "warpage": self.warpage.to_dict(),
            "bow": self.bow.to_dict(),
            "total_thickness_variation": self.total_thickness_variation.to_dict(),
            "stress": self.stress.to_dict(),
            "contamination_levels": {k: v.to_dict() for k, v in self.contamination_levels.items()},
            "temperature": self.temperature.to_dict(),
            "location": self.location,
            "is_scrapped": self.is_scrapped,
            "scrap_reason": self.scrap_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WaferState:
        contam = {k: PhysicalQuantity.from_dict(v) for k, v in data.get("contamination_levels", {}).items()}
        return cls(
            particle_count=int(data["particle_count"]),
            defect_count=int(data["defect_count"]),
            warpage=PhysicalQuantity.from_dict(data["warpage"]),
            bow=PhysicalQuantity.from_dict(data["bow"]),
            total_thickness_variation=PhysicalQuantity.from_dict(data["total_thickness_variation"]),
            stress=PhysicalQuantity.from_dict(data["stress"]),
            contamination_levels=contam,
            temperature=PhysicalQuantity.from_dict(data["temperature"]),
            location=str(data.get("location", "FOUP")),
            is_scrapped=bool(data.get("is_scrapped", False)),
            scrap_reason=data.get("scrap_reason"),
        )


@dataclass(frozen=True)
class ProcessStepRecord:
    """Historical record of an individual process operation performed on the wafer."""
    step_number: int
    step_id: str
    equipment_id: str
    recipe_id: str
    start_time: float
    end_time: float
    status: str  # "SUCCESS", "ABORTED", "EXCURSION"
    parameters_recorded: Dict[str, PhysicalQuantity] = field(default_factory=dict)
    operator_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "step_id": self.step_id,
            "equipment_id": self.equipment_id,
            "recipe_id": self.recipe_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "parameters_recorded": {k: v.to_dict() for k, v in self.parameters_recorded.items()},
            "operator_notes": self.operator_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProcessStepRecord:
        params = {k: PhysicalQuantity.from_dict(v) for k, v in data.get("parameters_recorded", {}).items()}
        return cls(
            step_number=int(data["step_number"]),
            step_id=str(data["step_id"]),
            equipment_id=str(data["equipment_id"]),
            recipe_id=str(data["recipe_id"]),
            start_time=float(data["start_time"]),
            end_time=float(data["end_time"]),
            status=str(data["status"]),
            parameters_recorded=params,
            operator_notes=str(data.get("operator_notes", "")),
        )


@dataclass
class ProcessHistory:
    """Chronological execution trace of all process operations executed on the wafer."""
    steps: List[ProcessStepRecord] = field(default_factory=list)

    def record_step(self, record: ProcessStepRecord) -> None:
        """Append an executed process step record."""
        self.steps.append(record)

    def get_records_by_equipment(self, equipment_id: str) -> List[ProcessStepRecord]:
        """Filter execution records for a specific tool."""
        return [s for s in self.steps if s.equipment_id == equipment_id]

    def has_excursions(self) -> bool:
        """Check if any step resulted in an abort or process excursion."""
        return any(s.status in ("ABORTED", "EXCURSION") for s in self.steps)

    def to_dict(self) -> Dict[str, Any]:
        return {"steps": [s.to_dict() for s in self.steps]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProcessHistory:
        return cls(steps=[ProcessStepRecord.from_dict(s) for s in data.get("steps", [])])


@dataclass
class MetrologyRecord:
    """In-line metrology measurement taken at a process checkpoint."""
    timestamp: float
    step_id: str
    metrology_type: MetrologyType
    parameter_name: str
    mean_value: PhysicalQuantity
    uniformity_percentage: PhysicalQuantity
    pass_spec: bool
    spec_limits: Tuple[PhysicalQuantity, PhysicalQuantity]
    site_measurements: List[PhysicalQuantity] = field(default_factory=list)
    inspector_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "step_id": self.step_id,
            "metrology_type": self.metrology_type.value,
            "parameter_name": self.parameter_name,
            "mean_value": self.mean_value.to_dict(),
            "uniformity_percentage": self.uniformity_percentage.to_dict(),
            "pass_spec": self.pass_spec,
            "spec_limits": [self.spec_limits[0].to_dict(), self.spec_limits[1].to_dict()],
            "site_measurements": [m.to_dict() for m in self.site_measurements],
            "inspector_notes": self.inspector_notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MetrologyRecord:
        lims = (
            PhysicalQuantity.from_dict(data["spec_limits"][0]),
            PhysicalQuantity.from_dict(data["spec_limits"][1]),
        )
        sites = [PhysicalQuantity.from_dict(m) for m in data.get("site_measurements", [])]
        return cls(
            timestamp=float(data["timestamp"]),
            step_id=str(data["step_id"]),
            metrology_type=MetrologyType(data["metrology_type"]),
            parameter_name=str(data["parameter_name"]),
            mean_value=PhysicalQuantity.from_dict(data["mean_value"]),
            uniformity_percentage=PhysicalQuantity.from_dict(data["uniformity_percentage"]),
            pass_spec=bool(data["pass_spec"]),
            spec_limits=lims,
            site_measurements=sites,
            inspector_notes=str(data.get("inspector_notes", "")),
        )


@dataclass
class MetrologyResults:
    """Collection of all metrology measurements taken on this wafer."""
    records: List[MetrologyRecord] = field(default_factory=list)

    def add_record(self, record: MetrologyRecord) -> None:
        self.records.append(record)

    def get_latest_measurement(self, parameter_name: str) -> Optional[MetrologyRecord]:
        for rec in reversed(self.records):
            if rec.parameter_name.lower() == parameter_name.lower():
                return rec
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {"records": [r.to_dict() for r in self.records]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MetrologyResults:
        return cls(records=[MetrologyRecord.from_dict(r) for r in data.get("records", [])])


class Wafer:
    """Complete digital twin model of a semiconductor wafer.

    Aggregates identity, substrate physics (including SOI properties),
    thin-film layer stack, operational/defect state, process history,
    and metrology data.
    """

    def __init__(
        self,
        wafer_id: WaferID,
        substrate: Optional[WaferSubstrate] = None,
        layer_stack: Optional[LayerStack] = None,
        state: Optional[WaferState] = None,
        history: Optional[ProcessHistory] = None,
        metrology: Optional[MetrologyResults] = None,
    ) -> None:
        self.wafer_id = wafer_id
        self.substrate = substrate if substrate is not None else WaferSubstrate()
        self.layer_stack = layer_stack if layer_stack is not None else LayerStack()
        self.state = state if state is not None else WaferState()
        self.history = history if history is not None else ProcessHistory()
        self.metrology = metrology if metrology is not None else MetrologyResults()

    def mark_scrapped(self, reason: str) -> None:
        """Mark the wafer as scrapped due to catastrophic defect or excursion."""
        self.state.is_scrapped = True
        self.state.scrap_reason = reason

    def update_stress_and_bow(self) -> None:
        """Recompute wafer bow change caused by film stack via Stoney equation."""
        radius = self.substrate.diameter / 2.0
        bow_change = self.layer_stack.calculate_stoney_bow_change(
            substrate_thickness=self.substrate.thickness,
            wafer_radius=radius,
        )
        # Update state bow
        base_bow_um = 2.0
        new_bow_um = base_bow_um + bow_change.to_unit("um").value
        self.state.bow = PhysicalQuantity(
            value=new_bow_um,
            unit="um",
            valid_range=(-150.0, 150.0),
            uncertainty=bow_change.uncertainty,
            source="Stoney Equation Wafer Bow Calculation",
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize full wafer digital twin to dictionary."""
        return {
            "wafer_id": self.wafer_id.to_dict(),
            "substrate": self.substrate.to_dict(),
            "layer_stack": self.layer_stack.to_dict(),
            "state": self.state.to_dict(),
            "history": self.history.to_dict(),
            "metrology": self.metrology.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Wafer:
        """Reconstruct Wafer digital twin from serialized dictionary."""
        return cls(
            wafer_id=WaferID.from_dict(data["wafer_id"]),
            substrate=WaferSubstrate.from_dict(data["substrate"]),
            layer_stack=LayerStack.from_dict(data["layer_stack"]),
            state=WaferState.from_dict(data["state"]),
            history=ProcessHistory.from_dict(data["history"]),
            metrology=MetrologyResults.from_dict(data["metrology"]),
        )

    @classmethod
    def create_22nm_fdsoi_wafer(
        cls,
        lot_id: str,
        wafer_number: int,
        laser_mark: Optional[str] = None,
    ) -> Wafer:
        """Factory method: Initialize an ultra-thin body 22nm FD-SOI wafer.

        Substrate incorporates:
          - 300 mm diameter
          - 775 um bulk silicon support substrate
          - 20.0 nm Buried Oxide (BOX) SiO2 layer
          - 6.0 nm top Ultra-Thin Body (UTB) monocrystalline silicon device layer
        """
        mark = laser_mark or f"{lot_id}-W{wafer_number:02d}-FDSOI22"
        wid = WaferID(
            lot_id=lot_id,
            wafer_number=wafer_number,
            laser_mark=mark,
            substrate_description="300mm SmartCut™ 22nm FD-SOI Wafer (20nm BOX / 6nm UTB Si)",
        )
        sub = WaferSubstrate(
            material=SubstrateMaterial.SOI_FDSOI,
            orientation=CrystalOrientation.ORIENTATION_100,
            diameter=wafer_diameter(300.0, 0.2),
            thickness=wafer_thickness(775.0, 15.0),
            is_soi=True,
            box_thickness=PhysicalQuantity(
                value=20.0,
                unit="nm",
                valid_range=(10.0, 50.0),
                uncertainty=0.5,
                source="SEMI M1 / 22FDX Substrate Specification (20nm BOX)",
            ),
            device_layer_thickness=PhysicalQuantity(
                value=6.0,
                unit="nm",
                valid_range=(4.0, 15.0),
                uncertainty=0.2,
                source="22FDX Ultra-Thin Body Device Layer Spec (6nm Top Si)",
            ),
            box_material="SiO2",
        )
        return cls(wafer_id=wid, substrate=sub)

    def __repr__(self) -> str:
        return (
            f"Wafer(lot={self.wafer_id.lot_id!r}, "
            f"num={self.wafer_id.wafer_number}, "
            f"material={self.substrate.material.value}, "
            f"layers={len(self.layer_stack.layers)}, "
            f"loc={self.state.location!r})"
        )

    def __str__(self) -> str:
        soi_tag = " [SOI]" if self.substrate.is_soi else ""
        return (
            f"Wafer #{self.wafer_id.wafer_number} ({self.wafer_id.lot_id}){soi_tag} "
            f"at {self.state.location} | Layers: {len(self.layer_stack.layers)} | "
            f"Defects: {self.state.defect_count} | Scrapped: {self.state.is_scrapped}"
        )
