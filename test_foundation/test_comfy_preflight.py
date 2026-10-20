import unittest
from unittest.mock import patch
from urllib.error import URLError
from tools.comfy_preflight import inspect_port, inspect_ports, NEEDED_IP


class PreflightTests(unittest.TestCase):
    def test_loaded_nodes_and_checkpoint(self):
        def fake(_, route, timeout=3.0):
            if route == "/system_stats":
                return {"system": {"comfyui_version": "0.42.1"}}
            if route == "/object_info/CheckpointLoaderSimple":
                return {"CheckpointLoaderSimple": {"input": {"required": {
                    "ckpt_name": [["animagine-xl-3.1.safetensors"]]
                }}}}
            if route.startswith("/object_info/IPAdapter"):
                key = route.rsplit("/", 1)[-1]
                return {key: {"input": {}}}
            raise AssertionError(route)
        with patch("tools.comfy_preflight._get", side_effect=fake):
            data = inspect_port(8188, "animagine-xl-3.1.safetensors")
        self.assertTrue(data["comfyui"])
        self.assertTrue(data["checkpoint_found"])
        self.assertTrue(all(data["ipadapter_nodes"].values()))

    def test_checkpoint_is_present_but_nodes_not_loaded(self):
        def fake(_, route, timeout=3.0):
            if route == "/system_stats":
                return {"system": {"comfyui_version": "0.42.1"}}
            if route == "/object_info/CheckpointLoaderSimple":
                return {"CheckpointLoaderSimple": {"input": {"required": {
                    "ckpt_name": [["checkpoint-not-named-sdxl.safetensors"]]
                }}}}
            if route.startswith("/object_info/IPAdapter"):
                return {}
            raise AssertionError(route)
        with patch("tools.comfy_preflight._get", side_effect=fake):
            data = inspect_port(8188, "checkpoint-not-named-sdxl.safetensors")
        self.assertTrue(data["checkpoint_found"])
        self.assertEqual(data["ipadapter_nodes"], {k: False for k in NEEDED_IP})

    def test_wrong_server_is_rejected(self):
        with patch("tools.comfy_preflight._get", return_value={"not_comfy": "hello"}):
            data = inspect_port(8188)
        self.assertFalse(data["comfyui"])
        self.assertIn("형식", data["error"])

    def test_offline_instance_is_reported(self):
        with patch("tools.comfy_preflight._get", side_effect=URLError("offline")):
            data = inspect_port(16116)
        self.assertFalse(data["reachable"])
        self.assertFalse(data["comfyui"])

    def test_port_validation(self):
        for port in (0, 65536, -1):
            with self.subTest(port=port), self.assertRaises(ValueError):
                inspect_port(port)

    def test_multiple_ports_checked_independently(self):
        def fake(url, route, timeout=3.0):
            if "8188" in url:
                raise URLError("offline")
            if route == "/system_stats":
                return {"system": {"comfyui_version": "0.42.1"}}
            return {}
        with patch("tools.comfy_preflight._get", side_effect=fake):
            reports = inspect_ports([8188, 16116])
        self.assertFalse(reports[0]["comfyui"])
        self.assertTrue(reports[1]["comfyui"])


if __name__ == "__main__":
    unittest.main()
