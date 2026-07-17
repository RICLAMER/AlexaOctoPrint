import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_hue_module():
    module_name = "alexaoctoprint_hue"
    path = ROOT / "Source" / "octoprint_alexaoctoprint" / "hue.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


hue = load_hue_module()


class HueTests(unittest.TestCase):
    def test_light_key_roundtrip(self):
        identity = hue.build_identity("aabbccddeeff")
        light_id = hue.encode_light_key(identity, 3)
        self.assertEqual(hue.decode_light_key(identity, light_id), 3)

    def test_lights_payload(self):
        identity = hue.build_identity("aabbccddeeff")
        payload = hue.lights_payload(identity, [{"name": "Pause Print"}])
        self.assertEqual(len(payload), 1)
        light = next(iter(payload.values()))
        self.assertEqual(light["name"], "Pause Print")
        self.assertEqual(light["type"], "On/off light")

    def test_description_xml(self):
        identity = hue.build_identity("aabbccddeeff")
        xml = hue.description_xml("http://192.168.1.50/", identity)
        self.assertIn("<modelName>Philips hue bridge 2012</modelName>", xml)
        self.assertIn("<URLBase>http://192.168.1.50/</URLBase>", xml)
        self.assertIn("<friendlyName>Espalexa (192.168.1.50:80)</friendlyName>", xml)
        self.assertIn("aabbccddeeff", xml)

    def test_hue_username_is_unique_and_valid(self):
        first = hue.generate_hue_username()
        second = hue.generate_hue_username()
        self.assertNotEqual(first, second)
        self.assertTrue(hue.valid_hue_username(first))
        self.assertTrue(hue.username_matches(first, first))
        self.assertFalse(hue.username_matches(first, second))
        self.assertEqual(
            hue.username_response(first),
            [{"success": {"username": first}}],
        )

    def test_unauthorized_response_and_logs_redact_username(self):
        username = "a" * 40
        path = f"/api/{username}/lights"
        response = hue.unauthorized_response(path)
        self.assertEqual(response[0]["error"]["type"], 1)
        self.assertNotIn(username, str(response))
        self.assertEqual(
            hue.sanitize_hue_path(path),
            "/api/<redacted>/lights",
        )

    def test_root_urls_are_fixed_to_port_80(self):
        self.assertEqual(
            hue.hue_base_url("192.168.1.50", 80, "/"),
            "http://192.168.1.50:80/",
        )
        self.assertEqual(
            hue.location_url("192.168.1.50", 80, "/"),
            "http://192.168.1.50:80/description.xml",
        )


if __name__ == "__main__":
    unittest.main()
