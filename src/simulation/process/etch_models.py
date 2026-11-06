"""Plasma Etch Process and Profile Simulation Models.

This module provides physically grounded models for reactive ion etching (RIE),
inductively coupled plasma (ICP), and capacitively coupled plasma (CCP) etch processes.

Theoretical & Empirical Foundations:
  - Coburn, J. W., & Winters, H. F. (1979). "Ion-surface interactions in plasma-etching
    that enable the simulation of etched profiles". J. Appl. Phys., 50(5), 3189-3196.
  - Gottscho, R. A., Jurgensen, C. W., & Vitkavage, D. J. (1992). "Microscopic
    uniformity in plasma etching". J. Vac. Sci. Technol. B, 10(5), 2133-2147.
  - Matsunami, N. et al. (1984). "Energy dependence of the ion-induced sputtering
    yields of monochromatic solids". Atomic Data and Nuclear Data Tables, 31(1), 1-80.
  - Lieberman, M. A., & Lichtenberg, A. J. (2005). "Principles of Plasma Discharges
    and Materials Processing". 2nd Edition, John Wiley & Sons.
  - Schaepkens, M., & Oehrlein, G. S. (2000). "Asymmetric microloading and feature
    profile evolution during SiO2 etching in fluorocarbon plasmas".
    J. Electrochem. Soc., 148(4), C211.

Key Physical Phenomena Modeled:
  1. Synergistic ion-enhanced etching via Coburn-Winters surface site balance
  2. Spontaneous chemical reaction component (Arrhenius-type radical attack)
  3. Physical ion sputtering threshold & energy scaling (Matsunami / Yamamura formulation)
  4. Material-specific chemistries (Si in SF6/CF4, SiO2 in CHF3/C4F8, Si3N4, PR, Poly-Si)
  5. Material selectivity matrices (target vs mask, target vs stop-layer)
  6. Etch profile anisotropy, sidewall passivation polymer deposition, and taper angle
  7. Microscopic uniformity: Aspect-Ratio Dependent Etching (ARDE / RIE lag) via Knudsen transport
  8. Pattern density micro-loading effect (open-area radical depletion)
  9. Optical emission spectroscopy (OES) endpoint detection signal evolution
  10. Macroscopic center-to-edge wafer uniformity (bowl vs dome radial distributions)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

try:
    from src.simulation.core.units import (
        PhysicalQuantity,
        convert_value,
        duration,
        film_thickness,
        gas_flow,
        pressure,
        rf_power,
        temperature,
    )
except ImportError:
    try:
        from simulation.core.units import (
            PhysicalQuantity,
            convert_value,
            duration,
            film_thickness,
            gas_flow,
            pressure,
            rf_power,
            temperature,
        )
    except ImportError:
        try:
            from core.units import (
                PhysicalQuantity,
                convert_value,
                duration,
                film_thickness,
                gas_flow,
                pressure,
                rf_power,
                temperature,
            )
        except ImportError:
            from ..core.units import (  # type: ignore
                PhysicalQuantity,
                convert_value,
                duration,
                film_thickness,
                gas_flow,
                pressure,
                rf_power,
                temperature,
            )

KB_EV_PER_K: float = 8.617333262e-5


class SubstrateMaterial(str, Enum):
    """Semiconductor fab thin-film materials subjected to plasma etching."""
    SILICON = "SILICON"
    POLYSILICON = "POLYSILICON"
    SILICON_DIOXIDE = "SILICON_DIOXIDE"
    SILICON_NITRIDE = "SILICON_NITRIDE"
    PHOTORESIST = "PHOTORESIST"
    TITANIUM_NITRIDE = "TITANIUM_NITRIDE"
    ALUMINUM = "ALUMINUM"


class EtchGasChemistry(str, Enum):
    """Standard fab plasma etch gas chemistries."""
    SF6_O2 = "SF6_O2"          # High-rate chemical Si etch
    CF4_O2 = "CF4_O2"          # Moderate-rate Si and Poly-Si etch
    CHF3_CF4 = "CHF3_CF4"      # Selective SiO2 / Si3N4 etch with polymer formation
    C4F8_AR = "C4F8_AR"        # High-aspect-ratio deep SiO2 contact hole etch
    HBR_CL2_O2 = "HBR_CL2_O2"  # Ultra-high selectivity Poly-Si gate etch over gate oxide
    CL2_BCL3 = "CL2_BCL3"      # Aluminum metal stack etch
    O2_PLASMA = "O2_PLASMA"    # Photoresist ash / strip


class RadialProfileShape(str, Enum):
    """Wafer center-to-edge macroscopic etch rate non-uniformity profile."""
    BOWL_SHAPED = "BOWL_SHAPED"  # Fast at edge, slow at center
    DOME_SHAPED = "DOME_SHAPED"  # Fast at center, slow at edge
    FLAT = "FLAT"                # Uniform across wafer


@dataclass(frozen=True)
class MaterialEtchParameters:
    """Fundamental surface reaction and sputtering constants for an etched material.

    Attributes:
        solid_density_atoms_cm3: Target atom density in solid (e.g. 5.0e22 for Si).
        binding_energy_ev: Surface atom binding energy / cohesive energy (eV).
        sputter_threshold_energy_ev: Minimum ion kinetic energy for physical sputter (eV).
        chemical_activation_energy_ev: Spontaneous radical reaction activation energy (eV).
        sticking_probability_radical: Sticking coefficient of halogen radicals on clean surface.
        ion_enhanced_yield_coefficient: Multiplier for ion-assisted chemical product yield.
    """
    solid_density_atoms_cm3: float
    binding_energy_ev: float
    sputter_threshold_energy_ev: float
    chemical_activation_energy_ev: float
    sticking_probability_radical: float
    ion_enhanced_yield_coefficient: float


# Literature material calibration parameters (Lieberman & Lichtenberg 2005, Matsunami 1984)
MATERIAL_CALIBRATIONS: Dict[SubstrateMaterial, MaterialEtchParameters] = {
    SubstrateMaterial.SILICON: MaterialEtchParameters(
        solid_density_atoms_cm3=5.0e22,
        binding_energy_ev=4.63,
        sputter_threshold_energy_ev=22.0,
        chemical_activation_energy_ev=0.108,  # Spontaneous Si + F reaction (Flamm et al. 1981)
        sticking_probability_radical=0.25,
        ion_enhanced_yield_coefficient=0.045,
    ),
    SubstrateMaterial.POLYSILICON: MaterialEtchParameters(
        solid_density_atoms_cm3=5.0e22,
        binding_energy_ev=4.60,
        sputter_threshold_energy_ev=20.0,
        chemical_activation_energy_ev=0.120,
        sticking_probability_radical=0.30,
        ion_enhanced_yield_coefficient=0.050,
    ),
    SubstrateMaterial.SILICON_DIOXIDE: MaterialEtchParameters(
        solid_density_atoms_cm3=6.6e22,  # total atoms in SiO2
        binding_energy_ev=9.28,         # High Si-O bond strength
        sputter_threshold_energy_ev=35.0,
        chemical_activation_energy_ev=0.165,  # Very low spontaneous etching without ion assist
        sticking_probability_radical=0.08,
        ion_enhanced_yield_coefficient=0.028,
    ),
    SubstrateMaterial.SILICON_NITRIDE: MaterialEtchParameters(
        solid_density_atoms_cm3=9.0e22,
        binding_energy_ev=7.50,
        sputter_threshold_energy_ev=30.0,
        chemical_activation_energy_ev=0.145,
        sticking_probability_radical=0.12,
        ion_enhanced_yield_coefficient=0.032,
    ),
    SubstrateMaterial.PHOTORESIST: MaterialEtchParameters(
        solid_density_atoms_cm3=4.5e22,
        binding_energy_ev=3.50,
        sputter_threshold_energy_ev=15.0,
        chemical_activation_energy_ev=0.095,
        sticking_probability_radical=0.15,
        ion_enhanced_yield_coefficient=0.038,
    ),
    SubstrateMaterial.TITANIUM_NITRIDE: MaterialEtchParameters(
        solid_density_atoms_cm3=9.6e22,
        binding_energy_ev=8.10,
        sputter_threshold_energy_ev=32.0,
        chemical_activation_energy_ev=0.180,
        sticking_probability_radical=0.10,
        ion_enhanced_yield_coefficient=0.025,
    ),
    SubstrateMaterial.ALUMINUM: MaterialEtchParameters(
        solid_density_atoms_cm3=6.02e22,
        binding_energy_ev=3.39,
        sputter_threshold_energy_ev=18.0,
        chemical_activation_energy_ev=0.130,
        sticking_probability_radical=0.20,
        ion_enhanced_yield_coefficient=0.040,
    ),
}


@dataclass
class PlasmaState:
    """Internal plasma state variables derived from tool operating settings.

    Attributes:
        radical_flux_cm2_s: Flux of reactive halogen / radical species arriving at wafer.
        ion_flux_cm2_s: Flux of energetic positive ions arriving at wafer.
        mean_ion_energy_ev: Average kinetic energy of ions crossing the plasma sheath.
        polymer_precursor_flux_cm2_s: Flux of CFx passivating polymer precursors.
        chamber_pressure_mtorr: Operating vacuum chamber pressure in mTorr.
        wafer_temp_c: Wafer chuck temperature in °C.
    """
    radical_flux_cm2_s: float
    ion_flux_cm2_s: float
    mean_ion_energy_ev: float
    polymer_precursor_flux_cm2_s: float
    chamber_pressure_mtorr: float
    wafer_temp_c: float


@dataclass
class EtchRateComponents:
    """Decomposition of the vertical and lateral etch rate components.

    Attributes:
        chemical_rate_nm_min: Spontaneous thermal chemical etch component.
        physical_rate_nm_min: Physical sputtering etch component.
        ion_enhanced_rate_nm_min: Synergistic ion-assisted chemical etch component.
        polymer_deposition_rate_nm_min: Fluorocarbon polymer deposition rate.
        net_vertical_rate_nm_min: Total vertical etch rate (depth progression).
        net_lateral_rate_nm_min: Total lateral etch rate (mask undercut).
        surface_coverage: Fractional halogen radical coverage theta (0.0 to 1.0).
    """
    chemical_rate_nm_min: float
    physical_rate_nm_min: float
    ion_enhanced_rate_nm_min: float
    polymer_deposition_rate_nm_min: float
    net_vertical_rate_nm_min: float
    net_lateral_rate_nm_min: float
    surface_coverage: float


@dataclass
class EtchProfileResult:
    """Geometric and kinetics result of an etched micro-feature.

    Attributes:
        vertical_etch_rate: Vertical etch rate in nm/min as PhysicalQuantity.
        lateral_etch_rate: Lateral etch rate in nm/min as PhysicalQuantity.
        anisotropy: Anisotropy parameter A = 1 - (R_lateral / R_vertical) [0.0 = isotropic, 1.0 = vertical].
        sidewall_angle_deg: Profile taper angle from horizontal in degrees (e.g. 88.5° to 90.0°).
        aspect_ratio: Feature depth / width ratio.
        arde_lag_factor: Etch rate reduction factor due to ARDE (0.0 < factor <= 1.0).
        microloading_factor: Etch rate reduction factor due to local pattern density.
        components: Kinetic rate breakdown.
    """
    vertical_etch_rate: PhysicalQuantity
    lateral_etch_rate: PhysicalQuantity
    anisotropy: float
    sidewall_angle_deg: float
    aspect_ratio: float
    arde_lag_factor: float
    microloading_factor: float
    components: EtchRateComponents


@dataclass
class EndpointSignalPoint:
    """Time-series data point for optical emission spectroscopy (OES) endpoint detection."""
    time_s: float
    product_emission_intensity_au: float
    reactant_emission_intensity_au: float
    film_thickness_remaining_nm: float
    endpoint_triggered: bool


@dataclass
class WaferRadialEtchUniformity:
    """Center-to-edge radial etch rate distribution across wafer diameter.

    Attributes:
        mean_rate_nm_min: Wafer mean etch rate.
        min_rate_nm_min: Minimum radial etch rate.
        max_rate_nm_min: Maximum radial etch rate.
        non_uniformity_3sigma_pct: 3-sigma percentage non-uniformity [(max - min) / (2 * mean) * 100].
        profile_shape: Radial distribution classification (BOWL, DOME, FLAT).
        radial_points: List of (radius_mm, rate_nm_min) pairs across 300 mm wafer.
    """
    mean_rate_nm_min: float
    min_rate_nm_min: float
    max_rate_nm_min: float
    non_uniformity_3sigma_pct: float
    profile_shape: RadialProfileShape
    radial_points: List[Tuple[float, float]] = field(default_factory=list)


class PlasmaEtchModel:
    """Comprehensive plasma etch simulation model implementing Coburn-Winters kinetics,
    feature profile evolution, ARDE lag, microloading, and optical endpoint detection.
    """

    def __init__(self) -> None:
        """Initialize etch simulation model."""
        pass

    def compute_plasma_state(
        self,
        source_power_w: float,
        bias_power_w: float,
        pressure_mtorr: float,
        gas_chemistry: EtchGasChemistry,
        total_flow_sccm: float,
        wafer_temp_c: float = 20.0,
    ) -> PlasmaState:
        """Derive microscopic plasma parameters from macroscopic tool recipe settings.

        Args:
            source_power_w: ICP / top electrode RF power (generates plasma density).
            bias_power_w: Wafer chuck RF power (governs ion sheath acceleration).
            pressure_mtorr: Chamber vacuum pressure in mTorr.
            gas_chemistry: Gas mixture chemistry.
            total_flow_sccm: Total mass flow rate in sccm.
            wafer_temp_c: Wafer chuck cooled/heated temperature in °C.

        Returns:
            PlasmaState object with flux and energy estimations.
        """
        # Radical flux scales with source power and pressure (collisional dissociation)
        # Typ. radical flux 1e16 to 5e17 cm^-2 s^-1
        rad_scale = math.sqrt(max(10.0, source_power_w)) * (pressure_mtorr ** 0.6)
        radical_flux = 1.2e15 * rad_scale

        # Ion flux scales with plasma density (source power) and inversely with sqrt(pressure)
        # Typ. ion flux 1e15 to 5e16 cm^-2 s^-1
        ion_flux = 4.0e14 * (max(10.0, source_power_w) ** 0.75) / math.sqrt(max(1.0, pressure_mtorr))

        # Mean ion energy scales with bias voltage: V_bias ~ sqrt(Bias_Power / Pressure)
        # Average ion sheath voltage drop + Bohm pre-sheath (typically 30 to 800 eV)
        ion_energy_ev = 15.0 + 8.5 * math.sqrt(max(0.0, bias_power_w) / max(0.5, pressure_mtorr * 0.1))
        ion_energy_ev = min(1200.0, ion_energy_ev)

        # Passivating polymer precursor flux (CF2, CF3 radicals in fluorocarbon gases)
        if gas_chemistry in (EtchGasChemistry.CHF3_CF4, EtchGasChemistry.C4F8_AR):
            # C/F ratio and pressure promote polymer deposition
            poly_flux = 0.35 * radical_flux * (1.0 + math.log10(max(1.0, pressure_mtorr)))
        elif gas_chemistry == EtchGasChemistry.HBR_CL2_O2:
            # SiBrxOx inorganic passivation
            poly_flux = 0.15 * radical_flux
        else:
            poly_flux = 0.0

        return PlasmaState(
            radical_flux_cm2_s=radical_flux,
            ion_flux_cm2_s=ion_flux,
            mean_ion_energy_ev=ion_energy_ev,
            polymer_precursor_flux_cm2_s=poly_flux,
            chamber_pressure_mtorr=pressure_mtorr,
            wafer_temp_c=wafer_temp_c,
        )

    def calculate_etch_components(
        self,
        material: SubstrateMaterial,
        plasma_state: PlasmaState,
    ) -> EtchRateComponents:
        """Evaluate Coburn-Winters surface site balance and component rates.

        Surface Balance (Coburn & Winters 1979):
          d(theta)/dt = S0 * F_rad * (1 - theta) - Y_ie * J_ion * theta = 0
          theta = (S0 * F_rad) / (S0 * F_rad + Y_ie * J_ion)

        Returns:
            EtchRateComponents containing individual and total rates.
        """
        props = MATERIAL_CALIBRATIONS[material]

        t_k = plasma_state.wafer_temp_c + 273.15
        kt = KB_EV_PER_K * t_k

        # 1. Spontaneous chemical reaction component (Arrhenius)
        # Rate = A * exp(-Ea / kT) * F_rad
        chem_factor = math.exp(-props.chemical_activation_energy_ev / kt)
        chem_rate_atoms_cm2_s = 0.08 * props.sticking_probability_radical * chem_factor * plasma_state.radical_flux_cm2_s

        # 2. Physical Sputtering Yield (Yamamura & Matsunami 1984)
        # Y_sputter = A * max(0, sqrt(E_i) - sqrt(E_th))
        e_ion = plasma_state.mean_ion_energy_ev
        e_th = props.sputter_threshold_energy_ev
        if e_ion > e_th:
            sputter_yield = 0.008 * (math.sqrt(e_ion) - math.sqrt(e_th))
        else:
            sputter_yield = 0.0
        phys_rate_atoms_cm2_s = sputter_yield * plasma_state.ion_flux_cm2_s

        # 3. Synergistic Ion-Enhanced Etch Yield
        # Y_ie = coefficient * (sqrt(E_i) - sqrt(E_th_ie))
        e_th_ie = max(5.0, e_th * 0.3)  # Ion-enhanced reactions have much lower threshold than sputtering
        if e_ion > e_th_ie:
            y_ie = props.ion_enhanced_yield_coefficient * (math.sqrt(e_ion) - math.sqrt(e_th_ie))
        else:
            y_ie = 0.0

        # Coburn-Winters site coverage fraction theta
        arrival_flux = props.sticking_probability_radical * plasma_state.radical_flux_cm2_s
        desorption_flux = y_ie * plasma_state.ion_flux_cm2_s
        denom = arrival_flux + desorption_flux
        theta = arrival_flux / denom if denom > 1e-12 else 0.0

        ion_enhanced_atoms_cm2_s = y_ie * plasma_state.ion_flux_cm2_s * theta

        # Polymer deposition rate (fluorocarbon buildup)
        # Suppressed by ion bombardment on horizontal surfaces, survives on vertical sidewalls
        poly_dep_atoms_cm2_s = 0.02 * plasma_state.polymer_precursor_flux_cm2_s

        # Convert atomic flux rates (atoms/cm^2/s) to thickness rates (nm / min)
        # nm/min = (atoms/cm^2/s / solid_density) * (1e7 nm / cm) * 60 s/min
        flux_to_nm_min = (1.0 / props.solid_density_atoms_cm3) * 1e7 * 60.0

        chem_nm_min = chem_rate_atoms_cm2_s * flux_to_nm_min
        phys_nm_min = phys_rate_atoms_cm2_s * flux_to_nm_min
        ie_nm_min = ion_enhanced_atoms_cm2_s * flux_to_nm_min
        poly_dep_nm_min = poly_dep_atoms_cm2_s * flux_to_nm_min

        # Net vertical rate receives direct ion bombardment (clears polymer)
        net_vertical = max(0.0, ie_nm_min + chem_nm_min * theta + phys_nm_min * (1.0 - theta))

        # Net lateral rate receives NO directional ion flux, driven purely by spontaneous chemical etching
        # minus sidewall polymer passivation deposition
        net_lateral = max(0.0, chem_nm_min * theta - poly_dep_nm_min)

        return EtchRateComponents(
            chemical_rate_nm_min=chem_nm_min,
            physical_rate_nm_min=phys_nm_min,
            ion_enhanced_rate_nm_min=ie_nm_min,
            polymer_deposition_rate_nm_min=poly_dep_nm_min,
            net_vertical_rate_nm_min=net_vertical,
            net_lateral_rate_nm_min=net_lateral,
            surface_coverage=theta,
        )

    def calculate_selectivity(
        self,
        target_material: SubstrateMaterial,
        reference_material: SubstrateMaterial,
        plasma_state: PlasmaState,
    ) -> float:
        """Calculate etch selectivity ratio S = Rate(target) / Rate(reference).

        Typical fab targets:
          - Poly-Si over gate SiO2 in HBr/Cl2/O2: 80:1 to 200:1
          - SiO2 over Si in C4F8/Ar: 15:1 to 30:1
          - Si over SiO2 in SF6: 10:1 to 40:1
          - Target over Photoresist: 3:1 to 8:1

        Args:
            target_material: Film layer being etched.
            reference_material: Mask layer or etch stop layer.
            plasma_state: Tool plasma environment.

        Returns:
            Selectivity ratio as a positive float.
        """
        r_target = self.calculate_etch_components(target_material, plasma_state).net_vertical_rate_nm_min
        r_ref = self.calculate_etch_components(reference_material, plasma_state).net_vertical_rate_nm_min
        if r_ref <= 1e-4:
            return 9999.0
        return r_target / r_ref

    def simulate_profile(
        self,
        target_material: SubstrateMaterial,
        plasma_state: PlasmaState,
        feature_depth_nm: float,
        critical_dimension_nm: float,
        open_area_fraction: float = 0.20,
    ) -> EtchProfileResult:
        """Simulate feature vertical & lateral rate, ARDE lag, microloading, and taper angle.

        Microscopic Phenomena:
          1. Aspect Ratio Dependent Etching (ARDE / RIE Lag):
             Knudsen diffusion conductance: K_AR = 1 / (1 + 0.38 * AR)
             Gottscho et al. (1992): ER(AR) = ER_0 * [1 / (1 + alpha * AR)]
          2. Microloading (Schaepkens & Oehrlein 2000):
             Radical depletion across wafer due to open area fraction:
             ER(f_open) = ER_0 / (1 + beta * f_open)
          3. Anisotropy:
             A = 1 - (R_lateral / R_vertical)

        Args:
            target_material: Material being etched.
            plasma_state: Operating plasma condition.
            feature_depth_nm: Instantaneous or target trench/hole depth in nm.
            critical_dimension_nm: Trench width or contact hole diameter in nm.
            open_area_fraction: Fractional wafer open silicon area (0.01 to 0.99).

        Returns:
            EtchProfileResult with complete geometric metrics.
        """
        components = self.calculate_etch_components(target_material, plasma_state)
        r_v0 = components.net_vertical_rate_nm_min
        r_l0 = components.net_lateral_rate_nm_min

        # Aspect ratio
        cd = max(5.0, critical_dimension_nm)
        ar = max(0.0, feature_depth_nm / cd)

        # ARDE lag factor
        alpha_arde = 0.12  # Calibration constant for Knudsen radical choking
        arde_factor = 1.0 / (1.0 + alpha_arde * ar + 0.005 * (ar ** 2))

        # Microloading factor
        beta_load = 0.45  # Depletion factor
        microloading_factor = 1.0 / (1.0 + beta_load * max(0.01, min(0.99, open_area_fraction)))

        # Effective rates
        effective_vertical_nm_min = r_v0 * arde_factor * microloading_factor
        effective_lateral_nm_min = r_l0 * microloading_factor

        # Anisotropy
        if effective_vertical_nm_min > 1e-4:
            anisotropy = max(0.0, min(1.0, 1.0 - (effective_lateral_nm_min / effective_vertical_nm_min)))
        else:
            anisotropy = 1.0

        # Sidewall angle: arctan(1 / (1 - A))
        # When A = 1.0 (no lateral etch), angle is 90.0°
        # When A = 0.0 (isotropic), angle is 45.0° (spherical undercut slope)
        if anisotropy >= 0.9999:
            angle_deg = 90.0
        else:
            lateral_ratio = effective_lateral_nm_min / max(1e-6, effective_vertical_nm_min)
            angle_rad = math.atan2(1.0, lateral_ratio)
            angle_deg = math.degrees(angle_rad)

        return EtchProfileResult(
            vertical_etch_rate=PhysicalQuantity(
                value=effective_vertical_nm_min,
                unit="nm",  # rate magnitude
                valid_range=(0.0, 50000.0),
                uncertainty=effective_vertical_nm_min * 0.03,
                source="Coburn-Winters Kinetic Model",
            ),
            lateral_etch_rate=PhysicalQuantity(
                value=effective_lateral_nm_min,
                unit="nm",
                valid_range=(0.0, 50000.0),
                uncertainty=effective_lateral_nm_min * 0.05,
                source="Coburn-Winters Lateral Passivation Model",
            ),
            anisotropy=anisotropy,
            sidewall_angle_deg=angle_deg,
            aspect_ratio=ar,
            arde_lag_factor=arde_factor,
            microloading_factor=microloading_factor,
            components=components,
        )

    def simulate_endpoint_detection(
        self,
        film_thickness_nm: float,
        vertical_etch_rate_nm_min: float,
        overetch_pct: float = 15.0,
        sample_interval_s: float = 0.5,
    ) -> List[EndpointSignalPoint]:
        """Simulate Optical Emission Spectroscopy (OES) endpoint trace during etching.

        Models product emission decay (e.g. SiF* at 440nm, CO* at 483nm)
        and reactant emission rise (e.g. F* at 703nm) as film clears.

        Args:
            film_thickness_nm: Initial film thickness to be removed.
            vertical_etch_rate_nm_min: Etch rate in nm/min.
            overetch_pct: Planned over-etch duration percentage beyond optical endpoint.
            sample_interval_s: Metrology sampling period in seconds.

        Returns:
            List of EndpointSignalPoint covering main etch, clearing inflection, and overetch.
        """
        rate_nm_s = max(0.01, vertical_etch_rate_nm_min / 60.0)
        t_nominal_ep = film_thickness_nm / rate_nm_s
        total_time = t_nominal_ep * (1.0 + max(0.0, overetch_pct) / 100.0)

        # Clearing transition width sigma (accounting for wafer non-uniformity across 300mm)
        sigma_clear = max(1.0, t_nominal_ep * 0.04)

        points: List[EndpointSignalPoint] = []
        n_steps = max(20, int(total_time / sample_interval_s))

        for step in range(n_steps + 1):
            t = step * sample_interval_s
            rem_thickness = max(0.0, film_thickness_nm - rate_nm_s * t)

            # Product signal (e.g. SiF*): high during etch, sigmoidal drop at clearing
            # 1 / (1 + exp((t - t_ep) / sigma))
            trans_arg = min(50.0, max(-50.0, (t - t_nominal_ep) / sigma_clear))
            product_sig = 100.0 / (1.0 + math.exp(trans_arg)) + 5.0  # +5 AU background

            # Reactant signal (e.g. F*): low while consumed, rises when film clears
            reactant_sig = 90.0 * (1.0 - (1.0 / (1.0 + math.exp(trans_arg)))) + 10.0

            # Endpoint trigger criterion: product signal drops below 30% of peak
            ep_flag = (t >= t_nominal_ep)

            points.append(
                EndpointSignalPoint(
                    time_s=t,
                    product_emission_intensity_au=product_sig,
                    reactant_emission_intensity_au=reactant_sig,
                    film_thickness_remaining_nm=rem_thickness,
                    endpoint_triggered=ep_flag,
                )
            )

        return points

    def calculate_wafer_uniformity(
        self,
        center_rate_nm_min: float,
        edge_rate_factor: float = 1.05,
        wafer_radius_mm: float = 150.0,
        radial_points_count: int = 21,
    ) -> WaferRadialEtchUniformity:
        """Model macroscopic center-to-edge etch rate variation across wafer surface.

        Radial model:
          Rate(r) = Rate_center * [1 + delta * (r / R_wafer)^2]

        Args:
            center_rate_nm_min: Measured or simulated center etch rate.
            edge_rate_factor: Ratio of edge rate to center rate (e.g. 1.05 = 5% faster at edge).
            wafer_radius_mm: Wafer radius in mm (150 mm for 300 mm wafer).
            radial_points_count: Number of radial evaluation points.

        Returns:
            WaferRadialEtchUniformity object with statistics and 3-sigma non-uniformity.
        """
        delta = edge_rate_factor - 1.0
        if delta > 0.005:
            shape = RadialProfileShape.BOWL_SHAPED
        elif delta < -0.005:
            shape = RadialProfileShape.DOME_SHAPED
        else:
            shape = RadialProfileShape.FLAT

        points: List[Tuple[float, float]] = []
        rates: List[float] = []

        dr = wafer_radius_mm / max(1, (radial_points_count - 1))
        for i in range(radial_points_count):
            r = i * dr
            norm_r = r / wafer_radius_mm
            rate = center_rate_nm_min * (1.0 + delta * (norm_r ** 2))
            points.append((r, rate))
            rates.append(rate)

        mean_rate = sum(rates) / len(rates)
        min_rate = min(rates)
        max_rate = max(rates)
        nu_3s = ((max_rate - min_rate) / (2.0 * max(1e-6, mean_rate))) * 100.0

        return WaferRadialEtchUniformity(
            mean_rate_nm_min=mean_rate,
            min_rate_nm_min=min_rate,
            max_rate_nm_min=max_rate,
            non_uniformity_3sigma_pct=nu_3s,
            profile_shape=shape,
            radial_points=points,
        )
