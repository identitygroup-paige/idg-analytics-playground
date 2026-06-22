import json
import sys
from pathlib import Path


##STATIC → fields may be empty
##VARIABLE_pure → all fields should be content_kind variable
##COMBINATION_simple/rich → fields may be static or variable

if len(sys.argv) != 2:
    print("Usage: python scripts/validate_production_json.py <production_json>")
    sys.exit(1)


path = Path(sys.argv[1])
data = json.loads(path.read_text())

errors = []

required_top_level = [
    "sign_id",
    "sign_type",
    "description",
    "units_per_inch",
    "physical_size",
    "page_size",
    "eps_source",
    "fields",
    "template_type",
]

for key in required_top_level:
    if key not in data:
        errors.append(f"Missing top-level key: {key}")

if not data.get("fields"):
    errors.append("No fields found")

for field in data.get("fields", []):
    field_id = field.get("id", "<missing id>")

    required_field_keys = [
        "id",
        "type",
        "content_kind",
        "alignment",
        "bbox_review",
        "eps_position",
        "eps_font",
        "ps_command",
    ]

    for key in required_field_keys:
        if key not in field:
            errors.append(f"{field_id} missing field key: {key}")

    if not field.get("ps_command"):
        errors.append(f"{field_id} missing ps_command")

    if not field.get("eps_position", {}).get("baseline_y_pt"):
        errors.append(f"{field_id} missing baseline_y_pt")

    if not field.get("eps_font", {}).get("font_size_pt"):
        errors.append(f"{field_id} missing font_size_pt")

template_type = data.get("template_type")

if template_type == "STATIC":
    if data.get("fields"):
        errors.append("STATIC template should usually have no variable fields")

elif template_type == "VARIABLE_pure":
    for field in data.get("fields", []):
        if field.get("content_kind") != "variable":
            errors.append(f"{field.get('id')} should be variable for VARIABLE_pure template")

elif template_type in ["COMBINATION_simple", "COMBINATION_rich"]:
    kinds = {field.get("content_kind") for field in data.get("fields", [])}
    if "variable" not in kinds:
        errors.append(f"{template_type} must include at least one variable field")

if errors:
    print("Validation failed:")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("Validation passed.")