import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Source"


def install_octoprint_stubs():
    octoprint = types.ModuleType("octoprint")
    plugin = types.ModuleType("octoprint.plugin")

    class StartupPlugin:
        pass

    class ShutdownPlugin:
        pass

    class SettingsPlugin:
        def on_settings_save(self, data):
            return None

    class TemplatePlugin:
        pass

    class AssetPlugin:
        pass

    class BlueprintPlugin:
        @staticmethod
        def route(*args, **kwargs):
            def decorator(function):
                return function

            return decorator

    class SimpleApiPlugin:
        pass

    class EventHandlerPlugin:
        pass

    plugin.StartupPlugin = StartupPlugin
    plugin.ShutdownPlugin = ShutdownPlugin
    plugin.SettingsPlugin = SettingsPlugin
    plugin.TemplatePlugin = TemplatePlugin
    plugin.AssetPlugin = AssetPlugin
    plugin.BlueprintPlugin = BlueprintPlugin
    plugin.SimpleApiPlugin = SimpleApiPlugin
    plugin.EventHandlerPlugin = EventHandlerPlugin
    octoprint.plugin = plugin

    server = types.ModuleType("octoprint.server")
    server_util = types.ModuleType("octoprint.server.util")
    server_flask = types.ModuleType("octoprint.server.util.flask")
    server_flask.restricted_access = lambda function: function
    events = types.ModuleType("octoprint.events")

    class Events:
        FILE_SELECTED = "FileSelected"
        PRINT_STARTED = "PrintStarted"

    events.Events = Events
    sys.modules["octoprint"] = octoprint
    sys.modules["octoprint.plugin"] = plugin
    sys.modules["octoprint.server"] = server
    sys.modules["octoprint.server.util"] = server_util
    sys.modules["octoprint.server.util.flask"] = server_flask
    sys.modules["octoprint.events"] = events


def install_flask_stub():
    flask = types.ModuleType("flask")
    flask.Response = lambda *args, **kwargs: types.SimpleNamespace(headers={})
    flask.jsonify = lambda payload: types.SimpleNamespace(payload=payload, headers={})
    flask.request = types.SimpleNamespace(
        headers={},
        remote_addr="127.0.0.1",
        path="/",
        method="GET",
        get_json=lambda silent=True: {},
    )
    sys.modules["flask"] = flask


install_octoprint_stubs()
install_flask_stub()
sys.path.insert(0, str(SOURCE))

import octoprint_alexaoctoprint as plugin_module  # noqa: E402
from octoprint_alexaoctoprint import actions, hue  # noqa: E402


class FakeLogger:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def exception(self, *args, **kwargs):
        return None


class FakePrinter:
    def __init__(self, printing=False, paused=False):
        self.printing = printing
        self.paused = paused
        self.sent_commands = []

    def is_operational(self):
        return True

    def is_printing(self):
        return self.printing

    def is_paused(self):
        return self.paused

    def is_error(self):
        return False

    def is_closed_or_error(self):
        return False

    def commands(self, commands):
        self.sent_commands.append(list(commands))


class PluginBehaviorTests(unittest.TestCase):
    def make_plugin(self, settings):
        implementation = plugin_module.AlexaOctoPrintPlugin()
        implementation._logger = FakeLogger()
        implementation._printer = FakePrinter()
        implementation._record = lambda *args, **kwargs: None
        implementation._settings_snapshot = lambda: settings
        implementation._identity = hue.build_identity("aabbccddeeff")
        return implementation

    def test_missing_enclosure_returns_controlled_status_and_action_error(self):
        settings = actions.merged_settings({})
        implementation = self.make_plugin(settings)
        implementation._plugin_manager = None

        snapshot = implementation._enclosure_outputs_snapshot()
        self.assertFalse(snapshot["available"])
        self.assertIn("unavailable", snapshot["error"])

        result = implementation._execute_action(
            "printer_power",
            source="test",
            requested_on=True,
        )
        self.assertFalse(result["ok"])
        self.assertIn("plugin manager is unavailable", result["error"])

    def test_enclosure_dropdown_reads_runtime_labels(self):
        settings = actions.merged_settings({})
        implementation = self.make_plugin(settings)
        enclosure = types.SimpleNamespace(
            rpi_outputs=[
                {"label": "Main Relay", "index_id": 1, "gpio_pin": 17},
                {"label": "Work Light", "index_id": 2, "gpio_pin": 27},
            ]
        )
        plugin_info = types.SimpleNamespace(
            implementation=enclosure,
            instance=None,
        )
        implementation._plugin_manager = types.SimpleNamespace(
            get_plugin_info=lambda identifier: plugin_info
        )

        snapshot = implementation._enclosure_outputs_snapshot()
        self.assertTrue(snapshot["available"])
        self.assertEqual(
            [output["label"] for output in snapshot["outputs"]],
            ["Main Relay", "Work Light"],
        )

    def test_bidirectional_motor_device_sends_on_and_off_gcode(self):
        settings = actions.merged_settings({})
        for action in settings["actions"].values():
            action["enabled"] = False
        settings["actions"]["motors"]["enabled"] = True
        implementation = self.make_plugin(settings)

        light_id = hue.encode_light_key(implementation._identity, 0)
        on_result = implementation._execute_light(
            light_id,
            source="test",
            payload={"on": True},
        )
        off_result = implementation._execute_light(
            light_id,
            source="test",
            payload={"on": False},
        )

        self.assertTrue(on_result["ok"])
        self.assertTrue(off_result["ok"])
        self.assertEqual(
            implementation._printer.sent_commands,
            [["M17"], ["M18"]],
        )
        self.assertFalse(implementation._device_states.get("motors"))
        implementation._device_states.close()

    def test_power_off_is_blocked_while_printing_by_default(self):
        settings = actions.merged_settings({})
        implementation = self.make_plugin(settings)
        implementation._printer = FakePrinter(printing=True)

        result = implementation._execute_action(
            "printer_power",
            source="test",
            requested_on=False,
        )
        self.assertFalse(result["ok"])
        self.assertIn("blocked while printer is printing", result["error"])
        implementation._device_states.close()


if __name__ == "__main__":
    unittest.main()
