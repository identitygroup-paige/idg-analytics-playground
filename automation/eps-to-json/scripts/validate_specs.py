import json
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("Usage: python scripts/validate_specs.py <spec_json>")
    sys.exit(1)

spec_path = Path(sys.argv[1])
spec = json.loads(spec_path.read_text())

errors = []

if not spec.get("document", {}).get("width_in"):
    errors.append("Missing document width_in")

if not spec.get("document", {}).get("height_in"):
    errors.append("Missing document height_in")

semantic = spec.get("semantic_fields", {})

for field_name in ["room_number", "braille"]:
    field = semantic.get(field_name)

    if not field:
        errors.append(f"Missing semantic field: {field_name}")
        continue

    required_keys = [
        "x",
        "y",
        "width",
        "height",
        "x_in",
        "y_in",
        "width_in",
        "height_in",
        "font_family",
        "font_size",
    ]

    for key in required_keys:
        if field.get(key) is None:
            errors.append(f"{field_name} missing {key}")

if errors:
    print("Validation failed:")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("Validation passed.")