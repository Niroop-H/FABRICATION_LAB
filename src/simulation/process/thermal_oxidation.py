"""Thermal Oxidation Process Simulation Models.

This module implements the Deal-Grove linear-parabolic oxidation model and its
modern extensions for silicon thermal oxidation in microelectronics fabrication.

Theoretical & Empirical Foundations:
  - Deal, B. E., & Grove, A. S. (1965). "General Relationship for the Thermal
    Oxidation of Silicon". Journal of Applied Physics, 36(12), 3770-3778.
  - Massoud, H. Z., Plummer, J. D., & Irene, E. A. (1985). "Thermal oxidation of
    silicon in dry oxygen: Growth-rate enhancement in the thin regime".
    J. Electrochem. Soc., 132(7), 1745-1753.
  - Razouk, R. R., Lie, L. N., & Deal, B. E. (1982). "Kinetics of High Pressure
    Oxidation of Silicon in Pyrogenic Steam". J. Electrochem. Soc., 128(10), 2214-2220.
  - Hess, D. W., & Deal, B. E. (1977). "Kinetics of the Thermal Oxidation of
    Silicon in O2/HCl Mixtures". J. Electrochem. Soc., 124(5), 735-739.
  - Plummer, J. D., Deal, M. D., & Griffin, P. B. (2000). "Silicon VLSI
    Technology: Fundamentals, Practice and Modeling". Prentice Hall.

Key Physical Phenomena Modeled:
  1. Deal-Grove linear-parabolic kinetics: x^2 + A*x = B*(t + tau)
  2. Surface reaction limited (linear constant B/A) vs oxidant diffusion limited
     (parabolic constant B)
  3. Arrhenius temperature dependence for dry O2 and wet H2O ambients
  4. Orientation dependence: Si(100), Si(111), Si(110) surface bond density ratios
  5. Thin oxide growth enhancement regime (< 30 nm) via Massoud empirical formulation
  6. Chlorinated oxidation (HCl / Trans-LC) enhancement and mobile ion passivation
  7. Heavy dopant concentration effects (Phosphorus, Arsenic, Boron segregation)
  8. Pilling-Bedworth volume expansion (44% Silicon consumption ratio)
  9. Uncertainty propagation on final oxide thickness
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
        pressure,
        temperature,
    )
except ImportError:
    try:
        from simulation.core.units import (
            PhysicalQuantity,
            convert_value,
            duration,
            film_thickness,
            pressure,
            temperature,
        )
    except ImportError:
        try:
            from core.units import (
                PhysicalQuantity,
                convert_value,
                duration,
                film_thickness,
                pressure,
                temperature,
            )
        except ImportError:
            from ..core.units import (  # type: ignore
                PhysicalQuantity,
                convert_value,
                duration,
                film_thickness,
                pressure,
                temperature,
            )


# Boltzmann constant in eV/K
KB_EV_PER_K: float = 8.617333262e-5

# Silicon volumetric consumption ratio: thickness of Si consumed per thickness of SiO2 grown
# Based on molecular weights and densities of Si (28.09 g/mol, 2.33 g/cm^3) and SiO2 (60.08 g/mol, 2.27 g/cm^3)
SI_CONSUMPTION_RATIO: float = 0.44


class OxidationAmbient(str, Enum):
    """Oxidizing furnace gas ambient."""
    DRY_O2 = "DRY_O2"
    WET_H2O = "WET_H2O"


class SiliconOrientation(str, Enum):
    """Silicon substrate crystallographic orientation."""
    ORIENTATION_100 = "100"
    ORIENTATION_111 = "111"
    ORIENTATION_110 = "110"


class DopantType(str, Enum):
    """Silicon substrate background or well doping species."""
    UNDOPED = "UNDOPED"
    BORON = "BORON"
    PHOSPHORUS = "PHOSPHORUS"
    ARSENIC = "ARSENIC"


@dataclass(frozen=True)
class DealGroveParameters:
    """Deal-Grove kinetic rate parameters at a specific process temperature and pressure.

    Attributes:
        b_parabolic: Parabolic rate constant B in nm^2 / s.
        b_over_a_linear: Linear rate constant (B/A) in nm / s.
        a_parameter: Characteristic thickness parameter A = B / (B/A) in nm.
        tau: Initial time offset accounting for initial oxide in seconds.
        regime_transition_thickness: A / 2 in nm (crossover from linear to parabolic).
        temperature_k: Temperature in Kelvin.
        pressure_atm: Partial pressure in atmospheres.
        orientation: Substrate crystallographic orientation.
        ambient: Oxidation ambient.
    """
    b_parabolic: float
    b_over_a_linear: float
    a_parameter: float
    tau: float
    regime_transition_thickness: float
    temperature_k: float
    pressure_atm: float
    orientation: SiliconOrientation
    ambient: OxidationAmbient


@dataclass
class OxidationProfilePoint:
    """Data point along the oxidation trajectory."""
    time_s: float
    oxide_thickness_nm: float
    growth_rate_nm_per_s: float
    si_consumed_nm: float


@dataclass
class OxidationResult:
    """Comprehensive output of a thermal oxidation simulation.

    Attributes:
        final_thickness: Final oxide thickness as a PhysicalQuantity with uncertainty.
        silicon_consumed: Total silicon thickness consumed as a PhysicalQuantity.
        deal_grove_params: Calibrated kinetic parameters.
        time_series: Time evolution of thickness and growth rate.
        thin_regime_enhancement_applied: Whether thin-oxide enhancement was active.
        chlorine_enhancement_factor: Multiplier applied due to HCl content.
        dopant_enhancement_factor: Multiplier applied due to heavy doping.
    """
    final_thickness: PhysicalQuantity
    silicon_consumed: PhysicalQuantity
    deal_grove_params: DealGroveParameters
    time_series: List[OxidationProfilePoint] = field(default_factory=list)
    thin_regime_enhancement_applied: bool = False
    chlorine_enhancement_factor: float = 1.0
    dopant_enhancement_factor: float = 1.0


class ThermalOxidationModel:
    """Physically grounded Deal-Grove oxidation simulator for silicon wafers.

    Literature Kinetic References:
      - Plummer et al. (2000), Table 6-1, 6-2:
        Dry O2:
          B = 7.72e2 um^2/hr * exp(-1.24 eV / kT)
          (B/A)_111 = 6.23e6 um/hr * exp(-2.00 eV / kT)
          (B/A)_100 = (B/A)_111 / 1.68
        Wet H2O (Pyrogenic Steam):
          B = 3.86e2 um^2/hr * exp(-0.78 eV / kT)
          (B/A)_111 = 1.63e8 um/hr * exp(-2.05 eV / kT)
          (B/A)_100 = (B/A)_111 / 1.68
    """

    # Activation energies in eV
    EA_B_DRY: float = 1.24
    EA_BA_DRY: float = 2.00
    EA_B_WET: float = 0.78
    EA_BA_WET: float = 2.05

    # Pre-exponential factors in nm^2/s and nm/s
    # 7.72e2 um^2/hr = 7.72e2 * 1e6 nm^2 / 3600 s = 2.14444e5 nm^2/s
    B0_DRY_NM2_S: float = 2.144444e5
    # 6.23e6 um/hr = 6.23e6 * 1e3 nm / 3600 s = 1.730556e6 nm/s
    BA0_DRY_111_NM_S: float = 1.730556e6

    # 3.86e2 um^2/hr = 3.86e2 * 1e6 nm^2 / 3600 s = 1.072222e5 nm^2/s
    B0_WET_NM2_S: float = 1.072222e5
    # 1.63e8 um/hr = 1.63e8 * 1e3 nm / 3600 s = 4.527778e7 nm/s
    BA0_WET_111_NM_S: float = 4.527778e7

    # Crystallographic Orientation Multipliers relative to (111)
    # Available surface silicon atom densities:
    # (111): 1.18e15 atoms/cm^2
    # (110): 9.60e14 atoms/cm^2 -> ratio ~ 0.814
    # (100): 6.78e14 atoms/cm^2 -> ratio 1 / 1.68 ~ 0.5952
    ORIENTATION_FACTORS: Dict[SiliconOrientation, float] = {
        SiliconOrientation.ORIENTATION_111: 1.0,
        SiliconOrientation.ORIENTATION_100: 1.0 / 1.68,  # ~0.595238
        SiliconOrientation.ORIENTATION_110: 1.45 / 1.68,  # ~0.863095
    }

    # Massoud Thin-Oxide Enhancement Parameters (Dry O2, thickness < 30 nm)
    # dx/dt_enhanced = dx/dt_DG + Ce * exp(-x / Le)
    # Plummer et al., Massoud & Plummer (1985)
    LE_THIN_REGIME_NM: float = 7.0  # Characteristic decay length in nm
    CE0_THIN_REGIME_NM_S: float = 4.333e6  # Pre-exponential factor (~2.6e8 nm/min)
    EA_THIN_REGIME_EV: float = 2.37  # Activation energy in eV

    def __init__(self) -> None:
        """Initialize thermal oxidation model engine."""
        pass

    def calculate_rate_constants(
        self,
        temp_c: float,
        ambient: OxidationAmbient = OxidationAmbient.DRY_O2,
        orientation: SiliconOrientation = SiliconOrientation.ORIENTATION_100,
        pressure_atm: float = 1.0,
        hcl_percentage: float = 0.0,
        dopant_type: DopantType = DopantType.UNDOPED,
        dopant_conc_cm3: float = 0.0,
        initial_thickness_nm: float = 0.0,
    ) -> DealGroveParameters:
        """Calculate Deal-Grove rate constants B and B/A at the given process condition.

        Args:
            temp_c: Furnace temperature in Celsius (valid range: 700 to 1250 °C).
            ambient: DRY_O2 or WET_H2O pyrogenic steam.
            orientation: Substrate crystallographic orientation.
            pressure_atm: Ambient oxidant pressure in atmospheres (0.1 to 25 atm).
            hcl_percentage: Chlorine additive percentage (0.0 to 10.0 %).
            dopant_type: Substrate dopant species.
            dopant_conc_cm3: Substrate dopant concentration in atoms/cm^3.
            initial_thickness_nm: Initial native or pre-existing oxide in nm.

        Returns:
            DealGroveParameters containing calibrated constants.

        Raises:
            ValueError: If inputs exceed physically valid ranges.
        """
        if not (650.0 <= temp_c <= 1300.0):
            raise ValueError(
                f"Oxidation temperature {temp_c}°C outside valid thermal range [650, 1300]°C."
            )
        if pressure_atm <= 0.0 or pressure_atm > 30.0:
            raise ValueError(
                f"Oxidation pressure {pressure_atm} atm outside valid range (0, 30] atm."
            )
        if not (0.0 <= hcl_percentage <= 10.0):
            raise ValueError(
                f"HCl percentage {hcl_percentage}% outside valid range [0, 10]%."
            )

        temp_k = temp_c + 273.15
        kt = KB_EV_PER_K * temp_k

        # Calculate nominal Arrhenius constants
        if ambient == OxidationAmbient.DRY_O2:
            b_nom = self.B0_DRY_NM2_S * math.exp(-self.EA_B_DRY / kt)
            ba_111 = self.BA0_DRY_111_NM_S * math.exp(-self.EA_BA_DRY / kt)
            # Pressure dependence: B and B/A scale linearly with dry O2 partial pressure
            b = b_nom * (pressure_atm ** 1.0)
            ba = ba_111 * self.ORIENTATION_FACTORS[orientation] * (pressure_atm ** 1.0)
        else:  # WET_H2O
            b_nom = self.B0_WET_NM2_S * math.exp(-self.EA_B_WET / kt)
            ba_111 = self.BA0_WET_111_NM_S * math.exp(-self.EA_BA_WET / kt)
            # Razouk et al. (1982): For steam, B scales linearly with P at typical fab pressures
            b = b_nom * (pressure_atm ** 1.0)
            ba = ba_111 * self.ORIENTATION_FACTORS[orientation] * (pressure_atm ** 1.0)

        # Chlorine (HCl) enhancement factors (Hess & Deal 1977)
        # Adding 1-3% HCl enhances B by 1.2-1.8x and B/A by 1.1-1.5x at 1000°C
        if hcl_percentage > 0.0:
            # Empirical polynomial enhancement derived from Hess & Deal
            temp_ratio = 1273.15 / temp_k
            cl_factor_b = 1.0 + (0.18 * hcl_percentage) * temp_ratio
            cl_factor_ba = 1.0 + (0.12 * hcl_percentage) * temp_ratio
            b *= cl_factor_b
            ba *= cl_factor_ba

        # Heavy doping effect (Ho & Plummer 1979)
        # High n-type doping (Phosphorus, Arsenic > 1e19 cm^-3) enhances B/A through vacancy generation
        if dopant_type in (DopantType.PHOSPHORUS, DopantType.ARSENIC) and dopant_conc_cm3 > 1e19:
            # Intrinsic carrier concentration ni(T)
            # ni(T) in cm^-3 approx 3.87e16 * T^(1.5) * exp(-0.605 / kt)
            ni = 3.87e16 * (temp_k ** 1.5) * math.exp(-0.605 / kt)
            dopant_ratio = max(1.0, dopant_conc_cm3 / max(1e18, ni))
            enhancement = 1.0 + 0.35 * math.log10(dopant_ratio)
            ba *= enhancement
        elif dopant_type == DopantType.BORON and dopant_conc_cm3 > 1e19:
            # Boron slightly enhances B due to incorporation into growing oxide softening network
            b *= (1.0 + 0.15 * math.log10(dopant_conc_cm3 / 1e19))

        a = b / ba
        x0 = max(0.0, initial_thickness_nm)
        # tau accounts for pre-existing initial oxide: x0^2 + A*x0 = B*tau
        tau = (x0 ** 2 + a * x0) / b
        regime_trans = a / 2.0

        return DealGroveParameters(
            b_parabolic=b,
            b_over_a_linear=ba,
            a_parameter=a,
            tau=tau,
            regime_transition_thickness=regime_trans,
            temperature_k=temp_k,
            pressure_atm=pressure_atm,
            orientation=orientation,
            ambient=ambient,
        )

    def simulate_oxidation(
        self,
        temperature_c: Union[float, PhysicalQuantity],
        time_seconds: Union[float, PhysicalQuantity],
        ambient: OxidationAmbient = OxidationAmbient.DRY_O2,
        initial_thickness_nm: Union[float, PhysicalQuantity] = 2.0,
        orientation: SiliconOrientation = SiliconOrientation.ORIENTATION_100,
        pressure_val: Union[float, PhysicalQuantity] = 1.0,
        pressure_unit: str = "atm",
        hcl_percentage: float = 0.0,
        dopant_type: DopantType = DopantType.UNDOPED,
        dopant_conc_cm3: float = 0.0,
        enable_thin_oxide_enhancement: bool = True,
        time_steps: int = 100,
    ) -> OxidationResult:
        """Simulate thermal oxide growth with full kinetic modeling.

        Args:
            temperature_c: Process temperature (scalar in °C or PhysicalQuantity).
            time_seconds: Total oxidation duration (scalar in s or PhysicalQuantity).
            ambient: Gas chemistry (DRY_O2 or WET_H2O).
            initial_thickness_nm: Pre-existing oxide thickness in nm (default 2.0 nm native oxide).
            orientation: Silicon wafer crystal orientation ((100), (111), (110)).
            pressure_val: Furnace ambient pressure.
            pressure_unit: Unit for pressure_val if scalar ('atm', 'Torr', 'bar').
            hcl_percentage: Added HCl concentration in volume % (0 to 10%).
            dopant_type: Substrate dopant species.
            dopant_conc_cm3: Dopant concentration in atoms/cm^3.
            enable_thin_oxide_enhancement: If True, applies Massoud empirical model for dry thin oxide.
            time_steps: Number of trajectory sample points.

        Returns:
            OxidationResult with final thickness, uncertainty, and trajectory.
        """
        # Extract scalar magnitudes
        if isinstance(temperature_c, PhysicalQuantity):
            t_degc = temperature_c.to_unit("degC").value
            temp_uncertainty = temperature_c.uncertainty
        else:
            t_degc = float(temperature_c)
            temp_uncertainty = 0.5  # Default thermocouple 1-sigma ±0.5°C

        if isinstance(time_seconds, PhysicalQuantity):
            t_sec = time_seconds.to_unit("s").value
        else:
            t_sec = float(time_seconds)

        if isinstance(initial_thickness_nm, PhysicalQuantity):
            x_init = initial_thickness_nm.to_unit("nm").value
        else:
            x_init = float(initial_thickness_nm)

        if isinstance(pressure_val, PhysicalQuantity):
            p_atm = pressure_val.to_unit("atm").value
        else:
            p_atm = convert_value(float(pressure_val), pressure_unit, "atm")

        # Kinetic parameters
        params = self.calculate_rate_constants(
            temp_c=t_degc,
            ambient=ambient,
            orientation=orientation,
            pressure_atm=p_atm,
            hcl_percentage=hcl_percentage,
            dopant_type=dopant_type,
            dopant_conc_cm3=dopant_conc_cm3,
            initial_thickness_nm=x_init,
        )

        b = params.b_parabolic
        a = params.a_parameter
        tau = params.tau

        # Determine if Massoud thin enhancement should be numerically integrated
        use_thin_enhancement = (
            enable_thin_oxide_enhancement
            and ambient == OxidationAmbient.DRY_O2
            and (x_init < 35.0)
        )

        time_series: List[OxidationProfilePoint] = []
        dt = t_sec / max(1, time_steps)
        current_time = 0.0
        current_x = x_init

        # Thin enhancement rate constant Ce(T)
        kt = KB_EV_PER_K * params.temperature_k
        ce_rate = self.CE0_THIN_REGIME_NM_S * math.exp(-self.EA_THIN_REGIME_EV / kt)

        # Initial point
        rate_0 = (b / (2.0 * current_x + a)) + (
            ce_rate * math.exp(-current_x / self.LE_THIN_REGIME_NM) if use_thin_enhancement else 0.0
        )
        time_series.append(
            OxidationProfilePoint(
                time_s=0.0,
                oxide_thickness_nm=current_x,
                growth_rate_nm_per_s=rate_0,
                si_consumed_nm=current_x * SI_CONSUMPTION_RATIO,
            )
        )

        if not use_thin_enhancement:
            # Pure analytical Deal-Grove solution: x(t) = [-A + sqrt(A^2 + 4B(t + tau))] / 2
            for step in range(1, time_steps + 1):
                t_val = step * dt
                # Deal-Grove quadratic root
                disc = (a ** 2) + 4.0 * b * (t_val + tau)
                x_val = (-a + math.sqrt(max(0.0, disc))) / 2.0
                rate_val = b / (2.0 * x_val + a)
                time_series.append(
                    OxidationProfilePoint(
                        time_s=t_val,
                        oxide_thickness_nm=x_val,
                        growth_rate_nm_per_s=rate_val,
                        si_consumed_nm=x_val * SI_CONSUMPTION_RATIO,
                    )
                )
            final_x = time_series[-1].oxide_thickness_nm
        else:
            # Numerical integration via 4th-order Runge-Kutta for Massoud differential equation:
            # dx/dt = B / (2x + A) + Ce * exp(-x / Le)
            def dxdt(x_pos: float) -> float:
                dg_term = b / (2.0 * max(0.0, x_pos) + a)
                thin_term = ce_rate * math.exp(-max(0.0, x_pos) / self.LE_THIN_REGIME_NM)
                return dg_term + thin_term

            for step in range(1, time_steps + 1):
                # RK4 step
                k1 = dxdt(current_x)
                k2 = dxdt(current_x + 0.5 * dt * k1)
                k3 = dxdt(current_x + 0.5 * dt * k2)
                k4 = dxdt(current_x + dt * k3)
                current_x += (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
                current_time += dt

                rate_val = dxdt(current_x)
                time_series.append(
                    OxidationProfilePoint(
                        time_s=current_time,
                        oxide_thickness_nm=current_x,
                        growth_rate_nm_per_s=rate_val,
                        si_consumed_nm=current_x * SI_CONSUMPTION_RATIO,
                    )
                )
            final_x = current_x

        # Uncertainty calculation:
        # Propagate temperature uncertainty through activation energy
        # d(ln(B))/dT = Ea / (k*T^2), d(ln(BA))/dT = Ea_ba / (k*T^2)
        # fractional uncertainty in thickness dx/x ~ 0.5 * (Ea / (k*T^2)) * dT
        effective_ea = 0.5 * (self.EA_B_DRY + self.EA_BA_DRY) if ambient == OxidationAmbient.DRY_O2 else 0.5 * (self.EA_B_WET + self.EA_BA_WET)
        fractional_unc_temp = (effective_ea / (KB_EV_PER_K * (params.temperature_k ** 2))) * temp_uncertainty
        # Combine with nominal metrology/gas flow uncertainty (2.0%)
        total_fractional_unc = math.hypot(fractional_unc_temp, 0.02)
        thickness_unc = max(0.15, final_x * total_fractional_unc)

        si_consumed_val = final_x * SI_CONSUMPTION_RATIO
        si_consumed_unc = thickness_unc * SI_CONSUMPTION_RATIO

        final_thickness_qty = film_thickness(
            thickness=final_x,
            unit="nm",
            uncertainty=thickness_unc,
            source=f"Deal-Grove Model ({ambient.value}, {t_degc:.1f}°C, {t_sec:.0f}s)",
        )

        si_consumed_qty = film_thickness(
            thickness=si_consumed_val,
            unit="nm",
            uncertainty=si_consumed_unc,
            source="Pilling-Bedworth Si Consumption (0.44 ratio)",
        )

        cl_factor = 1.0 + (0.15 * hcl_percentage) if hcl_percentage > 0 else 1.0
        dop_factor = params.b_over_a_linear / (params.b_parabolic / params.a_parameter)

        return OxidationResult(
            final_thickness=final_thickness_qty,
            silicon_consumed=si_consumed_qty,
            deal_grove_params=params,
            time_series=time_series,
            thin_regime_enhancement_applied=use_thin_enhancement,
            chlorine_enhancement_factor=cl_factor,
            dopant_enhancement_factor=dop_factor,
        )

    def time_to_grow_thickness(
        self,
        target_thickness_nm: Union[float, PhysicalQuantity],
        temperature_c: Union[float, PhysicalQuantity],
        ambient: OxidationAmbient = OxidationAmbient.DRY_O2,
        initial_thickness_nm: Union[float, PhysicalQuantity] = 2.0,
        orientation: SiliconOrientation = SiliconOrientation.ORIENTATION_100,
        pressure_val: Union[float, PhysicalQuantity] = 1.0,
        pressure_unit: str = "atm",
        hcl_percentage: float = 0.0,
    ) -> PhysicalQuantity:
        """Calculate required oxidation time to reach a target oxide thickness.

        Using the inverted Deal-Grove relationship:
          t = (x_target^2 - x_0^2)/B + (x_target - x_0)/(B/A)

        Args:
            target_thickness_nm: Target film thickness in nm.
            temperature_c: Furnace temperature in °C.
            ambient: DRY_O2 or WET_H2O.
            initial_thickness_nm: Pre-existing oxide in nm.
            orientation: Substrate orientation.
            pressure_val: Furnace pressure.
            pressure_unit: Unit for pressure_val.
            hcl_percentage: HCl volume %.

        Returns:
            Required duration as a PhysicalQuantity in seconds.
        """
        if isinstance(target_thickness_nm, PhysicalQuantity):
            x_target = target_thickness_nm.to_unit("nm").value
        else:
            x_target = float(target_thickness_nm)

        if isinstance(initial_thickness_nm, PhysicalQuantity):
            x_0 = initial_thickness_nm.to_unit("nm").value
        else:
            x_0 = float(initial_thickness_nm)

        if x_target <= x_0:
            return duration(0.0, "s", source="Deal-Grove Inversion (Target <= Initial)")

        if isinstance(temperature_c, PhysicalQuantity):
            t_degc = temperature_c.to_unit("degC").value
        else:
            t_degc = float(temperature_c)

        if isinstance(pressure_val, PhysicalQuantity):
            p_atm = pressure_val.to_unit("atm").value
        else:
            p_atm = convert_value(float(pressure_val), pressure_unit, "atm")

        params = self.calculate_rate_constants(
            temp_c=t_degc,
            ambient=ambient,
            orientation=orientation,
            pressure_atm=p_atm,
            hcl_percentage=hcl_percentage,
            initial_thickness_nm=x_0,
        )

        # Inverted Deal-Grove equation
        # t = (x^2 - x0^2)/B + (x - x0) / (B/A)
        b = params.b_parabolic
        ba = params.b_over_a_linear

        time_parabolic = (x_target ** 2 - x_0 ** 2) / b
        time_linear = (x_target - x_0) / ba
        total_time_s = max(0.0, time_parabolic + time_linear)

        return duration(
            value=total_time_s,
            unit="s",
            uncertainty=total_time_s * 0.03,
            source=f"Deal-Grove Inversion ({ambient.value}, {x_target:.1f}nm @ {t_degc:.0f}°C)",
        )
