"""Comprehensive Physical Units System for Semiconductor Fabrication Digital Twin.

This module provides a rigorous, type-safe physical quantity and unit conversion
system designed specifically for semiconductor manufacturing processes (lithography,
etch, deposition, CMP, implant, diffusion/anneal, and metrology).

Every numerical value carries:
  1. Magnitude (value)
  2. Physical unit
  3. Valid physical/engineering range (min, max)
  4. Measurement or process uncertainty (+/- 1-sigma)
  5. Provenance/source reference string (e.g., SEMI standard, ITRS roadmap, fab spec)

Standards References:
  - SEMI E12: Standard for Equipment Specific Gas and Chemical Systems
  - SEMI M1: Specifications for Polished Single Crystal Silicon Wafers
  - SEMI E95: Specification for Human Interface for Semiconductor Manufacturing Equipment
  - NIST Special Publication 811: Guide for the Use of the International System of Units
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Final, Optional, Set, Tuple, Union


class UnitDimension(str, Enum):
    """Fundamental physical dimensions encountered in semiconductor fab equipment and processes."""
    LENGTH = "LENGTH"
    TIME = "TIME"
    TEMPERATURE = "TEMPERATURE"
    PRESSURE = "PRESSURE"
    POWER = "POWER"
    CURRENT = "CURRENT"
    FLOW_RATE = "FLOW_RATE"
    ROTATIONAL_SPEED = "ROTATIONAL_SPEED"
    ENERGY = "ENERGY"
    DOSE_IMPLANT = "DOSE_IMPLANT"
    DOSE_LITHO = "DOSE_LITHO"
    STRESS = "STRESS"
    RESISTIVITY = "RESISTIVITY"
    SHEET_RESISTANCE = "SHEET_RESISTANCE"
    FREQUENCY = "FREQUENCY"
    DIMENSIONLESS = "DIMENSIONLESS"


# Normalized canonical representations and conversion multipliers to standard base units.
# For temperature, affine transformation (Kelvin = scale * unit + offset) is handled explicitly.

_CANONICAL_UNIT_MAP: Final[Dict[str, str]] = {
    # Length (base: meter 'm')
    "m": "m", "meter": "m", "meters": "m",
    "cm": "cm", "centimeter": "cm",
    "mm": "mm", "millimeter": "mm",
    "um": "um", "μm": "um", "micron": "um", "micrometer": "um",
    "nm": "nm", "nanometer": "nm",
    "angstrom": "angstrom", "a": "angstrom", "å": "angstrom", "ang": "angstrom",
    "pm": "pm", "picometer": "pm",

    # Time (base: second 's')
    "s": "s", "sec": "s", "second": "s", "seconds": "s",
    "ms": "ms", "millisecond": "ms",
    "us": "us", "μs": "us", "microsecond": "us",
    "min": "min", "minute": "min", "minutes": "min",
    "hr": "hr", "h": "hr", "hour": "hr", "hours": "hr",

    # Temperature (base: Kelvin 'K')
    "k": "K", "kelvin": "K",
    "degc": "degC", "°c": "degC", "c": "degC", "celsius": "degC",
    "degf": "degF", "°f": "degF", "f": "degF", "fahrenheit": "degF",

    # Pressure (base: Pascal 'Pa')
    "pa": "Pa", "pascal": "Pa",
    "kpa": "kPa", "kilopascal": "kPa",
    "mpa": "MPa_pressure", "megapascal": "MPa_pressure",
    "torr": "Torr",
    "mtorr": "mTorr", "millitorr": "mTorr",
    "mbar": "mbar", "millibar": "mbar",
    "bar": "bar",
    "atm": "atm", "atmosphere": "atm",
    "psi": "psi",

    # Power (base: Watt 'W')
    "w": "W", "watt": "W", "watts": "W",
    "kw": "kW", "kilowatt": "kW",
    "mw": "mW", "milliwatt": "mW",

    # Current (base: Ampere 'A')
    "a": "A", "amp": "A", "ampere": "A",
    "ma": "mA", "milliamp": "mA",
    "ua": "uA", "μa": "uA", "microamp": "uA",
    "na": "nA", "nanoamp": "nA",

    # Flow Rate (base: sccm [standard cubic centimeter per minute @ STP])
    "sccm": "sccm",
    "slm": "slm", "slpm": "slm",
    "sccs": "sccs",

    # Rotational Speed (base: rpm)
    "rpm": "rpm",
    "rps": "rps",
    "deg/s": "deg/s",

    # Energy (base: electron-volt 'eV')
    "ev": "eV", "electronvolt": "eV",
    "kev": "keV", "kiloelectronvolt": "keV",
    "mev": "MeV",
    "j": "J", "joule": "J",

    # Dose - Ion Implantation (base: ions/cm^2)
    "ions/cm^2": "ions/cm^2", "ions/cm2": "ions/cm^2", "atoms/cm^2": "ions/cm^2", "atoms/cm2": "ions/cm^2",
    "cm^-2": "ions/cm^2",

    # Dose - Photolithography Exposure (base: mJ/cm^2)
    "mj/cm^2": "mJ/cm^2", "mj/cm2": "mJ/cm^2",
    "j/cm^2": "J/cm^2", "j/cm2": "J/cm^2",

    # Mechanical Stress (base: MegaPascal 'MPa')
    "mpa_stress": "MPa", "mpa": "MPa",
    "gpa": "GPa",
    "pa_stress": "Pa_stress",

    # Resistivity & Sheet Resistance
    "ohm*cm": "ohm*cm", "ohm-cm": "ohm*cm", "ω*cm": "ohm*cm", "ω·cm": "ohm*cm",
    "mohm*cm": "mohm*cm",
    "ohm/sq": "ohm/sq", "ohm/square": "ohm/sq", "ω/sq": "ohm/sq", "ω/□": "ohm/sq",

    # Frequency
    "hz": "Hz", "khz": "kHz", "mhz": "MHz", "ghz": "GHz",

    # Dimensionless
    "%": "%", "percent": "%",
    "ppm": "ppm", "ppb": "ppb",
    "count": "count", "ea": "count", "dimensionless": "count", "": "count",
}

# Dimension association for each canonical unit
_UNIT_TO_DIMENSION: Final[Dict[str, UnitDimension]] = {
    "m": UnitDimension.LENGTH, "cm": UnitDimension.LENGTH, "mm": UnitDimension.LENGTH,
    "um": UnitDimension.LENGTH, "nm": UnitDimension.LENGTH, "angstrom": UnitDimension.LENGTH, "pm": UnitDimension.LENGTH,

    "s": UnitDimension.TIME, "ms": UnitDimension.TIME, "us": UnitDimension.TIME,
    "min": UnitDimension.TIME, "hr": UnitDimension.TIME,

    "K": UnitDimension.TEMPERATURE, "degC": UnitDimension.TEMPERATURE, "degF": UnitDimension.TEMPERATURE,

    "Pa": UnitDimension.PRESSURE, "kPa": UnitDimension.PRESSURE, "MPa_pressure": UnitDimension.PRESSURE,
    "Torr": UnitDimension.PRESSURE, "mTorr": UnitDimension.PRESSURE, "mbar": UnitDimension.PRESSURE,
    "bar": UnitDimension.PRESSURE, "atm": UnitDimension.PRESSURE, "psi": UnitDimension.PRESSURE,

    "W": UnitDimension.POWER, "kW": UnitDimension.POWER, "mW": UnitDimension.POWER,
    "A": UnitDimension.CURRENT, "mA": UnitDimension.CURRENT, "uA": UnitDimension.CURRENT, "nA": UnitDimension.CURRENT,

    "sccm": UnitDimension.FLOW_RATE, "slm": UnitDimension.FLOW_RATE, "sccs": UnitDimension.FLOW_RATE,
    "rpm": UnitDimension.ROTATIONAL_SPEED, "rps": UnitDimension.ROTATIONAL_SPEED, "deg/s": UnitDimension.ROTATIONAL_SPEED,

    "eV": UnitDimension.ENERGY, "keV": UnitDimension.ENERGY, "MeV": UnitDimension.ENERGY, "J": UnitDimension.ENERGY,

    "ions/cm^2": UnitDimension.DOSE_IMPLANT,
    "mJ/cm^2": UnitDimension.DOSE_LITHO, "J/cm^2": UnitDimension.DOSE_LITHO,

    "MPa": UnitDimension.STRESS, "GPa": UnitDimension.STRESS, "Pa_stress": UnitDimension.STRESS,

    "ohm*cm": UnitDimension.RESISTIVITY, "mohm*cm": UnitDimension.RESISTIVITY,
    "ohm/sq": UnitDimension.SHEET_RESISTANCE,

    "Hz": UnitDimension.FREQUENCY, "kHz": UnitDimension.FREQUENCY, "MHz": UnitDimension.FREQUENCY, "GHz": UnitDimension.FREQUENCY,

    "%": UnitDimension.DIMENSIONLESS, "ppm": UnitDimension.DIMENSIONLESS, "ppb": UnitDimension.DIMENSIONLESS, "count": UnitDimension.DIMENSIONLESS,
}

# Scale factors relative to the dimension's standard reference base
# Reference base per dimension:
#   LENGTH: m
#   TIME: s
#   PRESSURE: Pa
#   POWER: W
#   CURRENT: A
#   FLOW_RATE: sccm
#   ROTATIONAL_SPEED: rpm
#   ENERGY: eV
#   DOSE_IMPLANT: ions/cm^2
#   DOSE_LITHO: mJ/cm^2
#   STRESS: MPa
#   RESISTIVITY: ohm*cm
#   SHEET_RESISTANCE: ohm/sq
#   FREQUENCY: Hz
#   DIMENSIONLESS: count (1.0)
_CONVERSION_FACTORS: Final[Dict[str, float]] = {
    # Length -> meters
    "m": 1.0,
    "cm": 1e-2,
    "mm": 1e-3,
    "um": 1e-6,
    "nm": 1e-9,
    "angstrom": 1e-10,
    "pm": 1e-12,

    # Time -> seconds
    "s": 1.0,
    "ms": 1e-3,
    "us": 1e-6,
    "min": 60.0,
    "hr": 3600.0,

    # Pressure -> Pascal (1 Torr = 133.32236842105 Pa; 1 atm = 101325 Pa)
    "Pa": 1.0,
    "kPa": 1e3,
    "MPa_pressure": 1e6,
    "Torr": 133.32236842105,
    "mTorr": 0.13332236842105,
    "mbar": 100.0,
    "bar": 100000.0,
    "atm": 101325.0,
    "psi": 6894.757293168,

    # Power -> Watts
    "W": 1.0,
    "kW": 1000.0,
    "mW": 1e-3,

    # Current -> Amperes
    "A": 1.0,
    "mA": 1e-3,
    "uA": 1e-6,
    "nA": 1e-9,

    # Gas Flow -> sccm (1 slm = 1000 sccm; 1 sccs = 60 sccm)
    "sccm": 1.0,
    "slm": 1000.0,
    "sccs": 60.0,

    # Rotational speed -> rpm
    "rpm": 1.0,
    "rps": 60.0,
    "deg/s": 1.0 / 6.0,

    # Energy -> eV (1 eV = 1.602176634e-19 J)
    "eV": 1.0,
    "keV": 1e3,
    "MeV": 1e6,
    "J": 1.0 / 1.602176634e-19,

    # Implant Dose -> ions/cm^2
    "ions/cm^2": 1.0,

    # Litho Dose -> mJ/cm^2
    "mJ/cm^2": 1.0,
    "J/cm^2": 1000.0,

    # Stress -> MPa
    "MPa": 1.0,
    "GPa": 1000.0,
    "Pa_stress": 1e-6,

    # Resistivity -> ohm*cm
    "ohm*cm": 1.0,
    "mohm*cm": 1e-3,

    # Sheet resistance -> ohm/sq
    "ohm/sq": 1.0,

    # Frequency -> Hz
    "Hz": 1.0,
    "kHz": 1e3,
    "MHz": 1e6,
    "GHz": 1e9,

    # Dimensionless
    "count": 1.0,
    "%": 0.01,
    "ppm": 1e-6,
    "ppb": 1e-9,
}


def normalize_unit(unit_str: str) -> str:
    """Normalize input unit string into its canonical semiconductor symbol.

    Args:
        unit_str: Raw unit string (e.g. 'nm', 'nanometer', 'mTorr', 'degC').

    Returns:
        Canonical unit string.

    Raises:
        ValueError: If unit string cannot be matched to known fab units.
    """
    clean_key = unit_str.strip().lower()
    if clean_key in _CANONICAL_UNIT_MAP:
        return _CANONICAL_UNIT_MAP[clean_key]
    # Check for direct case-sensitive match
    if unit_str in _UNIT_TO_DIMENSION:
        return unit_str
    raise ValueError(
        f"Unknown or unsupported semiconductor unit: '{unit_str}'. "
        f"Supported units include: {sorted(set(_CANONICAL_UNIT_MAP.values()))}"
    )


def get_unit_dimension(unit_str: str) -> UnitDimension:
    """Retrieve the physical dimension for a given unit.

    Args:
        unit_str: Unit symbol.

    Returns:
        UnitDimension enum value.
    """
    canonical = normalize_unit(unit_str)
    return _UNIT_TO_DIMENSION[canonical]


def convert_value(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a numeric scalar value from one unit to another within the same dimension.

    Handles linear scaling as well as affine transformations (Kelvin/Celsius/Fahrenheit).

    Args:
        value: Numerical magnitude.
        from_unit: Source unit string.
        to_unit: Destination unit string.

    Returns:
        Converted numeric value.

    Raises:
        ValueError: If units belong to incompatible dimensions.
    """
    from_canon = normalize_unit(from_unit)
    to_canon = normalize_unit(to_unit)

    if from_canon == to_canon:
        return float(value)

    dim_from = _UNIT_TO_DIMENSION[from_canon]
    dim_to = _UNIT_TO_DIMENSION[to_canon]

    if dim_from != dim_to:
        raise ValueError(
            f"Dimension mismatch during conversion: '{from_unit}' ({dim_from.value}) "
            f"cannot be converted to '{to_unit}' ({dim_to.value})"
        )

    # Handle Temperature affine conversion explicitly
    if dim_from == UnitDimension.TEMPERATURE:
        # Convert to Kelvin first
        val = float(value)
        match from_canon:
            case "K":
                k_val = val
            case "degC":
                k_val = val + 273.15
            case "degF":
                k_val = (val - 32.0) * (5.0 / 9.0) + 273.15
            case _:
                raise ValueError(f"Unsupported source temperature unit: {from_canon}")

        # Convert Kelvin to target
        match to_canon:
            case "K":
                return k_val
            case "degC":
                return k_val - 273.15
            case "degF":
                return (k_val - 273.15) * 1.8 + 32.0
            case _:
                raise ValueError(f"Unsupported destination temperature unit: {to_canon}")

    # Standard proportional scaling via reference factor
    factor_from = _CONVERSION_FACTORS[from_canon]
    factor_to = _CONVERSION_FACTORS[to_canon]

    # value_in_base = value * factor_from
    # value_in_target = value_in_base / factor_to
    base_val = float(value) * factor_from
    return base_val / factor_to


@dataclass(frozen=True)
class PhysicalQuantity:
    """A physically grounded quantity carrying magnitude, unit, valid range, uncertainty, and provenance.

    Attributes:
        value: Float magnitude.
        unit: Physical unit symbol (e.g. 'nm', 'mTorr', 'degC', 'sccm', 'W').
        valid_range: (min_value, max_value) allowed physical or engineering range.
        uncertainty: Absolute measurement / process uncertainty (+/- value).
        source: Textual reference or provenance (e.g., standard, spec sheet, recipe ID).
    """

    value: float
    unit: str
    valid_range: Tuple[float, float]
    uncertainty: float = 0.0
    source: str = "Fab Digital Twin Engineering Model"

    def __post_init__(self) -> None:
        """Validate bounds, unit dimension, and uncertainty constraints upon initialization."""
        canonical_unit = normalize_unit(self.unit)
        object.__setattr__(self, "unit", canonical_unit)

        val = float(self.value)
        unc = float(self.uncertainty)
        object.__setattr__(self, "value", val)
        object.__setattr__(self, "uncertainty", unc)

        if not isinstance(self.valid_range, (tuple, list)) or len(self.valid_range) != 2:
            raise ValueError(
                f"valid_range must be a 2-tuple (min, max), got: {self.valid_range!r}"
            )

        min_val = float(self.valid_range[0])
        max_val = float(self.valid_range[1])
        if min_val > max_val:
            raise ValueError(
                f"Invalid range specification: min ({min_val}) cannot exceed max ({max_val})"
            )
        object.__setattr__(self, "valid_range", (min_val, max_val))

        if unc < 0.0:
            raise ValueError(f"Uncertainty must be non-negative, got: {unc}")

        # Physical range validation
        # Small tolerance for floating point boundary equality
        tol = 1e-9 * max(1.0, abs(val))
        if val < (min_val - tol) or val > (max_val + tol):
            raise ValueError(
                f"Value {val} {self.unit} is outside valid engineering range "
                f"[{min_val}, {max_val}] {self.unit}. Source: {self.source}"
            )

    @property
    def dimension(self) -> UnitDimension:
        """Return the physical dimension of this quantity."""
        return get_unit_dimension(self.unit)

    def to_unit(self, target_unit: str) -> PhysicalQuantity:
        """Convert this quantity to a target unit within the same dimension.

        Args:
            target_unit: Target unit symbol.

        Returns:
            A new PhysicalQuantity converted to target_unit.
        """
        target_canon = normalize_unit(target_unit)
        if target_canon == self.unit:
            return self

        new_val = convert_value(self.value, self.unit, target_canon)

        # For range conversion: convert both boundary limits
        new_min = convert_value(self.valid_range[0], self.unit, target_canon)
        new_max = convert_value(self.valid_range[1], self.unit, target_canon)
        if new_min > new_max:
            new_min, new_max = new_max, new_min

        # For uncertainty: convert delta (for temperature, scale without offset)
        if self.dimension == UnitDimension.TEMPERATURE:
            if target_canon in ("degC", "K") and self.unit in ("degC", "K"):
                new_unc = self.uncertainty
            elif target_canon == "degF" and self.unit in ("degC", "K"):
                new_unc = self.uncertainty * 1.8
            elif target_canon in ("degC", "K") and self.unit == "degF":
                new_unc = self.uncertainty * (5.0 / 9.0)
            else:
                new_unc = self.uncertainty
        else:
            factor_from = _CONVERSION_FACTORS[self.unit]
            factor_to = _CONVERSION_FACTORS[target_canon]
            new_unc = self.uncertainty * factor_from / factor_to

        new_source = f"{self.source} [conv -> {target_canon}]"
        return PhysicalQuantity(
            value=new_val,
            unit=target_canon,
            valid_range=(new_min, new_max),
            uncertainty=new_unc,
            source=new_source,
        )

    # Arithmetic Operator Overloads
    def __add__(self, other: Any) -> PhysicalQuantity:
        if isinstance(other, PhysicalQuantity):
            other_converted = other.to_unit(self.unit)
            combined_val = self.value + other_converted.value
            combined_unc = math.hypot(self.uncertainty, other_converted.uncertainty)
            combined_range = (
                self.valid_range[0] + other_converted.valid_range[0],
                self.valid_range[1] + other_converted.valid_range[1],
            )
            return PhysicalQuantity(
                value=combined_val,
                unit=self.unit,
                valid_range=combined_range,
                uncertainty=combined_unc,
                source=f"({self.source} + {other.source})",
            )
        raise TypeError(f"Unsupported operand type for +: 'PhysicalQuantity' and '{type(other).__name__}'")

    def __sub__(self, other: Any) -> PhysicalQuantity:
        if isinstance(other, PhysicalQuantity):
            other_converted = other.to_unit(self.unit)
            combined_val = self.value - other_converted.value
            combined_unc = math.hypot(self.uncertainty, other_converted.uncertainty)
            combined_range = (
                self.valid_range[0] - other_converted.valid_range[1],
                self.valid_range[1] - other_converted.valid_range[0],
            )
            return PhysicalQuantity(
                value=combined_val,
                unit=self.unit,
                valid_range=combined_range,
                uncertainty=combined_unc,
                source=f"({self.source} - {other.source})",
            )
        raise TypeError(f"Unsupported operand type for -: 'PhysicalQuantity' and '{type(other).__name__}'")

    def __mul__(self, scalar: Union[int, float]) -> PhysicalQuantity:
        if isinstance(scalar, (int, float)):
            s = float(scalar)
            new_val = self.value * s
            new_range = (
                min(self.valid_range[0] * s, self.valid_range[1] * s),
                max(self.valid_range[0] * s, self.valid_range[1] * s),
            )
            new_unc = abs(self.uncertainty * s)
            return PhysicalQuantity(
                value=new_val,
                unit=self.unit,
                valid_range=new_range,
                uncertainty=new_unc,
                source=self.source,
            )
        raise TypeError(f"PhysicalQuantity can only be multiplied by scalar numeric types, got '{type(scalar).__name__}'")

    def __rmul__(self, scalar: Union[int, float]) -> PhysicalQuantity:
        return self.__mul__(scalar)

    def __truediv__(self, other: Union[int, float, PhysicalQuantity]) -> Union[PhysicalQuantity, float]:
        if isinstance(other, (int, float)):
            d = float(other)
            if d == 0.0:
                raise ZeroDivisionError("Division by zero in PhysicalQuantity scalar division")
            new_val = self.value / d
            new_range = (
                min(self.valid_range[0] / d, self.valid_range[1] / d),
                max(self.valid_range[0] / d, self.valid_range[1] / d),
            )
            new_unc = abs(self.uncertainty / d)
            return PhysicalQuantity(
                value=new_val,
                unit=self.unit,
                valid_range=new_range,
                uncertainty=new_unc,
                source=self.source,
            )
        if isinstance(other, PhysicalQuantity):
            # Ratio of two quantities of the same dimension -> dimensionless float ratio
            other_converted = other.to_unit(self.unit)
            if other_converted.value == 0.0:
                raise ZeroDivisionError("Division by zero in PhysicalQuantity ratio")
            return self.value / other_converted.value
        raise TypeError(f"Unsupported operand type for /: 'PhysicalQuantity' and '{type(other).__name__}'")

    def __neg__(self) -> PhysicalQuantity:
        return PhysicalQuantity(
            value=-self.value,
            unit=self.unit,
            valid_range=(-self.valid_range[1], -self.valid_range[0]),
            uncertainty=self.uncertainty,
            source=self.source,
        )

    def __abs__(self) -> PhysicalQuantity:
        new_min = 0.0 if (self.valid_range[0] <= 0 <= self.valid_range[1]) else min(abs(self.valid_range[0]), abs(self.valid_range[1]))
        new_max = max(abs(self.valid_range[0]), abs(self.valid_range[1]))
        return PhysicalQuantity(
            value=abs(self.value),
            unit=self.unit,
            valid_range=(new_min, new_max),
            uncertainty=self.uncertainty,
            source=self.source,
        )

    # Comparisons
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PhysicalQuantity):
            return False
        if self.dimension != other.dimension:
            return False
        other_converted = other.to_unit(self.unit)
        tol = max(1e-9, self.uncertainty + other_converted.uncertainty)
        return abs(self.value - other_converted.value) <= tol

    def __lt__(self, other: PhysicalQuantity) -> bool:
        if not isinstance(other, PhysicalQuantity):
            return NotImplemented
        other_converted = other.to_unit(self.unit)
        return self.value < other_converted.value

    def __le__(self, other: PhysicalQuantity) -> bool:
        return self.__lt__(other) or self.__eq__(other)

    def __gt__(self, other: PhysicalQuantity) -> bool:
        if not isinstance(other, PhysicalQuantity):
            return NotImplemented
        other_converted = other.to_unit(self.unit)
        return self.value > other_converted.value

    def __ge__(self, other: PhysicalQuantity) -> bool:
        return self.__gt__(other) or self.__eq__(other)

    # Serialization
    def to_dict(self) -> Dict[str, Any]:
        """Serialize physical quantity to JSON-compatible dictionary."""
        return {
            "value": self.value,
            "unit": self.unit,
            "valid_range": list(self.valid_range),
            "uncertainty": self.uncertainty,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PhysicalQuantity:
        """Reconstruct PhysicalQuantity from dictionary representation."""
        return cls(
            value=float(data["value"]),
            unit=str(data["unit"]),
            valid_range=(float(data["valid_range"][0]), float(data["valid_range"][1])),
            uncertainty=float(data.get("uncertainty", 0.0)),
            source=str(data.get("source", "Deserialized")),
        )

    def __repr__(self) -> str:
        return (
            f"PhysicalQuantity(value={self.value:.4g}, unit={self.unit!r}, "
            f"valid_range=({self.valid_range[0]:.4g}, {self.valid_range[1]:.4g}), "
            f"uncertainty={self.uncertainty:.4g}, source={self.source!r})"
        )

    def __str__(self) -> str:
        unc_str = f" ± {self.uncertainty:.3g}" if self.uncertainty > 0 else ""
        return (
            f"{self.value:.4g}{unc_str} {self.unit} "
            f"[{self.valid_range[0]:.3g}, {self.valid_range[1]:.3g}] (source: {self.source})"
        )


# ============================================================================
# Semiconductor Factory Constructors for Common Physical Quantities
# ============================================================================

def length(
    value: float,
    unit: str = "nm",
    valid_range: Tuple[float, float] = (0.0, 1e9),
    uncertainty: float = 0.0,
    source: str = "SEMI Standard Dimension",
) -> PhysicalQuantity:
    """Create a length / dimension physical quantity."""
    return PhysicalQuantity(value, unit, valid_range, uncertainty, source)


def wafer_diameter(
    diameter_mm: float = 300.0,
    uncertainty_mm: float = 0.2,
    source: str = "SEMI M1-0302 Specification for 300mm Polished Monocrystalline Silicon Wafers",
) -> PhysicalQuantity:
    """Create a standardized wafer diameter quantity (default 300 mm)."""
    return PhysicalQuantity(
        value=diameter_mm,
        unit="mm",
        valid_range=(50.0, 450.0),
        uncertainty=uncertainty_mm,
        source=source,
    )


def wafer_thickness(
    thickness_um: float = 775.0,
    uncertainty_um: float = 20.0,
    source: str = "SEMI M1 Table 1 - 300mm Wafer Thickness Standard",
) -> PhysicalQuantity:
    """Create a standardized wafer bulk thickness quantity (default 775 μm)."""
    return PhysicalQuantity(
        value=thickness_um,
        unit="um",
        valid_range=(100.0, 1500.0),
        uncertainty=uncertainty_um,
        source=source,
    )


def film_thickness(
    thickness: float,
    unit: str = "nm",
    uncertainty: float = 0.1,
    source: str = "Thin Film Metrology Ellipsometry/XRR",
) -> PhysicalQuantity:
    """Create a thin-film layer thickness quantity (supports nm, angstrom, um)."""
    # Valid ranges adapted for modern microelectronics (0.1 nm to 100 um)
    canon = normalize_unit(unit)
    max_val = convert_value(100.0, "um", canon)
    return PhysicalQuantity(
        value=thickness,
        unit=canon,
        valid_range=(0.0, max_val),
        uncertainty=uncertainty,
        source=source,
    )


def temperature(
    value: float,
    unit: str = "degC",
    valid_range: Optional[Tuple[float, float]] = None,
    uncertainty: float = 0.5,
    source: str = "Chamber Thermocouple / Pyrometer",
) -> PhysicalQuantity:
    """Create a process temperature quantity (default range -20 degC to 1400 degC)."""
    canon = normalize_unit(unit)
    if valid_range is None:
        min_c, max_c = -50.0, 1450.0
        r_min = convert_value(min_c, "degC", canon)
        r_max = convert_value(max_c, "degC", canon)
        valid_range = (min(r_min, r_max), max(r_min, r_max))
    return PhysicalQuantity(value, canon, valid_range, uncertainty, source)


def pressure(
    value: float,
    unit: str = "mTorr",
    valid_range: Optional[Tuple[float, float]] = None,
    uncertainty: float = 0.05,
    source: str = "Capacitance Manometer / Penning Gauge",
) -> PhysicalQuantity:
    """Create a chamber vacuum or atmospheric pressure quantity."""
    canon = normalize_unit(unit)
    if valid_range is None:
        # Default covers extreme high vacuum (1e-10 Torr) to 5 atm (furnaces)
        p_min = convert_value(1e-10, "Torr", canon)
        p_max = convert_value(5.0, "atm", canon)
        valid_range = (min(p_min, p_max), max(p_min, p_max))
    return PhysicalQuantity(value, canon, valid_range, uncertainty, source)


def gas_flow(
    value: float,
    unit: str = "sccm",
    valid_range: Tuple[float, float] = (0.0, 50000.0),
    uncertainty: float = 0.5,
    source: str = "Mass Flow Controller (SEMI E12 standard conditions)",
) -> PhysicalQuantity:
    """Create a mass flow rate quantity (sccm or slm)."""
    return PhysicalQuantity(value, unit, valid_range, uncertainty, source)


def rf_power(
    value: float,
    unit: str = "W",
    valid_range: Tuple[float, float] = (0.0, 10000.0),
    uncertainty: float = 5.0,
    source: str = "RF Plasma Generator (13.56MHz / 400kHz / 2.45GHz)",
) -> PhysicalQuantity:
    """Create an RF/DC plasma excitation power quantity."""
    return PhysicalQuantity(value, unit, valid_range, uncertainty, source)


def implant_dose(
    value: float,
    unit: str = "ions/cm^2",
    valid_range: Tuple[float, float] = (1e10, 1e17),
    uncertainty: float = 1e10,
    source: str = "Ion Beam Faraday Cup Integrator",
) -> PhysicalQuantity:
    """Create an ion implantation dose quantity."""
    return PhysicalQuantity(value, unit, valid_range, uncertainty, source)


def litho_dose(
    value: float,
    unit: str = "mJ/cm^2",
    valid_range: Tuple[float, float] = (0.1, 1000.0),
    uncertainty: float = 0.2,
    source: str = "Photolithography Scanner Radiometer",
) -> PhysicalQuantity:
    """Create an exposure dose quantity for ArF/EUV/i-line photolithography."""
    return PhysicalQuantity(value, unit, valid_range, uncertainty, source)


def ion_energy(
    value: float,
    unit: str = "keV",
    valid_range: Tuple[float, float] = (0.1, 5000.0),
    uncertainty: float = 0.05,
    source: str = "Implanter Acceleration Column / Analyzer Magnet",
) -> PhysicalQuantity:
    """Create an ion kinetic energy quantity."""
    return PhysicalQuantity(value, unit, valid_range, uncertainty, source)


def duration(
    value: float,
    unit: str = "s",
    valid_range: Tuple[float, float] = (0.0, 86400.0),
    uncertainty: float = 0.01,
    source: str = "Tool PLC Recipe Timer",
) -> PhysicalQuantity:
    """Create a time duration quantity."""
    return PhysicalQuantity(value, unit, valid_range, uncertainty, source)


def rotation_speed(
    value: float,
    unit: str = "rpm",
    valid_range: Tuple[float, float] = (0.0, 10000.0),
    uncertainty: float = 1.0,
    source: str = "Wafer Chuck Spin Motor Encoder",
) -> PhysicalQuantity:
    """Create a rotational speed quantity (coater spin-speed, CMP platen speed)."""
    return PhysicalQuantity(value, unit, valid_range, uncertainty, source)
