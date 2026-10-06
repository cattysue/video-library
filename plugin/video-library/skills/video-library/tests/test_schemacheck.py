from video_library.schemacheck import check


def test_valid_instance_returns_empty_list():
    schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}
    assert check({"a": 1}, schema) == []


def test_type_mismatch_reports_path():
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
    assert check({"a": "x"}, schema) == ["$.a: integer 이어야 함"]


def test_bool_is_not_integer_or_number():
    assert check(True, {"type": "integer"}) == ["$: integer 이어야 함"]
    assert check(False, {"type": "number"}) == ["$: number 이어야 함"]
    assert check(1.5, {"type": "number"}) == []


def test_required_missing():
    assert check({}, {"type": "object", "required": ["x"]}) == ["$: 필수 항목 'x' 없음"]


def test_enum_pattern_lengths():
    assert check("z", {"enum": ["a", "b"]}) == ["$: 허용 값 ['a', 'b'] 중 하나여야 함"]
    assert check("abc", {"type": "string", "pattern": "^[a-z]{2}$"}) == ["$: 형식(^[a-z]{2}$)에 맞지 않음"]
    assert check("", {"type": "string", "minLength": 1}) == ["$: 1자 이상이어야 함"]
    assert check("abcd", {"type": "string", "maxLength": 3}) == ["$: 3자 이하여야 함"]


def test_minimum_and_item_counts():
    assert check(-1, {"type": "number", "minimum": 0}) == ["$: 0 이상이어야 함"]
    assert check([1], {"type": "array", "minItems": 2}) == ["$: 항목 2개 이상이어야 함"]
    assert check([1, 2, 3], {"type": "array", "maxItems": 2}) == ["$: 항목 2개 이하여야 함"]


def test_items_and_additional_properties():
    schema = {"type": "object",
              "additionalProperties": {"type": "array", "items": {"type": "integer"}}}
    assert check({"en": [1, "x"]}, schema) == ["$.en[1]: integer 이어야 함"]


def test_additional_properties_skips_declared_properties():
    schema = {"type": "object", "properties": {"a": {"type": "string"}},
              "additionalProperties": {"type": "integer"}}
    assert check({"a": "ok", "b": 2}, schema) == []


def test_ref_resolves_recursively():
    schema = {
        "$defs": {"node": {"type": "object", "required": ["kids"],
                           "properties": {"kids": {"type": "array", "items": {"$ref": "#/$defs/node"}}}}},
        "$ref": "#/$defs/node",
    }
    assert check({"kids": [{"kids": []}, {}]}, schema) == ["$.kids[1]: 필수 항목 'kids' 없음"]


def test_ref_with_explicit_root():
    root = {"$defs": {"n": {"type": "integer"}}}
    assert check("x", {"$ref": "#/$defs/n"}, root=root, path="$[3]") == ["$[3]: integer 이어야 함"]


def test_pattern_dollar_rejects_trailing_newline():
    assert check("AbCdEfGhIjK\n", {"type": "string", "pattern": "^[A-Za-z]{11}$"}) == \
        ["$: 형식(^[A-Za-z]{11}$)에 맞지 않음"]


def test_nan_and_infinity_are_not_numbers():
    assert check(float("nan"), {"type": "number"}) == ["$: number 이어야 함"]
    assert check(float("inf"), {"type": "number"}) == ["$: number 이어야 함"]
