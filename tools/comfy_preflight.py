"""Read-only localhost ComfyUI diagnostic. No dependencies, no installs, no mutations.

Usage: python tools/comfy_preflight.py --ports 8188 16116 16117 --checkpoint animagine-xl-3.1.safetensors
"""
from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

NEEDED_IP = ("IPAdapterUnifiedLoader", "IPAdapterAdvanced")


def _get(base: str, route: str, timeout: float = 3.0):
    with urlopen(base + route, timeout=timeout) as response:
        return json.load(response)


def inspect_port(port: int, checkpoint: str = "") -> dict:
    """Return actual server, checkpoint and IPAdapter-node status per port."""
    if not 1 <= port <= 65535:
        raise ValueError("invalid port")
    base = f"http://127.0.0.1:{port}"
    report = {
        "port": port, "url": base, "reachable": False, "comfyui": False,
        "checkpoint_found": None, "checkpoints": [],
        "ipadapter_nodes": {node: False for node in NEEDED_IP},
        "error": "",
    }
    try:
        stats = _get(base, "/system_stats")
        if not isinstance(stats, dict) or not isinstance(stats.get("system"), dict):
            report["error"] = "응답은 있지만 ComfyUI /system_stats 형식이 아닙니다."
            return report
        report["reachable"] = True
        report["comfyui"] = True
        report["version"] = str(stats["system"].get("comfyui_version", "unknown"))
        try:
            node = _get(base, "/object_info/CheckpointLoaderSimple")
            spec = (node.get("CheckpointLoaderSimple") or {}).get("input", {}).get("required", {}).get("ckpt_name")
            if isinstance(spec, list) and spec and isinstance(spec[0], list):
                report["checkpoints"] = [x for x in spec[0] if isinstance(x, str)]
            else:
                report["warning"] = "CheckpointLoaderSimple 형식 확인 필요"
        except (ValueError, HTTPError, URLError, TimeoutError, OSError) as exc:
            report["warning"] = "체크포인트 목록 조회 실패: " + str(exc)
        if checkpoint:
            report["checkpoint_found"] = checkpoint in report["checkpoints"]
        for kind in NEEDED_IP:
            try:
                data = _get(base, "/object_info/" + kind)
                report["ipadapter_nodes"][kind] = isinstance(data, dict) and kind in data
            except (ValueError, HTTPError, URLError, TimeoutError, OSError):
                report["ipadapter_nodes"][kind] = False
    except (ValueError, HTTPError, URLError, TimeoutError, OSError) as exc:
        report["error"] = str(exc)
    return report


def inspect_ports(ports, checkpoint=""):
    return [inspect_port(int(p), checkpoint) for p in ports]


def main(argv=None):
    parser = argparse.ArgumentParser(description="ComfyUI localhost read-only model/node diagnostic")
    parser.add_argument("--ports", nargs="+", type=int, default=[8188, 16116, 16117, 8081])
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    reports = inspect_ports(args.ports, args.checkpoint)
    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return 0
    for item in reports:
        print(f"\n[{item['url']}]")
        if not item["comfyui"]:
            print("  ComfyUI 서버 미확인:", item["error"])
            continue
        print("  ComfyUI:", item.get("version", "unknown"))
        print("  체크포인트 수:", len(item["checkpoints"]))
        if args.checkpoint:
            print("  선택 모델:", "인식됨" if item["checkpoint_found"] else "미인식")
        for node, found in item["ipadapter_nodes"].items():
            print(f"  {node}:", "LOADED" if found else "NOT LOADED")
        if item.get("warning"):
            print("  경고:", item["warning"])
    print("\n※ 관리자 화면의 '설치됨'이 아닌 실제 실행 서버의 등록 상태를 표시합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
