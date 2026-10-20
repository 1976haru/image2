"""Read-only preflight for cubiq IPAdapter Plus and SDXL matching models.

Never install/delete extensions or download model weights without user action.
Checking the user-selected Shared Models root is informational: ComfyUI can have
other model roots configured in extra_model_paths.yaml or instance directories.
"""
from __future__ import annotations
from pathlib import Path

NODE_NAMES = ("IPAdapterUnifiedLoader", "IPAdapterAdvanced")
ASSET_FILES = {
    "ipadapter": "ip-adapter-plus_sdxl_vit-h.safetensors",
    "clip_vision": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
}
EXTENSION_URL = "https://github.com/cubiq/ComfyUI_IPAdapter_plus"
DOWNLOAD_LINKS = {
    "ipadapter": "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors",
    "clip_vision": "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors",
}


def inspect_ipadapter(info: dict, shared_root: str | Path) -> dict:
    """Return concrete readiness evidence, never assume server's other model roots."""
    root = Path(shared_root)
    missing_nodes = [x for x in NODE_NAMES if x not in info]
    present_assets = {}
    for folder, filename in ASSET_FILES.items():
        # ComfyUI accepts files inside model subdirectories as well.
        base = root/folder
        matches = (p for p in base.rglob(filename) if p.is_file()) if base.is_dir() else iter(())
        present_assets[folder] = next(matches, None)
    return {
        "root": str(root),
        "missing_nodes": missing_nodes,
        "node_ready": not missing_nodes,
        "assets": present_assets,
        "shared_root_ready": all(present_assets.values()),
    }


def format_ipadapter_report(result: dict, server: str) -> str:
    out = ["CHILI LAB · SDXL IPAdapter 사전 점검", f"ComfyUI 서버: {server}",
           f"확인한 Shared Models: {result['root']}", ""]
    if result['missing_nodes']:
        out += ["[확장 노드 누락] " + ", ".join(result['missing_nodes']),
                "현재 인스턴스의 확장 프로그램 관리자에서 'ComfyUI_IPAdapter_plus'를 설치하세요.",
                "설치할 곳은 Comfy Desktop 실행 프로그램 폴더가 아니라 현재 사용 중인 ComfyUI 인스턴스입니다.",
                "설치 후 해당 인스턴스를 완전히 재시작하고 이 점검을 다시 실행하세요.",
                "공식 확장: " + EXTENSION_URL]
    else:
        out += ["[노드] 필수 확장 노드 2개 모두 서버에서 확인됨"]
    out += ["", "[SDXL 보조 모델] 아래 두 파일이 모두 필요합니다."]
    for folder,filename in ASSET_FILES.items():
        found=result['assets'][folder]
        out += [f"- {'공유 폴더에서 발견' if found else '선택한 공유 폴더에 없음'}: {filename}",
                "  확인 위치: " + str(Path(result['root'])/folder/filename)]
        if not found:out.append("  다운로드: " + DOWNLOAD_LINKS[folder])
    if not result['shared_root_ready']:
        out += ["", "주의: 파일이 이 공유 폴더에 없더라도 인스턴스별 다른 모델 경로에서 읽을 수 있습니다.",
                "이 진단은 선택 폴더만 검사하므로 다른 경로의 존재까지 단정하지 않습니다."]
    out += ["", "모델명 주의: CLIP Vision 다운로드 원본은 model.safetensors입니다.",
            "지정 폴더에 저장할 때 위 CLIP-ViT-H-14... 파일명으로 변경하세요.",
            "Unified Loader의 PLUS (high strength)는 SDXL용 ip-adapter-plus_sdxl_vit-h 모델을 찾습니다.",
            "남녀 얼굴을 100% 고정하는 기능은 아니며 두 인물 특성이 섞일 수 있습니다."]
    if result['node_ready'] and result['shared_root_ready']:
        out += ["", "서버 노드와 선택 폴더의 두 모델 파일 확인됨. 실제 GPU 추론 성공은 별도 테스트가 필요합니다."]
    else:
        out += ["", "필수 요소를 확인한 뒤 1장 시험 생성부터 진행하세요. 같은 오류로 4장을 재실행하지 마세요."]
    return "\n".join(out)
