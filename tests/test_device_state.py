import importlib.util
import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, filename):
    path = ROOT / "Source" / "octoprint_alexaoctoprint" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


device_state = load_module("alexaoctoprint_device_state", "device_state.py")
enclosure = load_module("alexaoctoprint_enclosure", "enclosure.py")


class DeviceStateTests(unittest.TestCase):
    def test_state_is_available_until_automatic_reset(self):
        states = device_state.HueDeviceStateStore()
        states.set("home", True, reset_after=0.03)
        self.assertTrue(states.get("home"))
        time.sleep(0.08)
        self.assertFalse(states.get("home"))
        states.close()

    def test_manual_reset_cancels_pending_timer(self):
        states = device_state.HueDeviceStateStore()
        states.set("bed_heat", True, reset_after=0.05)
        states.set("bed_heat", False)
        self.assertFalse(states.get("bed_heat"))
        states.close()

    def test_enclosure_label_is_whitespace_and_case_insensitive(self):
        outputs = [{"label": "POWER ", "index_id": 1}, {"label": "LIGHT", "index_id": 2}]
        self.assertEqual(enclosure.find_output_by_label(outputs, "Power")["index_id"], 1)
        self.assertEqual(enclosure.find_output_by_label(outputs, " light ")["index_id"], 2)

    def test_active_low_hardware_value(self):
        self.assertFalse(enclosure.hardware_value(True, active_low=True))
        self.assertTrue(enclosure.hardware_value(False, active_low=True))

    def test_enclosure_dropdown_labels_are_unique(self):
        outputs = [
            {"label": "Power", "index_id": 1, "gpio_pin": 17},
            {"label": " power ", "index_id": 2, "gpio_pin": 18},
            {"label": "LIGHT ", "index_id": 3, "gpio_pin": 27},
            {"label": "", "index_id": 4},
            {"label": "Fan PWM", "index_id": 5, "output_type": "pwm"},
        ]
        labels = enclosure.list_output_labels(outputs)
        self.assertEqual([item["label"] for item in labels], ["Power", "LIGHT"])


if __name__ == "__main__":
    unittest.main()
