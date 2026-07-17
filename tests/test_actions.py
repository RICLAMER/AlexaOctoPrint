import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_actions_module():
    module_name = "alexaoctoprint_actions"
    path = ROOT / "Source" / "octoprint_alexaoctoprint" / "actions.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


actions = load_actions_module()


class ActionTests(unittest.TestCase):
    def test_language_defaults_have_no_octo_prefix(self):
        settings = actions.merged_settings({"language": "pt"})
        self.assertEqual(actions.action_name(settings, "pause"), "Pausar Impressão")

        settings = actions.merged_settings({"language": "en"})
        self.assertEqual(actions.action_name(settings, "printer_power"), "3D Printer")

        settings = actions.merged_settings({"language": "es"})
        self.assertEqual(actions.action_name(settings, "resume"), "Reanudar Impresión")

    def test_custom_name_wins(self):
        settings = actions.merged_settings(
            {"actions": {"pause": {"name": "My Pause Command"}}}
        )
        self.assertEqual(actions.action_name(settings, "pause"), "My Pause Command")

    def test_temperature_gcode(self):
        settings = actions.merged_settings(
            {"actions": {"bed_heat": {"temperature": 95}}}
        )
        self.assertEqual(
            actions.build_gcode_for_action(settings, "bed_heat"),
            ["M140 S95"],
        )

    def test_z_move_gcode(self):
        settings = actions.merged_settings(
            {"actions": {"z_up": {"distance_mm": 2.5, "feedrate": 700}}}
        )
        self.assertEqual(
            actions.build_gcode_for_action(settings, "z_up"),
            ["G91", "G1 Z2.5 F700", "G90"],
        )
        settings["actions"]["z_down"]["distance_mm"] = 2.5
        self.assertEqual(
            actions.build_gcode_for_action(settings, "z_down"),
            ["G91", "G1 Z-2.5 F600", "G90"],
        )

    def test_retract_uses_configured_magnitude(self):
        settings = actions.merged_settings(
            {"actions": {"retract": {"extrusion_mm": 7, "feedrate": 1200}}}
        )
        self.assertEqual(
            actions.build_gcode_for_action(settings, "retract"),
            ["M83", "G1 E-7 F1200"],
        )

    def test_motor_on_and_off_gcode(self):
        settings = actions.merged_settings({})
        self.assertTrue(actions.action_supports_off("motors"))
        self.assertEqual(
            actions.build_gcode_for_action(settings, "motors", requested_on=True),
            ["M17"],
        )
        self.assertEqual(
            actions.build_gcode_for_action(settings, "motors", requested_on=False),
            ["M18"],
        )

    def test_disabled_safety_defaults(self):
        settings = actions.merged_settings({})
        keys = actions.enabled_action_keys(settings)
        self.assertNotIn("emergency", keys)
        self.assertNotIn("print_last", keys)
        self.assertNotIn("print_piece1", keys)
        self.assertIn("pause", keys)

    def test_fixed_network_and_debug_schema(self):
        settings = actions.merged_settings({})
        self.assertEqual(
            set(settings["network"]),
            {"bridge_id", "uuid", "hue_username"},
        )
        self.assertNotIn("test_device_enabled", settings["debug"])
        self.assertNotIn("cancel_requires_arm", settings)

    def test_legacy_enclosure_and_motor_actions_are_migrated(self):
        settings = actions.merged_settings(
            {
                "actions": {
                    "printer_power_on": {
                        "enabled": True,
                        "enclosure_label": "Main Relay",
                        "enclosure_status": True,
                    },
                    "light_on": {
                        "enabled": True,
                        "enclosure_label": "Case Light",
                    },
                    "motors_off": {"enabled": True, "gcode": "M84"},
                }
            }
        )
        self.assertEqual(
            settings["actions"]["printer_power"]["enclosure_label"],
            "Main Relay",
        )
        self.assertFalse(
            settings["actions"]["printer_power"]["allow_while_printing"]
        )
        self.assertEqual(
            settings["actions"]["printer_light"]["enclosure_label"],
            "Case Light",
        )
        self.assertEqual(settings["actions"]["motors"]["gcode"], "M17")
        self.assertEqual(settings["actions"]["motors"]["off_gcode"], "M84")
        for legacy_key in actions.LEGACY_ACTION_KEYS:
            self.assertNotIn(legacy_key, settings["actions"])


if __name__ == "__main__":
    unittest.main()
