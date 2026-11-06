"""Statistical Process Control (SPC) Subsystem for Semiconductor Metrology.

Implements standard fab SPC analytics, including:
  - Control chart types: X-bar, R-chart, S-chart, and Individual & Moving-Range (I-MR)
  - Complete Western Electric Rules (Rules 1 through 8) for out-of-control detection
  - Dynamic limit estimation via standard ASTM/ISO statistical factors (A2, D3, D4, d2, E2)
  - Process Capability Indices (Cp, Cpk) and Process Performance Indices (Pp, Ppk)
  - Structured HMI visualization data packaging for real-time fab dashboards

Standards References:
  - ASTM E2587: Standard Practice for Use of Control Charts in Statistical Process Control
  - ISO 22514: Statistical methods in process management - Capability and performance
  - SEMI E95: Specification for Human Interface for Semiconductor Manufacturing Equipment
  - Western Electric Company (1956): Statistical Quality Control Handbook
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


class ControlChartType(str, Enum):
    """Statistical control chart methodology."""
    XBAR = "XBAR"                      # Subgroup averages
    R_CHART = "R_CHART"                # Subgroup ranges
    S_CHART = "S_CHART"                # Subgroup standard deviations
    INDIVIDUAL = "INDIVIDUAL"          # Individual wafer measurements (I-chart)
    MOVING_RANGE = "MOVING_RANGE"      # Moving Range between consecutive individuals (MR-chart)


class WesternElectricRuleId(int, Enum):
    """The 8 canonical Western Electric Rules for SPC out-of-control detection."""
    RULE_1_BEYOND_3SIGMA = 1      # 1 point beyond Zone A (> 3-sigma from CL)
    RULE_2_RUN_OF_NINE = 2        # 9 consecutive points on same side of CL
    RULE_3_TREND_OF_SIX = 3       # 6 consecutive points steadily increasing or decreasing
    RULE_4_ALTERNATING_14 = 4     # 14 consecutive points alternating up and down
    RULE_5_TWO_OF_THREE_2SIGMA = 5  # 2 of 3 consecutive points in Zone A or beyond (> 2-sigma, same side)
    RULE_6_FOUR_OF_FIVE_1SIGMA = 6  # 4 of 5 consecutive points in Zone B or beyond (> 1-sigma, same side)
    RULE_7_STRATIFICATION_15 = 7    # 15 consecutive points in Zone C (< 1-sigma on either side)
    RULE_8_MIXTURE_8 = 8           # 8 consecutive points beyond Zone C on either side (no points in Zone C)


@dataclass(frozen=True)
class RuleViolation:
    """An alert detailing an out-of-control condition detected on a control chart."""
    rule_id: WesternElectricRuleId
    rule_name: str
    point_index: int
    point_value: float
    description: str
    severity: str = "CRITICAL"  # WARNING or CRITICAL


@dataclass
class SPCPoint:
    """Individual data point on an SPC chart."""
    index: int
    timestamp: str
    value: float
    subgroup_id: Optional[str] = None
    subgroup_values: List[float] = field(default_factory=list)
    zone: str = "C"  # "A+", "B+", "C+", "C-", "B-", "A-", "OUT"


# ASTM E2587 Statistical Control Chart Constant Tables for Subgroup sizes n = 2..10
# d2: expected value of relative range (R / sigma)
# A2: 3 / (d2 * sqrt(n)) factor for Xbar UCL/LCL from Rbar
# D3, D4: lower/upper factors for R-chart limits
_ASTM_FACTORS: Dict[int, Dict[str, float]] = {
    2: {"d2": 1.128, "A2": 1.880, "D3": 0.000, "D4": 3.267, "E2": 2.660},
    3: {"d2": 1.693, "A2": 1.023, "D3": 0.000, "D4": 2.574, "E2": 1.772},
    4: {"d2": 2.059, "A2": 0.729, "D3": 0.000, "D4": 2.282, "E2": 1.457},
    5: {"d2": 2.326, "A2": 0.577, "D3": 0.000, "D4": 2.114, "E2": 1.290},
    6: {"d2": 2.534, "A2": 0.483, "D3": 0.000, "D4": 2.004, "E2": 1.184},
    7: {"d2": 2.704, "A2": 0.419, "D3": 0.076, "D4": 1.924, "E2": 1.109},
    8: {"d2": 2.847, "A2": 0.373, "D3": 0.136, "D4": 1.864, "E2": 1.054},
    9: {"d2": 2.970, "A2": 0.337, "D3": 0.184, "D4": 1.816, "E2": 1.010},
    10: {"d2": 3.078, "A2": 0.308, "D3": 0.223, "D4": 1.777, "E2": 0.975},
}


class WesternElectricRules:
    """Evaluates the 8 standard Western Electric Statistical Process Control rules."""

    @staticmethod
    def evaluate(
        values: List[float],
        center_line: float,
        sigma: float,
    ) -> List[RuleViolation]:
        """Examine a sequence of values against Western Electric SPC rules 1 through 8.

        Args:
            values: Chronological sequence of chart points.
            center_line: Process mean (CL).
            sigma: Process standard error (sigma of the charted statistic).

        Returns:
            List of detected RuleViolation objects.
        """
        violations: List[RuleViolation] = []
        n = len(values)
        if n == 0 or sigma <= 1e-12:
            return violations

        # Classify each point into zones relative to center line:
        # Zones:
        #   > +3 sigma: OUT_UPPER
        #   +2 to +3 sigma: ZONE_A_PLUS
        #   +1 to +2 sigma: ZONE_B_PLUS
        #    0 to +1 sigma: ZONE_C_PLUS
        #   -1 to 0 sigma: ZONE_C_MINUS
        #   -2 to -1 sigma: ZONE_B_MINUS
        #   -3 to -2 sigma: ZONE_A_MINUS
        #   < -3 sigma: OUT_LOWER

        z_scores = [(v - center_line) / sigma for v in values]

        for i in range(n):
            z = z_scores[i]
            val = values[i]

            # Rule 1: Beyond 3-sigma (> Zone A)
            if abs(z) > 3.0:
                violations.append(
                    RuleViolation(
                        rule_id=WesternElectricRuleId.RULE_1_BEYOND_3SIGMA,
                        rule_name="Rule 1: Point Beyond 3-Sigma",
                        point_index=i,
                        point_value=val,
                        description=f"Point {i + 1} ({val:.3f}) lies {abs(z):.2f}-sigma from CL (beyond 3-sigma)",
                        severity="CRITICAL",
                    )
                )

            # Rule 2: 9 consecutive points on same side of center line
            if i >= 8:
                last_9 = z_scores[i - 8 : i + 1]
                if all(score > 0 for score in last_9):
                    violations.append(
                        RuleViolation(
                            rule_id=WesternElectricRuleId.RULE_2_RUN_OF_NINE,
                            rule_name="Rule 2: Run of 9 on Same Side",
                            point_index=i,
                            point_value=val,
                            description=f"9 consecutive points up to point {i + 1} are strictly above CL",
                            severity="CRITICAL",
                        )
                    )
                elif all(score < 0 for score in last_9):
                    violations.append(
                        RuleViolation(
                            rule_id=WesternElectricRuleId.RULE_2_RUN_OF_NINE,
                            rule_name="Rule 2: Run of 9 on Same Side",
                            point_index=i,
                            point_value=val,
                            description=f"9 consecutive points up to point {i + 1} are strictly below CL",
                            severity="CRITICAL",
                        )
                    )

            # Rule 3: 6 consecutive points steadily increasing or decreasing (trend)
            if i >= 5:
                sub_vals = values[i - 5 : i + 1]
                diffs = [sub_vals[k + 1] - sub_vals[k] for k in range(5)]
                if all(d > 0 for d in diffs):
                    violations.append(
                        RuleViolation(
                            rule_id=WesternElectricRuleId.RULE_3_TREND_OF_SIX,
                            rule_name="Rule 3: Trend of 6 Increasing/Decreasing",
                            point_index=i,
                            point_value=val,
                            description=f"6 consecutive points up to point {i + 1} show persistent increasing trend",
                            severity="WARNING",
                        )
                    )
                elif all(d < 0 for d in diffs):
                    violations.append(
                        RuleViolation(
                            rule_id=WesternElectricRuleId.RULE_3_TREND_OF_SIX,
                            rule_name="Rule 3: Trend of 6 Increasing/Decreasing",
                            point_index=i,
                            point_value=val,
                            description=f"6 consecutive points up to point {i + 1} show persistent decreasing trend",
                            severity="WARNING",
                        )
                    )

            # Rule 4: 14 consecutive points alternating up and down (systematic variation)
            if i >= 13:
                sub_vals = values[i - 13 : i + 1]
                signs = [math.copysign(1.0, sub_vals[k + 1] - sub_vals[k]) for k in range(13)]
                is_alternating = all(signs[k] != signs[k + 1] for k in range(12))
                if is_alternating:
                    violations.append(
                        RuleViolation(
                            rule_id=WesternElectricRuleId.RULE_4_ALTERNATING_14,
                            rule_name="Rule 4: 14 Alternating Points",
                            point_index=i,
                            point_value=val,
                            description=f"14 consecutive points up to point {i + 1} alternate direction (sawtooth pattern)",
                            severity="WARNING",
                        )
                    )

            # Rule 5: 2 out of 3 consecutive points in Zone A or beyond (> 2-sigma, same side)
            if i >= 2:
                last_3 = z_scores[i - 2 : i + 1]
                if sum(1 for s in last_3 if s > 2.0) >= 2:
                    violations.append(
                        RuleViolation(
                            rule_id=WesternElectricRuleId.RULE_5_TWO_OF_THREE_2SIGMA,
                            rule_name="Rule 5: 2 of 3 in Zone A (> 2-sigma)",
                            point_index=i,
                            point_value=val,
                            description=f"2 of 3 points ending at {i + 1} exceed +2 sigma",
                            severity="CRITICAL",
                        )
                    )
                elif sum(1 for s in last_3 if s < -2.0) >= 2:
                    violations.append(
                        RuleViolation(
                            rule_id=WesternElectricRuleId.RULE_5_TWO_OF_THREE_2SIGMA,
                            rule_name="Rule 5: 2 of 3 in Zone A (> 2-sigma)",
                            point_index=i,
                            point_value=val,
                            description=f"2 of 3 points ending at {i + 1} fall below -2 sigma",
                            severity="CRITICAL",
                        )
                    )

            # Rule 6: 4 out of 5 consecutive points in Zone B or beyond (> 1-sigma, same side)
            if i >= 4:
                last_5 = z_scores[i - 4 : i + 1]
                if sum(1 for s in last_5 if s > 1.0) >= 4:
                    violations.append(
                        RuleViolation(
                            rule_id=WesternElectricRuleId.RULE_6_FOUR_OF_FIVE_1SIGMA,
                            rule_name="Rule 6: 4 of 5 in Zone B or Beyond (> 1-sigma)",
                            point_index=i,
                            point_value=val,
                            description=f"4 of 5 points ending at {i + 1} exceed +1 sigma",
                            severity="WARNING",
                        )
                    )
                elif sum(1 for s in last_5 if s < -1.0) >= 4:
                    violations.append(
                        RuleViolation(
                            rule_id=WesternElectricRuleId.RULE_6_FOUR_OF_FIVE_1SIGMA,
                            rule_name="Rule 6: 4 of 5 in Zone B or Beyond (> 1-sigma)",
                            point_index=i,
                            point_value=val,
                            description=f"4 of 5 points ending at {i + 1} fall below -1 sigma",
                            severity="WARNING",
                        )
                    )

            # Rule 7: 15 consecutive points in Zone C (< 1-sigma on either side)
            if i >= 14:
                last_15 = z_scores[i - 14 : i + 1]
                if all(abs(s) <= 1.0 for s in last_15):
                    violations.append(
                        RuleViolation(
                            rule_id=WesternElectricRuleId.RULE_7_STRATIFICATION_15,
                            rule_name="Rule 7: Stratification (15 in Zone C)",
                            point_index=i,
                            point_value=val,
                            description=f"15 consecutive points ending at {i + 1} tightly cluster within 1-sigma (stratification)",
                            severity="WARNING",
                        )
                    )

            # Rule 8: 8 consecutive points beyond Zone C on either side (no points within 1-sigma)
            if i >= 7:
                last_8 = z_scores[i - 7 : i + 1]
                if all(abs(s) > 1.0 for s in last_8):
                    violations.append(
                        RuleViolation(
                            rule_id=WesternElectricRuleId.RULE_8_MIXTURE_8,
                            rule_name="Rule 8: Mixture Pattern (8 Beyond Zone C)",
                            point_index=i,
                            point_value=val,
                            description=f"8 consecutive points ending at {i + 1} avoid Zone C (bimodal mixture pattern)",
                            severity="WARNING",
                        )
                    )

        return violations


@dataclass
class ProcessCapabilityReport:
    """Rigorous process capability and performance metrics per ISO 22514."""
    cp: float              # Potential capability: (USL - LSL) / (6 * sigma_within)
    cpk: float             # Demonstrated capability: min(USL - mu, mu - LSL) / (3 * sigma_within)
    pp: float              # Overall performance: (USL - LSL) / (6 * sigma_overall)
    ppk: float             # Overall demonstrated performance: min(USL - mu, mu - LSL) / (3 * sigma_overall)
    mean: float
    sigma_within: float
    sigma_overall: float
    usl: float
    lsl: float
    target: float
    is_capable: bool       # Cpk >= 1.33 (industry standard capability threshold)
    six_sigma_level: float  # Equivalent standard deviations (e.g. 3.0 to 6.0)


class SPCMonitor:
    """Comprehensive Statistical Process Control Monitor for Fab Metrology Stations.

    Supports:
      - X-bar & R / S charts (for subgrouped wafer sampling).
      - Individual & Moving Range (I-MR) charts (for single lot/wafer measurements).
      - Historical baseline calibration of Control Limits (CL, UCL, LCL).
      - Automated Western Electric rule evaluation on incoming points.
      - Process capability indices (Cp, Cpk, Pp, Ppk).
      - Clean visualization data structures for front-end dashboards.
    """

    def __init__(
        self,
        parameter_name: str,
        unit: str,
        target: float,
        lsl: float,
        usl: float,
        subgroup_size: int = 5,
        chart_type: ControlChartType = ControlChartType.XBAR,
    ) -> None:
        """Initialize SPC monitor."""
        self.parameter_name: str = parameter_name
        self.unit: str = unit
        self.target: float = target
        self.lsl: float = lsl
        self.usl: float = usl
        self.subgroup_size: int = subgroup_size
        self.chart_type: ControlChartType = chart_type

        # Data series
        self._raw_points: List[float] = []
        self._chart_values: List[float] = []  # Subgroup means (or individuals)
        self._dispersion_values: List[float] = []  # Ranges or Moving Ranges
        self._timestamps: List[str] = []

        # Statistical limits (defaults until calibrated)
        self.center_line: float = target
        self.ucl: float = target + 0.1 * target
        self.lcl: float = target - 0.1 * target
        self.sigma: float = (self.ucl - self.center_line) / 3.0

        # Dispersion chart limits
        self.dispersion_cl: float = 0.0
        self.dispersion_ucl: float = 0.0
        self.dispersion_lcl: float = 0.0

        self.violations: List[RuleViolation] = []

    def calibrate_limits_from_baseline(
        self,
        baseline_subgroups: List[List[float]],
    ) -> None:
        """Calibrate standard 3-sigma control limits from historical calibration runs.

        Uses ASTM E2587 standard constants (d2, A2, D3, D4, E2).
        """
        if not baseline_subgroups:
            raise ValueError("Baseline subgroups must not be empty")

        n = len(baseline_subgroups[0])
        if n < 1:
            raise ValueError("Subgroups must contain at least 1 reading")

        if self.chart_type in (ControlChartType.XBAR, ControlChartType.R_CHART, ControlChartType.S_CHART):
            n_clamped = min(10, max(2, n))
            factors = _ASTM_FACTORS.get(n_clamped, _ASTM_FACTORS[5])

            means = [float(np.mean(sg)) for sg in baseline_subgroups]
            ranges = [float(np.ptp(sg)) for sg in baseline_subgroups]

            grand_mean = float(np.mean(means))
            r_bar = float(np.mean(ranges))

            self.center_line = grand_mean
            self.ucl = grand_mean + (factors["A2"] * r_bar)
            self.lcl = grand_mean - (factors["A2"] * r_bar)
            self.sigma = (self.ucl - self.center_line) / 3.0

            # Range chart limits
            self.dispersion_cl = r_bar
            self.dispersion_ucl = factors["D4"] * r_bar
            self.dispersion_lcl = factors["D3"] * r_bar

        else:  # INDIVIDUAL or MOVING_RANGE
            # Flat list of all readings
            flat_vals: List[float] = [val for sg in baseline_subgroups for val in sg]
            if len(flat_vals) < 2:
                raise ValueError("At least 2 readings required for I-MR calibration")

            mr_values = [abs(flat_vals[i] - flat_vals[i - 1]) for i in range(1, len(flat_vals))]
            mr_bar = float(np.mean(mr_values))
            x_bar = float(np.mean(flat_vals))

            # d2 = 1.128 for n=2 moving range; E2 = 2.66
            self.center_line = x_bar
            self.ucl = x_bar + (2.66 * mr_bar)
            self.lcl = x_bar - (2.66 * mr_bar)
            self.sigma = mr_bar / 1.128

            self.dispersion_cl = mr_bar
            self.dispersion_ucl = 3.267 * mr_bar
            self.dispersion_lcl = 0.0

    def add_subgroup(
        self,
        values: List[float],
        timestamp: str,
    ) -> List[RuleViolation]:
        """Add a new measurement subgroup, compute statistic, and evaluate Western Electric rules."""
        if not values:
            raise ValueError("Subgroup values cannot be empty")

        for v in values:
            self._raw_points.append(v)

        if self.chart_type in (ControlChartType.XBAR, ControlChartType.R_CHART):
            charted_val = float(np.mean(values))
            r_val = float(np.ptp(values))
            self._dispersion_values.append(r_val)
        else:
            # Individual chart: take first or single value
            charted_val = float(values[0])
            if self._chart_values:
                mr = abs(charted_val - self._chart_values[-1])
            else:
                mr = 0.0
            self._dispersion_values.append(mr)

        self._chart_values.append(charted_val)
        self._timestamps.append(timestamp)

        # Evaluate rules on updated series
        new_violations = WesternElectricRules.evaluate(
            values=self._chart_values,
            center_line=self.center_line,
            sigma=self.sigma,
        )

        # Retain latest violations
        self.violations = new_violations
        return new_violations

    def calculate_capability(self) -> ProcessCapabilityReport:
        """Calculate standard process capability indices (Cp, Cpk, Pp, Ppk)."""
        if len(self._raw_points) < 5:
            # Insufficient points: return baseline defaults
            return ProcessCapabilityReport(
                cp=1.0,
                cpk=1.0,
                pp=1.0,
                ppk=1.0,
                mean=self.center_line,
                sigma_within=self.sigma,
                sigma_overall=self.sigma,
                usl=self.usl,
                lsl=self.lsl,
                target=self.target,
                is_capable=False,
                six_sigma_level=3.0,
            )

        raw_arr = np.array(self._raw_points, dtype=np.float64)
        mean_val = float(np.mean(raw_arr))
        sigma_overall = float(np.std(raw_arr, ddof=1))

        # Within-subgroup sigma estimated from Rbar/d2 or average moving range
        sigma_within = max(1e-12, self.sigma)
        sigma_overall = max(1e-12, sigma_overall)

        spec_width = self.usl - self.lsl

        # Cp & Cpk (within-subgroup short-term potential)
        cp = spec_width / (6.0 * sigma_within)
        cpu = (self.usl - mean_val) / (3.0 * sigma_within)
        cpl = (mean_val - self.lsl) / (3.0 * sigma_within)
        cpk = min(cpu, cpl)

        # Pp & Ppk (overall long-term performance)
        pp = spec_width / (6.0 * sigma_overall)
        ppu = (self.usl - mean_val) / (3.0 * sigma_overall)
        ppl = (mean_val - self.lsl) / (3.0 * sigma_overall)
        ppk = min(ppu, ppl)

        is_capable = cpk >= 1.33
        six_sigma_level = round(3.0 * cpk, 2)

        return ProcessCapabilityReport(
            cp=round(cp, 3),
            cpk=round(cpk, 3),
            pp=round(pp, 3),
            ppk=round(ppk, 3),
            mean=round(mean_val, 3),
            sigma_within=round(sigma_within, 4),
            sigma_overall=round(sigma_overall, 4),
            usl=self.usl,
            lsl=self.lsl,
            target=self.target,
            is_capable=is_capable,
            six_sigma_level=six_sigma_level,
        )

    def get_chart_data(self) -> Dict[str, Any]:
        """Generate structured data for HMI / dashboard rendering.

        Provides:
          - Points with coordinate index and zones
          - Center line, control limits, and specification limits
          - Zone boundary lines (+/- 1s, +/- 2s, +/- 3s)
          - Active rule violations
          - Process capability summary
        """
        points_data: List[Dict[str, Any]] = []

        for idx, (val, ts) in enumerate(zip(self._chart_values, self._timestamps)):
            z = (val - self.center_line) / max(1e-12, self.sigma)
            if abs(z) > 3.0:
                zone = "OUT_OF_SPEC"
            elif z > 2.0:
                zone = "ZONE_A_PLUS"
            elif z > 1.0:
                zone = "ZONE_B_PLUS"
            elif z >= 0.0:
                zone = "ZONE_C_PLUS"
            elif z >= -1.0:
                zone = "ZONE_C_MINUS"
            elif z >= -2.0:
                zone = "ZONE_B_MINUS"
            else:
                zone = "ZONE_A_MINUS"

            # Check if this point triggers any violation
            viols = [v.rule_name for v in self.violations if v.point_index == idx]

            points_data.append({
                "index": idx,
                "timestamp": ts,
                "value": round(val, 3),
                "z_score": round(z, 2),
                "zone": zone,
                "violations": viols,
            })

        cap = self.calculate_capability()

        return {
            "parameter_name": self.parameter_name,
            "unit": self.unit,
            "chart_type": self.chart_type.value,
            "total_points": len(self._chart_values),
            "limits": {
                "ucl": round(self.ucl, 3),
                "cl": round(self.center_line, 3),
                "lcl": round(self.lcl, 3),
                "plus_2_sigma": round(self.center_line + 2.0 * self.sigma, 3),
                "plus_1_sigma": round(self.center_line + 1.0 * self.sigma, 3),
                "minus_1_sigma": round(self.center_line - 1.0 * self.sigma, 3),
                "minus_2_sigma": round(self.center_line - 2.0 * self.sigma, 3),
                "usl": self.usl,
                "target": self.target,
                "lsl": self.lsl,
            },
            "points": points_data,
            "violations_count": len(self.violations),
            "violations": [
                {
                    "rule_id": v.rule_id.value,
                    "rule_name": v.rule_name,
                    "point_index": v.point_index,
                    "point_value": round(v.point_value, 3),
                    "description": v.description,
                    "severity": v.severity,
                }
                for v in self.violations
            ],
            "capability": {
                "cp": cap.cp,
                "cpk": cap.cpk,
                "pp": cap.pp,
                "ppk": cap.ppk,
                "sigma_within": cap.sigma_within,
                "sigma_overall": cap.sigma_overall,
                "is_capable": cap.is_capable,
                "six_sigma_level": cap.six_sigma_level,
            },
        }
