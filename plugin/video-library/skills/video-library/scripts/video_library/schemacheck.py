"""JSON Schema(2020-12)의 작은 부분집합 검사기. 표준 라이브러리만.

지원 키워드: type, required, properties, additionalProperties(스키마), items, enum,
minimum, minLength, maxLength, minItems, maxItems, pattern, $ref("#/$defs/<이름>").
오류는 "<경로>: <이유>" 문자열 목록으로 돌려준다(빈 목록 = 통과). 예외를 던지지 않는다.
bool 은 integer·number 로 보지 않는다(파이썬에서 bool 은 int 의 하위 타입이라 따로 막는다).
NaN·Infinity 는 number 가 아니다(표준 JSON 이 아니라 브라우저가 읽지 못한다).
pattern 끝의 $ 는 JavaScript 처럼 문자열의 진짜 끝만 뜻한다(파이썬 $ 는 끝의 줄바꿈 앞에서도 맞는다).
"""
from __future__ import annotations

import math
import re

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v),
    "boolean": lambda v: isinstance(v, bool),
}
_REF_PREFIX = "#/$defs/"


def _js_end(pattern: str) -> str:
    """끝의 $ 를 \\Z 로 바꿔 끝에 붙은 줄바꿈을 허용하지 않는다."""
    if pattern.endswith("$") and not pattern.endswith("\\$"):
        return pattern[:-1] + r"\Z"
    return pattern


def resolve(root: dict, ref: str) -> dict:
    if not ref.startswith(_REF_PREFIX):
        raise ValueError(f"지원하지 않는 $ref: {ref}")
    return root["$defs"][ref[len(_REF_PREFIX):]]


def check(instance, schema: dict, root: dict | None = None, path: str = "$") -> list[str]:
    root = schema if root is None else root
    if "$ref" in schema:
        return check(instance, resolve(root, schema["$ref"]), root, path)

    t = schema.get("type")
    if t is not None and not _TYPES[t](instance):
        return [f"{path}: {t} 이어야 함"]

    errors: list[str] = []
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: 허용 값 {schema['enum']} 중 하나여야 함")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: {schema['minLength']}자 이상이어야 함")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: {schema['maxLength']}자 이하여야 함")
        if "pattern" in schema and not re.search(_js_end(schema["pattern"]), instance):
            errors.append(f"{path}: 형식({schema['pattern']})에 맞지 않음")

    if _TYPES["number"](instance) and "minimum" in schema and instance < schema["minimum"]:
        errors.append(f"{path}: {schema['minimum']} 이상이어야 함")

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: 필수 항목 '{key}' 없음")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in instance:
                errors += check(instance[key], sub, root, f"{path}.{key}")
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict):
            for key, value in instance.items():
                if key not in props:
                    errors += check(value, extra, root, f"{path}.{key}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: 항목 {schema['minItems']}개 이상이어야 함")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: 항목 {schema['maxItems']}개 이하여야 함")
        if "items" in schema:
            for i, item in enumerate(instance):
                errors += check(item, schema["items"], root, f"{path}[{i}]")

    return errors
