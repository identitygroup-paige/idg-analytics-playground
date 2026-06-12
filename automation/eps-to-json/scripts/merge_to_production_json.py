import json
import sys
from pathlib import Path


if len(sys.argv) != 3:
    print("Usage: python scripts/merge_to_production_json.py <eps_json> <output_json>")
    sys.exit(1)


eps_json_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

eps_data = json.loads(eps_json_path.read_text())
eps_source = eps_data["eps_source"]

UNITS_PER_INCH = 54
PT_PER_UNIT = 72 / UNITS_PER_INCH


def to_points(value):
    return round(value * PT_PER_UNIT, 4) if value is not None else None


production_json = {
    "sign_id": "88668",
    "sign_type": "RMN",
    "description": "ALOFT 2019 ROOM NUMBER",

    "svg_viewBox": "49.0 0.0 274.0 395.0",
    "units_per_inch": UNITS_PER_INCH,

    "physical_size": {
        "width_in": 5.07,
        "height_in": 7.31
    },

    "page_size": {
        "width_in": 5.5,
        "height_in": 7.75
    },

    "eps_source": eps_source,

    "fields": [],

    "unit_conversion": {
        "rule": "All EPS-source numeric values are in EPS userspace units, not points.",
        "formula": "pt_value = eps_value × (72 / units_per_inch)",
        "for_this_brand": {
            "units_per_inch": UNITS_PER_INCH,
            "pt_per_unit": PT_PER_UNIT
        }
    }
}


if "room_number" in eps_source:
    room = eps_source["room_number"]

    production_json["fields"].append({
        "id": "ROOM_NUMBER",
        "type": "room-number",
        "source": "eps",
        "value": room.get("value"),
        "font": {
            "source_font": room.get("font"),
            "font_matrix": room.get("font_matrix"),
            "font_size": room.get("font_size"),
            "font_size_pt": to_points(room.get("font_size")),
        },
        "eps_position": {
            "start_x": room.get("start_x"),
            "baseline_y": room.get("baseline_y"),
            "start_x_pt": to_points(room.get("start_x")),
            "baseline_y_pt": to_points(room.get("baseline_y")),
            "glyph_advance": room.get("glyph_advance"),
            "glyph_advance_pt": to_points(room.get("glyph_advance")),
            "glyph_advances": room.get("glyph_advances"),
        },
        "ps_command": room.get("ps_command")
    })


if "braille" in eps_source:
    braille = eps_source["braille"]

    production_json["fields"].append({
        "id": "BRAILLE_TEXT",
        "type": "braille-label",
        "source": "eps",
        "value": braille.get("value"),
        "font": {
            "source_font": braille.get("font"),
            "font_matrix": braille.get("font_matrix"),
            "font_size": braille.get("font_size"),
            "font_size_pt": to_points(braille.get("font_size")),
        },
        "eps_position": {
            "start_x": braille.get("start_x"),
            "baseline_y": braille.get("baseline_y"),
            "start_x_pt": to_points(braille.get("start_x")),
            "baseline_y_pt": to_points(braille.get("baseline_y")),
        },
        "ps_command": braille.get("ps_command")
    })


output_path.write_text(json.dumps(production_json, indent=2))

print(f"Wrote {output_path}")
print(f"Fields created: {len(production_json['fields'])}")