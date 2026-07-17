import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_update_module():
    module_name = "alexaoctoprint_update"
    path = ROOT / "Source" / "octoprint_alexaoctoprint" / "update.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


update = load_update_module()


class UpdateTests(unittest.TestCase):
    def test_update_information_uses_github_releases(self):
        information = update.build_update_information(
            "alexaoctoprint",
            "Alexa OctoPrint",
            "0.2.0",
        )
        check = information["alexaoctoprint"]
        self.assertEqual(check["current"], "0.2.0")
        self.assertEqual(check["type"], "github_release")
        self.assertEqual(check["user"], "RICLAMER")
        self.assertEqual(check["repo"], "AlexaOctoPrint")
        self.assertEqual(
            check["pip"],
            "https://github.com/RICLAMER/AlexaOctoPrint/archive/{target_version}.zip",
        )


if __name__ == "__main__":
    unittest.main()
