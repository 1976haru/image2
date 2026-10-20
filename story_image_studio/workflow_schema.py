"""Validate a ComfyUI API graph against the *running* server's /object_info.

Catches wrong node names, missing required inputs, unknown combo values (e.g. a
model file the selected instance does not list) and dangling links BEFORE
POST /prompt, so a bad graph never occupies the GPU queue.
"""
from __future__ import annotations


class GraphSchemaError(ValueError):
    pass


def combo_options(spec) -> list | None:
    """Return combo choices for both encodings ComfyUI uses, else None.

    Legacy: [["a.safetensors", "b.safetensors"], {...}]
    V3:     ["COMBO", {"options": ["a", "b"], ...}]
    """
    if not isinstance(spec, list) or not spec:
        return None
    head = spec[0]
    if isinstance(head, list):
        return [x for x in head if isinstance(x, str)]
    if head == 'COMBO' and len(spec) > 1 and isinstance(spec[1], dict):
        options = spec[1].get('options')
        if isinstance(options, list):
            return [x for x in options if isinstance(x, str)]
    return None


def validate_graph(nodes: dict, info: dict) -> None:
    problems = []
    for node_id, node in nodes.items():
        cls = node.get('class_type')
        schema = info.get(cls)
        if not isinstance(schema, dict):
            problems.append(f'[{node_id}] 서버에 등록되지 않은 노드: {cls}')
            continue
        inputs = node.get('inputs') or {}
        declared = schema.get('input') or {}
        required = declared.get('required') or {}
        optional = declared.get('optional') or {}
        for name in required:
            if name not in inputs:
                problems.append(f'[{node_id}] {cls}: 필수 입력 누락 {name}')
        for name, value in inputs.items():
            spec = required.get(name, optional.get(name))
            if spec is None:
                problems.append(f'[{node_id}] {cls}: 서버 스키마에 없는 입력 {name}')
                continue
            if isinstance(value, list):
                if len(value) != 2 or str(value[0]) not in nodes:
                    problems.append(f'[{node_id}] {cls}.{name}: 연결 대상 노드 없음 {value}')
                continue
            options = combo_options(spec)
            if options is not None and cls != 'LoadImage' and value not in options:
                problems.append(f'[{node_id}] {cls}.{name}: 서버 목록에 없는 값 {value!r}')
    if problems:
        raise GraphSchemaError('워크플로가 현재 ComfyUI 서버와 맞지 않습니다:\n' + '\n'.join(problems))
