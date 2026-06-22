import json
import sys
from pathlib import Path


if len(sys.argv) != 4:
    print(
        "Usage: python scripts/merge_to_production_json.py "
        "<eps_json> <field_parameters_json> <output_json>"
    )
    sys.exit(1)


eps_json_path = Path(sys.argv[1])
field_params_path = Path(sys.argv[2])
output_path = Path(sys.argv[3])

eps_data = json.loads(eps_json_path.read_text())
field_params = json.loads(field_params_path.read_text())

eps_source = eps_data["eps_source"]

units_per_inch = field_params.get("units_per_inch", 54)
pt_per_unit = 72 / units_per_inch


def to_points(value):
    return round(value * pt_per_unit, 4) if value is not None else None


production_json = {
    "sign_id": field_params["sign_id"],
    "sign_type": field_params["sign_type"],
    "description": field_params["description"],
    "template_type": field_params.get("template_type"),
    "static": field_params.get("static", False),
    "combination_sign": field_params.get("combination_sign", False),
    "svg_viewBox": field_params.get("svg_viewBox"),
    "units_per_inch": units_per_inch,
    "physical_size": field_params.get("physical_size"),
    "page_size": field_params.get("page_size"),
    "field_review": field_params.get("field_review"),
    "eps_source": eps_source,
    "fields": [],
    "unit_conversion": {
        "rule": "All EPS-source numeric values are in EPS userspace units, not points.",
        "formula": "pt_value = eps_value × (72 / units_per_inch)",
        "for_this_brand": {
            "units_per_inch": units_per_inch,
            "pt_per_unit": round(pt_per_unit, 6)
        }
    }
}


for field in field_params["fields"]:
    field_id = field["id"]

    if field_id == "ROOM_NUMBER":
        eps_field = eps_source.get("room_number", {})
    elif field_id == "BRAILLE_TEXT":
        eps_field = eps_source.get("braille", {})
    else:
        eps_field = {}

    merged_field = {
        **field,
        "eps_position": {
            "start_x": eps_field.get("start_x"),
            "baseline_y": eps_field.get("baseline_y"),
            "start_x_pt": to_points(eps_field.get("start_x")),
            "baseline_y_pt": to_points(eps_field.get("baseline_y")),
            "glyph_advance": eps_field.get("glyph_advance"),
            "glyph_advance_pt": to_points(eps_field.get("glyph_advance")),
            "glyph_advances": eps_field.get("glyph_advances")
        },
        "eps_font": {
            "source_font": eps_field.get("font"),
            "font_matrix": eps_field.get("font_matrix"),
            "font_size": eps_field.get("font_size"),
            "font_size_pt": to_points(eps_field.get("font_size"))
        },
        "eps_value": eps_field.get("value"),
        "ps_command": eps_field.get("ps_command")
    }

    production_json["fields"].append(merged_field)


output_path.write_text(json.dumps(production_json, indent=2))

print(f"Wrote {output_path}")
print(f"Fields created: {len(production_json['fields'])}")