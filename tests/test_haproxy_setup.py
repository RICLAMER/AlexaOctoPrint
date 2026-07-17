import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_haproxy_module():
    module_name = "alexaoctoprint_haproxy_setup"
    path = ROOT / "Source" / "octoprint_alexaoctoprint" / "haproxy_setup.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


haproxy_setup = load_haproxy_module()


BASE_CONFIG = """global
        maxconn 4096

defaults
        mode http

frontend public
        bind :::80 v4v6
        use_backend webcam if { path_beg /webcam/ }
        default_backend octoprint

backend octoprint
        server octoprint1 127.0.0.1:5000

backend webcam
        server webcam1 127.0.0.1:8080
"""


class HAProxySetupTests(unittest.TestCase):
    def test_managed_config_preserves_existing_routes(self):
        configured = haproxy_setup.build_managed_config(BASE_CONFIG, 5000)
        self.assertIn("use_backend webcam if { path_beg /webcam/ }", configured)
        self.assertIn("default_backend octoprint", configured)
        self.assertIn("backend webcam", configured)
        self.assertIn(haproxy_setup.FRONTEND_BEGIN, configured)
        self.assertIn(haproxy_setup.BACKEND_BEGIN, configured)
        self.assertIn("server alexaoctoprint 127.0.0.1:5000", configured)

    def test_routes_are_limited_to_hue_paths_and_key_shape(self):
        configured = haproxy_setup.build_managed_config(BASE_CONFIG, 5000)
        self.assertIn("^/api/[0-9a-fA-F]{40}/?$", configured)
        self.assertIn("^/api/[0-9a-fA-F]{40}/lights", configured)
        self.assertNotIn("/api/job", configured)
        self.assertNotIn("/api/files", configured)

    def test_removal_returns_original_configuration(self):
        configured = haproxy_setup.build_managed_config(BASE_CONFIG, 5000)
        restored = haproxy_setup.remove_alexaoctoprint_routes(configured)
        self.assertEqual(restored, BASE_CONFIG)

    def test_legacy_routes_are_replaced_without_static_username(self):
        legacy = BASE_CONFIG.replace(
            "        default_backend octoprint\n",
            "        acl alexaoctoprint_api_user path -i /api/OldStaticKey\n"
            "        use_backend alexaoctoprint_hue if alexaoctoprint_api_user\n"
            "        default_backend octoprint\n",
        ) + """
backend alexaoctoprint_hue
        server octoprint1 127.0.0.1:5000
"""
        configured = haproxy_setup.build_managed_config(legacy, 5000)
        self.assertNotIn("OldStaticKey", configured)
        self.assertEqual(
            configured.splitlines().count("backend alexaoctoprint_hue"),
            1,
        )

    def test_missing_port_80_frontend_is_rejected(self):
        with self.assertRaises(RuntimeError):
            haproxy_setup.build_managed_config(
                BASE_CONFIG.replace(":::80", ":::8080"),
                5000,
            )


if __name__ == "__main__":
    unittest.main()
