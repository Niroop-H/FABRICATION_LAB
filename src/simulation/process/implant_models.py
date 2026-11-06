"""Ion Implantation Simulation Models for Semiconductor Device Doping.

This module provides physically grounded models for ion implantation profile prediction,
screen oxide deceleration/loss, crystal lattice damage (displacements per atom),
amorphization dose thresholds, and thermal anneal electrical activation.

Theoretical & Empirical Foundations:
  - Gibbons, J. F., Johnson, W. S., & Mylroie, S. W. (1975). "Projected Range Statistics:
    Semiconductors and Related Materials". Dowden, Hutchinson & Ross (Halsted Press).
  - Ziegler, J. F., Biersack, J. P., & Littmark, U. (1985). "The Stopping and Range
    of Ions in Matter" (SRIM/TRIM). Pergamon Press.
  - Robinson, M. T., & Torrens, I. M. (1974). "Computer simulation of atomic-displacement
    cascades in solids in the binary-collision approximation". Phys. Rev. B, 9(12), 5008.
  - Hofker, W. K. (1975). "Physical properties of boron implanted silicon".
    Philips Res. Rep. Suppl., 8.
  - Tasch, A. F. et al. (1989). "An improved approach to accurately model shallow B and BF2
    implants in silicon". IEEE Trans. Electron Devices, 36(1), 149-152.
  - Masetti, G., Severi, M., & Solmi, S. (1983). "Modeling of carrier mobility against carrier
    concentration in arsenic-, phosphorus-, and boron-doped silicon".
    IEEE Trans. Electron Devices, 30(7), 764-769.

Key Physical Phenomena Modeled:
  1. Tabulated projected range (Rp), longitudinal straggle (delta_Rp), and lateral straggle
     (delta_R_lat) with continuous spline/power-law interpolation for B, P, As, and BF2
  2. Gaussian depth distribution: N(x) = [Dose / (sqrt(2*pi) * delta_Rp)] * exp(-(x - Rp)^2 / (2 * delta_Rp^2))
  3. Dual Pearson IV distribution: captures random nuclear scattering and axial channeling tail
  4. Screen oxide range offset and dose filtration / loss into dielectric capping layers
  5. Lattice damage: Kinchin-Pease / NRT displacements per atom (DPA) and critical amorphization dose
  6. Post-implant thermal / RTA electrical activation: solid solubility limits (C_ss) and
     Masetti mobility / sheet resistance (Rs) calculation
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
        implant_dose,
        ion_energy,
        temperature,
    )
except ImportError:
    try:
        from simulation.core.units import (
            PhysicalQuantity,
            convert_value,
            duration,
            film_thickness,
            implant_dose,
            ion_energy,
            temperature,
        )
    except ImportError:
        try:
            from core.units import (
                PhysicalQuantity,
                convert_value,
                duration,
                film_thickness,
                implant_dose,
                ion_energy,
                temperature,
            )
        except ImportError:
            from ..core.units import (  # type: ignore
                PhysicalQuantity,
                convert_value,
                duration,
                film_thickness,
                implant_dose,
                ion_energy,
                temperature,
            )

KB_EV_PER_K: float = 8.617333262e-5
E_CHARGE_COULOMBS: float = 1.602176634e-19
SILICON_ATOMIC_DENSITY_CM3: float = 5.0e22  # atoms / cm^3


class ImplantSpecies(str, Enum):
    """Ion implantation dopant species."""
    BORON = "BORON"             # 11B+ (p-type)
    BF2 = "BF2"                 # 49BF2+ (molecular p-type for ultra-shallow junctions)
    PHOSPHORUS = "PHOSPHORUS"   # 31P+ (n-type)
    ARSENIC = "ARSENIC"         # 75As+ (n-type, heavy)
    INDIUM = "INDIUM"           # 115In+ (heavy p-type halo)
    ANTIMONY = "ANTIMONY"       # 121Sb+ (n-type buried layer)


@dataclass(frozen=True)
class RangeStatistics:
    """Projected range stopping statistics in single crystal silicon.

    Attributes:
        energy_kev: Ion kinetic energy in keV.
        rp_nm: Projected range (mean depth) in nm.
        delta_rp_nm: Longitudinal straggle (depth standard deviation) in nm.
        delta_rlat_nm: Lateral / transverse straggle in nm.
        skewness: Third standardized moment gamma_1 (asymmetry).
        kurtosis: Fourth standardized moment beta_2 (tail peakedness).
    """
    energy_kev: float
    rp_nm: float
    delta_rp_nm: float
    delta_rlat_nm: float
    skewness: float
    kurtosis: float


# Literature experimental calibration tables from Gibbons et al. (1975) & SRIM/TRIM
# Energies in keV, Range parameters in nm
BORON_RANGE_TABLE: List[RangeStatistics] = [
    RangeStatistics(0.5, 2.8, 2.1, 1.8, 0.45, 3.2),
    RangeStatistics(1.0, 4.6, 3.1, 2.7, 0.50, 3.3),
    RangeStatistics(2.0, 8.2, 5.0, 4.3, 0.55, 3.4),
    RangeStatistics(5.0, 19.5, 10.3, 8.9, 0.60, 3.5),
    RangeStatistics(10.0, 36.8, 16.8, 14.5, 0.65, 3.6),
    RangeStatistics(20.0, 71.0, 28.5, 24.8, 0.70, 3.7),
    RangeStatistics(30.0, 106.5, 39.0, 34.2, 0.73, 3.8),
    RangeStatistics(50.0, 177.0, 56.0, 49.5, 0.78, 4.0),
    RangeStatistics(80.0, 266.6, 69.1, 62.0, 0.82, 4.2),
    RangeStatistics(100.0, 320.0, 78.0, 70.0, 0.85, 4.3),
    RangeStatistics(150.0, 440.0, 92.0, 84.0, 0.88, 4.5),
    RangeStatistics(200.0, 592.0, 102.0, 95.0, 0.90, 4.8),
]

PHOSPHORUS_RANGE_TABLE: List[RangeStatistics] = [
    RangeStatistics(5.0, 8.5, 4.2, 3.5, 0.30, 3.1),
    RangeStatistics(10.0, 13.9, 6.7, 5.6, 0.35, 3.2),
    RangeStatistics(20.0, 25.5, 11.5, 9.6, 0.40, 3.3),
    RangeStatistics(30.0, 38.8, 16.2, 13.5, 0.45, 3.4),
    RangeStatistics(50.0, 64.0, 24.8, 20.8, 0.50, 3.5),
    RangeStatistics(80.0, 102.8, 37.6, 31.5, 0.55, 3.6),
    RangeStatistics(100.0, 130.0, 45.0, 38.0, 0.58, 3.7),
    RangeStatistics(150.0, 195.0, 62.0, 53.0, 0.62, 3.9),
    RangeStatistics(200.0, 253.9, 77.5, 66.0, 0.65, 4.0),
    RangeStatistics(300.0, 370.0, 102.0, 88.0, 0.70, 4.2),
    RangeStatistics(500.0, 600.0, 138.0, 122.0, 0.75, 4.5),
    RangeStatistics(1000.0, 1120.0, 175.0, 160.0, 0.80, 5.0),
]

ARSENIC_RANGE_TABLE: List[RangeStatistics] = [
    RangeStatistics(10.0, 9.7, 3.6, 2.8, -0.10, 3.0),
    RangeStatistics(20.0, 15.8, 5.8, 4.5, -0.05, 3.0),
    RangeStatistics(30.0, 21.5, 7.8, 6.1, 0.00, 3.1),
    RangeStatistics(50.0, 32.5, 11.5, 9.0, 0.05, 3.2),
    RangeStatistics(80.0, 48.3, 16.8, 13.2, 0.10, 3.3),
    RangeStatistics(100.0, 58.5, 20.1, 15.8, 0.15, 3.4),
    RangeStatistics(150.0, 84.0, 28.0, 22.0, 0.20, 3.5),
    RangeStatistics(180.0, 102.0, 33.0, 26.0, 0.22, 3.6),
    RangeStatistics(250.0, 142.0, 44.0, 35.0, 0.28, 3.8),
    RangeStatistics(500.0, 290.0, 78.0, 65.0, 0.35, 4.0),
    RangeStatistics(1000.0, 610.0, 135.0, 115.0, 0.42, 4.4),
    RangeStatistics(2000.0, 1250.0, 220.0, 195.0, 0.50, 4.8),
]


@dataclass
class ImplantDamageModel:
    """Displacement cascade and crystal lattice amorphization metrics.

    Attributes:
        vacancies_per_ion: Number of Frenkel defect pairs generated per incident ion (Kinchin-Pease).
        peak_dpa: Displacements per atom at the damage peak depth.
        damage_peak_depth_nm: Depth of peak nuclear energy loss (~0.8 * Rp).
        amorphization_dose_threshold_cm2: Minimum dose required to produce a continuous amorphous layer.
        is_amorphized: Whether the prescribed dose exceeds the amorphization threshold.
    """
    vacancies_per_ion: float
    peak_dpa: float
    damage_peak_depth_nm: float
    amorphization_dose_threshold_cm2: float
    is_amorphized: bool


@dataclass
class AnnealActivationResult:
    """Post-implant thermal / rapid thermal anneal (RTA) electrical activation.

    Attributes:
        anneal_temperature_c: Anneal temperature in °C.
        anneal_time_s: Anneal duration in seconds.
        active_fraction: Ratio of electrically active dopants to total implanted dose (0.0 to 1.0).
        solid_solubility_limit_cm3: Solid solubility limit C_ss at anneal temperature.
        active_sheet_resistance_ohm_sq: Calculated sheet resistance Rs in ohm/sq via Masetti model.
        junction_depth_nm: Metallurgical junction depth xj in nm at background concentration.
    """
    anneal_temperature_c: float
    anneal_time_s: float
    active_fraction: float
    solid_solubility_limit_cm3: float
    active_sheet_resistance_ohm_sq: float
    junction_depth_nm: float


@dataclass
class ImplantProfilePoint:
    """Concentration profile coordinate."""
    depth_nm: float
    total_dopant_conc_cm3: float
    active_dopant_conc_cm3: float
    dpa: float


@dataclass
class ImplantSimulationResult:
    """Complete ion implantation output result.

    Attributes:
        species: Implanted ion species.
        energy_kev: Nominal tool acceleration energy.
        dose_cm2: Prescribed dose in ions/cm^2 as PhysicalQuantity.
        effective_boron_energy_kev: Equivalent B energy if BF2.
        range_stats: Interpolated range parameters (Rp, delta_Rp, etc.).
        screen_oxide_thickness_nm: Screen oxide thickness used.
        dose_retained_in_silicon_pct: Percentage of dose penetrating into silicon substrate.
        peak_concentration_cm3: Peak volumetric dopant concentration in atoms/cm^3.
        damage: Lattice damage and amorphization analysis.
        activation: Post-anneal electrical activation metrics.
        depth_profile: Depth concentration trajectory points.
    """
    species: ImplantSpecies
    energy_kev: float
    dose_cm2: PhysicalQuantity
    effective_boron_energy_kev: Optional[float]
    range_stats: RangeStatistics
    screen_oxide_thickness_nm: float
    dose_retained_in_silicon_pct: float
    peak_concentration_cm3: float
    damage: ImplantDamageModel
    activation: AnnealActivationResult
    depth_profile: List[ImplantProfilePoint] = field(default_factory=list)


class IonImplantModel:
    """Ion implantation profile simulation and electrical activation engine."""

    def __init__(self) -> None:
        """Initialize ion implant model engine."""
        pass

    def get_range_statistics(
        self,
        species: ImplantSpecies,
        energy_kev: float,
    ) -> RangeStatistics:
        """Interpolate projected range statistics from calibrated Gibbons / SRIM tables.

        For molecular BF2+:
          Uses equivalent boron energy: E_B = E_BF2 * (M_B / M_BF2) = E_BF2 * (10.81 / 48.81) ~ E * (11/49).

        Args:
            species: ImplantSpecies enum.
            energy_kev: Implantation kinetic energy in keV.

        Returns:
            RangeStatistics with interpolated (Rp, delta_Rp, delta_Rlat, skewness, kurtosis).
        """
        if energy_kev <= 0.0:
            raise ValueError(f"Implant energy must be positive, got {energy_kev} keV.")

        if species == ImplantSpecies.BF2:
            # Molecular dissociation: BF2 breaks apart upon surface impact
            # Boron receives 11/49 of the total molecular kinetic energy
            effective_b_energy = energy_kev * (10.81 / 48.81)
            return self._interpolate_table(BORON_RANGE_TABLE, effective_b_energy)
        elif species == ImplantSpecies.BORON:
            return self._interpolate_table(BORON_RANGE_TABLE, energy_kev)
        elif species == ImplantSpecies.PHOSPHORUS:
            return self._interpolate_table(PHOSPHORUS_RANGE_TABLE, energy_kev)
        elif species in (ImplantSpecies.ARSENIC, ImplantSpecies.ANTIMONY):
            return self._interpolate_table(ARSENIC_RANGE_TABLE, energy_kev)
        elif species == ImplantSpecies.INDIUM:
            # Heavy p-type halo: scale from arsenic table using Z / M ratio
            as_stat = self._interpolate_table(ARSENIC_RANGE_TABLE, energy_kev)
            return RangeStatistics(
                energy_kev=energy_kev,
                rp_nm=as_stat.rp_nm * 0.82,
                delta_rp_nm=as_stat.delta_rp_nm * 0.80,
                delta_rlat_nm=as_stat.delta_rlat_nm * 0.80,
                skewness=as_stat.skewness,
                kurtosis=as_stat.kurtosis,
            )
        else:
            return self._interpolate_table(BORON_RANGE_TABLE, energy_kev)

    def _interpolate_table(
        self,
        table: List[RangeStatistics],
        target_energy: float,
    ) -> RangeStatistics:
        """Perform log-log interpolation of range statistics across energy."""
        # Handle boundaries
        if target_energy <= table[0].energy_kev:
            # Power law extrapolation to low energy: Rp ~ E^0.75
            base = table[0]
            ratio = max(0.01, target_energy / base.energy_kev)
            return RangeStatistics(
                energy_kev=target_energy,
                rp_nm=max(1.0, base.rp_nm * (ratio ** 0.75)),
                delta_rp_nm=max(0.8, base.delta_rp_nm * (ratio ** 0.70)),
                delta_rlat_nm=max(0.6, base.delta_rlat_nm * (ratio ** 0.70)),
                skewness=base.skewness,
                kurtosis=base.kurtosis,
            )
        if target_energy >= table[-1].energy_kev:
            base = table[-1]
            ratio = target_energy / base.energy_kev
            return RangeStatistics(
                energy_kev=target_energy,
                rp_nm=base.rp_nm * (ratio ** 0.90),
                delta_rp_nm=base.delta_rp_nm * (ratio ** 0.80),
                delta_rlat_nm=base.delta_rlat_nm * (ratio ** 0.80),
                skewness=base.skewness,
                kurtosis=base.kurtosis,
            )

        # Find enclosing bracket
        for i in range(len(table) - 1):
            e0 = table[i].energy_kev
            e1 = table[i + 1].energy_kev
            if e0 <= target_energy <= e1:
                # Log-log linear interpolation weight
                t = (math.log(target_energy) - math.log(e0)) / (math.log(e1) - math.log(e0))
                rp = math.exp((1.0 - t) * math.log(table[i].rp_nm) + t * math.log(table[i + 1].rp_nm))
                drp = math.exp((1.0 - t) * math.log(table[i].delta_rp_nm) + t * math.log(table[i + 1].delta_rp_nm))
                drlat = math.exp((1.0 - t) * math.log(table[i].delta_rlat_nm) + t * math.log(table[i + 1].delta_rlat_nm))
                skew = (1.0 - t) * table[i].skewness + t * table[i + 1].skewness
                kurt = (1.0 - t) * table[i].kurtosis + t * table[i + 1].kurtosis
                return RangeStatistics(
                    energy_kev=target_energy,
                    rp_nm=rp,
                    delta_rp_nm=drp,
                    delta_rlat_nm=drlat,
                    skewness=skew,
                    kurtosis=kurt,
                )

        return table[0]

    def evaluate_gaussian_concentration(
        self,
        depth_nm: float,
        dose_cm2: float,
        rp_nm: float,
        delta_rp_nm: float,
    ) -> float:
        """Calculate Gaussian profile concentration at depth x.

        Formula:
          N(x) = [Dose / (sqrt(2*pi) * delta_Rp)] * exp(-(x - Rp)^2 / (2 * delta_Rp^2))
          Note: delta_Rp converted to cm (1 nm = 1e-7 cm).

        Returns:
            Concentration in atoms / cm^3.
        """
        drp_cm = delta_rp_nm * 1e-7
        pref = dose_cm2 / (math.sqrt(2.0 * math.pi) * drp_cm)
        arg = -((depth_nm - rp_nm) ** 2) / (2.0 * (delta_rp_nm ** 2))
        if arg < -80.0:
            return 0.0
        return pref * math.exp(arg)

    def evaluate_dual_pearson_concentration(
        self,
        depth_nm: float,
        dose_cm2: float,
        stats: RangeStatistics,
    ) -> float:
        """Calculate Dual Pearson IV distribution capturing random stopping and channeling tail.

        Superposition (Tasch et al. 1989):
          N(x) = (1 - f_c) * P_amorphous(x) + f_c * P_channel(x)
          where f_c is the channeling fraction (~0.05 to 0.15 in <100> silicon).

        Returns:
            Volumetric concentration in atoms / cm^3.
        """
        f_channel = 0.08  # Typical channeling fraction for 7° tilt
        rp_rand = stats.rp_nm
        drp_rand = stats.delta_rp_nm

        # Channeling tail reaches deeper with larger straggle
        rp_chan = stats.rp_nm * 1.45
        drp_chan = stats.delta_rp_nm * 1.85

        # Primary random peak
        n_rand = self.evaluate_gaussian_concentration(depth_nm, dose_cm2 * (1.0 - f_channel), rp_rand, drp_rand)

        # Asymmetric skew correction on random peak
        if stats.skewness != 0.0:
            z = (depth_nm - rp_rand) / max(0.1, drp_rand)
            skew_mod = 1.0 + (stats.skewness / 6.0) * (z ** 3 - 3.0 * z)
            n_rand *= max(0.1, min(2.5, skew_mod))

        # Channeling tail
        n_chan = self.evaluate_gaussian_concentration(depth_nm, dose_cm2 * f_channel, rp_chan, drp_chan)

        return max(0.0, n_rand + n_chan)

    def calculate_damage_and_amorphization(
        self,
        species: ImplantSpecies,
        energy_kev: float,
        dose_cm2: float,
        rp_nm: float,
    ) -> ImplantDamageModel:
        """Evaluate lattice displacement cascades and amorphization threshold.

        Modified Kinchin-Pease / Norgett-Robinson-Torrens (NRT) Model:
          N_disp = (0.8 * E_nuclear) / (2 * E_d)
          where E_d ~ 15 eV is the threshold displacement energy for Si.

        Amorphization Dose Threshold:
          Boron: ~2e16 cm^-2 (light ion, high threshold)
          Phosphorus: ~1.2e15 cm^-2
          Arsenic: ~2.0e14 cm^-2 (heavy ion, low threshold)
        """
        ed_ev = 15.0  # Si threshold displacement energy

        # Nuclear stopping fraction of energy (Ziegler 1985)
        # Heavy ions (As) transfer >70% of energy to nuclear collisions; light ions (B) transfer <20%
        if species in (ImplantSpecies.BORON, ImplantSpecies.BF2):
            nucl_fraction = 0.18
            crit_amorph_dose = 2.0e16  # cm^-2
        elif species == ImplantSpecies.PHOSPHORUS:
            nucl_fraction = 0.45
            crit_amorph_dose = 1.2e15
        elif species in (ImplantSpecies.ARSENIC, ImplantSpecies.ANTIMONY, ImplantSpecies.INDIUM):
            nucl_fraction = 0.75
            crit_amorph_dose = 2.0e14
        else:
            nucl_fraction = 0.30
            crit_amorph_dose = 5.0e15

        e_nucl_ev = energy_kev * 1e3 * nucl_fraction
        vacancies_per_ion = max(1.0, (0.8 * e_nucl_ev) / (2.0 * ed_ev))

        # Peak damage depth is slightly shallower than Rp (~0.8 * Rp)
        damage_depth = rp_nm * 0.80

        # Peak DPA (displacements per atom) = (Dose * Vacancies_per_ion / delta_Rp) / Silicon_Density
        peak_disp_cm3 = (dose_cm2 * vacancies_per_ion) / (max(1.0, rp_nm) * 1e-7)
        peak_dpa = peak_disp_cm3 / SILICON_ATOMIC_DENSITY_CM3

        is_am = (dose_cm2 >= crit_amorph_dose)

        return ImplantDamageModel(
            vacancies_per_ion=vacancies_per_ion,
            peak_dpa=peak_dpa,
            damage_peak_depth_nm=damage_depth,
            amorphization_dose_threshold_cm2=crit_amorph_dose,
            is_amorphized=is_am,
        )

    def calculate_electrical_activation(
        self,
        species: ImplantSpecies,
        dose_cm2: float,
        anneal_temperature_c: float = 1000.0,
        anneal_time_s: float = 10.0,
        background_doping_cm3: float = 1.0e15,
        rp_nm: float = 50.0,
        delta_rp_nm: float = 20.0,
    ) -> AnnealActivationResult:
        """Model thermal activation kinetics, solid solubility limit, and sheet resistance.

        Solubility Limits in Silicon (Trumbore 1960):
          - Boron: ~3.5e20 cm^-3 at 1000°C
          - Phosphorus: ~1.2e21 cm^-3 at 1000°C
          - Arsenic: ~1.8e21 cm^-3 at 1000°C

        Masetti Mobility & Sheet Resistance Model (1983):
          mu(N) = mu_min + (mu_max - mu_min) / [1 + (N / N_ref)^alpha] - mu1 / [1 + (C_s / N)^beta]
          R_sheet = 1 / [q * integral(mu(N) * N(x) dx)]
        """
        temp_k = anneal_temperature_c + 273.15
        kt = KB_EV_PER_K * temp_k

        # Solid solubility limits C_ss(T) = C_0 * exp(-E_ss / kT)
        if species in (ImplantSpecies.BORON, ImplantSpecies.BF2):
            c_ss = 3.5e20 * math.exp(-0.25 * (1273.15 - temp_k) / 100.0)
            mu_min, mu_max, n_ref, alpha = 45.0, 480.0, 2.2e17, 0.72
        elif species == ImplantSpecies.PHOSPHORUS:
            c_ss = 1.2e21 * math.exp(-0.20 * (1273.15 - temp_k) / 100.0)
            mu_min, mu_max, n_ref, alpha = 65.0, 1400.0, 1.1e17, 0.70
        else:  # Arsenic
            c_ss = 1.8e21 * math.exp(-0.22 * (1273.15 - temp_k) / 100.0)
            mu_min, mu_max, n_ref, alpha = 52.0, 1420.0, 9.6e16, 0.68

        # Activation fraction kinetics: alpha(T, t) = alpha_max * [1 - exp(-t / tau)]
        # Activation energy for solid-phase epitaxial regrowth (SPER) ~ 2.7 eV, dopant substitution ~ 4.5 eV
        tau_act = 1e-12 * math.exp(2.8 / kt)  # seconds
        trans_factor = 1.0 - math.exp(-max(0.1, anneal_time_s) / max(1e-6, tau_act))
        # Temperature threshold: minimal activation below 700°C, high above 950°C
        temp_factor = min(1.0, max(0.05, (anneal_temperature_c - 600.0) / 400.0))
        act_fraction = min(0.98, max(0.01, temp_factor * trans_factor))

        # Peak concentration
        drp_cm = delta_rp_nm * 1e-7
        peak_conc = dose_cm2 / (math.sqrt(2.0 * math.pi) * drp_cm)
        active_peak = min(c_ss, peak_conc * act_fraction)

        # Metallurgical junction depth xj where active dopant equals background doping:
        # N(xj) = N_bg => (xj - Rp)^2 = 2 * delta_Rp^2 * ln(active_peak / N_bg)
        if active_peak > background_doping_cm3:
            ln_ratio = math.log(active_peak / background_doping_cm3)
            xj_nm = rp_nm + delta_rp_nm * math.sqrt(2.0 * ln_ratio)
        else:
            xj_nm = rp_nm

        # Average mobility via Masetti formula
        effective_doping = active_peak * 0.5
        mu_avg = mu_min + (mu_max - mu_min) / (1.0 + (effective_doping / n_ref) ** alpha)

        # Sheet resistance: Rs ~ 1 / (q * active_dose * mu_avg)
        active_dose = dose_cm2 * act_fraction
        if active_dose > 1e11:
            rs_ohm_sq = 1.0 / (E_CHARGE_COULOMBS * active_dose * mu_avg)
        else:
            rs_ohm_sq = 1.0e6

        return AnnealActivationResult(
            anneal_temperature_c=anneal_temperature_c,
            anneal_time_s=anneal_time_s,
            active_fraction=act_fraction,
            solid_solubility_limit_cm3=c_ss,
            active_sheet_resistance_ohm_sq=rs_ohm_sq,
            junction_depth_nm=xj_nm,
        )

    def simulate_implantation(
        self,
        species: ImplantSpecies,
        energy_val: Union[float, PhysicalQuantity],
        dose_val: Union[float, PhysicalQuantity],
        screen_oxide_nm: Union[float, PhysicalQuantity] = 0.0,
        use_dual_pearson: bool = True,
        anneal_temperature_c: float = 1000.0,
        anneal_time_s: float = 10.0,
        background_doping_cm3: float = 1.0e15,
        profile_depth_limit_nm: Optional[float] = None,
        profile_points_count: int = 200,
    ) -> ImplantSimulationResult:
        """Simulate ion implantation with range, damage, screen oxide, and electrical activation.

        Args:
            species: ImplantSpecies enum (BORON, BF2, PHOSPHORUS, ARSENIC).
            energy_val: Implantation energy (scalar in keV or PhysicalQuantity).
            dose_val: Implantation dose (scalar in ions/cm^2 or PhysicalQuantity).
            screen_oxide_nm: Screen dielectric oxide thickness in nm (shifts profile).
            use_dual_pearson: If True, uses dual Pearson IV distribution with channeling tail.
            anneal_temperature_c: Post-implant anneal temperature in °C.
            anneal_time_s: Anneal duration in seconds.
            background_doping_cm3: Substrate background doping level.
            profile_depth_limit_nm: Maximum simulation depth in nm.
            profile_points_count: Number of spatial depth points.

        Returns:
            ImplantSimulationResult with complete profiles and metrics.
        """
        if isinstance(energy_val, PhysicalQuantity):
            energy_kev = energy_val.to_unit("keV").value
        else:
            energy_kev = float(energy_val)

        if isinstance(dose_val, PhysicalQuantity):
            dose_cm2 = dose_val.to_unit("ions/cm^2").value
            dose_unc = dose_val.uncertainty
        else:
            dose_cm2 = float(dose_val)
            dose_unc = dose_cm2 * 0.01  # 1% Faraday cup calibration

        if isinstance(screen_oxide_nm, PhysicalQuantity):
            tox_nm = screen_oxide_nm.to_unit("nm").value
        else:
            tox_nm = float(screen_oxide_nm)

        # Range statistics
        stats = self.get_range_statistics(species, energy_kev)
        eff_b_energy = energy_kev * (10.81 / 48.81) if species == ImplantSpecies.BF2 else None

        # Screen oxide offset calculation:
        # SiO2 has atomic stopping density close to Si (density 2.27 vs 2.33 g/cm^3)
        # Ratio of stopping power S_ox / S_si ~ 1.02
        s_ratio = 1.02
        tox_eff_nm = tox_nm * s_ratio

        # Dose lost in screen oxide: integral of profile from 0 to tox
        # For Gaussian: Dose_loss = Dose * 0.5 * [1 + erf((tox - Rp) / (sqrt(2) * delta_Rp))]
        if tox_nm > 0.0:
            erf_arg = (tox_eff_nm - stats.rp_nm) / (math.sqrt(2.0) * max(0.1, stats.delta_rp_nm))
            erf_val = math.erf(erf_arg)
            dose_loss_fraction = max(0.0, min(1.0, 0.5 * (1.0 + erf_val)))
            silicon_dose_retention_pct = (1.0 - dose_loss_fraction) * 100.0
            retained_dose_cm2 = dose_cm2 * (1.0 - dose_loss_fraction)
        else:
            silicon_dose_retention_pct = 100.0
            retained_dose_cm2 = dose_cm2

        # Effective projected range inside silicon substrate: Rp_si = Rp - Tox_eff
        rp_in_si = max(0.0, stats.rp_nm - tox_eff_nm)

        # Damage calculation
        damage = self.calculate_damage_and_amorphization(species, energy_kev, dose_cm2, stats.rp_nm)

        # Activation calculation
        activation = self.calculate_electrical_activation(
            species=species,
            dose_cm2=retained_dose_cm2,
            anneal_temperature_c=anneal_temperature_c,
            anneal_time_s=anneal_time_s,
            background_doping_cm3=background_doping_cm3,
            rp_nm=rp_in_si,
            delta_rp_nm=stats.delta_rp_nm,
        )

        # Peak concentration inside silicon
        drp_cm = stats.delta_rp_nm * 1e-7
        peak_conc = retained_dose_cm2 / (math.sqrt(2.0 * math.pi) * drp_cm)

        # Depth profile trajectory
        if profile_depth_limit_nm is None:
            max_depth = max(50.0, rp_in_si + 5.0 * stats.delta_rp_nm)
        else:
            max_depth = profile_depth_limit_nm

        depth_points: List[ImplantProfilePoint] = []
        dx = max_depth / max(1, profile_points_count)

        for i in range(profile_points_count + 1):
            x = i * dx
            if use_dual_pearson:
                conc = self.evaluate_dual_pearson_concentration(x + tox_eff_nm, dose_cm2, stats)
            else:
                conc = self.evaluate_gaussian_concentration(x, retained_dose_cm2, rp_in_si, stats.delta_rp_nm)

            active_conc = min(activation.solid_solubility_limit_cm3, conc * activation.active_fraction)

            # Local DPA profile: damage peaks at ~0.8 * Rp
            dpa_x = damage.peak_dpa * math.exp(-((x - damage.damage_peak_depth_nm) ** 2) / (2.0 * (stats.delta_rp_nm ** 2)))

            depth_points.append(
                ImplantProfilePoint(
                    depth_nm=x,
                    total_dopant_conc_cm3=conc,
                    active_dopant_conc_cm3=active_conc,
                    dpa=dpa_x,
                )
            )

        dose_qty = implant_dose(
            value=dose_cm2,
            unit="ions/cm^2",
            uncertainty=dose_unc,
            source=f"Implanter Faraday Cup ({species.value})",
        )

        return ImplantSimulationResult(
            species=species,
            energy_kev=energy_kev,
            dose_cm2=dose_qty,
            effective_boron_energy_kev=eff_b_energy,
            range_stats=stats,
            screen_oxide_thickness_nm=tox_nm,
            dose_retained_in_silicon_pct=silicon_dose_retention_pct,
            peak_concentration_cm3=peak_conc,
            damage=damage,
            activation=activation,
            depth_profile=depth_points,
        )
