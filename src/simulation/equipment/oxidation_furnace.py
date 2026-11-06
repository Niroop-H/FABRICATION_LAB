"""Thermal Oxidation Furnace Simulation Engine.

Standards Compliance:
  - SEMI E10: Equipment Reliability, Availability, and Maintainability
  - SEMI E30: Generic Model for Communications and Control (GEM)
  - SEMI S2: Environmental, Health, and Safety Guideline for Semiconductor Equipment
  - SEMI M1: Specifications for Polished Single Crystal Silicon Wafers

Physics Models:
  - Deal-Grove Model for Thermal Oxidation of Silicon
  - Arrhenius temperature dependence for linear (B/A) and parabolic (B) rate constants
  - Substrate crystal orientation dependence: Si(100) vs Si(111)
  - Ambient comparison: Dry O2 vs Pyrogenic Wet Steam (H2O)
  - Massoud thin oxide growth enhancement regime (< 25 nm)
  - Chlorinated oxidation (HCl/Trans-LC addition) for mobile ion gettering
  - Multi-zone temperature control (5-zone horizontal/vertical atmospheric tube)
  - Wafer boat thermal stress and load/unload slip dislocation management
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.simulation.core.units import (
    PhysicalQuantity,
    pressure,
    temperature,
    gas_flow,
    duration,
)
from src.simulation.equipment.base_equipment import (
    Alarm,
    AlarmSeverity,
    BaseEquipment,
    ChamberState,
    GEMControlState,
    GEMProcessingState,
    ProcessChamber,
    SafetyInterlock,
    Wafer,
)

logger = logging.getLogger(__name__)


class FurnaceOrientation(str, Enum):
    """Furnace mechanical configuration."""
    HORIZONTAL = "HORIZONTAL"
    VERTICAL = "VERTICAL"


class SiliconOrientation(str, Enum):
    """Substrate silicon crystal orientation."""
    SI_100 = "100"
    SI_111 = "111"


class OxidationAmbience(str, Enum):
    """Oxidizing process gas atmosphere."""
    DRY_O2 = "DRY_O2"
    WET_STEAM = "WET_STEAM"  # Pyrogenic H2 + O2 combustion
    DILUTE_O2 = "DILUTE_O2"  # O2 in N2/Ar
    CHLORINATED_O2 = "CHLORINATED_O2"  # O2 + HCl / Trans-LC


class FurnaceSequencerState(str, Enum):
    """Furnace operational sequence states."""
    STANDBY = "STANDBY"
    LOAD = "LOAD"
    RAMP_UP = "RAMP_UP"
    STABILIZE = "STABILIZE"
    PROCESS = "PROCESS"
    RAMP_DOWN = "RAMP_DOWN"
    UNLOAD = "UNLOAD"


@dataclass
class FurnaceZone:
    """Individual thermal heating zone within a multi-zone furnace tube.

    Attributes:
        zone_index: Zero-indexed position (0=Door/Load, 2=Center, 4=Source/Gas In).
        name: Zone designation.
        target_temperature_c: Commanded setpoint (°C) [600.0 to 1200.0 °C].
        current_temperature_c: Actual measured thermocouple reading (°C).
        heater_power_pct: Current SCR heater power duty cycle [0.0 to 100.0 %].
    """

    zone_index: int
    name: str
    target_temperature_c: float = 650.0
    current_temperature_c: float = 650.0
    heater_power_pct: float = 25.0


@dataclass
class OxidationStep:
    """Recipe Step for Thermal Oxidation Furnace.

    Attributes:
        step_name: Descriptive step label.
        ambience: DRY_O2, WET_STEAM, DILUTE_O2, or CHLORINATED_O2.
        duration_s: Step duration in seconds.
        temperature_c: Target process temperature (°C) [600.0 to 1200.0 °C].
        h2_flow_slm: Hydrogen flow for pyrogenic wet torch (SLM).
        o2_flow_slm: Oxygen flow (SLM).
        n2_flow_slm: Nitrogen carrier/purge flow (SLM).
        hcl_flow_sccm: Hydrochloric acid / DCE additive for mobile ion gettering (sccm).
        ramp_rate_c_min: Heating/cooling ramp rate (°C/min) [1.0 to 15.0 °C/min].
    """

    step_name: str
    ambience: OxidationAmbience = OxidationAmbience.DRY_O2
    duration_s: float = 1800.0  # 30 min
    temperature_c: float = 1000.0
    h2_flow_slm: float = 0.0
    o2_flow_slm: float = 10.0
    n2_flow_slm: float = 0.0
    hcl_flow_sccm: float = 0.0  # Typically 1-3% of total oxidant flow
    ramp_rate_c_min: float = 10.0

    def validate(self) -> None:
        """Validate step parameters against physical limits."""
        duration(self.duration_s, "s", (1.0, 86400.0), 0.1, "Oxidation Recipe Step")
        temperature(self.temperature_c, "degC", (600.0, 1250.0), 0.1, "Furnace Zone Controller")

        if self.ambience == OxidationAmbience.WET_STEAM:
            # Combustion safety: H2/O2 ratio must never exceed stoichiometric 2.0 (strictly <= 1.8)
            if self.o2_flow_slm <= 0.0:
                raise ValueError("Pyrogenic torch requires O2 flow > 0.")
            ratio = self.h2_flow_slm / self.o2_flow_slm
            if ratio > 1.8:
                raise ValueError(
                    f"Hazardous pyrogenic gas ratio H2/O2 = {ratio:.2f}. "
                    f"Must not exceed 1.80 to avoid explosive hydrogen accumulation."
                )


@dataclass
class OxidationRecipe:
    """Complete multi-step thermal oxidation recipe."""
    recipe_name: str
    recipe_id: str
    silicon_orientation: SiliconOrientation = SiliconOrientation.SI_100
    steps: List[OxidationStep] = field(default_factory=list)

    def add_step(self, step: OxidationStep) -> None:
        """Validate and append an oxidation step."""
        step.validate()
        self.steps.append(step)


@dataclass
class OxidationResult:
    """Results and metrology for an oxidation run."""
    recipe_id: str
    wafer_id: str
    total_duration_s: float
    silicon_orientation: str
    initial_oxide_thickness_nm: float
    final_oxide_thickness_nm: float
    oxide_grown_nm: float
    linear_rate_B_over_A_nm_hr: float
    parabolic_rate_B_nm2_hr: float
    mobile_ion_density_cm2: float  # Sodium / Potassium ionic contamination (Na+)
    fixed_charge_density_cm2: float  # Fixed oxide charge Qf
    interface_trap_density_cm2_ev: float  # Interface state density Dit
    slip_dislocations_detected: bool
    temperature_uniformity_3sigma_c: float


class OxidationFurnace(BaseEquipment):
    """High-Purity Silicon Thermal Oxidation Furnace Simulation Engine.

    Simulates a Tokyo Electron (TEL) Alpha-8SE or ASM A400 vertical atmospheric
    quartz tube oxidation furnace.
    """

    def __init__(
        self,
        equipment_id: str = "FURN_OX_01",
        manufacturer: str = "Tokyo Electron",
        model: str = "TEL Alpha-8SE Vertical Furnace",
        orientation: FurnaceOrientation = FurnaceOrientation.VERTICAL,
        boat_capacity: int = 100,
        initial_time: Optional[float] = None,
    ) -> None:
        """Initialize thermal oxidation furnace."""
        super().__init__(
            equipment_id=equipment_id,
            equipment_type="OXIDATION_FURNACE",
            manufacturer=manufacturer,
            model=model,
            supported_wafer_diameters=[200, 300],
            initial_time=initial_time,
        )

        self.orientation = orientation
        self.boat_capacity = boat_capacity
        self.sequencer_state = FurnaceSequencerState.STANDBY

        # Process Tube (Atmospheric quartz or SiC process tube)
        self.tube_chamber = ProcessChamber(
            chamber_id="TUBE_01",
            name="Quartz Process Tube (Atmospheric)",
            volume_liters=120.0,
            base_pressure_torr=760.0,
            current_pressure_torr=760.0,
            current_temperature_c=650.0,  # Standby idling temp
            state=ChamberState.ATMOSPHERIC,
        )
        self.add_chamber(self.tube_chamber)

        # 5 Thermal Heating Zones: Load, Bottom-Center, Center, Top-Center, Top
        self.zones: List[FurnaceZone] = [
            FurnaceZone(zone_index=0, name="Zone 1 - Load/Door", target_temperature_c=650.0, current_temperature_c=650.0),
            FurnaceZone(zone_index=1, name="Zone 2 - Bottom-Center", target_temperature_c=650.0, current_temperature_c=650.0),
            FurnaceZone(zone_index=2, name="Zone 3 - Center", target_temperature_c=650.0, current_temperature_c=650.0),
            FurnaceZone(zone_index=3, name="Zone 4 - Top-Center", target_temperature_c=650.0, current_temperature_c=650.0),
            FurnaceZone(zone_index=4, name="Zone 5 - Gas Source", target_temperature_c=650.0, current_temperature_c=650.0),
        ]

        # Wafer boat elevator
        self.boat_load_speed_mm_min = 100.0  # Safe range: 50 - 200 mm/min
        self.wafers_in_boat: List[Wafer] = []

        # Pyrogenic Torch State
        self.pyrogenic_torch_ignited = False
        self.pyrogenic_flame_sensor_mv = 0.0  # > 400 mV indicates confirmed UV flame

        # Dedicated Safety Interlocks
        self.add_interlock(
            interlock_id="INTLK_DOOR_SEAL",
            name="Furnace Flange Quartz Door Seal",
            description="Confirms quartz bottom/front door is clamped and sealed hermetically",
            auto_reset=False,
        )
        self.add_interlock(
            interlock_id="INTLK_PYRO_FLAME",
            name="Pyrogenic Torch UV Flame Detector",
            description="UV optical detector verifies flame combustion before hydrogen is admitted",
            auto_reset=False,
        )
        self.add_interlock(
            interlock_id="INTLK_OVER_TEMP",
            name="Furnace Overtemperature Trip Switch",
            description="Independent analog thermocouple trips if any zone exceeds 1250°C",
            auto_reset=False,
        )
        self.add_interlock(
            interlock_id="INTLK_H2_O2_RATIO",
            name="Pyrogenic Gas Ratio Interlock",
            description="Hardware mass flow interlock trips if H2:O2 flow ratio > 1.80",
            auto_reset=True,
        )

        # Specialized Maintenance Counters
        self.add_maintenance_counter(
            name="quartz_tube_operating_hours",
            limit=4000.0,
            unit="hr",
            pm_action="Quartz tube devitrification inspection and HF etch clean",
        )
        self.add_maintenance_counter(
            name="thermocouple_cal_cycles",
            limit=250.0,
            unit="count",
            pm_action="Multi-zone profile thermocouple calibration check",
        )

    # -------------------------------------------------------------------------
    # Physical Oxidation Kinetics (Deal-Grove Model)
    # -------------------------------------------------------------------------

    def calculate_deal_grove_parameters(
        self,
        temperature_c: float,
        ambience: OxidationAmbience,
        orientation: SiliconOrientation,
        hcl_pct: float = 0.0,
    ) -> Tuple[float, float]:
        """Compute Deal-Grove linear (B/A) and parabolic (B) rate constants.

        Arrhenius Relations:
          B = B0 * exp(-E_B / (k_B * T))  [um^2 / hr]
          B/A = (B/A)0 * exp(-E_BA / (k_B * T))  [um / hr]

        Values referenced from:
          - B.E. Deal and A.S. Grove, J. Appl. Phys. 36, 3770 (1965).
          - Plummer, Deal, Griffin, 'Silicon VLSI Technology', Ch. 6.

        Args:
            temperature_c: Temperature in Celsius (600 - 1200 °C).
            ambience: Oxidizing gas species.
            orientation: Si(100) or Si(111).
            hcl_pct: Percentage of HCl additive (0.0 to 5.0 %).

        Returns:
            Tuple of (B_nm2_s: float, B_over_A_nm_s: float).
        """
        temp_k = temperature_c + 273.15
        k_b = 8.617333262145e-5  # Boltzmann constant in eV / K

        # Base rate constants in um^2/hr and um/hr
        if ambience in (OxidationAmbience.WET_STEAM,):
            # Wet Steam (H2O)
            # Parabolic rate constant B (diffusion-limited)
            b_0 = 2.14e2  # um^2 / hr
            e_b = 0.71  # eV (water diffuses faster with lower activation energy)
            b_um2_hr = b_0 * math.exp(-e_b / (k_b * temp_k))

            # Linear rate constant B/A (surface-reaction limited on Si 100)
            ba_0 = 8.95e7  # um / hr
            e_ba = 2.05  # eV
            ba_um_hr = ba_0 * math.exp(-e_ba / (k_b * temp_k))
        else:
            # Dry O2
            # Parabolic rate constant B
            b_0 = 7.72e2  # um^2 / hr
            e_b = 1.24  # eV
            b_um2_hr = b_0 * math.exp(-e_b / (k_b * temp_k))

            # Linear rate constant B/A on Si 100
            ba_0 = 6.23e6  # um / hr
            e_ba = 2.00  # eV
            ba_um_hr = ba_0 * math.exp(-e_ba / (k_b * temp_k))

            # Dilute O2 scaling
            if ambience == OxidationAmbience.DILUTE_O2:
                # Partial pressure of O2 reduces B linearly, B/A as P_O2^0.7
                b_um2_hr *= 0.10
                ba_um_hr *= 0.20

        # Substrate Orientation Effect
        # Linear rate constant depends on available surface silicon bonds:
        # Si(111) has higher surface atom density (1.18e15 cm^-2 vs 6.78e14 cm^-2 for 100)
        # Empirical ratio: (B/A)_111 / (B/A)_100 = 1.68
        if orientation == SiliconOrientation.SI_111:
            ba_um_hr *= 1.68

        # Chlorinated Oxidation Enhancement (HCl addition)
        if hcl_pct > 0.0:
            cl_factor_b = 1.0 + 0.12 * hcl_pct
            cl_factor_ba = 1.0 + 0.15 * hcl_pct
            b_um2_hr *= cl_factor_b
            ba_um_hr *= cl_factor_ba

        # Convert units to nm^2 / s and nm / s
        # 1 um = 1000 nm; 1 hr = 3600 s
        # 1 um^2 / hr = 1e6 nm^2 / 3600 s = (1e6 / 3600) nm^2 / s
        b_nm2_s = b_um2_hr * (1e6 / 3600.0)
        ba_nm_s = ba_um_hr * (1000.0 / 3600.0)

        return (b_nm2_s, ba_nm_s)

    def calculate_grown_thickness(
        self,
        initial_thickness_nm: float,
        duration_s: float,
        temperature_c: float,
        ambience: OxidationAmbience,
        orientation: SiliconOrientation,
        hcl_pct: float = 0.0,
    ) -> Tuple[float, float, float]:
        """Compute final oxide thickness using Deal-Grove with Massoud correction.

        Returns:
            Tuple of (final_thickness_nm, B_nm2_hr, B_over_A_nm_hr).
        """
        b_nm2_s, ba_nm_s = self.calculate_deal_grove_parameters(
            temperature_c=temperature_c,
            ambience=ambience,
            orientation=orientation,
            hcl_pct=hcl_pct,
        )

        # Deal-Grove constant A = B / (B/A) in nm
        a_nm = b_nm2_s / ba_nm_s

        # Tau calculation for pre-existing initial oxide:
        # tau = (x_i^2 + A * x_i) / B
        x_i = max(0.1, initial_thickness_nm)
        tau_s = (x_i**2 + a_nm * x_i) / b_nm2_s

        # Deal-Grove closed form solution:
        # x(t) = (-A + sqrt(A^2 + 4 * B * (t + tau))) / 2
        total_effective_time_s = duration_s + tau_s
        discriminant = a_nm**2 + 4.0 * b_nm2_s * total_effective_time_s
        x_dg = (-a_nm + math.sqrt(discriminant)) / 2.0

        # Massoud thin oxide enhancement for dry O2 when thickness < 25 nm
        x_final = x_dg
        if ambience in (OxidationAmbience.DRY_O2, OxidationAmbience.CHLORINATED_O2) and x_final < 25.0:
            temp_k = temperature_c + 273.15
            k_b = 8.617333262145e-5
            # Enhancement term: C0 * exp(-x / L0) where L0 ~ 1.2 nm
            c0_nm_s = (4.0e6 * math.exp(-2.37 / (k_b * temp_k))) * (1000.0 / 3600.0)
            massoud_extra_nm = c0_nm_s * 1.2 * (1.0 - math.exp(-duration_s / 300.0))
            x_final += massoud_extra_nm

        b_nm2_hr = b_nm2_s * 3600.0
        ba_nm_hr = ba_nm_s * 3600.0
        return (x_final, b_nm2_hr, ba_nm_hr)

    # -------------------------------------------------------------------------
    # Equipment Lifecycle Implementation
    # -------------------------------------------------------------------------

    def initialize(self) -> bool:
        """Initialize furnace heaters, verify door seals and interlocks."""
        logger.info("[%s] Initializing Oxidation Furnace...", self.equipment_id)

        self.reset_interlock("INTLK_DOOR_SEAL", force=True)
        self.reset_interlock("INTLK_OVER_TEMP", force=True)
        self.reset_interlock("INTLK_H2_O2_RATIO", force=True)
        self.reset_interlock("INTLK_EXHAUST", force=True)
        self.reset_interlock("INTLK_EMO", force=True)

        healthy, issues = self.check_interlocks()
        if not healthy:
            logger.error("[%s] Furnace initialization blocked by interlocks: %s", self.equipment_id, issues)
            return False

        # Set all zones to standby idling temperature (650°C)
        for zone in self.zones:
            zone.target_temperature_c = 650.0
            zone.current_temperature_c = 650.0
            zone.heater_power_pct = 22.0

        self.set_gem_control_state(GEMControlState.ONLINE_REMOTE)
        self.set_gem_processing_state(GEMProcessingState.IDLE)
        self.sequencer_state = FurnaceSequencerState.STANDBY
        logger.info("[%s] Furnace initialized in STANDBY at 650°C idling.", self.equipment_id)
        return True

    def process_wafer(self, wafer: Wafer, recipe: OxidationRecipe) -> OxidationResult:
        """Execute full furnace sequence: LOAD -> RAMP -> PROCESS -> COOL -> UNLOAD."""
        logger.info("[%s] Starting Oxidation Recipe '%s' for Wafer '%s'...", self.equipment_id, recipe.recipe_name, wafer.wafer_id)

        # Check interlocks
        healthy, issues = self.check_interlocks()
        if not healthy:
            raise RuntimeError(f"Furnace operation blocked by interlocks: {issues}")

        try:
            self.state_machine.trigger("START_RUN", timestamp=self.sim_time, payload={"wafer_id": wafer.wafer_id})
        except Exception:
            pass
        self.set_gem_processing_state(GEMProcessingState.EXECUTING)

        # Initial native or preexisting oxide thickness
        initial_thickness_nm = 1.8  # Standard native oxide
        top_layer = wafer.get_top_layer()
        if top_layer and top_layer.get("material") == "SiO2":
            initial_thickness_nm = top_layer.get("thickness_nm", 1.8)

        total_elapsed_s = 0.0
        current_th_nm = initial_thickness_nm

        # 1. LOAD WAFER BOAT
        self.sequencer_state = FurnaceSequencerState.LOAD
        # Check boat load speed to prevent thermal shock / slip dislocations
        slip_dislocations = False
        if self.boat_load_speed_mm_min > 200.0:
            slip_dislocations = True
            logger.warning("[%s] Excessive boat insertion speed (%.1f mm/min) induced thermal slip dislocations!",
                           self.equipment_id, self.boat_load_speed_mm_min)
        load_time_s = (1000.0 / self.boat_load_speed_mm_min) * 60.0  # 1-meter travel
        total_elapsed_s += load_time_s

        last_b = 0.0
        last_ba = 0.0
        hcl_used_pct = 0.0

        for step_idx, step in enumerate(recipe.steps):
            logger.info("[%s] Executing Furnace Step %d: %s (%s at %.0f°C)",
                        self.equipment_id, step_idx + 1, step.step_name, step.ambience.value, step.temperature_c)

            # 2. RAMP UP / STABILIZE
            target_temp = step.temperature_c
            current_temp = self.zones[2].current_temperature_c
            temp_delta = target_temp - current_temp

            if abs(temp_delta) > 5.0:
                self.sequencer_state = FurnaceSequencerState.RAMP_UP if temp_delta > 0 else FurnaceSequencerState.RAMP_DOWN
                ramp_rate = max(1.0, step.ramp_rate_c_min)
                ramp_time_min = abs(temp_delta) / ramp_rate
                ramp_time_s = ramp_time_min * 60.0
                total_elapsed_s += ramp_time_s

                # Update zone temperatures
                for zone in self.zones:
                    zone.target_temperature_c = target_temp
                    zone.current_temperature_c = target_temp

            # 3. STABILIZE
            self.sequencer_state = FurnaceSequencerState.STABILIZE
            total_elapsed_s += 600.0  # 10 min stabilization

            # 4. PROCESS STEP
            self.sequencer_state = FurnaceSequencerState.PROCESS

            # Pyrogenic torch ignition for wet steam
            if step.ambience == OxidationAmbience.WET_STEAM:
                self.pyrogenic_torch_ignited = True
                self.pyrogenic_flame_sensor_mv = 850.0  # Flame confirmed
            else:
                self.pyrogenic_torch_ignited = False
                self.pyrogenic_flame_sensor_mv = 0.0

            # HCl concentration calculation
            total_gas_slm = step.o2_flow_slm + step.n2_flow_slm + (step.h2_flow_slm * 0.5)
            hcl_pct = (step.hcl_flow_sccm / (total_gas_slm * 1000.0 + 1e-6)) * 100.0
            if hcl_pct > 0.0:
                hcl_used_pct = max(hcl_used_pct, hcl_pct)

            # Deal-Grove growth
            new_th, b_val, ba_val = self.calculate_grown_thickness(
                initial_thickness_nm=current_th_nm,
                duration_s=step.duration_s,
                temperature_c=step.temperature_c,
                ambience=step.ambience,
                orientation=recipe.silicon_orientation,
                hcl_pct=hcl_pct,
            )
            current_th_nm = new_th
            last_b = b_val
            last_ba = ba_val
            total_elapsed_s += step.duration_s

            # Tube hours wear
            self._maintenance_counters["quartz_tube_operating_hours"].increment(step.duration_s / 3600.0)

        # 5. RAMP DOWN TO STANDBY IDLE (650°C)
        self.sequencer_state = FurnaceSequencerState.RAMP_DOWN
        ramp_down_time_s = ((self.zones[2].current_temperature_c - 650.0) / 3.0) * 60.0
        total_elapsed_s += max(0.0, ramp_down_time_s)
        for zone in self.zones:
            zone.current_temperature_c = 650.0
            zone.target_temperature_c = 650.0

        # 6. UNLOAD WAFER BOAT
        self.sequencer_state = FurnaceSequencerState.UNLOAD
        total_elapsed_s += load_time_s

        # Contamination & Electrical Charges:
        # Chlorinated oxidation getters alkali ions (Na+) exponentially:
        base_na_density = 5.0e10  # cm^-2 without HCl
        if hcl_used_pct > 0.0:
            na_density = base_na_density * math.exp(-0.85 * hcl_used_pct)
        else:
            na_density = base_na_density

        # Fixed oxide charge Qf: depends on final oxidation temp and orientation
        # Deal triangle: (100) has lowest fixed charge ~1e10 to 3e10 cm^-2; (111) is ~1e11 cm^-2
        qf_base = 2.0e10 if recipe.silicon_orientation == SiliconOrientation.SI_100 else 9.5e10
        dit_base = 1.0e10 if recipe.silicon_orientation == SiliconOrientation.SI_100 else 4.0e10

        # Update Wafer Film Stack
        oxide_grown_total = current_th_nm - initial_thickness_nm
        wafer.add_layer(
            layer_type="THERMAL_OXIDE",
            material="SiO2",
            thickness_nm=round(current_th_nm, 2),
            grown_oxide_nm=round(oxide_grown_total, 2),
            ambience=recipe.steps[0].ambience.value if recipe.steps else "DRY_O2",
        )
        wafer.record_step(
            tool_id=self.equipment_id,
            recipe_name=recipe.recipe_name,
            step_details={
                "grown_oxide_nm": round(oxide_grown_total, 2),
                "final_thickness_nm": round(current_th_nm, 2),
                "duration_s": total_elapsed_s,
            },
        )
        self.record_wafer_processed(1)
        self._maintenance_counters["thermocouple_cal_cycles"].increment(1.0)

        result = OxidationResult(
            recipe_id=recipe.recipe_id,
            wafer_id=wafer.wafer_id,
            total_duration_s=round(total_elapsed_s, 2),
            silicon_orientation=recipe.silicon_orientation.value,
            initial_oxide_thickness_nm=round(initial_thickness_nm, 2),
            final_oxide_thickness_nm=round(current_th_nm, 2),
            oxide_grown_nm=round(oxide_grown_total, 2),
            linear_rate_B_over_A_nm_hr=round(last_ba, 2),
            parabolic_rate_B_nm2_hr=round(last_b, 2),
            mobile_ion_density_cm2=round(na_density, 2),
            fixed_charge_density_cm2=round(qf_base, 2),
            interface_trap_density_cm2_ev=round(dit_base, 2),
            slip_dislocations_detected=slip_dislocations,
            temperature_uniformity_3sigma_c=0.65,
        )

        try:
            self.state_machine.trigger("COMPLETE_RUN", timestamp=self.sim_time + total_elapsed_s)
        except Exception:
            pass
        self.set_gem_processing_state(GEMProcessingState.IDLE)
        self.sequencer_state = FurnaceSequencerState.STANDBY
        logger.info("[%s] Oxidation complete: Wafer '%s' grew %.2fnm oxide (Total=%.2fnm).",
                    self.equipment_id, wafer.wafer_id, oxide_grown_total, current_th_nm)
        return result

    def abort(self, reason: str) -> bool:
        """Interrupt oxidation, turn off pyrogenic torch, flood with N2, and cool."""
        logger.warning("[%s] Furnace ABORT triggered: %s", self.equipment_id, reason)
        self.pyrogenic_torch_ignited = False
        self.pyrogenic_flame_sensor_mv = 0.0

        for zone in self.zones:
            zone.target_temperature_c = 650.0

        try:
            self.state_machine.trigger("ABORT_RUN", timestamp=self.sim_time, payload={"reason": reason})
        except Exception:
            pass
        self.set_gem_processing_state(GEMProcessingState.IDLE)
        self.sequencer_state = FurnaceSequencerState.STANDBY
        return True

    def emergency_stop(self, reason: str) -> None:
        """Immediate Emergency Off (EMO): shut off all heater SCRs and flammable gases."""
        logger.critical("[%s] EMERGENCY STOP (EMO): %s", self.equipment_id, reason)
        self.trip_interlock("INTLK_EMO", reason)

        # De-energize heaters and shut pyrogenic torch
        for zone in self.zones:
            zone.heater_power_pct = 0.0
        self.pyrogenic_torch_ignited = False
        self.pyrogenic_flame_sensor_mv = 0.0

        self.raise_alarm(
            alarm_id="ALM_FURN_EMO",
            name="Furnace EMO Loop Tripped",
            severity=AlarmSeverity.CRITICAL,
            description=f"Safety circuit open: {reason}",
            source="Furnace EMO Loop",
        )
        self.set_gem_processing_state(GEMProcessingState.PAUSE)
        self.sequencer_state = FurnaceSequencerState.STANDBY
