from scripts.validate_runtime_imports import validate_modules


def test_runtime_import_validation_classifies_required_and_optional_failures():
    def importer(name):
        if name in {"critical.missing", "optional.missing"}:
            raise ImportError(name)
        return object()

    results = validate_modules(
        critical=("critical.ok", "critical.missing"),
        optional=("optional.ok", "optional.missing"),
        importer=importer,
    )
    indexed = {result.module: result for result in results}
    assert indexed["critical.ok"].available is True
    assert indexed["critical.missing"].required is True
    assert indexed["critical.missing"].available is False
    assert indexed["optional.missing"].required is False
    assert indexed["optional.missing"].available is False


def test_mediapipe_is_not_a_critical_boot_import():
    from scripts.validate_runtime_imports import CRITICAL_MODULES, OPTIONAL_MODULES

    assert "mediapipe" not in CRITICAL_MODULES
    assert "mediapipe" in OPTIONAL_MODULES
