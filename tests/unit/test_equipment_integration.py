"""Regression coverage for equipment imports and their core state-machine wiring."""

import unittest

from src.simulation.core.state_machine import SemiE10State
from src.simulation.equipment.base_equipment import GEMProcessingState, Wafer
from src.simulation.equipment.cvd_system import CVDRecipe, CVDSystem
from src.simulation.equipment.oxidation_furnace import OxidationFurnace, OxidationRecipe
from src.simulation.equipment.plasma_etch import PlasmaEtchRecipe, PlasmaEtchSystem
from src.visualization.hmi.etch_hmi import EtchHMI


class TestEquipmentIntegration(unittest.TestCase):
    """Exercise concrete equipment, which the core-only suite never imported."""

    def test_tools_initialize_with_current_state_machine(self):
        for tool_class in (PlasmaEtchSystem, CVDSystem, OxidationFurnace):
            with self.subTest(tool=tool_class.__name__):
                tool = tool_class(initial_time=0.0)
                self.assertTrue(tool.initialize())
                self.assertEqual(tool.state_machine.current_state, SemiE10State.STANDBY)
                self.assertEqual(tool.gem_processing_state, GEMProcessingState.IDLE)

    def test_interlock_blocks_processing_and_marks_equipment_down(self):
        cases = (
            (PlasmaEtchSystem, PlasmaEtchRecipe),
            (CVDSystem, CVDRecipe),
            (OxidationFurnace, OxidationRecipe),
        )
        for tool_class, recipe_class in cases:
            with self.subTest(tool=tool_class.__name__):
                tool = tool_class(initial_time=0.0)
                tool.initialize()
                wafer = Wafer("TEST-01")
                recipe = recipe_class(recipe_name="Blocked run", recipe_id="TEST")
                with self.assertLogs(level="WARNING"):
                    tool.trip_interlock("INTLK_EXHAUST", "Simulated exhaust loss")
                self.assertEqual(
                    tool.state_machine.current_state, SemiE10State.UNSCHEDULED_DOWN
                )
                with self.assertRaisesRegex(RuntimeError, "interlocks"):
                    tool.process_wafer(wafer, recipe)
                self.assertEqual(wafer.process_history, [])
                self.assertEqual(wafer.layers, [])
                self.assertNotEqual(tool.gem_processing_state, GEMProcessingState.EXECUTING)

    def test_etch_hmi_connects_to_equipment(self):
        tool = PlasmaEtchSystem(initial_time=0.0)
        panel = EtchHMI(equipment_reference=tool)
        self.assertIs(panel.equipment, tool)


if __name__ == "__main__":
    unittest.main()
