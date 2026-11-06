"""Metrology Measurement Simulation Models for Semiconductor Manufacturing.

This module provides physically grounded metrology simulation models covering:
  1. Film Thickness & Optical Constants (Spectroscopic Ellipsometry)
  2. Critical Dimension SEM (CD, Sidewall Angle, LER, LWR)
  3. Overlay Metrology & Linear Correction Modeling (SEMI 6-parameter model)
  4. Defect Inspection & Yield Impact / Kill Ratio Modeling
  5. Four-Point Probe Sheet Resistance & Doping Concentration Extraction

Standards References:
  - SEMI E95: Specification for Human Interface for Semiconductor Manufacturing Equipment
  - ASTM F84: Standard Test Method for Measuring Resistivity of Silicon Wafers with an In-Line Four-Point Probe
  - SEMI M1: Specifications for Polished Single Crystal Silicon Wafers
  - ITRS Metrology Roadmap: Measurement Uncertainty Requirements for Sub-100nm Nodes
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


class PatternType(str, Enum):
    """Spatial measurement sampling grid pattern across circular wafer."""
    FIVE_POINT = "5_POINT"      # Center, Top, Bottom, Left, Right
    NINE_POINT = "9_POINT"      # Center + 4 inner ring + 4 outer ring
    FORTY_NINE_POINT = "49_POINT"  # Concentric rings dense ASTM pattern


class DefectClass(str, Enum):
    """SEMI standard defect classifications."""
    PARTICLE = "PARTICLE"
    SCRATCH = "SCRATCH"
    PATTERN_DEFECT = "PATTERN_DEFECT"
    RESIDUE = "RESIDUE"
    BRIDGING = "BRIDGING"
    VOID = "VOID"


@dataclass(frozen=True)
class MetrologySpecLimits:
    """Statistical Process Control and Engineering limits for metrology attributes.

    Attributes:
        target: Nominal engineering setpoint.
        lsl: Lower Specification Limit.
        usl: Upper Specification Limit.
        lcl: Lower Control Limit (typically 3-sigma below mean).
        ucl: Upper Control Limit (typically 3-sigma above mean).
        unit: Physical engineering unit string.
    """

    target: float
    lsl: float
    usl: float
    lcl: float
    ucl: float
    unit: str

    def is_in_spec(self, value: float) -> bool:
        """Check if reading is within engineering hard specification limits."""
        return self.lsl <= value <= self.usl

    def is_in_control(self, value: float) -> bool:
        """Check if reading is within statistical process control limits."""
        return self.lcl <= value <= self.ucl


# =====================================================================
# 1. FILM THICKNESS & REFRACTIVE INDEX (SPECTROSCOPIC ELLIPSOMETRY)
# =====================================================================

@dataclass
class FilmThicknessMeasurement:
    """Spectroscopic Ellipsometry thin-film metrology model.

    Physics Grounding:
      Measures relative phase difference Delta and amplitude ratio Psi:
        rho = r_p / r_s = tan(Psi) * exp(i * Delta)
      Calculates physical film thickness d (Angstroms / nm) and dispersion
      via Cauchy model: n(lambda) = A_n + B_n / lambda^2.
    """

    wafer_id: str
    film_type: str  # e.g., 'SiO2', 'Si3N4', 'HfO2', 'Polysilicon'
    nominal_thickness_angstrom: float
    pattern: PatternType = PatternType.FORTY_NINE_POINT
    wafer_diameter_mm: float = 300.0
    edge_exclusion_mm: float = 3.0
    limits: Optional[MetrologySpecLimits] = None

    # Measured outputs populated upon simulation run
    site_coordinates: List[Tuple[float, float]] = field(default_factory=list)  # (x_mm, y_mm)
    thickness_values_angstrom: List[float] = field(default_factory=list)
    refractive_index_n: float = 1.457  # Standard SiO2 at 632.8nm
    extinction_coeff_k: float = 0.0
    mean_thickness_angstrom: float = 0.0
    std_thickness_angstrom: float = 0.0
    min_thickness_angstrom: float = 0.0
    max_thickness_angstrom: float = 0.0
    uniformity_percent_range: float = 0.0  # (Max - Min) / (2 * Mean) * 100%
    uniformity_percent_1sigma: float = 0.0  # (1-sigma / Mean) * 100%
    goodness_of_fit_gof: float = 0.995     # MSE / GOF metric [0..1]

    def _generate_sampling_grid(self) -> List[Tuple[float, float]]:
        """Generate wafer coordinate sites based on chosen pattern with edge exclusion."""
        r_max = (self.wafer_diameter_mm / 2.0) - self.edge_exclusion_mm
        coords: List[Tuple[float, float]] = []

        if self.pattern == PatternType.FIVE_POINT:
            r_sample = 0.707 * r_max
            coords = [
                (0.0, 0.0),             # Center
                (0.0, r_sample),        # Top (12 o'clock)
                (0.0, -r_sample),       # Bottom (6 o'clock)
                (-r_sample, 0.0),       # Left (9 o'clock)
                (r_sample, 0.0),        # Right (3 o'clock)
            ]
        elif self.pattern == PatternType.NINE_POINT:
            r_inner = 0.45 * r_max
            r_outer = 0.85 * r_max
            coords.append((0.0, 0.0))
            for ang in [0.0, 90.0, 180.0, 270.0]:
                rad = math.radians(ang)
                coords.append((r_inner * math.cos(rad), r_inner * math.sin(rad)))
            for ang in [45.0, 135.0, 225.0, 315.0]:
                rad = math.radians(ang)
                coords.append((r_outer * math.cos(rad), r_outer * math.sin(rad)))
        else:  # FORTY_NINE_POINT concentric rings
            coords.append((0.0, 0.0))  # Center
            # Ring 1: 8 points at 0.3 * r_max
            for i in range(8):
                rad = i * (2.0 * math.pi / 8.0)
                coords.append((0.3 * r_max * math.cos(rad), 0.3 * r_max * math.sin(rad)))
            # Ring 2: 16 points at 0.6 * r_max
            for i in range(16):
                rad = i * (2.0 * math.pi / 16.0)
                coords.append((0.6 * r_max * math.cos(rad), 0.6 * r_max * math.sin(rad)))
            # Ring 3: 24 points at 0.9 * r_max
            for i in range(24):
                rad = i * (2.0 * math.pi / 24.0)
                coords.append((0.9 * r_max * math.cos(rad), 0.9 * r_max * math.sin(rad)))

        return coords

    def simulate_measurement(
        self,
        center_thickness_angstrom: Optional[float] = None,
        radial_gradient_pct: float = 1.5,
        instrument_noise_angstrom: float = 0.3,
        random_seed: Optional[int] = None,
    ) -> FilmThicknessMeasurement:
        """Simulate physical ellipsometry measurement across the wafer map.

        Args:
            center_thickness_angstrom: Actual physical thickness at center (defaults to nominal).
            radial_gradient_pct: Radial process non-uniformity (% change from center to edge).
            instrument_noise_angstrom: 1-sigma spectral ellipsometer optical noise.
            random_seed: Optional deterministic RNG seed.

        Returns:
            Self with populated measurement fields.
        """
        rng = np.random.default_rng(random_seed)
        nominal = center_thickness_angstrom or self.nominal_thickness_angstrom
        r_max = (self.wafer_diameter_mm / 2.0) - self.edge_exclusion_mm

        self.site_coordinates = self._generate_sampling_grid()
        measurements: List[float] = []

        for x, y in self.site_coordinates:
            r = math.sqrt(x**2 + y**2)
            normalized_r = min(1.0, r / max(1.0, r_max))

            # Parabolic radial process variation (typical of CVD/Furnace flow aerodynamics)
            radial_delta = nominal * (radial_gradient_pct / 100.0) * (normalized_r**2)

            # Random instrumental ellipsometric noise (Gaussian)
            noise = rng.normal(0.0, instrument_noise_angstrom)

            val = max(0.0, nominal + radial_delta + noise)
            measurements.append(round(val, 2))

        self.thickness_values_angstrom = measurements
        arr = np.array(measurements, dtype=np.float64)

        self.mean_thickness_angstrom = float(np.mean(arr))
        self.std_thickness_angstrom = float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0
        self.min_thickness_angstrom = float(np.min(arr))
        self.max_thickness_angstrom = float(np.max(arr))

        if self.mean_thickness_angstrom > 0.0:
            self.uniformity_percent_range = round(
                ((self.max_thickness_angstrom - self.min_thickness_angstrom) / (2.0 * self.mean_thickness_angstrom)) * 100.0,
                3,
            )
            self.uniformity_percent_1sigma = round(
                (self.std_thickness_angstrom / self.mean_thickness_angstrom) * 100.0, 3
            )

        # Realistic optical dispersion
        if "sio2" in self.film_type.lower() or "oxide" in self.film_type.lower():
            self.refractive_index_n = round(1.457 + float(rng.normal(0.0, 0.002)), 4)
            self.extinction_coeff_k = 0.0
        elif "nitride" in self.film_type.lower() or "si3n4" in self.film_type.lower():
            self.refractive_index_n = round(2.010 + float(rng.normal(0.0, 0.005)), 4)
            self.extinction_coeff_k = 0.0
        elif "hfo2" in self.film_type.lower():
            self.refractive_index_n = round(2.110 + float(rng.normal(0.0, 0.008)), 4)
            self.extinction_coeff_k = 0.001
        elif "poly" in self.film_type.lower():
            self.refractive_index_n = round(3.950 + float(rng.normal(0.0, 0.020)), 4)
            self.extinction_coeff_k = round(0.050 + float(rng.normal(0.0, 0.005)), 4)

        self.goodness_of_fit_gof = round(float(rng.uniform(0.991, 0.999)), 4)
        return self


# =====================================================================
# 2. CRITICAL DIMENSION SEM (CD-SEM)
# =====================================================================

@dataclass
class CDMeasurement:
    """Critical Dimension Scanning Electron Microscope (CD-SEM) model.

    Physics Grounding:
      Extracts line width profiles from SEM secondary electron intensity waveforms.
      Computes Top CD, Bottom CD, Sidewall Angle (SWA),
      Line Edge Roughness (LER), and Line Width Roughness (LWR).
    """

    wafer_id: str
    feature_name: str  # e.g., 'POLY_GATE', 'FIN_WIDTH', 'METAL1_TRENCH'
    target_bottom_cd_nm: float
    feature_height_nm: float
    sampling_sites_count: int = 13
    wafer_diameter_mm: float = 300.0
    limits: Optional[MetrologySpecLimits] = None

    # Measurements populated upon simulation
    site_bottom_cds_nm: List[float] = field(default_factory=list)
    site_top_cds_nm: List[float] = field(default_factory=list)
    site_sidewall_angles_deg: List[float] = field(default_factory=list)
    mean_bottom_cd_nm: float = 0.0
    cd_3sigma_nm: float = 0.0
    mean_sidewall_angle_deg: float = 88.5
    ler_3sigma_nm: float = 2.1  # Line Edge Roughness (nm, 3-sigma)
    lwr_3sigma_nm: float = 3.0  # Line Width Roughness (nm, 3-sigma)

    def simulate_measurement(
        self,
        actual_center_cd_nm: Optional[float] = None,
        target_swa_deg: float = 89.0,
        sem_beam_noise_nm: float = 0.25,
        random_seed: Optional[int] = None,
    ) -> CDMeasurement:
        """Simulate CD-SEM measurement across wafer sites."""
        rng = np.random.default_rng(random_seed)
        nominal_cd = actual_center_cd_nm or self.target_bottom_cd_nm

        bottom_cds: List[float] = []
        top_cds: List[float] = []
        swas: List[float] = []

        for site_idx in range(self.sampling_sites_count):
            # Radial etch loading effect: edges usually slightly smaller or larger
            r_norm = (site_idx / max(1, self.sampling_sites_count - 1))
            radial_shift = 0.4 * (r_norm - 0.5)

            # SEM measurement repeatability noise
            noise = rng.normal(0.0, sem_beam_noise_nm)
            b_cd = round(nominal_cd + radial_shift + noise, 3)

            # Sidewall angle calculation:
            # SWA = 90 - arctan((Bottom_CD - Top_CD) / (2 * Height))
            # Conversely: Top_CD = Bottom_CD - 2 * Height * tan(90 - SWA)
            swa_site = round(float(target_swa_deg + rng.normal(0.0, 0.3)), 2)
            swa_site = max(80.0, min(90.0, swa_site))
            swas.append(swa_site)

            swa_rad = math.radians(90.0 - swa_site)
            delta_cd = 2.0 * self.feature_height_nm * math.tan(swa_rad)
            t_cd = round(b_cd - delta_cd, 3)

            bottom_cds.append(b_cd)
            top_cds.append(t_cd)

        self.site_bottom_cds_nm = bottom_cds
        self.site_top_cds_nm = top_cds
        self.site_sidewall_angles_deg = swas

        arr_b = np.array(bottom_cds, dtype=np.float64)
        self.mean_bottom_cd_nm = round(float(np.mean(arr_b)), 3)
        std_b = float(np.std(arr_b, ddof=1)) if len(arr_b) > 1 else 0.0
        self.cd_3sigma_nm = round(3.0 * std_b, 3)
        self.mean_sidewall_angle_deg = round(float(np.mean(swas)), 2)

        # LER and LWR physically grounded models
        # LWR ~ sqrt(2) * LER for uncorrelated edges
        base_ler = max(1.2, 0.04 * self.mean_bottom_cd_nm)
        self.ler_3sigma_nm = round(base_ler + float(rng.normal(0.0, 0.15)), 2)
        self.lwr_3sigma_nm = round(math.sqrt(2.0) * self.ler_3sigma_nm + float(rng.normal(0.0, 0.1)), 2)

        return self


# =====================================================================
# 3. OVERLAY METROLOGY & CORRECTION MODELING
# =====================================================================

@dataclass
class OverlayCorrectionParameters:
    """SEMI standard 6-parameter linear overlay model parameters."""
    translation_x_nm: float = 0.0    # T_x
    translation_y_nm: float = 0.0    # T_y
    wafer_mag_x_ppm: float = 0.0     # M_x (parts per million)
    wafer_mag_y_ppm: float = 0.0     # M_y (parts per million)
    wafer_rot_x_urad: float = 0.0    # Theta_x (micro-radians)
    wafer_rot_y_urad: float = 0.0    # Theta_y (micro-radians)


@dataclass
class OverlayMeasurement:
    """Optical Overlay Tool simulation and linear error modeling.

    Physics Grounding:
      Measures relative alignment target displacement between consecutive litho layers.
      Standard SEMI model:
        Delta_X = T_x + M_x * x - Theta_x * y + Res_x
        Delta_Y = T_y + M_y * y + Theta_y * x + Res_y
    """

    wafer_id: str
    current_layer: str   # e.g., 'GATE_POLY'
    reference_layer: str  # e.g., 'ACTIVE_DIFF'
    field_count: int = 17
    wafer_diameter_mm: float = 300.0
    limits: Optional[MetrologySpecLimits] = None

    # Measurements populated upon simulation
    field_coordinates: List[Tuple[float, float]] = field(default_factory=list)  # (x_mm, y_mm)
    raw_delta_x_nm: List[float] = field(default_factory=list)
    raw_delta_y_nm: List[float] = field(default_factory=list)
    modeled_corrections: OverlayCorrectionParameters = field(default_factory=OverlayCorrectionParameters)
    residual_3sigma_x_nm: float = 0.0
    residual_3sigma_y_nm: float = 0.0
    max_overlay_error_vector_nm: float = 0.0

    def simulate_measurement(
        self,
        true_tx_nm: float = 2.4,
        true_ty_nm: float = -1.8,
        true_mag_ppm: float = 0.45,
        true_rot_urad: float = 0.60,
        stage_repeatability_nm: float = 0.4,
        random_seed: Optional[int] = None,
    ) -> OverlayMeasurement:
        """Simulate optical overlay readings across a multi-field die array and fit correction."""
        rng = np.random.default_rng(random_seed)
        r_max = (self.wafer_diameter_mm / 2.0) - 10.0

        # Create multi-die coordinate grid
        grid_coords: List[Tuple[float, float]] = []
        step = (2.0 * r_max) / 5.0
        for xi in np.arange(-r_max + 15, r_max, step):
            for yi in np.arange(-r_max + 15, r_max, step):
                if math.sqrt(xi**2 + yi**2) <= r_max:
                    grid_coords.append((float(round(xi, 1)), float(round(yi, 1))))

        if len(grid_coords) > self.field_count:
            # Deterministic subset
            idx_sub = np.linspace(0, len(grid_coords) - 1, self.field_count, dtype=int)
            self.field_coordinates = [grid_coords[i] for i in idx_sub]
        else:
            self.field_coordinates = grid_coords

        dx_list: List[float] = []
        dy_list: List[float] = []
        max_vec = 0.0

        # Generate modeled displacement + random measurement noise
        for x, y in self.field_coordinates:
            # Convert coordinates from mm to meters for ppm/urad calculations:
            # dx = T_x(nm) + M_x(ppm)*x(mm)*1e-3 + ...
            # 1 ppm * 1 mm = 1e-6 * 1e-3 m = 1e-9 m = 1 nm
            calc_dx = (
                true_tx_nm
                + (true_mag_ppm * x)
                - (true_rot_urad * y)
                + float(rng.normal(0.0, stage_repeatability_nm))
            )
            calc_dy = (
                true_ty_nm
                + (true_mag_ppm * y)
                + (true_rot_urad * x)
                + float(rng.normal(0.0, stage_repeatability_nm))
            )

            dx_list.append(round(calc_dx, 2))
            dy_list.append(round(calc_dy, 2))

            vec = math.sqrt(calc_dx**2 + calc_dy**2)
            if vec > max_vec:
                max_vec = vec

        self.raw_delta_x_nm = dx_list
        self.raw_delta_y_nm = dy_list
        self.max_overlay_error_vector_nm = round(max_vec, 2)

        # Fit 6-parameter linear overlay model via Least Squares Regression
        # X system: dx = [1, x, -y] * [Tx, Mx, RotX]^T
        # Y system: dy = [1, y,  x] * [Ty, My, RotY]^T
        n_pts = len(self.field_coordinates)
        if n_pts >= 3:
            A_x = np.column_stack([
                np.ones(n_pts),
                [pt[0] for pt in self.field_coordinates],
                [-pt[1] for pt in self.field_coordinates],
            ])
            A_y = np.column_stack([
                np.ones(n_pts),
                [pt[1] for pt in self.field_coordinates],
                [pt[0] for pt in self.field_coordinates],
            ])

            sol_x, residuals_x, _, _ = np.linalg.lstsq(A_x, dx_list, rcond=None)
            sol_y, residuals_y, _, _ = np.linalg.lstsq(A_y, dy_list, rcond=None)

            self.modeled_corrections = OverlayCorrectionParameters(
                translation_x_nm=round(float(sol_x[0]), 2),
                translation_y_nm=round(float(sol_y[0]), 2),
                wafer_mag_x_ppm=round(float(sol_x[1]), 3),
                wafer_mag_y_ppm=round(float(sol_y[1]), 3),
                wafer_rot_x_urad=round(float(sol_x[2]), 3),
                wafer_rot_y_urad=round(float(sol_y[2]), 3),
            )

            # Compute residuals
            fitted_x = A_x @ sol_x
            fitted_y = A_y @ sol_y
            res_x = np.array(dx_list) - fitted_x
            res_y = np.array(dy_list) - fitted_y

            self.residual_3sigma_x_nm = round(3.0 * float(np.std(res_x, ddof=1)), 2)
            self.residual_3sigma_y_nm = round(3.0 * float(np.std(res_y, ddof=1)), 2)

        return self


# =====================================================================
# 4. DEFECT INSPECTION & KILL RATIO MODELING
# =====================================================================

@dataclass
class DefectRecord:
    """Individual detected defect on wafer surface."""
    defect_id: int
    x_mm: float
    y_mm: float
    size_um: float
    classification: DefectClass
    is_fatal: bool
    kill_probability: float


@dataclass
class DefectInspection:
    """Darkfield/Brightfield Optical Laser Defect Inspection model.

    Physics Grounding:
      Detects particles, pattern bridges, and voids using laser scattering.
      Yield model uses Murphy and Seeds models with critical defect size kill ratios:
        P_kill = 1 / (1 + exp(-k * (size - CD_critical)))
        Yield = exp(-D_fatal * Area_die)
    """

    wafer_id: str
    inspection_step: str
    wafer_diameter_mm: float = 300.0
    critical_cd_nm: float = 180.0
    die_area_cm2: float = 0.50
    edge_exclusion_mm: float = 3.0

    # Inspection results populated upon simulation
    defect_records: List[DefectRecord] = field(default_factory=list)
    total_defect_count: int = 0
    defect_density_per_cm2: float = 0.0
    fatal_defect_count: int = 0
    estimated_die_yield_percent: float = 100.0
    defects_by_type: Dict[str, int] = field(default_factory=dict)

    @property
    def wafer_inspectable_area_cm2(self) -> float:
        """Inspectable surface area of the circular wafer in cm^2."""
        r_cm = ((self.wafer_diameter_mm / 2.0) - self.edge_exclusion_mm) / 10.0
        return math.pi * (r_cm**2)

    def simulate_inspection(
        self,
        base_lambda_defects: int = 28,
        random_seed: Optional[int] = None,
    ) -> DefectInspection:
        """Run stochastic defect scan across wafer area."""
        rng = np.random.default_rng(random_seed)
        r_max = (self.wafer_diameter_mm / 2.0) - self.edge_exclusion_mm

        # Poisson distribution for defect occurrence
        num_defects = int(rng.poisson(base_lambda_defects))
        records: List[DefectRecord] = []
        type_counts: Dict[str, int] = {c.value: 0 for c in DefectClass}
        fatal_count = 0

        crit_cd_um = self.critical_cd_nm / 1000.0

        for idx in range(1, num_defects + 1):
            # Uniform random location on circular disk
            r = r_max * math.sqrt(rng.uniform(0.0, 1.0))
            theta = rng.uniform(0.0, 2.0 * math.pi)
            x = round(r * math.cos(theta), 2)
            y = round(r * math.sin(theta), 2)

            # Defect size distribution: log-normal distribution
            size_um = round(float(rng.lognormal(mean=-1.5, sigma=0.65)), 3)
            size_um = max(0.03, size_um)

            # Classify defect
            p = rng.uniform(0.0, 1.0)
            if p < 0.50:
                d_class = DefectClass.PARTICLE
            elif p < 0.70:
                d_class = DefectClass.PATTERN_DEFECT
            elif p < 0.82:
                d_class = DefectClass.RESIDUE
            elif p < 0.92:
                d_class = DefectClass.BRIDGING
            elif p < 0.97:
                d_class = DefectClass.VOID
            else:
                d_class = DefectClass.SCRATCH

            type_counts[d_class.value] += 1

            # Kill ratio model:
            # Defects > 0.5 * CD have non-negligible kill probability
            # Defects > 1.0 * CD are almost certainly fatal
            ratio = size_um / max(0.01, crit_cd_um)
            if ratio < 0.3:
                kill_prob = 0.05
            elif ratio < 0.7:
                kill_prob = 0.35
            elif ratio < 1.0:
                kill_prob = 0.75
            else:
                kill_prob = 0.95

            is_fatal = bool(rng.uniform(0.0, 1.0) < kill_prob)
            if is_fatal:
                fatal_count += 1

            records.append(
                DefectRecord(
                    defect_id=idx,
                    x_mm=x,
                    y_mm=y,
                    size_um=size_um,
                    classification=d_class,
                    is_fatal=is_fatal,
                    kill_probability=round(kill_prob, 2),
                )
            )

        self.defect_records = records
        self.total_defect_count = num_defects
        self.defects_by_type = type_counts
        self.fatal_defect_count = fatal_count

        area = self.wafer_inspectable_area_cm2
        self.defect_density_per_cm2 = round(num_defects / area, 4) if area > 0 else 0.0

        # Poisson yield calculation: Y = exp(-D_fatal * Area_die)
        d_fatal_density = fatal_count / area if area > 0 else 0.0
        poisson_yield = math.exp(-d_fatal_density * self.die_area_cm2) * 100.0
        self.estimated_die_yield_percent = round(poisson_yield, 2)

        return self


# =====================================================================
# 5. SHEET RESISTANCE (FOUR-POINT PROBE)
# =====================================================================

@dataclass
class SheetResistanceMeasurement:
    """Four-Point Probe (4PP) Sheet Resistance and Doping Concentration model.

    Physics Grounding:
      Calculates sheet resistance R_s (ohms/sq) per ASTM F84:
        R_s = (V / I) * (pi / ln(2)) * F(t / s) * F_geom
      Correlates R_s and junction depth x_j to active doping concentration N_dop
      via Klaassen silicon carrier mobility equations:
        rho = R_s * x_j
        sigma = 1 / rho = q * N_dop * mu(N_dop)
    """

    wafer_id: str
    implant_step: str  # e.g., 'SOURCE_DRAIN_NMOS', 'WELL_IMPLANT'
    dopant_species: str  # 'Boron', 'Phosphorus', 'Arsenic'
    junction_depth_um: float = 0.20
    nominal_rs_ohm_per_sq: float = 50.0
    wafer_diameter_mm: float = 300.0
    pattern: PatternType = PatternType.FORTY_NINE_POINT
    limits: Optional[MetrologySpecLimits] = None

    # Measurements populated upon simulation
    site_rs_values: List[float] = field(default_factory=list)
    mean_rs_ohm_per_sq: float = 0.0
    rs_uniformity_percent_range: float = 0.0
    rs_std_dev: float = 0.0
    extracted_dopant_concentration_cm3: float = 1e20

    def _rs_to_doping_concentration(self, rs_ohm_sq: float, x_j_um: float) -> float:
        """Calculate active doping density from sheet resistance and junction depth."""
        # rho in ohm-cm = R_s (ohm/sq) * x_j (cm)
        x_j_cm = x_j_um * 1e-4
        rho = max(1e-6, rs_ohm_sq * x_j_cm)

        # Elementary charge
        q = 1.602176634e-19

        # Empirical mobility approximation for heavily doped silicon
        # For N > 1e18 cm^-3: mu_n ~ 100-200 cm^2/(V*s), mu_p ~ 50-80 cm^2/(V*s)
        is_n_type = self.dopant_species.lower() in ("phosphorus", "arsenic", "antimony")
        mu_approx = 130.0 if is_n_type else 65.0

        # N = 1 / (q * mu * rho)
        n_dop = 1.0 / (q * mu_approx * rho)
        return float(n_dop)

    def simulate_measurement(
        self,
        actual_center_rs: Optional[float] = None,
        radial_dose_gradient_pct: float = 2.0,
        probe_noise_ohm: float = 0.2,
        random_seed: Optional[int] = None,
    ) -> SheetResistanceMeasurement:
        """Simulate 4PP multi-site measurement and dopant density extraction."""
        rng = np.random.default_rng(random_seed)
        nominal_rs = actual_center_rs or self.nominal_rs_ohm_per_sq

        # Generate sampling sites using same grid geometry as thickness
        temp_thickness = FilmThicknessMeasurement(
            wafer_id=self.wafer_id,
            film_type="Si",
            nominal_thickness_angstrom=100.0,
            pattern=self.pattern,
            wafer_diameter_mm=self.wafer_diameter_mm,
        )
        grid = temp_thickness._generate_sampling_grid()
        r_max = (self.wafer_diameter_mm / 2.0) - 3.0

        readings: List[float] = []
        for x, y in grid:
            r = math.sqrt(x**2 + y**2)
            norm_r = min(1.0, r / max(1.0, r_max))

            # Dose uniformity across wafer during ion implantation (scan non-uniformity)
            delta = nominal_rs * (radial_dose_gradient_pct / 100.0) * (norm_r**1.5)
            noise = rng.normal(0.0, probe_noise_ohm)

            val = max(0.1, nominal_rs + delta + noise)
            readings.append(round(val, 3))

        self.site_rs_values = readings
        arr = np.array(readings, dtype=np.float64)

        self.mean_rs_ohm_per_sq = round(float(np.mean(arr)), 3)
        self.rs_std_dev = round(float(np.std(arr, ddof=1)), 3) if len(arr) > 1 else 0.0

        max_v = float(np.max(arr))
        min_v = float(np.min(arr))
        if self.mean_rs_ohm_per_sq > 0.0:
            self.rs_uniformity_percent_range = round(
                ((max_v - min_v) / (2.0 * self.mean_rs_ohm_per_sq)) * 100.0, 3
            )

        # Physics-based doping concentration extraction
        self.extracted_dopant_concentration_cm3 = self._rs_to_doping_concentration(
            self.mean_rs_ohm_per_sq, self.junction_depth_um
        )

        return self
