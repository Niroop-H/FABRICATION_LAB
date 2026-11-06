"""180nm CMOS Reference Process Flow (200mm Wafer).

This module defines a complete, industrially grounded 180nm (0.18 um) dual-gate oxide
CMOS reference fabrication route on 200mm single-crystal silicon substrates.
Features:
  - 1.8V / 3.3V dual-voltage operation
  - Shallow Trench Isolation (STI)
  - 3.5nm nominal core gate oxide
  - Cobalt/Titanium self-aligned silicide (salicide)
  - 6 levels of aluminum-copper interconnect with tungsten contacts/vias
  - Comprehensive metrology checkpoints and critical SPC specifications

Standards & Technology References:
  - SEMI M1: Specifications for Polished Single Crystal Silicon Wafers (200mm)
  - ITRS 180nm Technology Roadmap (Interconnect, Lithography, and Front-End Processes)
  - TSMC 0.18um Generic Logic Process Design Rule Manual & Process Specification
"""

from __future__ import annotations

from typing import Dict, List

from src.simulation.core.process_route import (
    CriticalSpec,
    ProcessRoute,
    ProcessStep,
    ProcessStepCategory,
)
from src.simulation.core.units import PhysicalQuantity


def get_180nm_cmos_process_route() -> ProcessRoute:
    """Construct and return the standardized 180nm CMOS 200mm fabrication route."""
    steps: List[ProcessStep] = []

    # -------------------------------------------------------------
    # Step 010: Initial Surface Clean (RCA Clean)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=10,
            step_id="STEP_010_RCA_CLEAN",
            name="Initial Wafer Surface Clean (RCA SC-1 / SC-2)",
            category=ProcessStepCategory.CLEAN,
            equipment_type="WET_BENCH_RCA",
            recipe_name="RECIPE_RCA_CLEAN_STD_200MM",
            estimated_duration_min=45.0,
            description="Sequential SC-1 (NH4OH:H2O2:H2O) organic clean, dilute HF oxide strip, and SC-2 (HCl:H2O2:H2O) metallic desorption.",
            parameters={
                "sc1_temperature": PhysicalQuantity(
                    value=75.0, unit="degC", valid_range=(65.0, 85.0), uncertainty=1.0, source="SEMI E12 Fab Standards"
                ),
                "sc2_temperature": PhysicalQuantity(
                    value=80.0, unit="degC", valid_range=(70.0, 90.0), uncertainty=1.0, source="SEMI E12 Fab Standards"
                ),
                "hf_concentration": PhysicalQuantity(
                    value=0.5, unit="%", valid_range=(0.2, 1.0), uncertainty=0.05, source="RCA Wet Clean Benchmark"
                ),
            },
            metrology_checkpoints=["DEFECT_INSPECTION_SURFACE"],
            critical_specs={
                "defect_density": CriticalSpec(
                    metric_name="defect_density",
                    target=PhysicalQuantity(0.05, "count", (0.0, 1.0), 0.01, "SEMI M1 Defect Spec"),
                    lsl=PhysicalQuantity(0.0, "count", (0.0, 0.0), 0.0, "Physical Lower Bound"),
                    usl=PhysicalQuantity(0.12, "count", (0.0, 0.5), 0.01, "Yield Boundary"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 020: Pad Oxide Growth
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=20,
            step_id="STEP_020_PAD_OXIDE",
            name="Pad Oxide Thermal Growth",
            category=ProcessStepCategory.OXIDATION,
            equipment_type="HORIZONTAL_DIFFUSION_FURNACE",
            recipe_name="RECIPE_DRY_O2_PAD_OX_10NM",
            estimated_duration_min=60.0,
            description="Dry oxidation to grow 10nm strain-relief pad oxide under Si3N4 mask.",
            parameters={
                "furnace_temperature": PhysicalQuantity(
                    value=900.0, unit="degC", valid_range=(850.0, 950.0), uncertainty=0.5, source="ITRS 180nm Front-End"
                ),
                "o2_flow_rate": PhysicalQuantity(
                    value=4500.0, unit="sccm", valid_range=(3000.0, 6000.0), uncertainty=10.0, source="ASM Furnace Manual"
                ),
                "process_time": PhysicalQuantity(
                    value=28.0, unit="min", valid_range=(15.0, 60.0), uncertainty=0.1, source="Deal-Grove Oxidation Model"
                ),
            },
            metrology_checkpoints=["THICKNESS_ELLIPSOMETRY"],
            critical_specs={
                "pad_oxide_thickness": CriticalSpec(
                    metric_name="pad_oxide_thickness",
                    target=PhysicalQuantity(10.0, "nm", (8.0, 12.0), 0.1, "180nm Process Spec"),
                    lsl=PhysicalQuantity(9.0, "nm", (8.0, 12.0), 0.1, "Engineering Limit"),
                    usl=PhysicalQuantity(11.0, "nm", (8.0, 12.0), 0.1, "Engineering Limit"),
                    lcl=PhysicalQuantity(9.5, "nm", (8.0, 12.0), 0.1, "SPC Control Limit"),
                    ucl=PhysicalQuantity(10.5, "nm", (8.0, 12.0), 0.1, "SPC Control Limit"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 030: LPCVD Silicon Nitride Deposition
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=30,
            step_id="STEP_030_LPCVD_NITRIDE",
            name="LPCVD Silicon Nitride (Si3N4) Deposition",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="LPCVD_VERTICAL_FURNACE",
            recipe_name="RECIPE_SI3N4_LPCVD_150NM",
            estimated_duration_min=90.0,
            description="Low-pressure chemical vapor deposition of 150nm Si3N4 using SiH2Cl2 (DCS) and NH3.",
            parameters={
                "deposition_temperature": PhysicalQuantity(
                    value=780.0, unit="degC", valid_range=(750.0, 820.0), uncertainty=0.5, source="ASM A400 LPCVD Guide"
                ),
                "chamber_pressure": PhysicalQuantity(
                    value=250.0, unit="mTorr", valid_range=(150.0, 350.0), uncertainty=2.0, source="LPCVD Spec"
                ),
                "dcs_flow": PhysicalQuantity(
                    value=50.0, unit="sccm", valid_range=(30.0, 80.0), uncertainty=0.5, source="LPCVD Spec"
                ),
                "nh3_flow": PhysicalQuantity(
                    value=150.0, unit="sccm", valid_range=(100.0, 250.0), uncertainty=1.0, source="LPCVD Spec"
                ),
            },
            metrology_checkpoints=["THICKNESS_ELLIPSOMETRY", "REFRACTIVE_INDEX"],
            critical_specs={
                "nitride_thickness": CriticalSpec(
                    metric_name="nitride_thickness",
                    target=PhysicalQuantity(150.0, "nm", (130.0, 170.0), 1.0, "180nm Hard Mask Spec"),
                    lsl=PhysicalQuantity(142.0, "nm", (130.0, 170.0), 1.0, "CMP Polish Stop Margin"),
                    usl=PhysicalQuantity(158.0, "nm", (130.0, 170.0), 1.0, "CMP Polish Stop Margin"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 040: Active Area Lithography (Mask 01: OD)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=40,
            step_id="STEP_040_ACTIVE_LITHO",
            name="Active Area (OD) Photolithography",
            category=ProcessStepCategory.LITHOGRAPHY,
            equipment_type="DUV_STEPPER_248NM",
            recipe_name="RECIPE_248NM_ACTIVE_OD",
            estimated_duration_min=30.0,
            description="248nm KrF DUV exposure of active diffusion islands (transistor active areas).",
            parameters={
                "exposure_dose": PhysicalQuantity(
                    value=22.5, unit="mJ/cm^2", valid_range=(15.0, 35.0), uncertainty=0.2, source="Nikon KrF Scanner Manual"
                ),
                "focus_offset": PhysicalQuantity(
                    value=0.0, unit="um", valid_range=(-0.3, 0.3), uncertainty=0.02, source="Focus-Exposure Matrix"
                ),
                "numerical_aperture": PhysicalQuantity(
                    value=0.68, unit="count", valid_range=(0.50, 0.82), uncertainty=0.005, source="KrF Optical Column"
                ),
            },
            metrology_checkpoints=["CD_SEM_AFTER_DEVELOP", "OVERLAY_METROLOGY"],
            critical_specs={
                "active_cd": CriticalSpec(
                    metric_name="active_cd",
                    target=PhysicalQuantity(220.0, "nm", (190.0, 250.0), 1.5, "180nm Design Rule OD.W.1"),
                    lsl=PhysicalQuantity(205.0, "nm", (190.0, 250.0), 1.5, "Short Margin"),
                    usl=PhysicalQuantity(235.0, "nm", (190.0, 250.0), 1.5, "Isolation Pitch Margin"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 050: Shallow Trench Isolation (STI) Etch
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=50,
            step_id="STEP_050_STI_ETCH",
            name="STI Silicon Trench Reactive Ion Etch",
            category=ProcessStepCategory.ETCH,
            equipment_type="ICP_RIE_ETCHER",
            recipe_name="RECIPE_STI_TRENCH_ETCH_350NM",
            estimated_duration_min=25.0,
            description="Anisotropic RIE of Si3N4/pad oxide and 350nm silicon substrate trench with 85-88 deg taper.",
            parameters={
                "source_power": PhysicalQuantity(
                    value=800.0, unit="W", valid_range=(500.0, 1200.0), uncertainty=5.0, source="Lam TCP 9400 Guide"
                ),
                "bias_power": PhysicalQuantity(
                    value=120.0, unit="W", valid_range=(60.0, 200.0), uncertainty=2.0, source="Lam TCP 9400 Guide"
                ),
                "cl2_flow": PhysicalQuantity(
                    value=75.0, unit="sccm", valid_range=(40.0, 120.0), uncertainty=1.0, source="Halogen Etch Chemistry"
                ),
                "hbr_flow": PhysicalQuantity(
                    value=150.0, unit="sccm", valid_range=(80.0, 250.0), uncertainty=1.0, source="Sidewall Passivation"
                ),
            },
            metrology_checkpoints=["CD_SEM_TRENCH_DEPTH", "DEFECT_INSPECTION"],
        )
    )

    # -------------------------------------------------------------
    # Step 060: STI Trench Liner Oxidation & HDP Oxide Fill
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=60,
            step_id="STEP_060_STI_FILL",
            name="STI Liner Oxidation & HDP-CVD Oxide Gap Fill",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="HDP_CVD_SYSTEM",
            recipe_name="RECIPE_HDP_OXIDE_STI_FILL_600NM",
            estimated_duration_min=50.0,
            description="High-density plasma (HDP) CVD void-free SiO2 deposition (simultaneous deposition and Ar sputter etch).",
            parameters={
                "hdp_rf_top_power": PhysicalQuantity(
                    value=2800.0, unit="W", valid_range=(2000.0, 3500.0), uncertainty=15.0, source="Applied Materials Ultima HDP"
                ),
                "sih4_flow": PhysicalQuantity(
                    value=90.0, unit="sccm", valid_range=(60.0, 130.0), uncertainty=1.0, source="AMAT Recipe Spec"
                ),
                "o2_flow": PhysicalQuantity(
                    value=140.0, unit="sccm", valid_range=(90.0, 200.0), uncertainty=1.0, source="AMAT Recipe Spec"
                ),
            },
            metrology_checkpoints=["THICKNESS_ELLIPSOMETRY"],
        )
    )

    # -------------------------------------------------------------
    # Step 070: STI Oxide Chemical Mechanical Planarization (CMP)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=70,
            step_id="STEP_070_STI_CMP",
            name="STI Oxide Chemical Mechanical Planarization (CMP)",
            category=ProcessStepCategory.CMP,
            equipment_type="CMP_POLISHER_200MM",
            recipe_name="RECIPE_STI_CERIA_CMP_STOP_NITRIDE",
            estimated_duration_min=40.0,
            description="High-selectivity ceria-based slurry CMP polishing down to Si3N4 stop layer.",
            parameters={
                "membrane_downforce_pressure": PhysicalQuantity(
                    value=3.2, unit="psi", valid_range=(2.0, 5.0), uncertainty=0.05, source="Mirra CMP Manual"
                ),
                "platen_speed": PhysicalQuantity(
                    value=75.0, unit="rpm", valid_range=(50.0, 110.0), uncertainty=0.5, source="Mirra CMP Manual"
                ),
            },
            metrology_checkpoints=["THICKNESS_ELLIPSOMETRY", "DEFECT_INSPECTION"],
            critical_specs={
                "remaining_nitride_thickness": CriticalSpec(
                    metric_name="remaining_nitride_thickness",
                    target=PhysicalQuantity(120.0, "nm", (90.0, 140.0), 2.0, "CMP Polish Overetch Control"),
                    lsl=PhysicalQuantity(100.0, "nm", (90.0, 140.0), 2.0, "Under-polish Protection"),
                    usl=PhysicalQuantity(135.0, "nm", (90.0, 140.0), 2.0, "Dishing Prevention"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 080: Nitride Strip & Pad Oxide Strip
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=80,
            step_id="STEP_080_NITRIDE_STRIP",
            name="Hot Phosphoric Acid Si3N4 Strip & DHF Pad Oxide Strip",
            category=ProcessStepCategory.STRIP,
            equipment_type="WET_BENCH_ACID",
            recipe_name="RECIPE_H3PO4_STRIP_160C",
            estimated_duration_min=60.0,
            description="Selective wet chemical strip of Si3N4 mask in 160 degC H3PO4 followed by dilute HF pad oxide strip.",
            parameters={
                "h3po4_temperature": PhysicalQuantity(
                    value=160.0, unit="degC", valid_range=(150.0, 170.0), uncertainty=1.0, source="SEMI Chemical Standards"
                ),
            },
            metrology_checkpoints=["DEFECT_INSPECTION"],
        )
    )

    # -------------------------------------------------------------
    # Step 090: Sacrificial Oxide & Well / Vt Implants
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=90,
            step_id="STEP_090_WELL_VT_IMPLANT",
            name="Well & Threshold Voltage (Vt) Ion Implants",
            category=ProcessStepCategory.ION_IMPLANT,
            equipment_type="MEDIUM_CURRENT_IMPLANTER",
            recipe_name="RECIPE_IMPLANT_RETROGRADE_WELLS",
            estimated_duration_min=75.0,
            description="Boron P-well / NMOS Vt adjust (B11+ @ 30 keV) and Phosphorus N-well / PMOS Vt adjust (P31+ @ 120 keV).",
            parameters={
                "pwell_boron_energy": PhysicalQuantity(
                    value=30.0, unit="keV", valid_range=(10.0, 80.0), uncertainty=0.1, source="Varian VIISion 80plus"
                ),
                "pwell_boron_dose": PhysicalQuantity(
                    value=1.2e12, unit="ions/cm^2", valid_range=(5e11, 5e12), uncertainty=1e10, source="180nm Device Physics Model"
                ),
                "nwell_phos_energy": PhysicalQuantity(
                    value=120.0, unit="keV", valid_range=(80.0, 200.0), uncertainty=0.2, source="Varian VIISion 80plus"
                ),
                "nwell_phos_dose": PhysicalQuantity(
                    value=2.5e12, unit="ions/cm^2", valid_range=(1e12, 6e12), uncertainty=2e10, source="180nm Device Physics Model"
                ),
            },
            metrology_checkpoints=["FOUR_POINT_PROBE_SHEET_R"],
        )
    )

    # -------------------------------------------------------------
    # Step 100: Pre-Gate Oxide Clean & Dry Gate Oxidation
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=100,
            step_id="STEP_100_GATE_OXIDATION",
            name="Critical Gate Dielectric Thermal Oxidation",
            category=ProcessStepCategory.OXIDATION,
            equipment_type="HORIZONTAL_DIFFUSION_FURNACE",
            recipe_name="RECIPE_DRY_O2_GATE_OX_35A",
            estimated_duration_min=55.0,
            description="Ultra-clean dry oxidation with trace N2O/NO anneal for 3.5nm (35 Angstrom) core gate oxide.",
            parameters={
                "furnace_temperature": PhysicalQuantity(
                    value=850.0, unit="degC", valid_range=(800.0, 900.0), uncertainty=0.2, source="TSMC 180nm G-Ox Baseline"
                ),
                "o2_flow": PhysicalQuantity(
                    value=2000.0, unit="sccm", valid_range=(1000.0, 4000.0), uncertainty=5.0, source="Furnace Recipe"
                ),
                "trans_lc_flow": PhysicalQuantity(
                    value=40.0, unit="sccm", valid_range=(20.0, 80.0), uncertainty=0.5, source="Chlorine Cleaning Agent"
                ),
            },
            metrology_checkpoints=["THICKNESS_ELLIPSOMETRY"],
            critical_specs={
                "gate_oxide_thickness": CriticalSpec(
                    metric_name="gate_oxide_thickness",
                    target=PhysicalQuantity(3.5, "nm", (3.0, 4.2), 0.05, "180nm Core Vdd=1.8V Spec"),
                    lsl=PhysicalQuantity(3.3, "nm", (3.0, 4.2), 0.05, "Gate Leakage Limit"),
                    usl=PhysicalQuantity(3.7, "nm", (3.0, 4.2), 0.05, "Drive Current Saturation Limit"),
                    lcl=PhysicalQuantity(3.4, "nm", (3.0, 4.2), 0.05, "Fab SPC UCL/LCL"),
                    ucl=PhysicalQuantity(3.6, "nm", (3.0, 4.2), 0.05, "Fab SPC UCL/LCL"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 110: Polysilicon Gate Deposition
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=110,
            step_id="STEP_110_POLY_DEP",
            name="LPCVD Polysilicon Gate Electrode Deposition",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="LPCVD_VERTICAL_FURNACE",
            recipe_name="RECIPE_POLY_LPCVD_200NM",
            estimated_duration_min=80.0,
            description="Low-pressure silane (SiH4) pyrolysis at 620 degC to deposit 200nm undoped polycrystalline silicon.",
            parameters={
                "deposition_temperature": PhysicalQuantity(
                    value=620.0, unit="degC", valid_range=(600.0, 640.0), uncertainty=0.3, source="LPCVD Poly Kinetics"
                ),
                "chamber_pressure": PhysicalQuantity(
                    value=300.0, unit="mTorr", valid_range=(200.0, 450.0), uncertainty=2.0, source="LPCVD Poly Kinetics"
                ),
                "sih4_flow": PhysicalQuantity(
                    value=180.0, unit="sccm", valid_range=(120.0, 250.0), uncertainty=1.0, source="LPCVD Poly Kinetics"
                ),
            },
            metrology_checkpoints=["THICKNESS_ELLIPSOMETRY"],
            critical_specs={
                "poly_thickness": CriticalSpec(
                    metric_name="poly_thickness",
                    target=PhysicalQuantity(200.0, "nm", (180.0, 220.0), 1.0, "180nm Gate Height Spec"),
                    lsl=PhysicalQuantity(190.0, "nm", (180.0, 220.0), 1.0, "Implant Channeling Stop"),
                    usl=PhysicalQuantity(210.0, "nm", (180.0, 220.0), 1.0, "Aspect Ratio Etch Margin"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 120: Gate Photolithography (Mask 02: PO)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=120,
            step_id="STEP_120_GATE_LITHO",
            name="Critical Poly Gate Photolithography (248nm DUV)",
            category=ProcessStepCategory.LITHOGRAPHY,
            equipment_type="DUV_STEPPER_248NM",
            recipe_name="RECIPE_248NM_GATE_POLY_CRITICAL",
            estimated_duration_min=35.0,
            description="Critical 180nm KrF exposure with organic bottom anti-reflective coating (BARC) for minimum gate length.",
            parameters={
                "exposure_dose": PhysicalQuantity(
                    value=28.0, unit="mJ/cm^2", valid_range=(20.0, 40.0), uncertainty=0.2, source="Scanner Dose Calibration"
                ),
                "barc_thickness": PhysicalQuantity(
                    value=60.0, unit="nm", valid_range=(50.0, 70.0), uncertainty=0.5, source="DUV Anti-Reflective Coating"
                ),
            },
            metrology_checkpoints=["CD_SEM_AFTER_DEVELOP", "OVERLAY_METROLOGY"],
            critical_specs={
                "develop_gate_cd": CriticalSpec(
                    metric_name="develop_gate_cd",
                    target=PhysicalQuantity(180.0, "nm", (165.0, 195.0), 1.0, "180nm Technology Node Ground Rule"),
                    lsl=PhysicalQuantity(170.0, "nm", (165.0, 195.0), 1.0, "Punchthrough Breakdown Limit"),
                    usl=PhysicalQuantity(190.0, "nm", (165.0, 195.0), 1.0, "Circuit Switching Speed Limit"),
                    lcl=PhysicalQuantity(175.0, "nm", (165.0, 195.0), 1.0, "SPC 3-Sigma Lower Bound"),
                    ucl=PhysicalQuantity(185.0, "nm", (165.0, 195.0), 1.0, "SPC 3-Sigma Upper Bound"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 130: Polysilicon Gate Reactive Ion Etch
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=130,
            step_id="STEP_130_GATE_ETCH",
            name="Polysilicon Gate Anisotropic Plasma Etch",
            category=ProcessStepCategory.ETCH,
            equipment_type="ICP_RIE_ETCHER",
            recipe_name="RECIPE_POLY_GATE_ETCH_HBR_CL2",
            estimated_duration_min=25.0,
            description="Highly selective HBr/Cl2/O2 ICP etch stopping with >100:1 selectivity on 3.5nm gate oxide.",
            parameters={
                "source_rf_power": PhysicalQuantity(
                    value=650.0, unit="W", valid_range=(450.0, 900.0), uncertainty=3.0, source="Lam Research Versys Poly Etcher"
                ),
                "bias_power": PhysicalQuantity(
                    value=80.0, unit="W", valid_range=(40.0, 150.0), uncertainty=1.0, source="Versys Recipe Spec"
                ),
                "hbr_flow": PhysicalQuantity(
                    value=200.0, unit="sccm", valid_range=(120.0, 300.0), uncertainty=1.5, source="HBr Chemistry"
                ),
            },
            metrology_checkpoints=["CD_SEM_AFTER_ETCH", "DEFECT_INSPECTION"],
            critical_specs={
                "final_gate_cd": CriticalSpec(
                    metric_name="final_gate_cd",
                    target=PhysicalQuantity(180.0, "nm", (165.0, 195.0), 1.0, "180nm Final Physical Poly CD"),
                    lsl=PhysicalQuantity(172.0, "nm", (165.0, 195.0), 1.0, "Leakage Floor"),
                    usl=PhysicalQuantity(188.0, "nm", (165.0, 195.0), 1.0, "Delay Ceiling"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 140: Lightly Doped Drain (LDD) & Halo Implantation
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=140,
            step_id="STEP_140_LDD_IMPLANT",
            name="NMOS / PMOS Lightly Doped Drain (LDD) & Halo Implants",
            category=ProcessStepCategory.ION_IMPLANT,
            equipment_type="MEDIUM_CURRENT_IMPLANTER",
            recipe_name="RECIPE_LDD_HALO_DUAL",
            estimated_duration_min=70.0,
            description="Phosphorus/Arsenic NMOS LDD with tilted Boron pocket halo; BF2 PMOS LDD with Arsenic halo.",
            parameters={
                "nmos_ldd_dose": PhysicalQuantity(
                    value=3.5e14, unit="ions/cm^2", valid_range=(1e14, 8e14), uncertainty=5e12, source="180nm Short-Channel Model"
                ),
                "nmos_ldd_energy": PhysicalQuantity(
                    value=15.0, unit="keV", valid_range=(8.0, 25.0), uncertainty=0.1, source="Implanter Beamline Spec"
                ),
                "halo_tilt_angle": PhysicalQuantity(
                    value=28.0, unit="count", valid_range=(20.0, 35.0), uncertainty=0.2, source="Quad-Rotated Halo Spec"
                ),
            },
            metrology_checkpoints=["FOUR_POINT_PROBE_SHEET_R"],
        )
    )

    # -------------------------------------------------------------
    # Step 150: Gate Sidewall Spacer Deposition & Etchback
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=150,
            step_id="STEP_150_SPACER_FORMATION",
            name="LPCVD Oxide/Nitride Spacer Deposition & Anisotropic Etchback",
            category=ProcessStepCategory.ETCH,
            equipment_type="ICP_RIE_ETCHER",
            recipe_name="RECIPE_SPACER_OX_SIN_ETCHBACK",
            estimated_duration_min=45.0,
            description="LPCVD 80nm Si3N4 spacer film followed by fluorocarbon RIE etchback leaving 70nm sidewall spacers.",
            parameters={
                "chf3_flow": PhysicalQuantity(
                    value=60.0, unit="sccm", valid_range=(40.0, 90.0), uncertainty=1.0, source="Spacer Etch Chemistry"
                ),
                "cf4_flow": PhysicalQuantity(
                    value=40.0, unit="sccm", valid_range=(20.0, 70.0), uncertainty=1.0, source="Spacer Etch Chemistry"
                ),
            },
            metrology_checkpoints=["CD_SEM_AFTER_ETCH"],
            critical_specs={
                "spacer_width": CriticalSpec(
                    metric_name="spacer_width",
                    target=PhysicalQuantity(70.0, "nm", (55.0, 85.0), 1.0, "LDD Offset Dimension"),
                    lsl=PhysicalQuantity(62.0, "nm", (55.0, 85.0), 1.0, "Hot Carrier Injection Shield"),
                    usl=PhysicalQuantity(78.0, "nm", (55.0, 85.0), 1.0, "Series Resistance Margin"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 160: Deep Source/Drain High-Current Ion Implantation
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=160,
            step_id="STEP_160_SD_IMPLANT",
            name="Deep Source/Drain (S/D) Heavy Ion Implantation",
            category=ProcessStepCategory.ION_IMPLANT,
            equipment_type="HIGH_CURRENT_IMPLANTER",
            recipe_name="RECIPE_DEEP_SD_AS_BF2",
            estimated_duration_min=90.0,
            description="As75+ @ 50 keV (5e15/cm2) for NMOS; BF2+ @ 35 keV (3e15/cm2) for PMOS.",
            parameters={
                "arsenic_energy": PhysicalQuantity(
                    value=50.0, unit="keV", valid_range=(35.0, 70.0), uncertainty=0.2, source="Applied Materials Quantum Leap"
                ),
                "arsenic_dose": PhysicalQuantity(
                    value=5.0e15, unit="ions/cm^2", valid_range=(3e15, 8e15), uncertainty=5e13, source="Quantum High-Current Spec"
                ),
                "bf2_energy": PhysicalQuantity(
                    value=35.0, unit="keV", valid_range=(20.0, 50.0), uncertainty=0.2, source="Quantum High-Current Spec"
                ),
                "bf2_dose": PhysicalQuantity(
                    value=3.0e15, unit="ions/cm^2", valid_range=(2e15, 6e15), uncertainty=3e13, source="Quantum High-Current Spec"
                ),
            },
            metrology_checkpoints=["FOUR_POINT_PROBE_SHEET_R"],
            critical_specs={
                "n_plus_sheet_resistance": CriticalSpec(
                    metric_name="n_plus_sheet_resistance",
                    target=PhysicalQuantity(45.0, "ohm/sq", (30.0, 65.0), 0.5, "180nm S/D As Implant Target"),
                    lsl=PhysicalQuantity(38.0, "ohm/sq", (30.0, 65.0), 0.5, "Over-doping Junction Leakage"),
                    usl=PhysicalQuantity(52.0, "ohm/sq", (30.0, 65.0), 0.5, "Series Resistance Limit"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 170: Rapid Thermal Anneal (RTA) Dopant Activation
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=170,
            step_id="STEP_170_RTA_ANNEAL",
            name="Source/Drain Rapid Thermal Dopant Activation Anneal",
            category=ProcessStepCategory.ANNEAL,
            equipment_type="RTA_SYSTEM",
            recipe_name="RECIPE_RTA_SPIKE_1020C",
            estimated_duration_min=20.0,
            description="Atmospheric N2 rapid thermal spike anneal at 1020 degC to activate dopants with minimal diffusion.",
            parameters={
                "peak_temperature": PhysicalQuantity(
                    value=1020.0, unit="degC", valid_range=(980.0, 1050.0), uncertainty=1.0, source="Mattson Helios RTA"
                ),
                "dwell_time": PhysicalQuantity(
                    value=15.0, unit="s", valid_range=(5.0, 30.0), uncertainty=0.1, source="Mattson Helios RTA"
                ),
                "ramp_rate": PhysicalQuantity(
                    value=75.0, unit="degC", valid_range=(50.0, 150.0), uncertainty=1.0, source="Pyrometer Control"
                ),
            },
            metrology_checkpoints=["FOUR_POINT_PROBE_SHEET_R"],
        )
    )

    # -------------------------------------------------------------
    # Step 180: Cobalt Self-Aligned Silicide (Salicide) Formation
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=180,
            step_id="STEP_180_SALICIDE",
            name="Cobalt Self-Aligned Silicidation (CoSi2 Salicide)",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="SPUTTER_PVD_SYSTEM",
            recipe_name="RECIPE_PVD_CO_TIN_CAP_SALICIDE",
            estimated_duration_min=50.0,
            description="PVD 12nm Co + 20nm TiN cap; 1st RTA 500 degC; selective wet strip of unreacted metal; 2nd RTA 800 degC to form low-resistivity CoSi2.",
            parameters={
                "co_thickness": PhysicalQuantity(
                    value=12.0, unit="nm", valid_range=(9.0, 15.0), uncertainty=0.2, source="Endura PVD Sputter System"
                ),
                "tin_cap_thickness": PhysicalQuantity(
                    value=20.0, unit="nm", valid_range=(15.0, 25.0), uncertainty=0.3, source="Endura PVD Sputter System"
                ),
                "first_rta_temp": PhysicalQuantity(
                    value=500.0, unit="degC", valid_range=(470.0, 530.0), uncertainty=1.0, source="Salicide 2-Step Kinetics"
                ),
                "second_rta_temp": PhysicalQuantity(
                    value=800.0, unit="degC", valid_range=(770.0, 830.0), uncertainty=1.0, source="Salicide Phase Transition"
                ),
            },
            metrology_checkpoints=["FOUR_POINT_PROBE_SHEET_R", "DEFECT_INSPECTION"],
            critical_specs={
                "salicide_sheet_resistance": CriticalSpec(
                    metric_name="salicide_sheet_resistance",
                    target=PhysicalQuantity(6.5, "ohm/sq", (4.0, 10.0), 0.2, "180nm CoSi2 Standard"),
                    lsl=PhysicalQuantity(5.0, "ohm/sq", (4.0, 10.0), 0.2, "Silicon Consumption Margin"),
                    usl=PhysicalQuantity(8.5, "ohm/sq", (4.0, 10.0), 0.2, "Contact Resistance Ceiling"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 190: Pre-Metal Dielectric (PMD) BPSG Deposition & CMP
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=190,
            step_id="STEP_190_PMD_DEPOSITION",
            name="Pre-Metal Dielectric (PMD) BPSG Deposition & CMP",
            category=ProcessStepCategory.CMP,
            equipment_type="CMP_POLISHER_200MM",
            recipe_name="RECIPE_PMD_PECVD_BPSG_CMP_800NM",
            estimated_duration_min=65.0,
            description="PECVD 800nm Borophosphosilicate Glass (BPSG) followed by planarizing oxide CMP to 600nm thickness.",
            parameters={
                "post_cmp_thickness": PhysicalQuantity(
                    value=600.0, unit="nm", valid_range=(520.0, 680.0), uncertainty=2.0, source="IL-Dielectric Rule"
                ),
            },
            metrology_checkpoints=["THICKNESS_ELLIPSOMETRY"],
        )
    )

    # -------------------------------------------------------------
    # Step 200: Contact Plug Etch (Mask 03: CT)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=200,
            step_id="STEP_200_CONTACT_ETCH",
            name="Contact Hole (CT) Lithography & High-Aspect RIE",
            category=ProcessStepCategory.ETCH,
            equipment_type="ICP_RIE_ETCHER",
            recipe_name="RECIPE_CONTACT_ETCH_HAR",
            estimated_duration_min=40.0,
            description="248nm DUV contact lithography and anisotropic C4F8/Ar/O2 etch stopping on CoSi2.",
            parameters={
                "contact_cd": PhysicalQuantity(
                    value=220.0, unit="nm", valid_range=(190.0, 250.0), uncertainty=1.0, source="180nm Contact Design Rule CT.W.1"
                ),
            },
            metrology_checkpoints=["CD_SEM_AFTER_ETCH", "DEFECT_INSPECTION"],
        )
    )

    # -------------------------------------------------------------
    # Step 210: Tungsten (W) Contact Plug Fill & CMP
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=210,
            step_id="STEP_210_W_PLUG_CMP",
            name="CVD Ti/TiN Liner, Tungsten (W) CVD Fill & W-CMP",
            category=ProcessStepCategory.CMP,
            equipment_type="CMP_POLISHER_200MM",
            recipe_name="RECIPE_W_CVD_CMP_PLUG",
            estimated_duration_min=75.0,
            description="PVD/CVD 10nm Ti + 15nm TiN adhesion liner; CVD WF6 tungsten reduction fill; tungsten CMP with colloidal silica.",
            parameters={
                "wf6_flow": PhysicalQuantity(
                    value=250.0, unit="sccm", valid_range=(150.0, 400.0), uncertainty=2.0, source="Novellus Concept One W-CVD"
                ),
            },
            metrology_checkpoints=["DEFECT_INSPECTION"],
        )
    )

    # -------------------------------------------------------------
    # Step 220: Metal 1 Deposition (PVD Al-0.5%Cu Stack)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=220,
            step_id="STEP_220_METAL1_PVD",
            name="Metal 1 Sputter Deposition (Ti/Al-Cu/TiN Stack)",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="SPUTTER_PVD_SYSTEM",
            recipe_name="RECIPE_PVD_M1_ALCU_STACK_500NM",
            estimated_duration_min=45.0,
            description="Cluster PVD: 30nm Ti underlayer, 450nm Al-0.5wt%Cu bulk conductor, 25nm TiN anti-reflective cap.",
            parameters={
                "m1_alcu_thickness": PhysicalQuantity(
                    value=450.0, unit="nm", valid_range=(400.0, 500.0), uncertainty=2.0, source="180nm Interconnect Spec M1"
                ),
                "tin_arc_thickness": PhysicalQuantity(
                    value=25.0, unit="nm", valid_range=(20.0, 30.0), uncertainty=0.5, source="Photolithography Anti-Reflective Cap"
                ),
            },
            metrology_checkpoints=["THICKNESS_ELLIPSOMETRY", "FOUR_POINT_PROBE_SHEET_R"],
            critical_specs={
                "m1_sheet_resistance": CriticalSpec(
                    metric_name="m1_sheet_resistance",
                    target=PhysicalQuantity(0.075, "ohm/sq", (0.060, 0.095), 0.002, "Al-Cu Resistivity ~3.2 uOhm-cm"),
                    lsl=PhysicalQuantity(0.065, "ohm/sq", (0.060, 0.095), 0.002, "Over-thickness Bridging Hazard"),
                    usl=PhysicalQuantity(0.088, "ohm/sq", (0.060, 0.095), 0.002, "RC Interconnect Delay"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 230: Metal 1 Lithography & Dry Etch (Mask 04: M1)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=230,
            step_id="STEP_230_METAL1_ETCH",
            name="Metal 1 Photolithography & Cl2/BCl3 Plasma Etch",
            category=ProcessStepCategory.ETCH,
            equipment_type="ICP_RIE_ETCHER",
            recipe_name="RECIPE_ALCU_ETCH_CL2_BCL3",
            estimated_duration_min=40.0,
            description="248nm KrF DUV patterning and anisotropic chlorine plasma etch followed by in-situ water rinse corrosion prevention.",
            parameters={
                "m1_minimum_width": PhysicalQuantity(
                    value=230.0, unit="nm", valid_range=(200.0, 260.0), uncertainty=1.0, source="180nm Design Rule M1.W.1"
                ),
                "cl2_flow": PhysicalQuantity(
                    value=100.0, unit="sccm", valid_range=(70.0, 150.0), uncertainty=1.0, source="Metal Etch Manual"
                ),
                "bcl3_flow": PhysicalQuantity(
                    value=80.0, unit="sccm", valid_range=(50.0, 120.0), uncertainty=1.0, source="Native Al2O3 Breaker"
                ),
            },
            metrology_checkpoints=["CD_SEM_AFTER_ETCH", "OVERLAY_METROLOGY"],
        )
    )

    # -------------------------------------------------------------
    # Step 240: Inter-Level Dielectric 1 (ILD-1) PECVD & CMP
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=240,
            step_id="STEP_240_ILD1_CMP",
            name="ILD-1 PECVD TEOS Deposition & Oxide CMP Planarization",
            category=ProcessStepCategory.CMP,
            equipment_type="CMP_POLISHER_200MM",
            recipe_name="RECIPE_ILD1_TEOS_CMP_800NM",
            estimated_duration_min=55.0,
            description="High-density PECVD tetraethylorthosilicate (TEOS) SiO2 dielectric followed by CMP planarization.",
            parameters={
                "post_cmp_ild_thickness": PhysicalQuantity(
                    value=700.0, unit="nm", valid_range=(620.0, 780.0), uncertainty=3.0, source="ILD1 Thickness Target"
                ),
            },
            metrology_checkpoints=["THICKNESS_ELLIPSOMETRY"],
        )
    )

    # -------------------------------------------------------------
    # Step 250: Via 1 Litho, Etch & W-Plug Fill (Mask 05: V1)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=250,
            step_id="STEP_250_VIA1_W_PLUG",
            name="Via 1 Litho, RIE Etch, Liner & Tungsten CMP",
            category=ProcessStepCategory.CMP,
            equipment_type="CMP_POLISHER_200MM",
            recipe_name="RECIPE_VIA1_HAR_ETCH_W_PLUG",
            estimated_duration_min=70.0,
            description="Via 1 patterning (260nm diameter), anisotropic oxide etch, Ti/TiN liner, W fill and W-CMP.",
            parameters={
                "via1_diameter": PhysicalQuantity(
                    value=260.0, unit="nm", valid_range=(230.0, 290.0), uncertainty=1.0, source="180nm Rule V1.W.1"
                ),
            },
            metrology_checkpoints=["CD_SEM_AFTER_ETCH"],
        )
    )

    # -------------------------------------------------------------
    # Step 260: Metal 2 Deposition, Litho & Etch (Mask 06: M2)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=260,
            step_id="STEP_260_METAL2_PATTERN",
            name="Metal 2 (M2) Sputter Stack, Litho & Cl2 Etch",
            category=ProcessStepCategory.ETCH,
            equipment_type="ICP_RIE_ETCHER",
            recipe_name="RECIPE_M2_ALCU_STACK_500NM",
            estimated_duration_min=60.0,
            description="500nm Ti/Al-Cu/TiN deposition, 248nm DUV patterning (minimum pitch 560nm), and anisotropic plasma etch.",
            parameters={
                "m2_pitch": PhysicalQuantity(
                    value=560.0, unit="nm", valid_range=(500.0, 620.0), uncertainty=2.0, source="180nm Rule M2.P.1"
                ),
            },
            metrology_checkpoints=["CD_SEM_AFTER_ETCH", "OVERLAY_METROLOGY"],
        )
    )

    # -------------------------------------------------------------
    # Step 270: Intermediate Interconnect (M3 / Via2 / M4 / Via3 / M5 / Via4)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=270,
            step_id="STEP_270_INTERMEDIATE_METALS",
            name="Intermediate Metal Levels (M3 through M5 & Vias)",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="SPUTTER_PVD_SYSTEM",
            recipe_name="RECIPE_M3_M4_M5_REPEATER_MODULE",
            estimated_duration_min=180.0,
            description="Sequential repetition of ILD deposition, CMP, Via etch, W-plug CMP, and Al-Cu patterning for Metal 3, 4, and 5.",
            parameters={
                "intermediate_metal_thickness": PhysicalQuantity(
                    value=500.0, unit="nm", valid_range=(450.0, 550.0), uncertainty=2.0, source="180nm Standard Semi-Global Metals"
                ),
            },
            metrology_checkpoints=["THICKNESS_ELLIPSOMETRY", "FOUR_POINT_PROBE_SHEET_R"],
        )
    )

    # -------------------------------------------------------------
    # Step 280: Metal 6 (Top Thick Metal Power/Ground Routing)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=280,
            step_id="STEP_280_TOP_METAL6",
            name="Metal 6 (Top Thick Metal) PVD, Litho & Etch",
            category=ProcessStepCategory.ETCH,
            equipment_type="ICP_RIE_ETCHER",
            recipe_name="RECIPE_M6_THICK_ALCU_1000NM",
            estimated_duration_min=65.0,
            description="1.0 um thick Al-Cu top routing metal for low-IR-drop power grid distribution and wire-bond pad underlayment.",
            parameters={
                "m6_thickness": PhysicalQuantity(
                    value=1000.0, unit="nm", valid_range=(900.0, 1100.0), uncertainty=5.0, source="180nm Power Distribution Spec"
                ),
            },
            metrology_checkpoints=["FOUR_POINT_PROBE_SHEET_R"],
            critical_specs={
                "m6_sheet_resistance": CriticalSpec(
                    metric_name="m6_sheet_resistance",
                    target=PhysicalQuantity(0.035, "ohm/sq", (0.025, 0.045), 0.001, "Top Thick Metal Spec"),
                    lsl=PhysicalQuantity(0.028, "ohm/sq", (0.025, 0.045), 0.001, "Over-thickness Aspect Limit"),
                    usl=PhysicalQuantity(0.042, "ohm/sq", (0.025, 0.045), 0.001, "IR Drop Spec Margin"),
                )
            },
        )
    )

    # -------------------------------------------------------------
    # Step 290: Passivation Dielectric Deposition
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=290,
            step_id="STEP_290_PASSIVATION_DEP",
            name="Final Passivation Dielectric Deposition (SiO2 + Si3N4)",
            category=ProcessStepCategory.THIN_FILM_DEPOSITION,
            equipment_type="PECVD_SYSTEM",
            recipe_name="RECIPE_PASSIVATION_OX_NITRIDE_DUAL",
            estimated_duration_min=50.0,
            description="Dual-layer moisture barrier: PECVD 500nm SiO2 followed by 800nm compressive Si3N4 capping layer.",
            parameters={
                "sio2_passivation_thickness": PhysicalQuantity(
                    value=500.0, unit="nm", valid_range=(450.0, 550.0), uncertainty=2.0, source="Passivation Spec"
                ),
                "sin_passivation_thickness": PhysicalQuantity(
                    value=800.0, unit="nm", valid_range=(720.0, 880.0), uncertainty=3.0, source="Hermetic Moisture Barrier Spec"
                ),
            },
            metrology_checkpoints=["THICKNESS_ELLIPSOMETRY"],
        )
    )

    # -------------------------------------------------------------
    # Step 300: Bond Pad Opening Etch (Mask 24: PAD)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=300,
            step_id="STEP_300_PAD_ETCH",
            name="Bond Pad Window Photolithography & Nitride/Oxide Etch",
            category=ProcessStepCategory.ETCH,
            equipment_type="ICP_RIE_ETCHER",
            recipe_name="RECIPE_BOND_PAD_OPEN_ETCH",
            estimated_duration_min=40.0,
            description="Thick resist lithography and selective dry etch opening bond pad windows down to top Metal 6 Al-Cu.",
            parameters={
                "pad_opening_width": PhysicalQuantity(
                    value=80.0, unit="um", valid_range=(60.0, 100.0), uncertainty=0.2, source="Wire Bond Pitch Standard"
                ),
            },
            metrology_checkpoints=["DEFECT_INSPECTION"],
        )
    )

    # -------------------------------------------------------------
    # Step 310: Forming Gas Alloy Anneal (FGA)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=310,
            step_id="STEP_310_ALLOY_ANNEAL",
            name="Forming Gas Contact Alloying Anneal (H2 / N2)",
            category=ProcessStepCategory.ANNEAL,
            equipment_type="HORIZONTAL_DIFFUSION_FURNACE",
            recipe_name="RECIPE_ALLOY_FGA_400C",
            estimated_duration_min=60.0,
            description="400 degC forming gas (10% H2 / 90% N2) anneal to passivate Si/SiO2 interface states and sinter contacts.",
            parameters={
                "anneal_temperature": PhysicalQuantity(
                    value=400.0, unit="degC", valid_range=(380.0, 420.0), uncertainty=0.5, source="Hydrogen Sintering Standard"
                ),
                "h2_flow_percent": PhysicalQuantity(
                    value=10.0, unit="%", valid_range=(8.0, 15.0), uncertainty=0.2, source="Non-Explosive Safety Limit"
                ),
                "soak_time": PhysicalQuantity(
                    value=30.0, unit="min", valid_range=(20.0, 45.0), uncertainty=0.2, source="Trap Annealing Kinetics"
                ),
            },
            metrology_checkpoints=[],
        )
    )

    # -------------------------------------------------------------
    # Step 320: Wafer Acceptance Testing (WAT) & Circuit Probing (CP)
    # -------------------------------------------------------------
    steps.append(
        ProcessStep(
            step_number=320,
            step_id="STEP_320_FINAL_WAT_CP",
            name="Parametric Wafer Acceptance Testing (WAT) & Electrical Sort",
            category=ProcessStepCategory.TEST,
            equipment_type="WAT_TESTER_AUTOMATED",
            recipe_name="RECIPE_WAT_PARAMETRIC_180NM",
            estimated_duration_min=90.0,
            description="Automated parametric testing of PCM test structures (Vth, Idsat, Ioff, contact chains, breakdown voltages, sheet rho).",
            parameters={
                "nmos_vth_target": PhysicalQuantity(
                    value=0.45, unit="count", valid_range=(0.35, 0.55), uncertainty=0.005, source="180nm Device Spec Vth (V)"
                ),
                "pmos_vth_target": PhysicalQuantity(
                    value=-0.45, unit="count", valid_range=(-0.55, -0.35), uncertainty=0.005, source="180nm Device Spec Vth (V)"
                ),
            },
            metrology_checkpoints=["DEFECT_INSPECTION"],
            critical_specs={
                "nmos_vth_spec": CriticalSpec(
                    metric_name="nmos_vth_spec",
                    target=PhysicalQuantity(0.45, "count", (0.35, 0.55), 0.005, "180nm Nominal Vt (V)"),
                    lsl=PhysicalQuantity(0.38, "count", (0.35, 0.55), 0.005, "Subthreshold Leakage Limit"),
                    usl=PhysicalQuantity(0.52, "count", (0.35, 0.55), 0.005, "Drive Current Limit"),
                    lcl=PhysicalQuantity(0.41, "count", (0.35, 0.55), 0.005, "SPC 3-Sigma Limit"),
                    ucl=PhysicalQuantity(0.49, "count", (0.35, 0.55), 0.005, "SPC 3-Sigma Limit"),
                )
            },
        )
    )

    return ProcessRoute(
        route_id="ROUTE_180NM_CMOS_BULK",
        name="180nm Generic CMOS Logic Reference Flow (200mm Wafer)",
        technology_node="180nm",
        wafer_diameter_mm=200.0,
        wafer_type="p-type Si (100), 200mm, 725±15 μm, 10-20 Ω·cm",
        steps=steps,
        description="Standard 180nm dual-well CMOS logic baseline featuring shallow trench isolation, 3.5nm gate oxide, CoSi2 salicide, and 6 levels of Al-Cu metallization.",
        mask_layers=24,
        metal_layers=6,
    )
