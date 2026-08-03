from xvector.common.pk import from_internal_id, generate_auto_id, to_internal_id


def test_int64_roundtrip():
    assert to_internal_id(123, "Int64") == "123"
    assert from_internal_id("123", "Int64") == 123


def test_varchar_roundtrip():
    assert to_internal_id("abc", "VarChar") == "abc"
    assert from_internal_id("abc", "VarChar") == "abc"


def test_autoid_types():
    i = generate_auto_id("Int64")
    assert isinstance(i, int)
    s = generate_auto_id("VarChar")
    assert isinstance(s, str) and len(s) > 0
