"""Chemical Vapor Deposition (CVD) System Simulation Engine.

Standards Compliance:
  - SEMI E10: Equipment Reliability, Availability, and Maintainability
  - SEMI E30: Generic Model for Communications and Control (GEM)
  - SEMI S2: Environmental, Health, and Safety Guideline for Semiconductor Equipment
  - SEMI E12: Standard for Equipment Specific Gas and Chemical Systems

Reactor Architectures:
  - Atmospheric Pressure CVD (APCVD): continuous / belt reactor
  - Low Pressure CVD (LPCVD): hot-wall quartz tube, batch reactor (400-900°C, 100-1000 mTorr)
  - Plasma-Enhanced CVD (PECVD): parallel-plate showerhead RF reactor (200-400°C, 0.5-5 Torr)

Supported Films and Precursor Chemistries:
  - Polysilicon (SiH4 pyrolysis)
  - Silicon Nitride (Si3N4: SiH2Cl2 + NH3 for LPCVD; SiH4 + NH3 for PECVD)
  - Silicon Dioxide (TEOS-based and Silane LTO)
  - Silicon Oxynitride (SiON: SiH4 + N2O + NH3 for ARC)
  - Amorphous Silicon (a-Si:H)
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
    rf_power,
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


class CVDType(str, Enum):
    """CVD Reactor Classification."""
    APCVD = "APCVD"
    LPCVD = "LPCVD"
    PECVD = "PECVD"


class FilmType(str, Enum):
    """CVD Deposited Thin Film Material."""
    POLYSILICON = "POLYSILICON"
    SILICON_NITRIDE_LPCVD = "SILICON_NITRIDE_LPCVD"
    SILICON_NITRIDE_PECVD = "SILICON_NITRIDE_PECVD"
    TEOS_OXIDE_LPCVD = "TEOS_OXIDE_LPCVD"
    TEOS_OXIDE_PECVD = "TEOS_OXIDE_PECVD"
    SILANE_OXIDE_LTO = "SILANE_OXIDE_LTO"
    SILICON_OXYNITRIDE = "SILICON_OXYNITRIDE"
    AMORPHOUS_SILICON = "AMORPHOUS_SILICON"


@dataclass
class CVDStep:
    """Recipe Step for CVD Deposition System.

    Attributes:
        step_name: Descriptive step label.
        film_type: Target thin film species.
        duration_s: Process deposition duration (s).
        pressure_mtorr: Chamber pressure setpoint (mTorr) [100.0 to 5000.0 mTorr].
        temperature_c: Substrate/pedestal temperature setpoint (°C) [200.0 to 900.0 °C].
        rf_hf_power_w: High-frequency 13.56 MHz RF power (W) [0.0 to 2000.0 W].
        rf_lf_power_w: Low-frequency 350 kHz RF power (W) for stress control [0.0 to 1000.0 W].
        gas_flows_sccm: Flow rates per precursor gas (SiH4, SiH2Cl2, NH3, TEOS, N2O, O2, N2, Ar).
        aspect_ratio: Target feature aspect ratio for step coverage calculation.
    """

    step_name: str
    film_type: FilmType = FilmType.POLYSILICON
    duration_s: float = 300.0
    pressure_mtorr: float = 300.0
    temperature_c: float = 620.0
    rf_hf_power_w: float = 0.0
    rf_lf_power_w: float = 0.0
    gas_flows_sccm: Dict[str, float] = field(default_factory=lambda: {"SiH4": 100.0, "N2": 500.0})
    aspect_ratio: float = 3.0

    def validate(self, cvd_type: CVDType) -> None:
        """Validate step parameters against reactor capabilities."""
        duration(self.duration_s, "s", (1.0, 7200.0), 0.1, "CVD Recipe Step")

        if cvd_type == CVDType.LPCVD:
            pressure(self.pressure_mtorr, "mTorr", (50.0, 2000.0), 1.0, "LPCVD Throttle Valve")
            temperature(self.temperature_c, "degC", (400.0, 950.0), 0.5, "LPCVD Furnace Controller")
            if self.rf_hf_power_w > 0.0 or self.rf_lf_power_w > 0.0:
                raise ValueError("LPCVD reactor does not support RF plasma excitation.")
        elif cvd_type == CVDType.PECVD:
            pressure(self.pressure_mtorr, "mTorr", (200.0, 10000.0), 5.0, "PECVD Throttle Valve")
            temperature(self.temperature_c, "degC", (150.0, 450.0), 0.5, "PECVD Heater Pedestal")
            rf_power(self.rf_hf_power_w, "W", (0.0, 2500.0), 2.0, "13.56 MHz RF Generator")
            rf_power(self.rf_lf_power_w, "W", (0.0, 1500.0), 2.0, "350 kHz Bias Generator")
        else:  # APCVD
            temperature(self.temperature_c, "degC", (350.0, 600.0), 1.0, "APCVD Belt Heater")


@dataclass
class CVDRecipe:
    """Multi-step CVD Deposition Recipe."""
    recipe_name: str
    recipe_id: str
    steps: List[CVDStep] = field(default_factory=list)

    def add_step(self, step: CVDStep, cvd_type: CVDType) -> None:
        """Validate and append a deposition step."""
        step.validate(cvd_type)
        self.steps.append(step)


@dataclass
class CVDResult:
    """Metrology and physical characteristics of deposited film."""
    recipe_id: str
    wafer_id: str
    film_type: str
    total_duration_s: float
    deposited_thickness_nm: float
    deposition_rate_nm_min: float
    thickness_uniformity_3sigma_pct: float
    refractive_index: float
    film_stress_mpa: float  # Negative = Compressive, Positive = Tensile
    step_coverage_pct: float  # Sidewall coverage / Top coverage * 100
    bottom_coverage_pct: float  # Trench bottom coverage / Top coverage * 100
    particle_count_adders: int
    chamber_clean_required: bool


class CVDSystem(BaseEquipment):
    """Chemical Vapor Deposition (CVD) System Simulation Engine.

    Simulates an Applied Materials Producer (PECVD) or TEL Formula (LPCVD) system.
    """

    def __init__(
        self,
        equipment_id: str = "CVD_PRODUCER_01",
        cvd_type: CVDType = CVDType.PECVD,
        manufacturer: str = "Applied Materials",
        model: str = "Producer GT PECVD",
        initial_time: Optional[float] = None,
    ) -> None:
        """Initialize CVD equipment."""
        super().__init__(
            equipment_id=equipment_id,
            equipment_type=f"CVD_{cvd_type.value}",
            manufacturer=manufacturer,
            model=model,
            supported_wafer_diameters=[200, 300],
            initial_time=initial_time,
        )

        self.cvd_type = cvd_type

        # Primary Process Chamber
        base_press = 5e-6 if cvd_type == CVDType.LPCVD else 1e-4
        volume = 85.0 if cvd_type == CVDType.LPCVD else 18.0
        self.chamber = ProcessChamber(
            chamber_id="CH1",
            name=f"{cvd_type.value} Deposition Chamber",
            volume_liters=volume,
            base_pressure_torr=base_press,
            current_pressure_torr=760.0,
            current_temperature_c=25.0,
            state=ChamberState.ATMOSPHERIC,
        )
        self.add_chamber(self.chamber)

        # Cumulative film build-up on chamber walls (in micrometers)
        self.cumulative_wall_thickness_um = 0.0
        self.max_wall_thickness_before_clean_um = 15.0

        # Dedicated Safety Interlocks
        self.add_interlock(
            interlock_id="INTLK_TOXIC_GAS_FLOW",
            name="Toxic Hydride Gas Detector & Scrubber",
            description="Interlocked to facility pyrophoric/toxic gas detection (SiH4, NH3)",
            auto_reset=False,
        )
        self.add_interlock(
            interlock_id="INTLK_SHOWERHEAD_RF",
            name="RF Shield Interlock",
            description="Confirms chamber enclosure RF shields are grounded and latched",
            auto_reset=True,
        )
        self.add_interlock(
            interlock_id="INTLK_VACUUM_BASE",
            name="CVD Base Vacuum Verification",
            description="Ensures moisture/oxygen base vacuum < 5e-4 Torr prior to silane introduction",
            auto_reset=True,
        )

        # Maintenance Counters
        self.add_maintenance_counter(
            name="cumulative_deposited_um",
            limit=self.max_wall_thickness_before_clean_um,
            unit="um",
            pm_action="Execute NF3 plasma in-situ chamber clean recipe",
        )
        self.add_maintenance_counter(
            name="showerhead_hours",
            limit=500.0,
            unit="hr",
            pm_action="Inspect and replace gas distribution showerhead plate",
        )

    # -------------------------------------------------------------------------
    # Physical CVD Deposition & Film Property Models
    # -------------------------------------------------------------------------

    def calculate_thermal_cvd_rate(
        self,
        film_type: FilmType,
        temperature_c: float,
        pressure_mtorr: float,
        gas_flows_sccm: Dict[str, float],
    ) -> float:
        """Compute LPCVD deposition rate using Arrhenius surface reaction kinetics.

        Rate = k0 * exp(-Ea / (kB * T)) * (P_reactant / (1 + sum(K_i * P_i)))
        """
        temp_k = temperature_c + 273.15
        k_b = 8.617333262145e-5  # eV / K

        if film_type == FilmType.POLYSILICON:
            # SiH4 pyrolysis: Ea ~ 1.65 eV (surface reaction limited regime)
            e_a = 1.65  # eV
            k0 = 2.8e15  # nm/min
            sih4_flow = gas_flows_sccm.get("SiH4", 100.0)
            total_flow = sum(gas_flows_sccm.values()) + 1e-6
            p_sih4 = (pressure_mtorr / 1000.0) * (sih4_flow / total_flow)  # Torr
            # Hydrogen desorption inhibition: 1 + K_H * sqrt(P_H2)
            rate = k0 * math.exp(-e_a / (k_b * temp_k)) * (p_sih4 / (1.0 + 1.2 * math.sqrt(max(0.01, p_sih4))))
            return max(0.5, rate)

        elif film_type == FilmType.SILICON_NITRIDE_LPCVD:
            # DCS (SiH2Cl2) + NH3: Ea ~ 1.80 eV, 750-800°C
            e_a = 1.80
            k0 = 1.5e15
            dcs_flow = gas_flows_sccm.get("SiH2Cl2", 50.0)
            total_flow = sum(gas_flows_sccm.values()) + 1e-6
            p_dcs = (pressure_mtorr / 1000.0) * (dcs_flow / total_flow)
            rate = k0 * math.exp(-e_a / (k_b * temp_k)) * p_dcs
            return max(0.2, rate)

        elif film_type == FilmType.TEOS_OXIDE_LPCVD:
            # TEOS decomposition: Ea ~ 1.95 eV, 650-750°C
            e_a = 1.95
            k0 = 8.5e15
            teos_flow = gas_flows_sccm.get("TEOS", 60.0)
            total_flow = sum(gas_flows_sccm.values()) + 1e-6
            p_teos = (pressure_mtorr / 1000.0) * (teos_flow / total_flow)
            rate = k0 * math.exp(-e_a / (k_b * temp_k)) * p_teos
            return max(0.5, rate)

        elif film_type == FilmType.SILANE_OXIDE_LTO:
            # SiH4 + O2: 400-450°C, Ea ~ 0.4 eV (mass transport / branched radical chain)
            e_a = 0.42
            k0 = 1.8e4
            sih4 = gas_flows_sccm.get("SiH4", 40.0)
            o2 = gas_flows_sccm.get("O2", 60.0)
            total_flow = sum(gas_flows_sccm.values()) + 1e-6
            ratio = o2 / max(1.0, sih4)
            # Optimum O2:SiH4 ratio is ~1.5 to 2.0; excess O2 inhibits reaction
            ratio_eff = math.exp(-((ratio - 1.8) ** 2) / 2.0)
            p_tot = pressure_mtorr / 1000.0
            rate = k0 * math.exp(-e_a / (k_b * temp_k)) * p_tot * ratio_eff
            return max(1.0, rate)

        return 10.0

    def calculate_pecvd_rate(
        self,
        film_type: FilmType,
        temperature_c: float,
        pressure_mtorr: float,
        rf_hf_power_w: float,
        rf_lf_power_w: float,
        gas_flows_sccm: Dict[str, float],
    ) -> float:
        """Compute PECVD deposition rate driven by electron-impact radical dissociation.

        Rate = k_plasma * (P_RF)^gamma * (P_gas)^beta * exp(-E_app / (k_B * T))
        Apparent activation energy is low (0.1 to 0.25 eV) because RF plasma dissociates bonds.
        """
        temp_k = temperature_c + 273.15
        k_b = 8.617333262145e-5
        total_rf = rf_hf_power_w + 0.3 * rf_lf_power_w
        if total_rf <= 0.0:
            return 0.0

        rf_factor = (total_rf / 400.0) ** 0.75
        p_factor = (pressure_mtorr / 2500.0) ** 0.5

        if film_type in (FilmType.SILICON_NITRIDE_PECVD,):
            # SiH4 + NH3 / N2 at 350-400°C: ~150-300 nm/min
            base_rate = 180.0
            e_app = 0.15
            rate = base_rate * rf_factor * p_factor * math.exp(-e_app / (k_b * temp_k))
            return max(5.0, rate)

        elif film_type in (FilmType.TEOS_OXIDE_PECVD,):
            # TEOS + O2 PECVD at 350-400°C: ~300-600 nm/min
            base_rate = 380.0
            e_app = 0.12
            rate = base_rate * rf_factor * p_factor * math.exp(-e_app / (k_b * temp_k))
            return max(10.0, rate)

        elif film_type in (FilmType.SILICON_OXYNITRIDE,):
            # SiH4 + N2O + NH3
            base_rate = 220.0
            e_app = 0.14
            rate = base_rate * rf_factor * p_factor * math.exp(-e_app / (k_b * temp_k))
            return max(5.0, rate)

        elif film_type in (FilmType.AMORPHOUS_SILICON,):
            # Pure SiH4 plasma at 250°C
            base_rate = 95.0
            e_app = 0.10
            rate = base_rate * rf_factor * p_factor * math.exp(-e_app / (k_b * temp_k))
            return max(2.0, rate)

        return 120.0

    def calculate_film_properties(
        self,
        film_type: FilmType,
        temperature_c: float,
        rf_hf_power_w: float,
        rf_lf_power_w: float,
        aspect_ratio: float,
    ) -> Dict[str, float]:
        """Calculate film physical properties: stress, refractive index, and step coverage."""
        # 1. Refractive Index (ellipsometry at 632.8 nm)
        if film_type == FilmType.POLYSILICON:
            n_index = 3.92
            sticking_coeff = 0.05
            stress_mpa = -150.0  # Slightly compressive
        elif film_type == FilmType.SILICON_NITRIDE_LPCVD:
            n_index = 2.01
            sticking_coeff = 0.03
            stress_mpa = 950.0  # High tensile
        elif film_type == FilmType.SILICON_NITRIDE_PECVD:
            # Dual frequency RF stress tuning:
            # LF induces ion bombardment and drives film compressive
            total_rf = rf_hf_power_w + rf_lf_power_w + 1e-6
            lf_ratio = rf_lf_power_w / total_rf
            # Tunable from +300 MPa (tensile, pure HF) down to -650 MPa (compressive, high LF)
            stress_mpa = 300.0 - (950.0 * lf_ratio)
            n_index = 1.98 + 0.08 * lf_ratio
            sticking_coeff = 0.08
        elif film_type == FilmType.TEOS_OXIDE_LPCVD:
            n_index = 1.458
            sticking_coeff = 0.01  # Ultra-low sticking -> exceptional conformality
            stress_mpa = -120.0  # Slightly compressive
        elif film_type == FilmType.TEOS_OXIDE_PECVD:
            n_index = 1.462
            sticking_coeff = 0.04
            stress_mpa = -180.0
        elif film_type == FilmType.SILANE_OXIDE_LTO:
            n_index = 1.455
            sticking_coeff = 0.12  # Higher sticking -> lower conformality
            stress_mpa = 150.0  # Moderately tensile
        elif film_type == FilmType.SILICON_OXYNITRIDE:
            n_index = 1.68
            sticking_coeff = 0.06
            stress_mpa = -50.0
        else:  # AMORPHOUS_SILICON
            n_index = 3.65
            sticking_coeff = 0.10
            stress_mpa = -220.0

        # Step Coverage Calculation:
        # Sidewall coverage = 1 / (1 + 1.5 * s_c * AR)
        # Bottom coverage = 1 / cosh(sqrt(s_c) * AR)
        ar = max(0.5, aspect_ratio)
        sidewall_ratio = 1.0 / (1.0 + 1.5 * sticking_coeff * ar)
        bottom_ratio = 1.0 / math.cosh(math.sqrt(sticking_coeff) * ar)

        return {
            "refractive_index": n_index,
            "film_stress_mpa": stress_mpa,
            "step_coverage_pct": min(98.0, max(25.0, sidewall_ratio * 100.0)),
            "bottom_coverage_pct": min(95.0, max(15.0, bottom_ratio * 100.0)),
        }

    # -------------------------------------------------------------------------
    # In-Situ Chamber Clean Cycle (NF3 Plasma)
    # -------------------------------------------------------------------------

    def execute_in_situ_clean(self, duration_s: float = 600.0) -> bool:
        """Execute in-situ NF3 plasma clean to strip accumulated wall deposits."""
        logger.info("[%s] Executing NF3 plasma in-situ chamber clean...", self.equipment_id)
        self.cumulative_wall_thickness_um = 0.0
        self.reset_maintenance_counter("cumulative_deposited_um")
        self.clear_alarm("ALM_CVD_WALL_FLAKING")
        logger.info("[%s] In-situ clean completed. Chamber walls restored to bare clean condition.", self.equipment_id)
        return True

    # -------------------------------------------------------------------------
    # Equipment Lifecycle Implementation
    # -------------------------------------------------------------------------

    def initialize(self) -> bool:
        """Initialize vacuum, throttle valve, heaters, and safety interlocks."""
        logger.info("[%s] Initializing CVD System (%s)...", self.equipment_id, self.cvd_type.value)

        self.reset_interlock("INTLK_TOXIC_GAS_FLOW", force=True)
        self.reset_interlock("INTLK_SHOWERHEAD_RF", force=True)
        self.reset_interlock("INTLK_VACUUM_BASE", force=True)
        self.reset_interlock("INTLK_EXHAUST", force=True)
        self.reset_interlock("INTLK_COOLING_WATER", force=True)
        self.reset_interlock("INTLK_EMO", force=True)

        healthy, issues = self.check_interlocks()
        if not healthy:
            logger.error("[%s] CVD initialization blocked by interlocks: %s", self.equipment_id, issues)
            return False

        self.chamber.current_temperature_c = 250.0 if self.cvd_type == CVDType.PECVD else 600.0
        self.set_gem_control_state(GEMControlState.ONLINE_REMOTE)
        self.set_gem_processing_state(GEMProcessingState.IDLE)
        logger.info("[%s] CVD system initialized in STANDBY.", self.equipment_id)
        return True

    def process_wafer(self, wafer: Wafer, recipe: CVDRecipe) -> CVDResult:
        """Execute a CVD deposition recipe on target wafer."""
        logger.info("[%s] Starting CVD deposition '%s' on wafer '%s'...", self.equipment_id, recipe.recipe_name, wafer.wafer_id)

        healthy, issues = self.check_interlocks()
        if not healthy:
            raise RuntimeError(f"CVD deposition blocked by interlocks: {issues}")

        try:
            self.state_machine.trigger("START_RUN", timestamp=self.sim_time, payload={"wafer_id": wafer.wafer_id})
        except Exception:
            pass
        self.set_gem_processing_state(GEMProcessingState.EXECUTING)

        total_elapsed_s = 0.0
        total_deposited_nm = 0.0
        last_film_type = FilmType.POLYSILICON

        for step_idx, step in enumerate(recipe.steps):
            logger.info("[%s] Step %d: Deposition of %s (%.0fs at %.0f°C)",
                        self.equipment_id, step_idx + 1, step.film_type.value, step.duration_s, step.temperature_c)
            last_film_type = step.film_type

            # Deposition rate calculation
            if self.cvd_type == CVDType.PECVD:
                dep_rate_nm_min = self.calculate_pecvd_rate(
                    film_type=step.film_type,
                    temperature_c=step.temperature_c,
                    pressure_mtorr=step.pressure_mtorr,
                    rf_hf_power_w=step.rf_hf_power_w,
                    rf_lf_power_w=step.rf_lf_power_w,
                    gas_flows_sccm=step.gas_flows_sccm,
                )
                self.record_rf_hours(step.duration_s / 3600.0)
            else:
                dep_rate_nm_min = self.calculate_thermal_cvd_rate(
                    film_type=step.film_type,
                    temperature_c=step.temperature_c,
                    pressure_mtorr=step.pressure_mtorr,
                    gas_flows_sccm=step.gas_flows_sccm,
                )

            step_thickness_nm = (dep_rate_nm_min / 60.0) * step.duration_s
            total_deposited_nm += step_thickness_nm
            total_elapsed_s += step.duration_s

            # Wall deposition accumulation (converted to micrometers)
            self.cumulative_wall_thickness_um += step_thickness_nm / 1000.0
            self._maintenance_counters["cumulative_deposited_um"].increment(step_thickness_nm / 1000.0)

            # Check gas phase nucleation / particle hazard:
            # High silane partial pressure + high oxidant pressure causes gas phase particle shower
            if "SiH4" in step.gas_flows_sccm and "O2" in step.gas_flows_sccm:
                if step.pressure_mtorr > 800.0 and step.temperature_c > 450.0:
                    self.raise_alarm(
                        alarm_id="ALM_GAS_PHASE_NUCLEATION",
                        name="CVD Gas Phase Homogeneous Nucleation Detected",
                        severity=AlarmSeverity.WARNING,
                        description="Operating pressure/temperature exceeds silane homogenous reaction limit.",
                        source="Reaction Kinetics Monitor",
                    )

        # Check chamber wall cleaning limit
        clean_due = self.cumulative_wall_thickness_um >= self.max_wall_thickness_before_clean_um
        if clean_due:
            self.raise_alarm(
                alarm_id="ALM_CVD_WALL_FLAKING",
                name="Chamber Wall Flaking Hazard: PM Clean Mandatory",
                severity=AlarmSeverity.WARNING,
                description=f"Wall thickness reached {self.cumulative_wall_thickness_um:.2f} um. Clean required.",
                source="Chamber Hygiene Subsystem",
            )

        # Calculate final film material properties
        props = self.calculate_film_properties(
            film_type=last_film_type,
            temperature_c=recipe.steps[-1].temperature_c if recipe.steps else 400.0,
            rf_hf_power_w=recipe.steps[-1].rf_hf_power_w if recipe.steps else 0.0,
            rf_lf_power_w=recipe.steps[-1].rf_lf_power_w if recipe.steps else 0.0,
            aspect_ratio=recipe.steps[-1].aspect_ratio if recipe.steps else 3.0,
        )

        # Particle generation model: base 5 adders + flaking contribution
        particle_adders = 5 + int(self.cumulative_wall_thickness_um * 2.5)

        # Update Wafer Film Stack
        wafer.add_layer(
            layer_type="CVD_FILM",
            material=last_film_type.value,
            thickness_nm=round(total_deposited_nm, 2),
            refractive_index=props["refractive_index"],
            stress_mpa=props["film_stress_mpa"],
            conformality_pct=props["step_coverage_pct"],
        )
        wafer.defect_count += particle_adders
        wafer.record_step(
            tool_id=self.equipment_id,
            recipe_name=recipe.recipe_name,
            step_details={
                "film_deposited": last_film_type.value,
                "thickness_nm": round(total_deposited_nm, 2),
                "duration_s": total_elapsed_s,
            },
        )
        self.record_wafer_processed(1)

        result = CVDResult(
            recipe_id=recipe.recipe_id,
            wafer_id=wafer.wafer_id,
            film_type=last_film_type.value,
            total_duration_s=round(total_elapsed_s, 2),
            deposited_thickness_nm=round(total_deposited_nm, 2),
            deposition_rate_nm_min=round((total_deposited_nm / max(1.0, total_elapsed_s)) * 60.0, 2),
            thickness_uniformity_3sigma_pct=1.45,
            refractive_index=round(props["refractive_index"], 4),
            film_stress_mpa=round(props["film_stress_mpa"], 1),
            step_coverage_pct=round(props["step_coverage_pct"], 1),
            bottom_coverage_pct=round(props["bottom_coverage_pct"], 1),
            particle_count_adders=particle_adders,
            chamber_clean_required=clean_due,
        )

        try:
            self.state_machine.trigger("COMPLETE_RUN", timestamp=self.sim_time + total_elapsed_s)
        except Exception:
            pass
        self.set_gem_processing_state(GEMProcessingState.IDLE)
        logger.info("[%s] Deposition complete: %.2fnm %s deposited on '%s'.",
                    self.equipment_id, total_deposited_nm, last_film_type.value, wafer.wafer_id)
        return result

    def abort(self, reason: str) -> bool:
        """Interrupt CVD process: de-energize RF, cut hydride gases, and N2 purge."""
        logger.warning("[%s] CVD ABORT triggered: %s", self.equipment_id, reason)
        try:
            self.state_machine.trigger("ABORT_RUN", timestamp=self.sim_time, payload={"reason": reason})
        except Exception:
            pass
        self.set_gem_processing_state(GEMProcessingState.IDLE)
        return True

    def emergency_stop(self, reason: str) -> None:
        """Immediate Emergency Stop (EMO): instantly lock silane/ammonia valves and kill RF."""
        logger.critical("[%s] EMERGENCY STOP TRIPPED (EMO): %s", self.equipment_id, reason)
        self.trip_interlock("INTLK_EMO", reason)

        self.raise_alarm(
            alarm_id="ALM_CVD_EMO",
            name="CVD Emergency Stop Active",
            severity=AlarmSeverity.CRITICAL,
            description=f"Safety circuit open: {reason}",
            source="CVD EMO Loop",
        )
        self.set_gem_processing_state(GEMProcessingState.PAUSE)
