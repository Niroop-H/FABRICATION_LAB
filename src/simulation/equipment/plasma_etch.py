"""Complete Plasma Etch System Simulation Engine.

Standards Compliance:
  - SEMI E10: Equipment Reliability, Availability, and Maintainability
  - SEMI E30: Generic Model for Communications and Control (GEM)
  - SEMI S2: Safety Guidelines for Environmental, Health, and Safety
  - SEMI E12: Standard for Equipment Specific Gas and Chemical Systems

Equipment Architecture:
  - Inductively Coupled Plasma (ICP) High-Density Etch Chamber
  - Turbomolecular and Dry Roughing Vacuum Subsystem with Pendulum Throttle Valve
  - Multi-channel Mass Flow Controllers (CF4, CHF3, SF6, Cl2, BCl3, HBr, O2, Ar, N2)
  - Dual RF power generator (13.56 MHz ICP Source coil, 13.56/2 MHz Substrate Bias)
  - Helium Backside Cooled Bipolar Electrostatic Chuck (ESC)
  - In-situ Optical Emission Spectroscopy (OES) Multi-wavelength Endpoint Detection
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


class EtchState(str, Enum):
    """Plasma Etch Chamber Physical Sequencer States."""
    IDLE = "IDLE"
    PUMP_DOWN = "PUMP_DOWN"
    GAS_STABILIZE = "GAS_STABILIZE"
    IGNITE_PLASMA = "IGNITE_PLASMA"
    PROCESS = "PROCESS"
    PURGE = "PURGE"
    VENT = "VENT"


@dataclass
class PlasmaEtchStep:
    """Recipe Step for Plasma Etch System.

    Attributes:
        step_name: Descriptive step label (e.g. 'BREAKTHROUGH', 'MAIN_ETCH').
        step_type: Sequence phase ('STABILIZE', 'IGNITE', 'MAIN_ETCH', 'OVER_ETCH', 'PURGE').
        duration_s: Step duration limit in seconds [0.1 to 3600.0 s].
        pressure_mtorr: Chamber pressure target [1.0 to 500.0 mTorr].
        rf_source_w: ICP coil source power [0.0 to 3000.0 W].
        rf_bias_w: Substrate bias power [0.0 to 600.0 W].
        gas_flows: Mass flow rates in sccm per gas species.
        chuck_temp_c: Electrostatic chuck temperature target [-20.0 to 80.0 °C].
        he_backside_pressure_torr: Helium backside cooling pressure [5.0 to 15.0 Torr].
        target_material: Dominant film to etch ('Si', 'SiO2', 'Si3N4', 'Photoresist').
        endpoint_enabled: True to terminate step via OES slope detection.
        endpoint_wavelength_nm: OES detection optical emission wavelength.
        endpoint_threshold_pct: Signal drop/rise percentage to trigger endpoint.
        over_etch_pct: Additional over-etch percentage time after endpoint detection.
    """

    step_name: str
    step_type: str = "MAIN_ETCH"
    duration_s: float = 60.0
    pressure_mtorr: float = 15.0
    rf_source_w: float = 800.0
    rf_bias_w: float = 120.0
    gas_flows: Dict[str, float] = field(default_factory=lambda: {"CF4": 50.0, "O2": 5.0, "Ar": 100.0})
    chuck_temp_c: float = 20.0
    he_backside_pressure_torr: float = 10.0
    target_material: str = "Si"
    endpoint_enabled: bool = False
    endpoint_wavelength_nm: float = 703.7  # Fluorine radical line (nm)
    endpoint_threshold_pct: float = 15.0
    over_etch_pct: float = 10.0

    def validate(self) -> None:
        """Validate all step parameters against physical equipment engineering ranges."""
        # Range checks using core unit definitions
        duration(self.duration_s, "s", (0.1, 7200.0), 0.01, "Recipe validator")
        pressure(self.pressure_mtorr, "mTorr", (1.0, 500.0), 0.05, "Recipe validator")
        rf_power(self.rf_source_w, "W", (0.0, 3000.0), 1.0, "ICP Source Generator")
        rf_power(self.rf_bias_w, "W", (0.0, 600.0), 1.0, "Bias Generator")
        temperature(self.chuck_temp_c, "degC", (-20.0, 80.0), 0.1, "ESC Chiller")

        if self.he_backside_pressure_torr < 5.0 or self.he_backside_pressure_torr > 15.0:
            raise ValueError(
                f"Helium backside pressure {self.he_backside_pressure_torr} Torr out of range [5.0, 15.0] Torr"
            )

        for gas, flow in self.gas_flows.items():
            if flow < 0.0 or flow > 500.0:
                raise ValueError(f"Gas flow {gas}={flow} sccm out of calibrated MFC range [0.0, 500.0] sccm")


@dataclass
class PlasmaEtchRecipe:
    """Multi-step Plasma Etch Recipe."""
    recipe_name: str
    recipe_id: str
    steps: List[PlasmaEtchStep] = field(default_factory=list)

    def add_step(self, step: PlasmaEtchStep) -> None:
        """Validate and append a recipe step."""
        step.validate()
        self.steps.append(step)


@dataclass
class EtchResult:
    """Etch Process Run Summary and Metrology."""
    recipe_id: str
    wafer_id: str
    total_duration_s: float
    material_etched: str
    depth_etched_nm: float
    vertical_etch_rate_nm_min: float
    lateral_etch_rate_nm_min: float
    anisotropy: float
    non_uniformity_3sigma_pct: float
    selectivity_to_oxide: float
    selectivity_to_photoresist: float
    endpoint_detected: bool
    endpoint_time_s: Optional[float]
    telemetry_samples: List[Dict[str, Any]] = field(default_factory=list)


class PlasmaEtchSystem(BaseEquipment):
    """Advanced ICP Plasma Etch System Simulation.

    Simulates an Applied Materials Centura / Lam Research Kiyo ICP etch tool
    featuring physical plasma rate models, vacuum pumping dynamics, gas kinetics,
    ESC thermal modeling, and multi-wavelength optical emission spectroscopy.
    """

    def __init__(
        self,
        equipment_id: str = "ETCH_ICP_01",
        manufacturer: str = "Lam Research",
        model: str = "Kiyo FX 300mm",
        initial_time: Optional[float] = None,
    ) -> None:
        """Initialize ICP Plasma Etch tool."""
        super().__init__(
            equipment_id=equipment_id,
            equipment_type="PLASMA_ETCH",
            manufacturer=manufacturer,
            model=model,
            supported_wafer_diameters=[200, 300],
            initial_time=initial_time,
        )

        # Primary Process Chamber
        self.chamber = ProcessChamber(
            chamber_id="CH1",
            name="ICP Etch Process Chamber",
            volume_liters=28.5,
            base_pressure_torr=1.5e-6,
            current_pressure_torr=760.0,
            current_temperature_c=22.0,
            state=ChamberState.ATMOSPHERIC,
        )
        self.add_chamber(self.chamber)

        # Physical Chamber State
        self.etch_state = EtchState.IDLE
        self.throttle_valve_angle_deg = 90.0  # 0 deg = closed, 90 deg = full open
        self.roughing_pump_active = False
        self.turbo_pump_active = False
        self.turbo_speed_pct = 0.0  # 0 to 100% (target 90,000 RPM)
        self.rf_source_power_w = 0.0
        self.rf_bias_power_w = 0.0
        self.rf_reflected_power_w = 0.0
        self.active_gas_flows: Dict[str, float] = {
            "CF4": 0.0,
            "CHF3": 0.0,
            "SF6": 0.0,
            "Cl2": 0.0,
            "BCl3": 0.0,
            "HBr": 0.0,
            "O2": 0.0,
            "Ar": 0.0,
            "N2": 0.0,
        }
        self.chuck_temperature_c = 20.0
        self.he_backside_pressure_torr = 0.0
        self.he_leak_rate_sccm = 0.0
        self.esc_clamping_voltage_v = 0.0

        # OES Spectral Channel Sensors (Wavelength -> Intensity)
        self.oes_spectrum: Dict[float, float] = {
            703.7: 0.0,  # F radical
            261.0: 0.0,  # SiF radical
            387.1: 0.0,  # CN radical
            725.6: 0.0,  # Cl radical
            777.4: 0.0,  # O radical
            750.4: 0.0,  # Ar reference actinometry line
        }

        # Dedicated Safety Interlocks
        self.add_interlock(
            interlock_id="INTLK_CHAMBER_LID",
            name="Chamber Upper Dome Vacuum Seal",
            description="Proximity micro-switch confirming vacuum lid is latched closed",
            auto_reset=False,
        )
        self.add_interlock(
            interlock_id="INTLK_BASE_VACUUM",
            name="Base Vacuum Interlock",
            description="Inhibits process gas introduction until high vacuum base < 5e-5 Torr is proven",
            auto_reset=True,
        )
        self.add_interlock(
            interlock_id="INTLK_RF_REFLECTED",
            name="RF Reflected Power Limit Interlock",
            description="Trips RF match if reflected power exceeds 10% or 100W",
            auto_reset=True,
        )
        self.add_interlock(
            interlock_id="INTLK_CHUCK_TEMP",
            name="ESC Over-Temperature Trip",
            description="Thermal switch trips if ESC exceeds 90°C",
            auto_reset=True,
        )
        self.add_interlock(
            interlock_id="INTLK_HE_LEAK",
            name="He Backside Leak Rate Interlock",
            description="Trips if backside helium leakage exceeds 3.0 sccm indicating de-chuck or broken wafer",
            auto_reset=True,
        )

        # Specialized Maintenance Counters
        self.add_maintenance_counter(
            name="focus_ring_rf_hours",
            limit=250.0,
            unit="hr",
            pm_action="Replace quartz/silicon focus ring due to plasma erosion",
        )
        self.add_maintenance_counter(
            name="chamber_clean_rf_hours",
            limit=50.0,
            unit="hr",
            pm_action="Execute in-situ SF6/O2 plasma dry clean to remove fluorocarbon polymer buildup",
        )

    # -------------------------------------------------------------------------
    # Physical Etch Models
    # -------------------------------------------------------------------------

    def calculate_etch_rates(
        self,
        pressure_mtorr: float,
        rf_source_w: float,
        rf_bias_w: float,
        gas_flows: Dict[str, float],
        chuck_temp_c: float,
    ) -> Dict[str, float]:
        """Compute physically grounded vertical etch rates for Si, SiO2, Si3N4, and Resist.

        Grounded in Gottscho & Lieberman ion-assisted plasma surface kinetics:
          - Plasma density n_e scales with Source Power (ICP).
          - Radical generation scales with Source Power and partial gas flow.
          - Ion bombarding energy E_ion scales with Bias Power / sqrt(Pressure).
          - Chemical etching follows Arrhenius temperature dependence.

        Returns:
            Dictionary of material -> etch_rate (nm/min).
        """
        if rf_source_w <= 0.0:
            return {"Si": 0.0, "SiO2": 0.0, "Si3N4": 0.0, "Photoresist": 0.0}

        # Temperature in Kelvin
        temp_k = chuck_temp_c + 273.15
        k_b = 8.617333262145e-5  # eV / K

        # Gas flow sums
        total_flow = sum(gas_flows.values()) + 1e-6
        cf4 = gas_flows.get("CF4", 0.0)
        chf3 = gas_flows.get("CHF3", 0.0)
        sf6 = gas_flows.get("SF6", 0.0)
        cl2 = gas_flows.get("Cl2", 0.0)
        hbr = gas_flows.get("HBr", 0.0)
        o2 = gas_flows.get("O2", 0.0)
        ar = gas_flows.get("Ar", 0.0)

        # Ion flux estimation (proportional to source power and inverse square root of pressure)
        j_ion = (rf_source_w / 1000.0) * math.sqrt(20.0 / max(1.0, pressure_mtorr))

        # Ion energy estimation (proportional to bias voltage ~ sqrt(bias_power / j_ion))
        e_ion = 15.0 + 18.0 * math.sqrt(max(0.0, rf_bias_w) / max(0.1, j_ion))  # eV

        # Radical density index
        f_rad = (sf6 * 4.0 + cf4 * 2.0 + chf3 * 1.0) / total_flow * (rf_source_w / 800.0)
        cl_rad = (cl2 * 2.0 + hbr * 1.0) / total_flow * (rf_source_w / 800.0)
        o_rad = (o2 * 2.0) / total_flow * (rf_source_w / 800.0)

        # Polymer passivating index (fluorocarbon ratio C/F)
        polymer_index = max(0.0, (chf3 * 1.2 - o2 * 1.5)) / total_flow

        # 1. Silicon Etch Rate (nm/min)
        # Chemical spontaneous etching (high for SF6, moderate for CF4, negligible for Cl2 without ions)
        chem_rate_si = (f_rad * 320.0 + cl_rad * 45.0) * math.exp(-0.12 / (k_b * temp_k))
        # Ion-enhanced component
        ion_rate_si = 85.0 * j_ion * math.sqrt(max(0.0, e_ion - 12.0))
        # Total silicon rate suppressed by polymer deposition
        er_si = (chem_rate_si + ion_rate_si) / (1.0 + 3.0 * polymer_index)

        # 2. SiO2 Etch Rate (nm/min)
        # Requires high ion energy to break Si-O bonds (threshold ~25-30 eV)
        if e_ion > 25.0:
            yield_ox = math.sqrt(e_ion - 25.0)
            # CHF3 / CF4 promote fluorocarbon assisted etching of SiO2 via CO/CO2 volatile formation
            er_sio2 = (18.0 * j_ion * yield_ox * (cf4 * 1.0 + chf3 * 1.8 + ar * 0.3) / total_flow)
        else:
            er_sio2 = 0.5 * j_ion  # Minimal physical sputter

        # 3. Si3N4 Etch Rate (nm/min)
        if e_ion > 20.0:
            yield_nitride = math.sqrt(e_ion - 20.0)
            er_si3n4 = (26.0 * j_ion * yield_nitride * (chf3 * 1.5 + cf4 * 1.1 + o2 * 0.5) / total_flow)
        else:
            er_si3n4 = 1.0 * j_ion

        # 4. Photoresist Etch Rate (nm/min)
        # Sputtered by argon and aggressively etched by oxygen radicals
        chem_pr = 450.0 * o_rad * math.exp(-0.25 / (k_b * temp_k))
        ion_pr = 22.0 * j_ion * math.sqrt(max(0.0, e_ion - 10.0))
        er_pr = chem_pr + ion_pr

        return {
            "Si": max(0.0, er_si),
            "SiO2": max(0.0, er_sio2),
            "Si3N4": max(0.0, er_si3n4),
            "Photoresist": max(0.0, er_pr),
        }

    def calculate_anisotropy(self, rf_bias_w: float, polymer_index: float) -> Tuple[float, float]:
        """Calculate etch anisotropy factor A and sidewall angle.

        Anisotropy A = 1 - (ER_lateral / ER_vertical).
        A = 1.0 represents perfectly vertical 90° etch profiles.
        A = 0.0 represents isotropic wet-like bowl profiles.

        Returns:
            Tuple of (anisotropy [0.0 to 1.0], sidewall_angle_deg [45.0 to 90.0°]).
        """
        # Bias power drives ion directionality
        bias_factor = rf_bias_w / (rf_bias_w + 40.0)
        # Sidewall passivation prevents lateral chemical attack
        passivation_factor = min(0.98, polymer_index * 2.5)

        anisotropy = min(0.995, max(0.05, 0.2 + 0.65 * bias_factor + 0.15 * passivation_factor))
        # Sidewall angle: arctan(ER_v / ER_l) = arctan(1 / (1 - A))
        er_ratio = 1.0 / max(0.005, 1.0 - anisotropy)
        sidewall_angle = math.degrees(math.atan(er_ratio))
        return (anisotropy, min(89.8, max(50.0, sidewall_angle)))

    def calculate_radial_uniformity(self, focus_ring_wear_hr: float) -> float:
        """Calculate 3-sigma center-to-edge etch non-uniformity percentage.

        As the focus ring erodes, plasma sheath distortion at the wafer edge
        leads to edge-fast or edge-slow etch non-uniformity.
        """
        base_non_uniformity = 1.8  # Baseline 1.8% 3-sigma
        wear_penalty = (focus_ring_wear_hr / 250.0) * 3.5
        return base_non_uniformity + wear_penalty

    # -------------------------------------------------------------------------
    # Physical Chamber Sequences
    # -------------------------------------------------------------------------

    def pump_down(self, target_pressure_torr: float = 5e-5) -> bool:
        """Pump down process chamber from atmospheric to high vacuum."""
        logger.info("[%s] Beginning chamber pump-down...", self.equipment_id)
        self.etch_state = EtchState.PUMP_DOWN
        self.chamber.state = ChamberState.PUMPING_DOWN

        # Step 1: Roughing pump operation down to 20 mTorr (0.02 Torr)
        self.roughing_pump_active = True
        self.chamber.current_pressure_torr = 0.02
        logger.info("[%s] Roughing stage complete: chamber pressure = 20 mTorr", self.equipment_id)

        # Step 2: Turbo pump crossover and ramp-up
        self.turbo_pump_active = True
        self.turbo_speed_pct = 100.0
        self.chamber.current_pressure_torr = self.chamber.base_pressure_torr
        self.chamber.state = ChamberState.HIGH_VACUUM
        logger.info("[%s] High vacuum achieved: %e Torr", self.equipment_id, self.chamber.current_pressure_torr)
        return True

    def vent_chamber(self) -> bool:
        """Vent chamber back to atmosphere with inert N2 purge."""
        logger.info("[%s] Venting chamber with dry N2...", self.equipment_id)
        self.etch_state = EtchState.VENT
        self.chamber.state = ChamberState.VENTING

        # De-energize RF and turbo
        self.rf_source_power_w = 0.0
        self.rf_bias_power_w = 0.0
        self.turbo_pump_active = False
        self.turbo_speed_pct = 0.0
        self.roughing_pump_active = False

        # N2 backfill
        self.chamber.current_pressure_torr = 760.0
        self.chamber.state = ChamberState.ATMOSPHERIC
        self.etch_state = EtchState.IDLE
        return True

    # -------------------------------------------------------------------------
    # Equipment Lifecycle Implementation
    # -------------------------------------------------------------------------

    def initialize(self) -> bool:
        """Perform tool self-tests, check interlocks, and initialize vacuum system."""
        logger.info("[%s] Initializing Plasma Etch System...", self.equipment_id)

        # Reset interlocks that are ready
        self.reset_interlock("INTLK_CHAMBER_LID", force=True)
        self.reset_interlock("INTLK_EXHAUST", force=True)
        self.reset_interlock("INTLK_COOLING_WATER", force=True)
        self.reset_interlock("INTLK_EMO", force=True)

        healthy, issues = self.check_interlocks()
        if not healthy:
            logger.error("[%s] Initialization aborted due to interlocks: %s", self.equipment_id, issues)
            return False

        # Transition to STANDBY in SEMI E10 state machine
        try:
            self.state_machine.trigger("START_WARMUP", timestamp=self.sim_time)
            self.state_machine.trigger("WARMUP_COMPLETE", timestamp=self.sim_time + 10.0)
        except Exception:
            pass

        self.set_gem_control_state(GEMControlState.ONLINE_REMOTE)
        self.set_gem_processing_state(GEMProcessingState.IDLE)
        self.etch_state = EtchState.IDLE
        logger.info("[%s] Tool initialization complete. Ready in STANDBY.", self.equipment_id)
        return True

    def process_wafer(self, wafer: Wafer, recipe: PlasmaEtchRecipe) -> EtchResult:
        """Execute a multi-step plasma etch recipe on a wafer."""
        logger.info("[%s] Starting recipe '%s' on wafer '%s'...", self.equipment_id, recipe.recipe_name, wafer.wafer_id)

        # Pre-check interlocks
        healthy, issues = self.check_interlocks()
        if not healthy:
            raise RuntimeError(f"Process inhibited by tripped safety interlocks: {issues}")

        # Transition SEMI E10 to PRODUCTIVE
        try:
            self.state_machine.trigger("START_RUN", timestamp=self.sim_time, payload={"wafer_id": wafer.wafer_id})
        except Exception:
            pass
        self.set_gem_processing_state(GEMProcessingState.EXECUTING)

        # Pump down to base vacuum
        self.pump_down()

        # Electrostatic Chuck Clamping & Backside Cooling Setup
        self.esc_clamping_voltage_v = 800.0  # +400V / -400V bipolar clamp
        self.he_backside_pressure_torr = 10.0
        self.he_leak_rate_sccm = 0.45  # Normal tight seal leak rate
        self.chamber.state = ChamberState.PROCESSING

        total_elapsed_s = 0.0
        depth_etched_total_nm = 0.0
        step_telemetry: List[Dict[str, Any]] = []
        target_mat = "Si"
        endpoint_hit = False
        endpoint_hit_time: Optional[float] = None

        focus_ring_wear = self._maintenance_counters["focus_ring_rf_hours"].current

        for step_idx, step in enumerate(recipe.steps):
            logger.info("[%s] Executing Step %d: %s (%s)", self.equipment_id, step_idx + 1, step.step_name, step.step_type)
            target_mat = step.target_material

            # 1. GAS STABILIZE
            self.etch_state = EtchState.GAS_STABILIZE
            self.active_gas_flows = dict(step.gas_flows)
            self.chuck_temperature_c = step.chuck_temp_c
            self.chamber.current_pressure_torr = step.pressure_mtorr / 1000.0
            total_elapsed_s += 5.0  # 5s stabilization

            # 2. IGNITE PLASMA
            self.etch_state = EtchState.IGNITE_PLASMA
            self.rf_source_power_w = step.rf_source_w
            self.rf_bias_power_w = step.rf_bias_w
            # Auto-matcher impedance match transient
            self.rf_reflected_power_w = step.rf_source_w * 0.015  # 1.5% reflected power
            total_elapsed_s += 1.5  # 1.5s strike

            # 3. PROCESS (MAIN ETCH)
            self.etch_state = EtchState.PROCESS
            rates = self.calculate_etch_rates(
                pressure_mtorr=step.pressure_mtorr,
                rf_source_w=step.rf_source_w,
                rf_bias_w=step.rf_bias_w,
                gas_flows=step.gas_flows,
                chuck_temp_c=step.chuck_temp_c,
            )
            v_rate = rates.get(target_mat, 100.0)

            # Polymer passivating index
            total_f = sum(step.gas_flows.values()) + 1e-6
            poly_idx = max(0.0, step.gas_flows.get("CHF3", 0.0) - step.gas_flows.get("O2", 0.0)) / total_f
            anisotropy, sidewall_deg = self.calculate_anisotropy(step.rf_bias_w, poly_idx)
            l_rate = v_rate * (1.0 - anisotropy)

            # OES Optical Emission Intensity
            f_conc = step.gas_flows.get("CF4", 0.0) * 2.0 + step.gas_flows.get("SF6", 0.0) * 4.0
            self.oes_spectrum[703.7] = f_conc * (step.rf_source_w / 500.0)  # F emission
            self.oes_spectrum[261.0] = v_rate * 1.8  # SiF byproduct emission
            self.oes_spectrum[750.4] = step.gas_flows.get("Ar", 20.0) * 0.8  # Actinometry ref

            # Check endpoint simulation if enabled
            effective_duration = step.duration_s
            if step.endpoint_enabled and not endpoint_hit:
                # Target clearing simulation
                clearing_time = min(step.duration_s * 0.75, 45.0)
                endpoint_hit = True
                endpoint_hit_time = total_elapsed_s + clearing_time
                # Add over-etch percentage
                effective_duration = clearing_time * (1.0 + step.over_etch_pct / 100.0)
                logger.info(
                    "[%s] EPD Triggered via OES %snm slope drop at t=%.1fs. Executing %.1f%% over-etch.",
                    self.equipment_id,
                    step.endpoint_wavelength_nm,
                    clearing_time,
                    step.over_etch_pct,
                )

            step_depth = (v_rate / 60.0) * effective_duration
            depth_etched_total_nm += step_depth
            total_elapsed_s += effective_duration

            # Accumulate RF generator hours
            self.record_rf_hours(effective_duration / 3600.0)
            self._maintenance_counters["focus_ring_rf_hours"].increment(effective_duration / 3600.0)

            # Record telemetry sample
            step_telemetry.append({
                "step_name": step.step_name,
                "step_duration_s": effective_duration,
                "pressure_mtorr": step.pressure_mtorr,
                "rf_source_w": step.rf_source_w,
                "rf_bias_w": step.rf_bias_w,
                "vertical_rate_nm_min": round(v_rate, 2),
                "lateral_rate_nm_min": round(l_rate, 2),
                "anisotropy": round(anisotropy, 4),
                "sidewall_angle_deg": round(sidewall_deg, 2),
                "oes_intensity_703nm": round(self.oes_spectrum[703.7], 1),
                "oes_intensity_261nm": round(self.oes_spectrum[261.0], 1),
            })

        # 4. PURGE AND EXTINGUISH
        self.etch_state = EtchState.PURGE
        self.rf_source_power_w = 0.0
        self.rf_bias_power_w = 0.0
        self.active_gas_flows = {g: 0.0 for g in self.active_gas_flows}
        self.active_gas_flows["N2"] = 200.0  # N2 purge
        total_elapsed_s += 10.0

        # De-chuck electrostatic chuck
        self.esc_clamping_voltage_v = 0.0
        self.he_backside_pressure_torr = 0.0

        # Update Wafer Layers & Metrology
        top_layer = wafer.get_top_layer()
        if top_layer:
            current_th = top_layer.get("thickness_nm", 300.0)
            new_th = max(0.0, current_th - depth_etched_total_nm)
            top_layer["thickness_nm"] = round(new_th, 2)

        wafer.record_step(
            tool_id=self.equipment_id,
            recipe_name=recipe.recipe_name,
            step_details={
                "depth_etched_nm": depth_etched_total_nm,
                "target_material": target_mat,
                "total_duration_s": total_elapsed_s,
            },
        )
        self.record_wafer_processed(1)

        # Calculate final non-uniformity and selectivities
        nu_3sigma = self.calculate_radial_uniformity(focus_ring_wear)
        final_rates = self.calculate_etch_rates(
            pressure_mtorr=15.0,
            rf_source_w=800.0,
            rf_bias_w=120.0,
            gas_flows={"CF4": 50.0, "O2": 5.0, "Ar": 100.0},
            chuck_temp_c=20.0,
        )
        sel_ox = final_rates["Si"] / max(0.1, final_rates["SiO2"])
        sel_pr = final_rates["Si"] / max(0.1, final_rates["Photoresist"])

        result = EtchResult(
            recipe_id=recipe.recipe_id,
            wafer_id=wafer.wafer_id,
            total_duration_s=round(total_elapsed_s, 2),
            material_etched=target_mat,
            depth_etched_nm=round(depth_etched_total_nm, 2),
            vertical_etch_rate_nm_min=round((depth_etched_total_nm / max(1.0, total_elapsed_s)) * 60.0, 2),
            lateral_etch_rate_nm_min=round(l_rate, 2),
            anisotropy=round(anisotropy, 4),
            non_uniformity_3sigma_pct=round(nu_3sigma, 2),
            selectivity_to_oxide=round(sel_ox, 2),
            selectivity_to_photoresist=round(sel_pr, 2),
            endpoint_detected=endpoint_hit,
            endpoint_time_s=endpoint_hit_time,
            telemetry_samples=step_telemetry,
        )

        # Transition SEMI E10 back to STANDBY
        try:
            self.state_machine.trigger("COMPLETE_RUN", timestamp=self.sim_time + total_elapsed_s)
        except Exception:
            pass
        self.set_gem_processing_state(GEMProcessingState.IDLE)
        self.etch_state = EtchState.IDLE
        logger.info("[%s] Wafer '%s' process complete. Etched %.1fnm %s.", self.equipment_id, wafer.wafer_id, depth_etched_total_nm, target_mat)
        return result

    def abort(self, reason: str) -> bool:
        """Safely extinguish plasma, stop toxic gas flows, and purge."""
        logger.warning("[%s] ABORT sequence executed: %s", self.equipment_id, reason)
        self.rf_source_power_w = 0.0
        self.rf_bias_power_w = 0.0
        self.active_gas_flows = {g: 0.0 for g in self.active_gas_flows}
        self.he_backside_pressure_torr = 0.0
        self.esc_clamping_voltage_v = 0.0

        try:
            self.state_machine.trigger("ABORT_RUN", timestamp=self.sim_time, payload={"reason": reason})
        except Exception:
            pass
        self.set_gem_processing_state(GEMProcessingState.IDLE)
        self.etch_state = EtchState.PURGE
        return True

    def emergency_stop(self, reason: str) -> None:
        """Execute immediate SEMI S2 Emergency Off (EMO)."""
        logger.critical("[%s] EMERGENCY STOP TRIPPED (EMO): %s", self.equipment_id, reason)
        self.trip_interlock("INTLK_EMO", reason)

        # Instantly de-energize all power and lock toxic valves
        self.rf_source_power_w = 0.0
        self.rf_bias_power_w = 0.0
        self.turbo_pump_active = False
        self.roughing_pump_active = False
        self.esc_clamping_voltage_v = 0.0
        self.active_gas_flows = {g: 0.0 for g in self.active_gas_flows}

        self.raise_alarm(
            alarm_id="ALM_EMO_ACTIVE",
            name="Emergency Stop Active",
            severity=AlarmSeverity.CRITICAL,
            description=f"Tool safety loop open: {reason}",
            source="EMO Button / Interlock",
        )
        self.set_gem_processing_state(GEMProcessingState.PAUSE)
        self.etch_state = EtchState.IDLE
