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

    def test_every_default_action_name_follows_selected_language(self):
        expected_names = {
            "pt": [
                "Impressora 3D",
                "Luz da Impressora",
                "Pausar Impressão",
                "Retomar Impressão",
                "Cancelar Impressão",
                "Levar Impressora para Home",
                "Nivelar Mesa",
                "Subir Eixo Z",
                "Baixar Eixo Z",
                "Extrudar Filamento",
                "Recolher Filamento",
                "Aquecer Mesa",
                "Desligar Mesa",
                "Aquecer Bico para PLA",
                "Aquecer Bico para ABS",
                "Aquecer Bico para PETG",
                "Desligar Aquecimento do Bico",
                "Motores da Impressora",
                "Imprimir Último Arquivo",
                "Imprimir Peça Um",
                "Imprimir Peça Dois",
                "Imprimir Peça Três",
                "Emergência da Impressora",
            ],
            "en": [
                "3D Printer",
                "Printer Light",
                "Pause Print",
                "Resume Print",
                "Cancel Print",
                "Home Printer",
                "Level Bed",
                "Raise Z Axis",
                "Lower Z Axis",
                "Extrude Filament",
                "Retract Filament",
                "Heat Bed",
                "Turn Off Bed",
                "Heat Nozzle for PLA",
                "Heat Nozzle for ABS",
                "Heat Nozzle for PETG",
                "Turn Off Nozzle Heating",
                "Printer Motors",
                "Print Last File",
                "Print Part One",
                "Print Part Two",
                "Print Part Three",
                "Printer Emergency",
            ],
            "es": [
                "Impresora 3D",
                "Luz de la Impresora",
                "Pausar Impresión",
                "Reanudar Impresión",
                "Cancelar Impresión",
                "Llevar Impresora a Inicio",
                "Nivelar Cama",
                "Subir Eje Z",
                "Bajar Eje Z",
                "Extruir Filamento",
                "Retraer Filamento",
                "Calentar Cama",
                "Apagar Cama",
                "Calentar Boquilla para PLA",
                "Calentar Boquilla para ABS",
                "Calentar Boquilla para PETG",
                "Apagar Calentamiento de la Boquilla",
                "Motores de la Impresora",
                "Imprimir Último Archivo",
                "Imprimir Pieza Uno",
                "Imprimir Pieza Dos",
                "Imprimir Pieza Tres",
                "Emergencia de la Impresora",
            ],
        }

        for language, expected in expected_names.items():
            settings = actions.merged_settings({"language": language})
            actual = [
                actions.action_name(settings, key)
                for key in actions.ACTION_ORDER
            ]
            self.assertEqual(actual, expected)

            metadata = actions.list_action_metadata(settings)
            self.assertTrue(
                all(
                    set(item["names"]) == set(actions.SUPPORTED_LANGUAGES)
                    for item in metadata
                )
            )

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        headings = {
            "pt": "### Portuguese",
            "en": "### English",
            "es": "### Spanish",
        }
        for language, heading in headings.items():
            section = readme.split(heading, 1)[1].split("### ", 1)[0]
            first_column = [
                line.split("|")[1].strip()
                for line in section.splitlines()
                if line.startswith("| ")
            ][2:]
            self.assertEqual(first_column, expected_names[language])

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
