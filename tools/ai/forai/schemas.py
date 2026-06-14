from __future__ import annotations

from pathlib import Path
from typing import Any

from .json_io import read_json
from .paths import schema_dir


SCHEMA_FILE_BY_ID = {
    "context-pack/v1": "context-pack.v1.schema.json",
    "domain-spec/v1": "domain-spec.v1.schema.json",
    "execution-plan/v1": "execution-plan.v1.schema.json",
    "intent-analysis/v1": "intent-analysis.v1.schema.json",
    "requirement-check/v1": "requirement-check.v1.schema.json",
    "risk-review/v1": "risk-review.v1.schema.json",
    "unity-execution/v1": "unity-execution.v1.schema.json",
    "validation-report/v1": "validation-report.v1.schema.json",
    "workflow-state/v1": "workflow-state.v1.schema.json",
    "workflow-state/v2": "workflow-state.v2.schema.json",
}


class SchemaValidationError(ValueError):
    pass


def load_schema(project_root: Path, schema_id: str) -> dict[str, Any]:
    filename = SCHEMA_FILE_BY_ID.get(schema_id)
    if filename is None:
        raise KeyError(f"Unknown schema id: {schema_id}")
    return read_json(schema_dir(project_root) / filename)


def validate_payload(schema: dict[str, Any], payload: Any) -> None:
    _validate_node(schema, payload, "$")


def _validate_node(schema: dict[str, Any], value: Any, path: str) -> None:
    expected_type = schema.get("type")
    if expected_type is not None:
        _validate_type(expected_type, value, path)

    if "const" in schema and value != schema["const"]:
        raise SchemaValidationError(f"{path}: expected const {schema['const']!r}, got {value!r}")

    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(f"{path}: expected one of {schema['enum']!r}, got {value!r}")

    if isinstance(value, str) and "minLength" in schema and len(value) < int(schema["minLength"]):
        raise SchemaValidationError(f"{path}: expected minLength {schema['minLength']}")

    if schema.get("type") == "object" or "properties" in schema or "required" in schema:
        if not isinstance(value, dict):
            raise SchemaValidationError(f"{path}: expected object")
        _validate_object(schema, value, path)

    if schema.get("type") == "array" or "items" in schema:
        if not isinstance(value, list):
            raise SchemaValidationError(f"{path}: expected array")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_node(item_schema, item, f"{path}[{index}]")


def _validate_object(schema: dict[str, Any], value: dict[str, Any], path: str) -> None:
    for field in schema.get("required", []):
        if field not in value:
            raise SchemaValidationError(f"{path}: missing required property {field!r}")

    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        extra = sorted(set(value) - set(properties))
        if extra:
            raise SchemaValidationError(f"{path}: additional properties not allowed: {', '.join(extra)}")

    for key, child_schema in properties.items():
        if key in value:
            _validate_node(child_schema, value[key], f"{path}.{key}")


def _validate_type(expected_type: str, value: Any, path: str) -> None:
    validators = {
        "object": lambda candidate: isinstance(candidate, dict),
        "array": lambda candidate: isinstance(candidate, list),
        "string": lambda candidate: isinstance(candidate, str),
        "boolean": lambda candidate: isinstance(candidate, bool),
        "integer": lambda candidate: isinstance(candidate, int) and not isinstance(candidate, bool),
        "number": lambda candidate: (isinstance(candidate, int | float) and not isinstance(candidate, bool)),
    }
    validator = validators.get(expected_type)
    if validator is None:
        raise SchemaValidationError(f"{path}: unsupported schema type {expected_type!r}")
    if not validator(value):
        raise SchemaValidationError(f"{path}: expected {expected_type}, got {type(value).__name__}")
