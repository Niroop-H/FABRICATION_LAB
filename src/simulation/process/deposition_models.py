"""Deposition Process Models for Semiconductor Thin-Film Fabrication.

This module provides physically grounded models for Chemical Vapor Deposition (CVD),
Low-Pressure CVD (LPCVD), Plasma-Enhanced CVD (PECVD), Physical Vapor Deposition (PVD/Sputtering),
and Atomic Layer Deposition (ALD).

Theoretical & Empirical Foundations:
  - Grove, A. S. (1967). "Physics and Technology of Semiconductor Devices".
    John Wiley & Sons. (Boundary layer mass-transfer vs surface-reaction model).
  - Smith, D. L. (1995). "Thin-Film Deposition: Principles and Practice". McGraw-Hill.
  - George, S. M. (2010). "Atomic Layer Deposition: An Overview".
    Chemical Reviews, 110(1), 111-131.
  - Mayadas, A. F., & Shatzkes, M. (1970). "Electrical-resistivity model for
    polycrystalline films: the case of arbitrary reflection at external surfaces".
    Phys. Rev. B, 1(4), 1382.
  - Stoney, G. G. (1909). "The tension of metallic films deposited on thin plates".
    Proc. R. Soc. Lond. A, 82, 172-175.
  - Kamins, T. I. (1988). "Polycrystalline Silicon for Integrated Circuit Applications".
    Kluwer Academic Publishers.

Key Physical Phenomena Modeled:
  1. CVD series kinetics: Grove boundary layer transport in series with surface reaction:
     1/R = 1/R_mt + 1/R_surface -> R = (R_mt * R_s) / (R_mt + R_s)
  2. Surface reaction limited (Arrhenius exponential T dependence) vs mass-transport limited
     (weak T^1.5 gas diffusion dependence) regimes and transition temperature
  3. Thin film stress: intrinsic deposition stress + thermal mismatch stress (Stoney formula)
  4. Dielectric optical properties: refractive index and extinction coefficient (Sellmeier dispersion)
  5. Conductor resistivity: Mayadas-Shatzkes grain-boundary and Fuchs-Sondheimer surface scattering
  6. Step coverage and conformality: LPCVD vs PECVD vs PVD line-of-sight shadowing
  7. Film-specific systems:
     - LPCVD Polysilicon (SiH4 -> Si + 2H2, grain growth, resistivity)
     - LPCVD Si3N4 (DCS + NH3, high tensile stress +1000 MPa, n=2.01)
     - PECVD SiO2 (TEOS or SiH4+N2O, compressive stress, RF power scaling)
     - PECVD SiNx (tuneable dual-frequency stress from -1000 MPa to +800 MPa)
     - PVD Aluminum & Copper (magnetron sputtering, columnar microstructure)
     - ALD (Langmuir adsorption saturation, Growth-Per-Cycle, thermal window)
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

# Silicon Substrate Mechanical & Thermal Properties (300mm wafer)
# SEMI M1 Standard Reference:
SI_YOUNGS_MODULUS_GPA: float = 169.0  # Si(100) biaxial modulus E / (1 - nu) ~ 180.5 GPa
SI_POISSON_RATIO: float = 0.28
SI_BIAXIAL_MODULUS_PA: float = (SI_YOUNGS_MODULUS_GPA * 1e9) / (1.0 - SI_POISSON_RATIO)  # ~ 2.347e11 Pa
SI_CTE_PER_K: float = 2.6e-6  # Coefficient of Thermal Expansion at 300K
ROOM_TEMP_C: float = 20.0


class DepositionProcessType(str, Enum):
    """Classification of deposition method."""
    LPCVD = "LPCVD"          # Low-Pressure CVD (thermal, highly conformal)
    PECVD = "PECVD"          # Plasma-Enhanced CVD (low-temp, moderate conformality)
    PVD = "PVD"              # Physical Vapor Deposition / Magnetron Sputtering
    ALD = "ALD"              # Atomic Layer Deposition (layer-by-layer, 100% conformal)
    THERMAL_OXIDATION = "THERMAL_OXIDATION"


class DepositionFilm(str, Enum):
    """Specific thin-film material systems."""
    LPCVD_POLYSILICON = "LPCVD_POLYSILICON"
    LPCVD_SILICON_NITRIDE = "LPCVD_SILICON_NITRIDE"
    PECVD_SILICON_DIOXIDE = "PECVD_SILICON_DIOXIDE"
    PECVD_SILICON_NITRIDE = "PECVD_SILICON_NITRIDE"
    PVD_ALUMINUM = "PVD_ALUMINUM"
    PVD_COPPER = "PVD_COPPER"
    ALD_ALUMINUM_OXIDE = "ALD_ALUMINUM_OXIDE"
    ALD_HAFNIUM_OXIDE = "ALD_HAFNIUM_OXIDE"


class KineticRegime(str, Enum):
    """CVD rate-controlling regime."""
    SURFACE_REACTION_LIMITED = "SURFACE_REACTION_LIMITED"
    MASS_TRANSPORT_LIMITED = "MASS_TRANSPORT_LIMITED"
    TRANSITIONAL = "TRANSITIONAL"


@dataclass(frozen=True)
class FilmMaterialProperties:
    """Intrinsic material and optical properties of a deposited thin film.

    Attributes:
        film: DepositionFilm identifier.
        youngs_modulus_gpa: Film Young's Modulus in GPa.
        poisson_ratio: Film Poisson's ratio.
        cte_per_k: Coefficient of thermal expansion (1/K).
        nominal_refractive_index: Refractive index n at 632.8 nm (He-Ne).
        bulk_resistivity_ohm_cm: Bulk electrical resistivity in ohm-cm (for conductors).
        nominal_intrinsic_stress_mpa: As-deposited intrinsic stress (positive = tensile, negative = compressive).
    """
    film: DepositionFilm
    youngs_modulus_gpa: float
    poisson_ratio: float
    cte_per_k: float
    nominal_refractive_index: float
    bulk_resistivity_ohm_cm: float
    nominal_intrinsic_stress_mpa: float


FILM_PROPERTIES_TABLE: Dict[DepositionFilm, FilmMaterialProperties] = {
    DepositionFilm.LPCVD_POLYSILICON: FilmMaterialProperties(
        film=DepositionFilm.LPCVD_POLYSILICON,
        youngs_modulus_gpa=160.0,
        poisson_ratio=0.22,
        cte_per_k=2.8e-6,
        nominal_refractive_index=3.95,  # Optical index at 632.8nm
        bulk_resistivity_ohm_cm=1.0e-3, # Doped polysilicon
        nominal_intrinsic_stress_mpa=-150.0, # Slightly compressive as-dep at 620°C
    ),
    DepositionFilm.LPCVD_SILICON_NITRIDE: FilmMaterialProperties(
        film=DepositionFilm.LPCVD_SILICON_NITRIDE,
        youngs_modulus_gpa=290.0,
        poisson_ratio=0.25,
        cte_per_k=3.0e-6,
        nominal_refractive_index=2.01,
        bulk_resistivity_ohm_cm=1.0e14, # Dielectric insulator
        nominal_intrinsic_stress_mpa=1050.0, # Highly tensile (+900 to +1200 MPa)
    ),
    DepositionFilm.PECVD_SILICON_DIOXIDE: FilmMaterialProperties(
        film=DepositionFilm.PECVD_SILICON_DIOXIDE,
        youngs_modulus_gpa=72.0,
        poisson_ratio=0.17,
        cte_per_k=0.5e-6,
        nominal_refractive_index=1.460,
        bulk_resistivity_ohm_cm=1.0e15,
        nominal_intrinsic_stress_mpa=-200.0, # Compressive
    ),
    DepositionFilm.PECVD_SILICON_NITRIDE: FilmMaterialProperties(
        film=DepositionFilm.PECVD_SILICON_NITRIDE,
        youngs_modulus_gpa=210.0,
        poisson_ratio=0.23,
        cte_per_k=2.5e-6,
        nominal_refractive_index=1.98,
        bulk_resistivity_ohm_cm=1.0e13,
        nominal_intrinsic_stress_mpa=-150.0, # Tuneable via dual-frequency RF
    ),
    DepositionFilm.PVD_ALUMINUM: FilmMaterialProperties(
        film=DepositionFilm.PVD_ALUMINUM,
        youngs_modulus_gpa=70.0,
        poisson_ratio=0.33,
        cte_per_k=23.1e-6, # High CTE mismatch with silicon
        nominal_refractive_index=1.35,
        bulk_resistivity_ohm_cm=2.65e-6, # 2.65 uOhm-cm
        nominal_intrinsic_stress_mpa=50.0,
    ),
    DepositionFilm.PVD_COPPER: FilmMaterialProperties(
        film=DepositionFilm.PVD_COPPER,
        youngs_modulus_gpa=128.0,
        poisson_ratio=0.34,
        cte_per_k=16.5e-6,
        nominal_refractive_index=0.25,
        bulk_resistivity_ohm_cm=1.68e-6, # 1.68 uOhm-cm
        nominal_intrinsic_stress_mpa=120.0,
    ),
    DepositionFilm.ALD_ALUMINUM_OXIDE: FilmMaterialProperties(
        film=DepositionFilm.ALD_ALUMINUM_OXIDE,
        youngs_modulus_gpa=180.0,
        poisson_ratio=0.24,
        cte_per_k=5.0e-6,
        nominal_refractive_index=1.65,
        bulk_resistivity_ohm_cm=1.0e14,
        nominal_intrinsic_stress_mpa=300.0, # Tensile
    ),
    DepositionFilm.ALD_HAFNIUM_OXIDE: FilmMaterialProperties(
        film=DepositionFilm.ALD_HAFNIUM_OXIDE,
        youngs_modulus_gpa=200.0,
        poisson_ratio=0.27,
        cte_per_k=6.5e-6,
        nominal_refractive_index=2.08,
        bulk_resistivity_ohm_cm=1.0e13,
        nominal_intrinsic_stress_mpa=450.0,
    ),
}


@dataclass
class CVDDepositionKinetics:
    """Kinetics parameters for CVD boundary-layer / surface-reaction model.

    Attributes:
        surface_reaction_rate_nm_min: Unconstrained surface reaction rate Rs (Arrhenius).
        mass_transport_rate_nm_min: Boundary layer diffusion rate Rmt.
        net_growth_rate_nm_min: Net combined growth rate R = (Rs * Rmt) / (Rs + Rmt).
        regime: Dominant kinetic regime.
        transition_temperature_c: Temperature where Rs = Rmt.
    """
    surface_reaction_rate_nm_min: float
    mass_transport_rate_nm_min: float
    net_growth_rate_nm_min: float
    regime: KineticRegime
    transition_temperature_c: float


@dataclass
class ThinFilmState:
    """Comprehensive state and properties of a newly deposited thin-film layer.

    Attributes:
        thickness: Film thickness as PhysicalQuantity.
        growth_rate: Deposition rate as PhysicalQuantity.
        intrinsic_stress_mpa: Intrinsic mechanical stress in MPa.
        thermal_stress_mpa: Thermal mismatch stress upon cooling to 20°C in MPa.
        total_stress_mpa: Total wafer curvature stress in MPa.
        wafer_bow_um: Calculated wafer center displacement (bow) in micrometers (Stoney equation).
        refractive_index: Optical refractive index n.
        electrical_resistivity_ohm_cm: Electrical resistivity in ohm-cm.
        step_coverage_pct: Bottom-to-top trench step coverage percentage (%).
        conformality_pct: Sidewall conformality percentage (%).
        grain_size_nm: Average polycrystalline grain diameter in nm (for poly-Si and metals).
    """
    thickness: PhysicalQuantity
    growth_rate: PhysicalQuantity
    intrinsic_stress_mpa: float
    thermal_stress_mpa: float
    total_stress_mpa: float
    wafer_bow_um: float
    refractive_index: float
    electrical_resistivity_ohm_cm: float
    step_coverage_pct: float
    conformality_pct: float
    grain_size_nm: float


@dataclass
class ALDCycleState:
    """Atomic Layer Deposition (ALD) self-limiting saturation status per cycle.

    Attributes:
        growth_per_cycle_nm: Film thickness grown in one full AB binary cycle (GPC).
        precursor_a_coverage: Fractional saturation of precursor A chemisorption theta_A.
        precursor_b_coverage: Fractional saturation of co-reactant B surface reaction theta_B.
        in_ald_window: Whether operating temperature is inside the ideal self-limiting plateau.
        purge_efficiency: Quality of inter-pulse inert purge (1.0 = zero CVD parasitics).
    """
    growth_per_cycle_nm: float
    precursor_a_coverage: float
    precursor_b_coverage: float
    in_ald_window: bool
    purge_efficiency: float


class DepositionSimulator:
    """Semiconductor thin-film deposition physics engine."""

    def __init__(self) -> None:
        """Initialize deposition simulation engine."""
        pass

    def calculate_cvd_kinetics(
        self,
        film: DepositionFilm,
        temp_c: float,
        pressure_torr: float,
        precursor_flow_sccm: float,
    ) -> CVDDepositionKinetics:
        """Evaluate Grove CVD two-step boundary-layer and surface reaction model.

        Grove Formulation (1967):
          Surface reaction: R_s = A_s * exp(-E_a / kT) * P_partial
          Mass transport: R_mt = h_g * C_g = D_AB / delta_BL * (P_partial / R_gas T)
          Net rate: 1/R = 1/R_s + 1/R_mt => R = (R_s * R_mt) / (R_s + R_mt)

        Returns:
            CVDDepositionKinetics object.
        """
        temp_k = temp_c + 273.15
        kt = KB_EV_PER_K * temp_k

        # Film-specific Arrhenius surface activation energies and diffusion parameters
        if film == DepositionFilm.LPCVD_POLYSILICON:
            # SiH4 pyrolysis: SiH4 -> Si + 2H2 (Ea ~ 1.60 eV, Kamins 1988)
            ea_surface = 1.60
            a_surface = 1.2e10  # pre-exponential (nm/min / Torr)
            # Boundary layer gas diffusion coefficient ~ T^1.5 / P
            h_g = 80.0 * ((temp_k / 873.15) ** 1.5) / max(0.01, pressure_torr)
        elif film == DepositionFilm.LPCVD_SILICON_NITRIDE:
            # DCS + NH3: 3 SiH2Cl2 + 4 NH3 -> Si3N4 + 6 HCl + 6 H2 (Ea ~ 1.80 eV)
            ea_surface = 1.80
            a_surface = 3.5e11
            h_g = 65.0 * ((temp_k / 1023.15) ** 1.5) / max(0.01, pressure_torr)
        elif film == DepositionFilm.PECVD_SILICON_DIOXIDE:
            # SiH4 + N2O or TEOS with RF plasma activation: apparent Ea is low (~0.25 eV)
            ea_surface = 0.28
            a_surface = 1.5e3
            h_g = 500.0 * ((temp_k / 673.15) ** 1.5) / max(0.1, pressure_torr)
        else:
            # Default generic CVD
            ea_surface = 1.20
            a_surface = 5.0e7
            h_g = 120.0 * ((temp_k / 800.0) ** 1.5) / max(0.1, pressure_torr)

        # Precursor partial pressure estimate
        p_partial = pressure_torr * min(1.0, max(0.05, precursor_flow_sccm / 500.0))

        # 1. Surface reaction rate Rs (Arrhenius) in nm/min
        r_surface = a_surface * math.exp(-ea_surface / kt) * p_partial

        # 2. Mass transport rate Rmt in nm/min (weak T dependence)
        r_mt = h_g * p_partial

        # Combined net rate
        if (r_surface + r_mt) > 1e-9:
            r_net = (r_surface * r_mt) / (r_surface + r_mt)
        else:
            r_net = 0.0

        # Transition temperature where Rs = Rmt
        # A_s * exp(-Ea / k T_trans) = h_g
        ratio = h_g / max(1e-12, a_surface)
        if 0.0 < ratio < 1.0:
            t_trans_k = -ea_surface / (KB_EV_PER_K * math.log(ratio))
            t_trans_c = t_trans_k - 273.15
        else:
            t_trans_c = 650.0  # nominal typical crossover

        # Classification
        if r_surface < 0.3 * r_mt:
            regime = KineticRegime.SURFACE_REACTION_LIMITED
        elif r_surface > 3.0 * r_mt:
            regime = KineticRegime.MASS_TRANSPORT_LIMITED
        else:
            regime = KineticRegime.TRANSITIONAL

        return CVDDepositionKinetics(
            surface_reaction_rate_nm_min=r_surface,
            mass_transport_rate_nm_min=r_mt,
            net_growth_rate_nm_min=r_net,
            regime=regime,
            transition_temperature_c=t_trans_c,
        )

    def calculate_film_stress_and_bow(
        self,
        film: DepositionFilm,
        thickness_nm: float,
        deposition_temp_c: float,
        wafer_diameter_mm: float = 300.0,
        wafer_thickness_um: float = 775.0,
        rf_bias_power_w: float = 0.0,
    ) -> Tuple[float, float, float, float]:
        """Calculate film stress components and wafer bow using Stoney's equation.

        Stress Formulation:
          sigma_total = sigma_intrinsic + sigma_thermal
          sigma_thermal = [E_f / (1 - nu_f)] * (alpha_Si - alpha_film) * (T_dep - T_room)

        Stoney's Equation (1909):
          Radius of Curvature: R_c = (E_s * t_s^2) / [6 * (1 - nu_s) * sigma_f * t_f]
          Wafer Bow displacement: Bow = D_w^2 / (8 * R_c) = [3 * (1 - nu_s) * D_w^2 / (4 * E_s * t_s^2)] * (sigma_f * t_f)

        Returns:
            Tuple of (intrinsic_stress_mpa, thermal_stress_mpa, total_stress_mpa, wafer_bow_um).
        """
        props = FILM_PROPERTIES_TABLE[film]

        # Intrinsic stress: base material stress modified by ion bombardment (RF power)
        # For PECVD films, ion bombardment drives atoms into interstitial spaces (atomic peening),
        # shifting stress in compressive direction (Davis 1993 model)
        base_intrinsic = props.nominal_intrinsic_stress_mpa
        if rf_bias_power_w > 0.0 and film in (DepositionFilm.PECVD_SILICON_DIOXIDE, DepositionFilm.PECVD_SILICON_NITRIDE):
            peening_shift_mpa = -1.2 * math.sqrt(rf_bias_power_w)
            intrinsic_stress_mpa = base_intrinsic + peening_shift_mpa
        else:
            intrinsic_stress_mpa = base_intrinsic

        # Thermal stress due to CTE mismatch upon cooling to room temperature (20°C)
        # Biaxial modulus of film: M_f = E_f / (1 - nu_f)
        biaxial_modulus_f_pa = (props.youngs_modulus_gpa * 1e9) / (1.0 - props.poisson_ratio)
        delta_t = deposition_temp_c - ROOM_TEMP_C
        delta_alpha = SI_CTE_PER_K - props.cte_per_k  # (alpha_substrate - alpha_film)
        thermal_stress_pa = biaxial_modulus_f_pa * delta_alpha * delta_t
        thermal_stress_mpa = thermal_stress_pa / 1e6

        total_stress_mpa = intrinsic_stress_mpa + thermal_stress_mpa

        # Stoney equation for wafer bow
        # Bow_um = [3 * (1 - nu_s) * D_w^2 / (4 * E_s * t_s^2)] * (sigma_total * t_f)
        # Units: D_w in m, t_s in m, E_s in Pa, sigma in Pa, t_f in m -> Bow in m
        d_w_m = wafer_diameter_mm * 1e-3
        t_s_m = wafer_thickness_um * 1e-6
        t_f_m = thickness_nm * 1e-9
        sigma_pa = total_stress_mpa * 1e6

        stoney_prefactor = (3.0 * (1.0 - SI_POISSON_RATIO) * (d_w_m ** 2)) / (4.0 * (SI_YOUNGS_MODULUS_GPA * 1e9) * (t_s_m ** 2))
        bow_m = stoney_prefactor * sigma_pa * t_f_m
        bow_um = bow_m * 1e6

        return intrinsic_stress_mpa, thermal_stress_mpa, total_stress_mpa, bow_um

    def calculate_electrical_resistivity(
        self,
        film: DepositionFilm,
        thickness_nm: float,
        deposition_temp_c: float,
        doping_conc_cm3: float = 0.0,
    ) -> Tuple[float, float]:
        """Calculate conductor thin-film electrical resistivity using Mayadas-Shatzkes model.

        For metals (Al, Cu):
          Accounts for grain-boundary scattering (Mayadas-Shatzkes 1970) and surface scattering (Fuchs-Sondheimer).
        For LPCVD Polysilicon:
          Accounts for grain size dependence on deposition temperature and dopant activation (Kamins 1988).

        Returns:
            Tuple of (resistivity_ohm_cm, grain_size_nm).
        """
        props = FILM_PROPERTIES_TABLE[film]

        if film == DepositionFilm.LPCVD_POLYSILICON:
            # Transition between amorphous silicon (<570°C) and polycrystalline (>600°C)
            if deposition_temp_c < 575.0:
                grain_size_nm = 5.0  # Quasi-amorphous microcrystals
            else:
                # Grain size increases with deposition temperature (Kamins 1988)
                grain_size_nm = 15.0 + 0.35 * (deposition_temp_c - 575.0)

            # Resistivity vs active doping:
            if doping_conc_cm3 > 1e16:
                # Carrier mobility limited by grain-boundary potential barriers
                q = 1.602176634e-19
                # Masetti-like effective mobility in poly-Si (10 to 45 cm^2 / V*s)
                mu_eff = 12.0 + 28.0 * (1.0 - math.exp(-grain_size_nm / 40.0))
                carrier_density = min(doping_conc_cm3, 2.0e20)
                rho = 1.0 / (q * carrier_density * mu_eff)
            else:
                rho = 1.0e5  # Undoped intrinsic polysilicon (semi-insulating)

            return rho, grain_size_nm

        elif film in (DepositionFilm.PVD_ALUMINUM, DepositionFilm.PVD_COPPER):
            # Metal thin film grain boundary & surface scattering
            # Grain size typically scales with film thickness: d_grain ~ 0.8 * thickness
            grain_size_nm = max(10.0, 0.75 * thickness_nm)
            bulk_rho = props.bulk_resistivity_ohm_cm
            # Electron mean free path lambda: ~39 nm for Cu, ~15 nm for Al
            mfp_nm = 39.0 if film == DepositionFilm.PVD_COPPER else 15.0

            # Mayadas-Shatzkes reflection coefficient R_gb ~ 0.30
            r_gb = 0.30
            alpha_ms = (mfp_nm / grain_size_nm) * (r_gb / (1.0 - r_gb))
            # Fuchs-Sondheimer surface specularity parameter p ~ 0.20
            p_surf = 0.20

            # Combined resistivity enhancement
            rho_film = bulk_rho * (1.0 + 1.5 * alpha_ms + (3.0 / 8.0) * (1.0 - p_surf) * (mfp_nm / max(5.0, thickness_nm)))
            return rho_film, grain_size_nm

        else:
            # Dielectrics: return nominal bulk insulator resistivity
            return props.bulk_resistivity_ohm_cm, 0.0

    def calculate_ald_cycle(
        self,
        film: DepositionFilm,
        temp_c: float,
        pulse_time_a_s: float,
        pulse_time_b_s: float,
        purge_time_s: float,
    ) -> ALDCycleState:
        """Model Atomic Layer Deposition (ALD) self-limiting saturation per cycle.

        Langmuir Chemisorption Kinetics:
          theta(t_pulse) = 1 - exp(-k_eff * t_pulse)
          Growth Per Cycle (GPC): GPC = GPC_ideal * theta_A * theta_B

        ALD Temperature Window:
          Below T_min: Precursor condensation or sluggish reaction
          Between T_min and T_max: Self-limiting saturation plateau (ideal GPC)
          Above T_max: Thermal decomposition (CVD-like parasitics) or precursor desorption

        Returns:
            ALDCycleState object.
        """
        # Define ALD window parameters for Al2O3 (TMA + H2O) or HfO2 (TDMAH + H2O)
        if film == DepositionFilm.ALD_ALUMINUM_OXIDE:
            # Standard TMA / H2O window: 150°C to 300°C, GPC ~ 0.11 nm/cycle
            t_min, t_max = 140.0, 320.0
            ideal_gpc = 0.112  # nm/cycle (Puurunen 2005)
            k_eff_a = 8.5  # 1/s chemisorption saturation rate
            k_eff_b = 6.0
        elif film == DepositionFilm.ALD_HAFNIUM_OXIDE:
            # TDMAH / H2O window: 180°C to 280°C, GPC ~ 0.095 nm/cycle
            t_min, t_max = 180.0, 280.0
            ideal_gpc = 0.095
            k_eff_a = 7.0
            k_eff_b = 5.5
        else:
            t_min, t_max = 150.0, 350.0
            ideal_gpc = 0.100
            k_eff_a = 5.0
            k_eff_b = 5.0

        # Check ALD window
        in_window = (t_min <= temp_c <= t_max)

        # Langmuir surface site coverages
        theta_a = 1.0 - math.exp(-k_eff_a * max(0.01, pulse_time_a_s))
        theta_b = 1.0 - math.exp(-k_eff_b * max(0.01, pulse_time_b_s))

        # Temperature window effects on GPC
        if temp_c < t_min:
            # Condensation or incomplete reaction
            temp_penalty = max(0.2, (temp_c / t_min) ** 1.5)
        elif temp_c > t_max:
            # Desorption or thermal decomposition
            temp_penalty = max(0.1, 1.0 - 0.005 * (temp_c - t_max))
        else:
            temp_penalty = 1.0

        gpc = ideal_gpc * theta_a * theta_b * temp_penalty

        # Purge efficiency: insufficient purge allows gas-phase parasitic CVD reactions
        min_purge_s = 2.0
        purge_eff = min(1.0, purge_time_s / min_purge_s)

        return ALDCycleState(
            growth_per_cycle_nm=gpc,
            precursor_a_coverage=theta_a,
            precursor_b_coverage=theta_b,
            in_ald_window=in_window,
            purge_efficiency=purge_eff,
        )

    def simulate_deposition(
        self,
        film: DepositionFilm,
        process_type: DepositionProcessType,
        target_thickness_nm: Union[float, PhysicalQuantity],
        deposition_temp_c: Union[float, PhysicalQuantity],
        chamber_pressure_torr: float = 0.5,
        precursor_flow_sccm: float = 100.0,
        rf_power_w: float = 0.0,
        ald_cycles: Optional[int] = None,
        doping_conc_cm3: float = 0.0,
    ) -> ThinFilmState:
        """Execute full thin-film deposition simulation.

        Calculates growth rate, conformality, stress, wafer bow, refractive index,
        and electrical resistivity.

        Args:
            film: Material system.
            process_type: LPCVD, PECVD, PVD, or ALD.
            target_thickness_nm: Desired film thickness in nm.
            deposition_temp_c: Process temperature in °C.
            chamber_pressure_torr: Chamber vacuum pressure in Torr.
            precursor_flow_sccm: Main reactant gas flow rate.
            rf_power_w: Applied RF plasma generator power in Watts.
            ald_cycles: Number of cycles if ALD.
            doping_conc_cm3: In-situ dopant concentration.

        Returns:
            ThinFilmState containing complete physical and mechanical metrics.
        """
        if isinstance(target_thickness_nm, PhysicalQuantity):
            thickness_val = target_thickness_nm.to_unit("nm").value
        else:
            thickness_val = float(target_thickness_nm)

        if isinstance(deposition_temp_c, PhysicalQuantity):
            temp_val = deposition_temp_c.to_unit("degC").value
        else:
            temp_val = float(deposition_temp_c)

        props = FILM_PROPERTIES_TABLE[film]

        # Calculate growth rate and conformality based on process type
        if process_type == DepositionProcessType.ALD:
            ald_state = self.calculate_ald_cycle(film, temp_val, 0.5, 0.5, 3.0)
            if ald_cycles is not None:
                actual_thickness = ald_state.growth_per_cycle_nm * ald_cycles
            else:
                actual_thickness = thickness_val
            # Cycle time ~ 5 s (pulse + purge + pulse + purge)
            rate_nm_min = (ald_state.growth_per_cycle_nm / 5.0) * 60.0
            step_coverage = 99.5
            conformality = 99.0

        elif process_type == DepositionProcessType.LPCVD:
            kinetics = self.calculate_cvd_kinetics(film, temp_val, chamber_pressure_torr, precursor_flow_sccm)
            rate_nm_min = kinetics.net_growth_rate_nm_min
            actual_thickness = thickness_val
            # Low sticking coefficient in LPCVD gives very high step coverage (85% to 95%)
            step_coverage = 92.0
            conformality = 90.0

        elif process_type == DepositionProcessType.PECVD:
            # PECVD rate scales with RF power and temperature
            base_rate = 35.0  # nm/min
            rf_factor = 1.0 + 0.015 * math.sqrt(max(0.0, rf_power_w))
            temp_factor = 1.0 + 0.002 * (temp_val - 300.0)
            rate_nm_min = base_rate * rf_factor * temp_factor
            actual_thickness = thickness_val
            step_coverage = 72.0
            conformality = 68.0

        elif process_type == DepositionProcessType.PVD:
            # Magnetron sputtering: directional line-of-sight deposition
            # Rate scales with target DC/RF power: typical 100 to 500 nm/min
            rate_nm_min = 120.0 * (max(50.0, rf_power_w) / 500.0)
            actual_thickness = thickness_val
            # PVD has significant sidewall shadowing in trenches (15% to 35% bottom coverage)
            step_coverage = 28.0
            conformality = 22.0

        else:
            rate_nm_min = 10.0
            actual_thickness = thickness_val
            step_coverage = 80.0
            conformality = 75.0

        # Mechanical stress & wafer bow
        s_int, s_th, s_tot, bow = self.calculate_film_stress_and_bow(
            film=film,
            thickness_nm=actual_thickness,
            deposition_temp_c=temp_val,
            rf_bias_power_w=rf_power_w,
        )

        # Electrical resistivity & grain structure
        rho, grain_size = self.calculate_electrical_resistivity(
            film=film,
            thickness_nm=actual_thickness,
            deposition_temp_c=temp_val,
            doping_conc_cm3=doping_conc_cm3,
        )

        # Refractive index: slight densification shift with deposition temperature
        # n = n_nominal * [1 + 0.0001 * (T - 300)]
        refractive_index = props.nominal_refractive_index * (1.0 + 0.00008 * (temp_val - 300.0))

        thick_qty = film_thickness(
            thickness=actual_thickness,
            unit="nm",
            uncertainty=actual_thickness * 0.02,
            source=f"{process_type.value} {film.value} Deposition",
        )

        rate_qty = PhysicalQuantity(
            value=rate_nm_min,
            unit="nm",  # rate
            valid_range=(0.0, 50000.0),
            uncertainty=rate_nm_min * 0.03,
            source=f"{process_type.value} Rate Model",
        )

        return ThinFilmState(
            thickness=thick_qty,
            growth_rate=rate_qty,
            intrinsic_stress_mpa=s_int,
            thermal_stress_mpa=s_th,
            total_stress_mpa=s_tot,
            wafer_bow_um=bow,
            refractive_index=refractive_index,
            electrical_resistivity_ohm_cm=rho,
            step_coverage_pct=step_coverage,
            conformality_pct=conformality,
            grain_size_nm=grain_size,
        )
