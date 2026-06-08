import json
from pathlib import Path
from pprint import pprint

file_a = Path("output/88668-vector-specs.json")
file_b = Path("output/88668-preview-vector-specs.json")

a = json.loads(file_a.read_text())
b = json.loads(file_b.read_text())

rects_a = {r.get("id"): r for r in a.get("rects", [])}
rects_b = {r.get("id"): r for r in b.get("rects", [])}
IGNORE_KEYS = {"style", "fill-opacity", "fill", "stroke", "opacity"}

has_differences = False

for rect_id in sorted(set(rects_a) | set(rects_b)):
    ra = rects_a.get(rect_id, {})
    rb = rects_b.get(rect_id, {})

    rect_has_diff = False

    for key in sorted((set(ra) | set(rb)) - IGNORE_KEYS):
        if ra.get(key) != rb.get(key):
            if not rect_has_diff:
                print(f"\n{rect_id}")
                print("-" * 50)
                rect_has_diff = True
                has_differences = True

            print(f"{key}:")
            print(f"  vector:  {ra.get(key)}")
            print(f"  preview: {rb.get(key)}")

if not has_differences:
    print("Specs match after ignoring cosmetic SVG fields.")