"""Unit Test Suite for Semiconductor Fab Digital Twin Core Modules.

Verifies:
  - units.py: PhysicalQuantity conversions, arithmetic, range checks, serialization.
  - state_machine.py: SEMI E10 states, event triggers, guards, RAM metrics, thread safety.
  - wafer.py: WaferID, WaferSubstrate (FD-SOI 22nm), LayerStack, Stoney bow, defect state.
  - recipe.py: RecipeParameter tolerances, RecipeStep branching, tool capability checks.
  - process_route.py: DAG validation, step dependencies, hold points, 22nm FEOL route.
"""

from __future__ import annotations

import math
import threading
import unittest
from typing import Set

from src.simulation.core import (
    BranchCondition,
    CriticalSpec,
    CrystalOrientation,
    EquipmentCapabilities,
    EquipmentEvent,
    EquipmentStateMachine,
    Layer,
    LayerStack,
    MetrologyRecord,
    MetrologyResults,
    MetrologyType,
    PhysicalQuantity,
    ProcessHistory,
    ProcessNode,
    ProcessRoute,
    ProcessStep,
    ProcessStepCategory,
    ProcessStepRecord,
    ProcessType,
    Recipe,
    RecipeLibrary,
    RecipeParameter,
    RecipeStep,
    RouteLibrary,
    SemiE10Metrics,
    SemiE10State,
    SemiE10Substate,
    SubstrateMaterial,
    TransitionRule,
    UnitDimension,
    Wafer,
    WaferID,
    WaferState,
    WaferSubstrate,
    convert_value,
    duration,
    film_thickness,
    gas_flow,
    ion_energy,
    length,
    litho_dose,
    pressure,
    rf_power,
    temperature,
    wafer_diameter,
    wafer_thickness,
)


class TestPhysicalUnits(unittest.TestCase):
    """Test suite for semiconductor physical units and PhysicalQuantity class."""

    def test_length_conversion(self) -> None:
        q_nm = length(22.0, "nm", (0.0, 100.0), 0.2, "ITRS 22nm Node")
        q_ang = q_nm.to_unit("angstrom")
        self.assertAlmostEqual(q_ang.value, 220.0, places=4)
        self.assertAlmostEqual(q_ang.uncertainty, 2.0, places=4)
        self.assertAlmostEqual(q_ang.valid_range[1], 1000.0, places=4)

        q_um = q_nm.to_unit("um")
        self.assertAlmostEqual(q_um.value, 0.022, places=6)

    def test_temperature_affine_conversion(self) -> None:
        t_c = temperature(25.0, "degC")
        t_k = t_c.to_unit("K")
        self.assertAlmostEqual(t_k.value, 298.15, places=4)

        t_rt = temperature(1050.0, "degC", valid_range=(900.0, 1200.0), source="RTA Spike")
        t_rt_k = t_rt.to_unit("K")
        self.assertAlmostEqual(t_rt_k.value, 1323.15, places=3)
        self.assertAlmostEqual(t_rt_k.valid_range[0], 1173.15, places=3)

    def test_pressure_vacuum_conversion(self) -> None:
        # 1 Torr = 133.322 Pa; 10 mTorr = 1.33322 Pa
        p_mtorr = pressure(10.0, "mTorr")
        p_pa = p_mtorr.to_unit("Pa")
        self.assertAlmostEqual(p_pa.value, 1.33322, places=3)

        p_torr = p_mtorr.to_unit("Torr")
        self.assertAlmostEqual(p_torr.value, 0.010, places=5)

    def test_gas_flow_conversion(self) -> None:
        flow_sccm = gas_flow(2500.0, "sccm")
        flow_slm = flow_sccm.to_unit("slm")
        self.assertAlmostEqual(flow_slm.value, 2.5, places=4)

    def test_range_validation(self) -> None:
        # Value within range succeeds
        q = PhysicalQuantity(10.0, "nm", (5.0, 15.0), 0.1)
        self.assertEqual(q.value, 10.0)

        # Value exceeding upper bound raises ValueError
        with self.assertRaises(ValueError):
            PhysicalQuantity(20.0, "nm", (5.0, 15.0), 0.1)

        # Value below lower bound raises ValueError
        with self.assertRaises(ValueError):
            PhysicalQuantity(2.0, "nm", (5.0, 15.0), 0.1)

        # Inverted range specification raises ValueError
        with self.assertRaises(ValueError):
            PhysicalQuantity(10.0, "nm", (20.0, 5.0), 0.1)

    def test_arithmetic_and_uncertainty(self) -> None:
        q1 = length(10.0, "nm", (0.0, 50.0), uncertainty=0.3)
        q2 = length(5.0, "nm", (0.0, 50.0), uncertainty=0.4)

        # Sum: 10 + 5 = 15; unc: sqrt(0.3^2 + 0.4^2) = 0.5
        q_sum = q1 + q2
        self.assertAlmostEqual(q_sum.value, 15.0, places=4)
        self.assertAlmostEqual(q_sum.uncertainty, 0.5, places=4)

        # Scalar multiplication
        q_scaled = q1 * 3.0
        self.assertAlmostEqual(q_scaled.value, 30.0, places=4)
        self.assertAlmostEqual(q_scaled.uncertainty, 0.9, places=4)

        # Ratio of same dimension yields float
        ratio = q1 / q2
        self.assertAlmostEqual(ratio, 2.0, places=4)

    def test_serialization(self) -> None:
        q = PhysicalQuantity(45.5, "mTorr", (0.1, 100.0), 0.5, "Capacitance Gauge")
        d = q.to_dict()
        q_rec = PhysicalQuantity.from_dict(d)
        self.assertEqual(q, q_rec)
        self.assertEqual(q.source, q_rec.source)


class TestEquipmentStateMachine(unittest.TestCase):
    """Test suite for SEMI E10 equipment state machine."""

    def test_initial_state_and_simple_transition(self) -> None:
        sm = EquipmentStateMachine("ETCH_ICP_01", initial_timestamp=1000.0)
        self.assertEqual(sm.current_state, SemiE10State.STANDBY)
        self.assertEqual(sm.current_substate, SemiE10Substate.NO_PRODUCT)

        # Transition: STANDBY -> PRODUCTIVE
        ok = sm.trigger(EquipmentEvent.START_RUN, reason="Lot 101 Dispatched", timestamp=1050.0)
        self.assertTrue(ok)
        self.assertEqual(sm.current_state, SemiE10State.PRODUCTIVE)
        self.assertEqual(sm.current_substate, SemiE10Substate.REGULAR_RUN)

        # Transition: PRODUCTIVE -> UNSCHEDULED_DOWN (Alarm Trip)
        ok = sm.trigger(EquipmentEvent.ALARM_TRIP, reason="He-Backside Coolant Leak", timestamp=1200.0)
        self.assertTrue(ok)
        self.assertEqual(sm.current_state, SemiE10State.UNSCHEDULED_DOWN)
        self.assertEqual(sm.current_substate, SemiE10Substate.EQUIPMENT_FAULT)

        # Clear Alarm -> STANDBY
        ok = sm.trigger(EquipmentEvent.CLEAR_ALARM, reason="O-ring seal replaced", timestamp=1500.0)
        self.assertTrue(ok)
        self.assertEqual(sm.current_state, SemiE10State.STANDBY)

    def test_guard_condition(self) -> None:
        sm = EquipmentStateMachine("CVD_01", initial_timestamp=0.0)

        # Add custom transition with a strict guard
        def chamber_clean_guard(ctx) -> bool:
            return ctx.payload.get("is_cleaned", False) is True

        sm.register_transition(TransitionRule(
            event="START_SUPER_RECIPE",
            source_state=SemiE10State.STANDBY,
            source_substate=None,
            target_state=SemiE10State.PRODUCTIVE,
            target_substate=SemiE10Substate.REGULAR_RUN,
            guard=chamber_clean_guard,
        ))

        # Attempt transition with guard failing (is_cleaned=False)
        ok = sm.trigger("START_SUPER_RECIPE", payload={"is_cleaned": False}, timestamp=10.0)
        self.assertFalse(ok)
        self.assertEqual(sm.current_state, SemiE10State.STANDBY)

        # Attempt transition with guard passing (is_cleaned=True)
        ok = sm.trigger("START_SUPER_RECIPE", payload={"is_cleaned": True}, timestamp=20.0)
        self.assertTrue(ok)
        self.assertEqual(sm.current_state, SemiE10State.PRODUCTIVE)

    def test_metrics_calculation(self) -> None:
        sm = EquipmentStateMachine("LITHO_01", initial_timestamp=0.0)
        # 0s to 1000s: STANDBY (1000s)
        # 1000s to 3000s: PRODUCTIVE (2000s)
        sm.trigger(EquipmentEvent.START_RUN, timestamp=1000.0)
        # 3000s to 3600s: UNSCHEDULED DOWN (600s)
        sm.trigger(EquipmentEvent.ALARM_TRIP, timestamp=3000.0)
        # 3600s to 4000s: STANDBY (400s)
        sm.trigger(EquipmentEvent.CLEAR_ALARM, timestamp=3600.0)

        metrics = sm.calculate_metrics(start_time=0.0, end_time=4000.0)
        self.assertAlmostEqual(metrics.total_time_hours, 4000.0 / 3600.0, places=3)
        self.assertAlmostEqual(metrics.productive_hours, 2000.0 / 3600.0, places=3)
        self.assertAlmostEqual(metrics.unscheduled_down_hours, 600.0 / 3600.0, places=3)
        self.assertEqual(metrics.failure_count, 1)
        self.assertEqual(metrics.repair_count, 1)

        # Availability: (4000 - 600) / 4000 = 3400 / 4000 = 0.85
        self.assertAlmostEqual(metrics.availability, 0.85, places=3)

    def test_thread_safety(self) -> None:
        sm = EquipmentStateMachine("THREAD_TEST_TOOL", initial_timestamp=0.0)
        errors = []

        def worker(w_id: int) -> None:
            try:
                for i in range(50):
                    sm.can_trigger(EquipmentEvent.START_RUN)
                    sm.get_time_in_current_state()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)


class TestWaferDigitalTwin(unittest.TestCase):
    """Test suite for Wafer substrate, LayerStack, and Stoney equation."""

    def test_22nm_fdsoi_wafer_initialization(self) -> None:
        w = Wafer.create_22nm_fdsoi_wafer("LOT-22FD-001", wafer_number=3)
        self.assertEqual(w.wafer_id.lot_id, "LOT-22FD-001")
        self.assertEqual(w.wafer_id.wafer_number, 3)
        self.assertTrue(w.substrate.is_soi)
        self.assertEqual(w.substrate.material, SubstrateMaterial.SOI_FDSOI)

        # Verify Buried Oxide (20nm) and Ultra-Thin Body (6nm)
        self.assertIsNotNone(w.substrate.box_thickness)
        self.assertAlmostEqual(w.substrate.box_thickness.value, 20.0, places=2)
        self.assertIsNotNone(w.substrate.device_layer_thickness)
        self.assertAlmostEqual(w.substrate.device_layer_thickness.value, 6.0, places=2)

    def test_layer_stack_and_stoney_bow(self) -> None:
        w = Wafer.create_22nm_fdsoi_wafer("LOT-EXP-01", wafer_number=1)
        initial_bow = w.state.bow.value

        # Deposit 100nm of high-stress tensile Si3N4 (1000 MPa)
        sin_layer = Layer(
            layer_id="L_SIN_01",
            name="STI SiN Hardmask",
            material="Si3N4",
            thickness=film_thickness(100.0, "nm"),
            stress_mpa=PhysicalQuantity(1000.0, "MPa", (-3000.0, 3000.0), 20.0, "Film Stress"),
        )
        w.layer_stack.add_layer(sin_layer)
        w.update_stress_and_bow()

        # Bow should have increased due to tensile stress
        self.assertGreater(w.state.bow.value, initial_bow)

        # Etch away 50nm of the SiN layer
        top_l, removed = w.layer_stack.etch_top_layer(film_thickness(50.0, "nm"))
        self.assertIsNotNone(top_l)
        self.assertAlmostEqual(top_l.thickness.value, 50.0, places=2)
        self.assertAlmostEqual(removed.value, 50.0, places=2)

    def test_wafer_serialization(self) -> None:
        w = Wafer.create_22nm_fdsoi_wafer("LOT-SERIAL-01", wafer_number=5)
        w.state.particle_count = 12
        w.state.defect_count = 2

        d = w.to_dict()
        w_rec = Wafer.from_dict(d)
        self.assertEqual(w_rec.wafer_id.lot_id, "LOT-SERIAL-01")
        self.assertEqual(w_rec.wafer_id.wafer_number, 5)
        self.assertEqual(w_rec.state.particle_count, 12)
        self.assertEqual(w_rec.substrate.material, SubstrateMaterial.SOI_FDSOI)


class TestRecipeSystem(unittest.TestCase):
    """Test suite for Process recipes, parameters, and conditional branching."""

    def test_parameter_tolerance_check(self) -> None:
        param = RecipeParameter(
            name="Chamber Pressure",
            setpoint=pressure(10.0, "mTorr"),
            tolerance=pressure(0.5, "mTorr"),
            unit="mTorr",
            valid_range=(1.0, 50.0),
        )
        # In tolerance: 10.3 mTorr
        self.assertTrue(param.is_within_tolerance(pressure(10.3, "mTorr")))
        # Out of tolerance: 10.8 mTorr
        self.assertFalse(param.is_within_tolerance(pressure(10.8, "mTorr")))

    def test_conditional_branching_evaluation(self) -> None:
        branch = BranchCondition(
            signal_name="OES_ENDPOINT",
            operator="==",
            target_step_on_true=4,
            target_step_on_false=3,
        )
        self.assertEqual(branch.evaluate({"OES_ENDPOINT": True}), 4)
        self.assertEqual(branch.evaluate({"OES_ENDPOINT": False}), 3)
        self.assertEqual(branch.evaluate({}), 3)

    def test_recipe_library_and_equipment_validation(self) -> None:
        lib = RecipeLibrary()
        rcp = lib.get_recipe("RCP-22FDSOI-GATE-ETCH")
        self.assertIsNotNone(rcp)
        self.assertEqual(rcp.node, "22nm_FDSOI")

        # Define equipment capability envelope
        caps = EquipmentCapabilities(
            tool_type="ICP_ETCHER_300MM",
            parameter_bounds={
                "Chamber Pressure": (pressure(1.0, "mTorr"), pressure(100.0, "mTorr")),
                "Source RF Power": (rf_power(50.0, "W"), rf_power(2000.0, "W")),
                "Bias RF Power": (rf_power(5.0, "W"), rf_power(500.0, "W")),
            },
            max_steps=20,
        )
        violations = caps.validate_recipe(rcp)
        self.assertEqual(len(violations), 0)


class TestProcessRoute(unittest.TestCase):
    """Test suite for Manufacturing Process Routes and DAG validation."""

    def test_22nm_feol_route_structure(self) -> None:
        lib = RouteLibrary()
        r22 = lib.get_route("ROUTE-22FDSOI-FEOL-FLOW")
        self.assertIsNotNone(r22)
        self.assertEqual(r22.process_node, ProcessNode.NM_22_FDSOI)

        hold_points = r22.get_hold_points()
        self.assertTrue(len(hold_points) >= 5)

        # Validate DAG
        errors = r22.validate_route()
        self.assertEqual(len(errors), 0)

        # Check initial eligible steps (empty completed set -> step 10 only)
        completed: Set[int] = set()
        eligible = r22.get_eligible_steps(completed)
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0].step_number, 10)

        # After step 10 completes -> step 20 becomes eligible
        completed.add(10)
        eligible = r22.get_eligible_steps(completed)
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0].step_number, 20)

    def test_invalid_route_dependency_detection(self) -> None:
        bad_route = ProcessRoute(
            route_id="ROUTE-BAD-DAG",
            name="Broken DAG Route",
            process_node=ProcessNode.NM_65,
        )
        # Step 10 depends on Step 20 (forward dependency / cycle!)
        bad_route.add_step(ProcessStep(
            step_number=10,
            step_id="STEP_010",
            name="Step 10",
            category=ProcessStepCategory.CLEAN,
            equipment_type="CLEAN_HOOD",
            recipe_reference="RCP_01",
            dependencies=[20],
        ))
        bad_route.add_step(ProcessStep(
            step_number=20,
            step_id="STEP_020",
            name="Step 20",
            category=ProcessStepCategory.OXIDATION,
            equipment_type="FURNACE",
            recipe_reference="RCP_02",
            dependencies=[],
        ))

        errors = bad_route.validate_route()
        self.assertGreater(len(errors), 0)
        self.assertIn("invalid dependency", errors[0])


if __name__ == "__main__":
    unittest.main()
