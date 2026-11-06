"""Plasma Etch System Human-Machine Interface (SEMI E95 Compliant).

Standards References:
  - SEMI E95: Specification for Human Interface for Semiconductor Manufacturing Equipment
  - SEMI E10: Standard for Definition and Measurement of Equipment Reliability,
              Availability, and Maintainability (RAM)
  - SEMI S2: Environmental, Health, and Safety Guideline for Semiconductor Manufacturing Equipment
  - SEMI E30: Generic Model for Communications and Control of Manufacturing Equipment (GEM)

This module provides the complete, interactive HMI console for an Inductively Coupled
Plasma (ICP) / Reactive Ion Etch (RIE) system. It features live multi-channel vacuum
gauging, MFC gas train readouts, dual-frequency RF generators with auto-match positions,
bipolar electrostatic chuck (ESC) backside helium cooling monitoring, real-time OES
endpoint detection trends, and authorization-guarded recipe and maintenance controls.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.simulation.core.units import (
    PhysicalQuantity,
    gas_flow,
    pressure,
    rf_power,
    temperature,
)
from src.simulation.equipment.base_equipment import (
    AlarmSeverity,
    BaseEquipment,
    ChamberState,
    GEMProcessingState,
)
from src.visualization.hmi.base_hmi import (
    AlarmList,
    AuthorizationLevel,
    ButtonControl,
    GaugeDisplay,
    HMIEvent,
    HMIEventType,
    HMIPanel,
    IndicatorState,
    NavigationTab,
    NumericDisplay,
    RecipeSelector,
    StatusIndicator,
    TrendChart,
    WaferMap,
    WidgetPosition,
    WidgetSize,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Etch Hardware Domain Enums
# =============================================================================

class ChamberCondition(str, Enum):
    """Etch process chamber physical state."""
    STANDBY = "STANDBY"
    VACUUM = "VACUUM"
    PROCESS = "PROCESS"
    VENT = "VENT"
    CLEAN = "CLEAN"


class ValveStatus(str, Enum):
    """Gas and vacuum pneumatic isolation valve states."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    THROTTLED = "THROTTLED"


# =============================================================================
# Etch HMI Panel Implementation
# =============================================================================

class EtchHMI(HMIPanel):
    """High-Fidelity Human-Machine Interface for Plasma Etch System."""

    def __init__(
        self,
        panel_id: str = "HMI_ICP_ETCH_01",
        equipment_reference: Optional[BaseEquipment] = None,
        initial_user_auth: AuthorizationLevel = AuthorizationLevel.OPERATOR,
        user_id: str = "ETCH_TECH_01",
    ) -> None:
        """Initialize Etch HMI panel and build all SEMI E95 screen widgets."""
        super().__init__(
            panel_id=panel_id,
            equipment_reference=equipment_reference,
            initial_tab=NavigationTab.MAIN,
            current_user_auth=initial_user_auth,
            user_id=user_id,
        )

        # Domain hardware telemetry state
        self.chamber_condition = ChamberCondition.STANDBY
        self.roughing_pump_on = True
        self.turbo_pump_rpm = 45000.0  # Nominally 45,000 RPM at full speed
        self.turbo_pump_ready = True
        self.foreline_pressure_mtorr = 25.0
        self.chamber_pressure_mtorr = 10.0
        self.throttle_valve_pos_pct = 42.5

        # Gas delivery (MFC channels: gas name -> {setpoint, actual, valve, unit})
        self.gas_channels: Dict[str, Dict[str, Any]] = {
            "Cl2": {"setpoint": 50.0, "actual": 49.8, "valve": ValveStatus.OPEN, "unit": "sccm"},
            "BCl3": {"setpoint": 20.0, "actual": 20.1, "valve": ValveStatus.OPEN, "unit": "sccm"},
            "CF4": {"setpoint": 0.0, "actual": 0.0, "valve": ValveStatus.CLOSED, "unit": "sccm"},
            "SF6": {"setpoint": 0.0, "actual": 0.0, "valve": ValveStatus.CLOSED, "unit": "sccm"},
            "Ar": {"setpoint": 100.0, "actual": 100.2, "valve": ValveStatus.OPEN, "unit": "sccm"},
            "O2": {"setpoint": 5.0, "actual": 4.9, "valve": ValveStatus.OPEN, "unit": "sccm"},
            "N2": {"setpoint": 0.0, "actual": 0.0, "valve": ValveStatus.CLOSED, "unit": "sccm"},
        }

        # RF Plasma Generation
        self.source_rf_freq_mhz = 13.56
        self.source_rf_fwd_w = 800.0
        self.source_rf_ref_w = 8.0
        self.source_match_tune_pct = 54.2
        self.source_match_load_pct = 48.7

        self.bias_rf_freq_khz = 400.0
        self.bias_rf_fwd_w = 150.0
        self.bias_rf_ref_w = 3.0
        self.bias_match_tune_pct = 61.0
        self.bias_match_load_pct = 52.3

        # Electrostatic Chuck (ESC)
        self.esc_clamped = True
        self.esc_voltage_v = 1200.0  # Bipolar +/- 1200 V
        self.esc_he_pressure_torr = 10.0  # Backside He pressure (5 - 15 Torr)
        self.esc_he_leak_sccm = 0.45  # Backside He flow (< 1.5 sccm spec)
        self.chuck_temperature_c = 45.0  # Target chiller temp
        self.chamber_wall_temp_c = 65.0  # Heated liner temp to prevent polymer deposition

        # Optical Emission Spectroscopy (OES) Endpoint Signal
        self.endpoint_signal_au = 1240.0  # Intensity arbitrary units
        self.endpoint_detected = False

        # Build UI widget hierarchy
        self._build_widgets()

    # -------------------------------------------------------------------------
    # Widget Layout Construction
    # -------------------------------------------------------------------------

    def _build_widgets(self) -> None:
        """Construct standard SEMI E95 screen widgets across all tabs."""

        # =====================================================================
        # 1. MAIN TAB: Primary Process Overview & Rapid Telemetry
        # =====================================================================
        self.add_widget(
            StatusIndicator(
                widget_id="main_process_state",
                label="Process Module Status",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(0, 0),
                size=WidgetSize(3, 1),
                initial_state=IndicatorState.READY,
                status_text="Idle / Ready",
                tooltip="Module SEMI E10 state indicator",
            )
        )
        self.add_widget(
            StatusIndicator(
                widget_id="main_chamber_cond",
                label="Chamber Condition",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(3, 0),
                size=WidgetSize(3, 1),
                initial_state=IndicatorState.READY,
                status_text=f"Chamber: {self.chamber_condition.value}",
                tooltip="Current vacuum and process mode",
            )
        )
        self.add_widget(
            StatusIndicator(
                widget_id="main_interlock_summary",
                label="Safety Interlocks",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(6, 0),
                size=WidgetSize(3, 1),
                initial_state=IndicatorState.READY,
                status_text="All Interlocks Satisfied",
                tooltip="SEMI S2 hardware interlock loop status",
            )
        )
        self.add_widget(
            StatusIndicator(
                widget_id="main_wafer_status",
                label="Wafer In Chamber",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(9, 0),
                size=WidgetSize(3, 1),
                initial_state=IndicatorState.READY,
                status_text="Wafer: Loaded (Slot 01)",
                tooltip="Substrate presence on electrostatic chuck",
            )
        )

        # Main Screen Gauges
        self.add_widget(
            GaugeDisplay(
                widget_id="main_chamber_pressure_gauge",
                label="Chamber Vacuum (mTorr)",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(0, 1),
                unit="mTorr",
                min_value=0.1,
                max_value=100.0,
                initial_value=self.chamber_pressure_mtorr,
                setpoint=10.0,
                green_zone=(5.0, 15.0),
                yellow_zone=(15.0, 30.0),
                red_zone=(30.0, 100.0),
                tooltip="Process manometer vacuum level",
            )
        )
        self.add_widget(
            NumericDisplay(
                widget_id="main_rf_source_power",
                label="Source RF Power",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(3, 1),
                unit="W",
                format_spec="{:.1f}",
                initial_value=self.source_rf_fwd_w,
                warning_low=750.0,
                warning_high=850.0,
                fault_low=700.0,
                fault_high=900.0,
                tooltip="13.56 MHz ICP Source Forward Power",
            )
        )
        self.add_widget(
            NumericDisplay(
                widget_id="main_rf_bias_power",
                label="Bias RF Power",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(3, 2),
                unit="W",
                format_spec="{:.1f}",
                initial_value=self.bias_rf_fwd_w,
                warning_low=140.0,
                warning_high=160.0,
                fault_low=120.0,
                fault_high=180.0,
                tooltip="Bias generator power (wafer ion bombardment energy)",
            )
        )
        self.add_widget(
            NumericDisplay(
                widget_id="main_chuck_temp",
                label="ESC Chuck Temperature",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(5, 1),
                unit="degC",
                format_spec="{:.1f}",
                initial_value=self.chuck_temperature_c,
                warning_low=40.0,
                warning_high=50.0,
                fault_low=35.0,
                fault_high=55.0,
                tooltip="Electrostatic chuck pedestal temperature",
            )
        )
        self.add_widget(
            NumericDisplay(
                widget_id="main_he_backside_press",
                label="He Backside Pressure",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(5, 2),
                unit="Torr",
                format_spec="{:.2f}",
                initial_value=self.esc_he_pressure_torr,
                warning_low=8.0,
                warning_high=12.0,
                fault_low=6.0,
                fault_high=14.0,
                tooltip="Backside helium thermal heat transfer pressure",
            )
        )

        # Quick Control Buttons on Main Screen
        self.add_widget(
            ButtonControl(
                widget_id="btn_main_start_run",
                label="START RUN",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(8, 1),
                action_name="START_RUN",
                required_auth=AuthorizationLevel.OPERATOR,
                button_style="success",
                tooltip="Initiate automated wafer etch process run",
            )
        )
        self.add_widget(
            ButtonControl(
                widget_id="btn_main_pause_run",
                label="PAUSE",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(8, 2),
                action_name="PAUSE_RUN",
                required_auth=AuthorizationLevel.OPERATOR,
                button_style="warning",
                tooltip="Safely pause active etch recipe step",
            )
        )
        self.add_widget(
            ButtonControl(
                widget_id="btn_main_abort_run",
                label="ABORT RUN",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(10, 1),
                action_name="ABORT_RUN",
                required_auth=AuthorizationLevel.OPERATOR,
                requires_confirmation=True,
                button_style="danger",
                tooltip="Immediately terminate recipe and purge chamber",
            )
        )
        self.add_widget(
            ButtonControl(
                widget_id="btn_main_emo",
                label="EMERGENCY OFF (EMO)",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(10, 2),
                action_name="EMERGENCY_STOP",
                required_auth=AuthorizationLevel.OPERATOR,
                requires_confirmation=True,
                button_style="danger",
                tooltip="SEMI S2 Emergency Off - Cuts all RF and toxic gas valves",
            )
        )

        # Main Screen Live Trend Display: Chamber Pressure & RF Power
        self.add_widget(
            TrendChart(
                widget_id="trend_main_pressure",
                label="Chamber Pressure Trend (mTorr)",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(0, 4),
                parameter_name="Chamber Vacuum",
                unit="mTorr",
                size=WidgetSize(6, 3),
                setpoint=10.0,
                upper_limit=15.0,
                lower_limit=5.0,
                tooltip="Live 5-minute chamber pressure trace",
            )
        )
        self.add_widget(
            TrendChart(
                widget_id="trend_main_rf_power",
                label="RF Source & Bias Power Trend (W)",
                tab=NavigationTab.MAIN,
                position=WidgetPosition(6, 4),
                parameter_name="RF Power",
                unit="W",
                size=WidgetSize(6, 3),
                setpoint=800.0,
                upper_limit=850.0,
                lower_limit=750.0,
                tooltip="Source RF forward output trace",
            )
        )

        # =====================================================================
        # 2. RECIPE TAB: Multi-Step Recipe Management & Step Parameters
        # =====================================================================
        sample_recipes = [
            {
                "recipe_id": "RCP_POLY_GATE_ETCH_V2",
                "name": "Poly-Si Gate Main Etch (180nm)",
                "process_type": "DRY_ETCH",
                "total_duration_sec": 75.0,
                "last_modified": "2026-03-15",
                "steps": [
                    {
                        "step_num": 1,
                        "name": "Breakthrough / Native Oxide Strip",
                        "duration_s": 8.0,
                        "pressure_mtorr": 5.0,
                        "rf_source_w": 600.0,
                        "rf_bias_w": 120.0,
                        "gases": {"CF4": 60.0, "Ar": 50.0},
                    },
                    {
                        "step_num": 2,
                        "name": "Main Etch (Anisotropic Cl2/HBr)",
                        "duration_s": 45.0,
                        "pressure_mtorr": 12.0,
                        "rf_source_w": 850.0,
                        "rf_bias_w": 160.0,
                        "gases": {"Cl2": 70.0, "BCl3": 15.0, "O2": 4.0},
                    },
                    {
                        "step_num": 3,
                        "name": "Over-Etch / Soft Landing",
                        "duration_s": 22.0,
                        "pressure_mtorr": 25.0,
                        "rf_source_w": 400.0,
                        "rf_bias_w": 40.0,
                        "gases": {"Cl2": 30.0, "O2": 8.0, "He": 80.0},
                    },
                ],
            },
            {
                "recipe_id": "RCP_OXIDE_VIA_RIE",
                "name": "SiO2 Contact Via Etch (C4F8/Ar)",
                "process_type": "DRY_ETCH",
                "total_duration_sec": 90.0,
                "last_modified": "2026-04-02",
                "steps": [
                    {
                        "step_num": 1,
                        "name": "Via High-Aspect Ratio Etch",
                        "duration_s": 90.0,
                        "pressure_mtorr": 15.0,
                        "rf_source_w": 1200.0,
                        "rf_bias_w": 350.0,
                        "gases": {"CF4": 40.0, "Ar": 120.0, "O2": 6.0},
                    }
                ],
            },
            {
                "recipe_id": "RCP_CHAMBER_DRY_CLEAN",
                "name": "In-Situ O2/SF6 Chamber Dry Clean",
                "process_type": "DRY_CLEAN",
                "total_duration_sec": 180.0,
                "last_modified": "2026-05-10",
                "steps": [
                    {
                        "step_num": 1,
                        "name": "O2/SF6 Fluorine Ash Clean",
                        "duration_s": 180.0,
                        "pressure_mtorr": 30.0,
                        "rf_source_w": 1500.0,
                        "rf_bias_w": 0.0,
                        "gases": {"SF6": 50.0, "O2": 200.0},
                    }
                ],
            },
        ]

        self.add_widget(
            RecipeSelector(
                widget_id="recipe_selector",
                label="Process Recipe Catalog",
                tab=NavigationTab.RECIPE,
                position=WidgetPosition(0, 0),
                size=WidgetSize(4, 5),
                recipes=sample_recipes,
                selected_recipe_id="RCP_POLY_GATE_ETCH_V2",
            )
        )
        self.add_widget(
            TrendChart(
                widget_id="trend_recipe_endpoint",
                label="Optical Emission Spectroscopy (OES) Endpoint Signal",
                tab=NavigationTab.RECIPE,
                position=WidgetPosition(4, 0),
                parameter_name="OES 703nm (Fluorine) Intensity",
                unit="count",
                size=WidgetSize(8, 4),
                setpoint=1200.0,
                tooltip="In-situ optical emission endpoint transition detector",
            )
        )
        self.add_widget(
            ButtonControl(
                widget_id="btn_recipe_load",
                label="Load Selected Recipe",
                tab=NavigationTab.RECIPE,
                position=WidgetPosition(4, 4),
                action_name="LOAD_RECIPE",
                required_auth=AuthorizationLevel.OPERATOR,
                button_style="default",
            )
        )
        self.add_widget(
            ButtonControl(
                widget_id="btn_recipe_verify",
                label="Validate Parameter Envelope",
                tab=NavigationTab.RECIPE,
                position=WidgetPosition(6, 4),
                action_name="VALIDATE_RECIPE",
                required_auth=AuthorizationLevel.ENGINEER,
                button_style="default",
            )
        )
        self.add_widget(
            ButtonControl(
                widget_id="btn_recipe_start",
                label="Execute Recipe",
                tab=NavigationTab.RECIPE,
                position=WidgetPosition(8, 4),
                action_name="START_RUN",
                required_auth=AuthorizationLevel.OPERATOR,
                button_style="success",
            )
        )
        self.add_widget(
            ButtonControl(
                widget_id="btn_recipe_abort",
                label="Abort Process",
                tab=NavigationTab.RECIPE,
                position=WidgetPosition(10, 4),
                action_name="ABORT_RUN",
                required_auth=AuthorizationLevel.OPERATOR,
                button_style="danger",
            )
        )

        # =====================================================================
        # 3. CHAMBER TAB: Detailed Subsystem Diagnostic Architecture
        # =====================================================================
        # Vacuum Pumps & Foreline
        self.add_widget(
            NumericDisplay(
                widget_id="chamber_turbo_rpm",
                label="Turbomolecular Pump Speed",
                tab=NavigationTab.CHAMBER,
                position=WidgetPosition(0, 0),
                unit="rpm",
                format_spec="{:.0f}",
                initial_value=self.turbo_pump_rpm,
                warning_low=43000.0,
                warning_high=47000.0,
                fault_low=40000.0,
                fault_high=48000.0,
                tooltip="Magnetic levitation turbomolecular high-vacuum pump",
            )
        )
        self.add_widget(
            NumericDisplay(
                widget_id="chamber_foreline_press",
                label="Foreline Vacuum Pressure",
                tab=NavigationTab.CHAMBER,
                position=WidgetPosition(2, 0),
                unit="mTorr",
                format_spec="{:.1f}",
                initial_value=self.foreline_pressure_mtorr,
                warning_low=10.0,
                warning_high=60.0,
                fault_low=5.0,
                fault_high=100.0,
                tooltip="Pirani gauge on dry backing pump foreline",
            )
        )
        self.add_widget(
            NumericDisplay(
                widget_id="chamber_throttle_pos",
                label="VAT Throttle Valve Opening",
                tab=NavigationTab.CHAMBER,
                position=WidgetPosition(4, 0),
                unit="%",
                format_spec="{:.1f}",
                initial_value=self.throttle_valve_pos_pct,
                warning_low=10.0,
                warning_high=90.0,
                tooltip="Pendulum throttle valve closed-loop position",
            )
        )

        # RF Generator Details & Match Network
        self.add_widget(
            NumericDisplay(
                widget_id="chamber_rf_src_ref",
                label="Source Reflected Power",
                tab=NavigationTab.CHAMBER,
                position=WidgetPosition(0, 1),
                unit="W",
                format_spec="{:.1f}",
                initial_value=self.source_rf_ref_w,
                warning_high=25.0,
                fault_high=50.0,
                tooltip="ICP coil reflected power (match quality)",
            )
        )
        self.add_widget(
            NumericDisplay(
                widget_id="chamber_src_tune_pos",
                label="Source Match Tune Pos",
                tab=NavigationTab.CHAMBER,
                position=WidgetPosition(2, 1),
                unit="%",
                format_spec="{:.1f}",
                initial_value=self.source_match_tune_pct,
                tooltip="Motorized match network tune capacitor position",
            )
        )
        self.add_widget(
            NumericDisplay(
                widget_id="chamber_src_load_pos",
                label="Source Match Load Pos",
                tab=NavigationTab.CHAMBER,
                position=WidgetPosition(4, 1),
                unit="%",
                format_spec="{:.1f}",
                initial_value=self.source_match_load_pct,
                tooltip="Motorized match network load capacitor position",
            )
        )

        # Electrostatic Chuck Subsystem
        self.add_widget(
            NumericDisplay(
                widget_id="chamber_esc_voltage",
                label="ESC Clamp Voltage",
                tab=NavigationTab.CHAMBER,
                position=WidgetPosition(0, 2),
                unit="count",  # V DC represented as numeric magnitude
                format_spec="{:.0f} V",
                initial_value=self.esc_voltage_v,
                warning_low=1000.0,
                warning_high=1400.0,
                tooltip="Coulombic / Johnsen-Rahbek electrostatic chuck clamping potential",
            )
        )
        self.add_widget(
            NumericDisplay(
                widget_id="chamber_he_leak",
                label="He Backside Leak Rate",
                tab=NavigationTab.CHAMBER,
                position=WidgetPosition(2, 2),
                unit="sccm",
                format_spec="{:.2f}",
                initial_value=self.esc_he_leak_sccm,
                warning_high=1.0,
                fault_high=2.0,
                tooltip="Helium seal integrity around wafer perimeter",
            )
        )
        self.add_widget(
            NumericDisplay(
                widget_id="chamber_wall_temp",
                label="Chamber Wall Heater",
                tab=NavigationTab.CHAMBER,
                position=WidgetPosition(4, 2),
                unit="degC",
                format_spec="{:.1f}",
                initial_value=self.chamber_wall_temp_c,
                warning_low=55.0,
                warning_high=75.0,
                tooltip="Heated chamber liner preventing etch byproduct condensation",
            )
        )

        # Gas Line MFC Displays
        col = 0
        for gas_name, g_info in list(self.gas_channels.items())[:6]:
            self.add_widget(
                NumericDisplay(
                    widget_id=f"mfc_{gas_name.lower()}",
                    label=f"MFC: {gas_name} Flow",
                    tab=NavigationTab.CHAMBER,
                    position=WidgetPosition(col * 2, 3),
                    unit="sccm",
                    format_spec="{:.1f}",
                    initial_value=g_info["actual"],
                    tooltip=f"Mass flow controller channel for {gas_name}",
                )
            )
            col += 1

        # =====================================================================
        # 4. ALARMS TAB: Active Annunciator & Historical Log
        # =====================================================================
        self.add_widget(
            AlarmList(
                widget_id="etch_alarm_list",
                label="SEMI E95 Etch Alarm Manager",
                tab=NavigationTab.ALARMS,
                position=WidgetPosition(0, 0),
                size=WidgetSize(12, 4),
            )
        )
        self.add_widget(
            ButtonControl(
                widget_id="btn_alarm_ack_all",
                label="Acknowledge All Alarms",
                tab=NavigationTab.ALARMS,
                position=WidgetPosition(0, 4),
                action_name="ACK_ALL_ALARMS",
                required_auth=AuthorizationLevel.OPERATOR,
                button_style="warning",
            )
        )
        self.add_widget(
            ButtonControl(
                widget_id="btn_alarm_clear_all",
                label="Clear Acknowledged Alarms",
                tab=NavigationTab.ALARMS,
                position=WidgetPosition(3, 4),
                action_name="CLEAR_ALL_ALARMS",
                required_auth=AuthorizationLevel.ENGINEER,
                button_style="danger",
            )
        )

        # =====================================================================
        # 5. HISTORY TAB: Post-Process Run Log & Wafer Map
        # =====================================================================
        sample_sites = [
            {"site_id": "SITE_CENTER", "x_mm": 0.0, "y_mm": 0.0, "value": 78.5, "unit": "nm", "pass": True},
            {"site_id": "SITE_TOP", "x_mm": 0.0, "y_mm": 120.0, "value": 77.9, "unit": "nm", "pass": True},
            {"site_id": "SITE_BOTTOM", "x_mm": 0.0, "y_mm": -120.0, "value": 78.2, "unit": "nm", "pass": True},
            {"site_id": "SITE_LEFT", "x_mm": -120.0, "y_mm": 0.0, "value": 79.1, "unit": "nm", "pass": True},
            {"site_id": "SITE_RIGHT", "x_mm": 120.0, "y_mm": 0.0, "value": 78.8, "unit": "nm", "pass": True},
        ]
        sample_defects = [
            {"defect_id": 1, "x_mm": 45.2, "y_mm": 88.1, "size_um": 0.22, "type": "Micro-masking particle"},
            {"defect_id": 2, "x_mm": -62.4, "y_mm": -34.7, "size_um": 0.18, "type": "Polymer flake"},
        ]
        wafer_map = WaferMap(
            widget_id="history_wafer_map",
            label="Post-Etch Critical Dimension (CD) & Defect Map",
            tab=NavigationTab.HISTORY,
            position=WidgetPosition(0, 0),
            size=WidgetSize(6, 5),
            diameter_mm=300.0,
        )
        wafer_map.set_sites(sample_sites)
        wafer_map.set_defects(sample_defects)
        self.add_widget(wafer_map)

        self.add_widget(
            TrendChart(
                widget_id="history_etch_rate_trend",
                label="Historical 25-Wafer Poly Etch Rate (nm/min)",
                tab=NavigationTab.HISTORY,
                position=WidgetPosition(6, 0),
                parameter_name="Etch Rate",
                unit="nm",
                size=WidgetSize(6, 4),
                setpoint=180.0,
                upper_limit=190.0,
                lower_limit=170.0,
            )
        )

        # =====================================================================
        # 6. MAINTENANCE TAB: Preventive Wear Counters & Calibrations
        # =====================================================================
        self.add_widget(
            NumericDisplay(
                widget_id="maint_wafer_counter",
                label="Chamber Wafer Counter",
                tab=NavigationTab.MAINTENANCE,
                position=WidgetPosition(0, 0),
                unit="count",
                format_spec="{:.0f}",
                initial_value=1240.0,
                warning_high=4500.0,
                fault_high=5000.0,
                tooltip="Wafers processed since last chamber wet clean",
            )
        )
        self.add_widget(
            NumericDisplay(
                widget_id="maint_rf_hours",
                label="RF Plasma On Hours",
                tab=NavigationTab.MAINTENANCE,
                position=WidgetPosition(2, 0),
                unit="hr",
                format_spec="{:.1f}",
                initial_value=72.4,
                warning_high=180.0,
                fault_high=200.0,
                tooltip="Accumulated RF source plasma burning time",
            )
        )
        self.add_widget(
            NumericDisplay(
                widget_id="maint_clean_cycles",
                label="Dry Clean Cycles Executed",
                tab=NavigationTab.MAINTENANCE,
                position=WidgetPosition(4, 0),
                unit="count",
                format_spec="{:.0f}",
                initial_value=48.0,
                tooltip="In-situ plasma dry clean recipes run",
            )
        )

        # Maintenance Action Buttons
        self.add_widget(
            ButtonControl(
                widget_id="btn_maint_trigger_clean",
                label="Trigger Chamber Dry Clean",
                tab=NavigationTab.MAINTENANCE,
                position=WidgetPosition(0, 1),
                action_name="START_CLEAN",
                required_auth=AuthorizationLevel.MAINTENANCE,
                button_style="warning",
                tooltip="Execute SF6/O2 chamber ash and wall cleaning cycle",
            )
        )
        self.add_widget(
            ButtonControl(
                widget_id="btn_maint_leak_check",
                label="Run Vacuum Leak-Up Rate Test",
                tab=NavigationTab.MAINTENANCE,
                position=WidgetPosition(2, 1),
                action_name="DIAG_LEAK_CHECK",
                required_auth=AuthorizationLevel.MAINTENANCE,
                button_style="default",
                tooltip="Isolate chamber from pumps and record rate of pressure rise (mTorr/min)",
            )
        )
        self.add_widget(
            ButtonControl(
                widget_id="btn_maint_rf_cal",
                label="RF Match Tuning Auto-Sweep",
                tab=NavigationTab.MAINTENANCE,
                position=WidgetPosition(4, 1),
                action_name="DIAG_RF_CAL",
                required_auth=AuthorizationLevel.MAINTENANCE,
                button_style="default",
                tooltip="Calibrate source and bias match network step motors",
            )
        )
        self.add_widget(
            ButtonControl(
                widget_id="btn_maint_reset_counter",
                label="Reset PM Wafer Counter",
                tab=NavigationTab.MAINTENANCE,
                position=WidgetPosition(0, 2),
                action_name="RESET_PM_COUNTER",
                required_auth=AuthorizationLevel.MAINTENANCE,
                requires_confirmation=True,
                button_style="danger",
                tooltip="Reset wafer counter following scheduled physical wet PM",
            )
        )

    # -------------------------------------------------------------------------
    # Custom Event Handling
    # -------------------------------------------------------------------------

    def _handle_custom_event(self, event: HMIEvent) -> Dict[str, Any]:
        """Execute etch-specific state-machine mediated hardware operations."""
        action = event.payload.get("action", event.widget_id)

        if action == "START_RUN" or event.widget_id in ("btn_main_start_run", "btn_recipe_start"):
            if self.equipment is not None:
                # Interlock verification
                healthy, tripped = self.equipment.check_interlocks()
                if not healthy:
                    return {
                        "success": False,
                        "error": f"Cannot start run: Safety interlock tripped: {'; '.join(tripped)}",
                    }
                # State transition via SEMI E10 state machine
                try:
                    self.equipment.state_machine.trigger(
                        event="START_RUN",
                        timestamp=event.timestamp,
                        payload={"recipe": "SELECTED_RECIPE", "user": event.user_id},
                    )
                    self.chamber_condition = ChamberCondition.PROCESS
                    return {"success": True, "action": "START_RUN", "state": self.equipment.state_machine.current_state.value}
                except Exception as exc:
                    return {"success": False, "error": f"State machine transition rejected: {exc}"}
            self.chamber_condition = ChamberCondition.PROCESS
            return {"success": True, "action": "START_RUN", "note": "Simulation mode"}

        if action == "ABORT_RUN" or event.widget_id in ("btn_main_abort_run", "btn_recipe_abort"):
            if self.equipment is not None:
                self.equipment.abort(reason=f"HMI Abort Button pressed by {event.user_id}")
                self.chamber_condition = ChamberCondition.STANDBY
                return {"success": True, "action": "ABORT_RUN"}
            self.chamber_condition = ChamberCondition.STANDBY
            return {"success": True, "action": "ABORT_RUN", "note": "Simulation mode"}

        if action == "START_CLEAN" or event.widget_id == "btn_maint_trigger_clean":
            if not event.authorization_level.has_permission(AuthorizationLevel.MAINTENANCE):
                return {"success": False, "error": "Starting clean requires MAINTENANCE authorization"}
            if self.equipment is not None:
                try:
                    self.equipment.state_machine.trigger(
                        event="START_CLEAN",
                        timestamp=event.timestamp,
                        payload={"reason": "Routine chamber dry clean"},
                    )
                    self.chamber_condition = ChamberCondition.CLEAN
                    return {"success": True, "action": "START_CLEAN"}
                except Exception as exc:
                    return {"success": False, "error": str(exc)}
            self.chamber_condition = ChamberCondition.CLEAN
            return {"success": True, "action": "START_CLEAN", "note": "Clean cycle engaged"}

        if action == "DIAG_LEAK_CHECK" or event.widget_id == "btn_maint_leak_check":
            if not event.authorization_level.has_permission(AuthorizationLevel.MAINTENANCE):
                return {"success": False, "error": "Leak check requires MAINTENANCE authorization"}
            # Simulated leak up rate: 0.45 mTorr/min (spec < 1.0 mTorr/min)
            leak_rate = 0.45
            return {
                "success": True,
                "action": "DIAG_LEAK_CHECK",
                "leak_rate_mtorr_per_min": leak_rate,
                "spec_limit_mtorr_per_min": 1.0,
                "pass": True,
            }

        if action == "RESET_PM_COUNTER" or event.widget_id == "btn_maint_reset_counter":
            if not event.authorization_level.has_permission(AuthorizationLevel.MAINTENANCE):
                return {"success": False, "error": "Resetting PM counters requires MAINTENANCE authorization"}
            if self.equipment is not None:
                self.equipment.reset_maintenance_counter("total_wafers_processed")
            w = self.get_widget("maint_wafer_counter")
            if isinstance(w, NumericDisplay):
                w.update_value(0.0)
            return {"success": True, "action": "RESET_PM_COUNTER"}

        return {"success": True, "action": action, "detail": "Etch action processed"}

    # -------------------------------------------------------------------------
    # Live Telemetry Sync
    # -------------------------------------------------------------------------

    def update_telemetry(self) -> None:
        """Refresh live sensor readings into widgets."""
        super().update_telemetry()

        # Update trend charts with current readings
        now = time.time()
        p_chart = self.get_widget("trend_main_pressure")
        if isinstance(p_chart, TrendChart):
            p_chart.add_point(self.chamber_pressure_mtorr, now)

        rf_chart = self.get_widget("trend_main_rf_power")
        if isinstance(rf_chart, TrendChart):
            rf_chart.add_point(self.source_rf_fwd_w, now)

        oes_chart = self.get_widget("trend_recipe_endpoint")
        if isinstance(oes_chart, TrendChart):
            oes_chart.add_point(self.endpoint_signal_au, now)
