import json
import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path


if len(sys.argv) != 3:
    print("Usage: python scripts/svg_to_json.py <input_svg> <output_json>")
    sys.exit(1)

svg_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])


def parse_inches(value):
    if not value:
        return None
    match = re.match(r"([\d.]+)in", value)
    return float(match.group(1)) if match else None


def parse_viewbox(value):
    if not value:
        return None
    return [float(x) for x in value.split()]


def as_float(value):
    try:
        return float(value) if value is not None else None
    except ValueError:
        return value


def clean_attrs(elem):
    attrs = {}
    for key, value in elem.attrib.items():
        clean_key = key.split("}")[-1]
        attrs[clean_key] = as_float(value)
    return attrs



def svg_to_inches_x(value):
    return round(value / svg_units_per_inch_x, 6) if value is not None else None


def svg_to_inches_y(value):
    return round(value / svg_units_per_inch_y, 6) if value is not None else None


tree = ET.parse(svg_path)
root = tree.getroot()

spec = {
    "source_svg": svg_path.name,
    "document": {
        "width_raw": root.attrib.get("width"),
        "height_raw": root.attrib.get("height"),
        "width_in": parse_inches(root.attrib.get("width")),
        "height_in": parse_inches(root.attrib.get("height")),
        "viewBox_raw": root.attrib.get("viewBox"),
        "viewBox": parse_viewbox(root.attrib.get("viewBox")),
        "preserveAspectRatio": root.attrib.get("preserveAspectRatio"),
    },
    "groups": [],
    "text_fields": [],
    "rects": [],
    "circles": [],
    "paths": [],
    "images": []
}

viewbox = spec["document"]["viewBox"]
svg_units_per_inch_x = viewbox[2] / spec["document"]["width_in"]
svg_units_per_inch_y = viewbox[3] / spec["document"]["height_in"]

spec["document"]["svg_units_per_inch_x"] = svg_units_per_inch_x
spec["document"]["svg_units_per_inch_y"] = svg_units_per_inch_y

for elem in root.iter():
    tag = elem.tag.split("}")[-1]

    if tag == "g":
        spec["groups"].append(clean_attrs(elem))

    elif tag == "text":
        item = clean_attrs(elem)
        item["value"] = "".join(elem.itertext()).strip()
        spec["text_fields"].append(item)

    elif tag == "rect":
        spec["rects"].append(clean_attrs(elem))

    elif tag == "circle":
        spec["circles"].append(clean_attrs(elem))

    elif tag == "path":
        spec["paths"].append(clean_attrs(elem))

    elif tag == "image":
        item = clean_attrs(elem)

        # Avoid dumping massive base64 into the JSON.
        href = item.get("href")
        if isinstance(href, str) and href.startswith("data:image"):
            item["href_type"] = "embedded_base64_image"
            item["href_preview"] = href[:80] + "..."
            item.pop("href", None)

        spec["images"].append(item)

spec["semantic_fields"] = {}

for rect in spec["rects"]:
    field_id = rect.get("id")

    if field_id == "TEXT_FIELD__ROOM_NUM":
        matching_text = next(
            (t for t in spec["text_fields"] if t.get("id") == "ROOM_NUMBER"),
            None
        )

        spec["semantic_fields"]["room_number"] = {
            "field_id": field_id,
            "value": matching_text.get("value") if matching_text else None,
            "x": rect.get("x"),
            "y": rect.get("y"),
            "width": rect.get("width"),
            "height": rect.get("height"),
            "center_x": rect.get("data-cx"),
            "center_y": rect.get("data-cy"),
            "baseline_y": rect.get("data-baseline-y"),
            "font_family": rect.get("data-font-family"),
            "font_file": rect.get("data-font-file"),
            "font_size": rect.get("data-font-size"),
            "text_align": rect.get("data-text-align"),
            "vertical_align": rect.get("data-vertical-align"),
            "cap_height_ratio": rect.get("data-cap-height-ratio"),
            "ada_max_cap_in": rect.get("data-ada-max-cap-in"),
            "ada_clearance_in": rect.get("data-ada-clearance-in"),
            "x_in": svg_to_inches_x(rect.get("x")),
            "y_in": svg_to_inches_y(rect.get("y")),
            "width_in": svg_to_inches_x(rect.get("width")),
            "height_in": svg_to_inches_y(rect.get("height")),
            "center_x_in": svg_to_inches_x(rect.get("data-cx")),
            "center_y_in": svg_to_inches_y(rect.get("data-cy"))
        }

    elif field_id == "TEXT_FIELD__BRAILLE":
        matching_text = next(
            (t for t in spec["text_fields"] if t.get("id") == "BRAILLE_TEXT"),
            None
        )

        spec["semantic_fields"]["braille"] = {
            "field_id": field_id,
            "value": matching_text.get("value") if matching_text else None,
            "x": rect.get("x"),
            "y": rect.get("y"),
            "width": rect.get("width"),
            "height": rect.get("height"),
            "center_x": rect.get("data-cx"),
            "center_y": rect.get("data-cy"),
            "baseline_y": rect.get("data-baseline-y"),
            "font_family": rect.get("data-font-family"),
            "font_file": rect.get("data-font-file"),
            "font_size": rect.get("data-font-size"),
            "text_align": rect.get("data-text-align"),
            "vertical_align": rect.get("data-vertical-align"),
            "cap_height_ratio": rect.get("data-cap-height-ratio"),
            "cap_height_svg": rect.get("data-cap-height-svg"),
            "glyph_advance_svg": rect.get("data-glyph-advance-svg"),
            "braille_rule": rect.get("data-braille-rule"),
            "field_type": rect.get("data-field-type"),
            "x_in": svg_to_inches_x(rect.get("x")),
            "y_in": svg_to_inches_y(rect.get("y")),
            "width_in": svg_to_inches_x(rect.get("width")),
            "height_in": svg_to_inches_y(rect.get("height")),
            "center_x_in": svg_to_inches_x(rect.get("data-cx")),
            "center_y_in": svg_to_inches_y(rect.get("data-cy"))
        }

output_path.write_text(json.dumps(spec, indent=2))

print(f"Wrote {output_path}")

print("\nExtraction Summary")
print("-" * 50)
print(f"Source SVG: {spec['source_svg']}")
print(f"Document size: {spec['document']['width_in']} in x {spec['document']['height_in']} in")
print(f"Text fields found: {len(spec['text_fields'])}")
print(f"Rects found: {len(spec['rects'])}")
print(f"Circles found: {len(spec['circles'])}")
print(f"Paths found: {len(spec['paths'])}")
print(f"Images found: {len(spec['images'])}")

for name, field in spec["semantic_fields"].items():
    print(f"\n{name}")
    print(f"  value: {field.get('value')}")
    print(f"  position: ({field.get('x_in')}, {field.get('y_in')}) in")
    print(f"  size: {field.get('width_in')} in x {field.get('height_in')} in")
    print(f"  font: {field.get('font_family')}")