import xml.etree.ElementTree as ET
from collections import Counter
svg_path = "output/source-vector.svg"

tree = ET.parse(svg_path)
root = tree.getroot()

print("SVG ROOT ATTRIBUTES")
print("-" * 50)
for k, v in root.attrib.items():
    print(f"{k}: {v}")

tag_counts = Counter()

for elem in root.iter():
    tag = elem.tag.split("}")[-1]
    tag_counts[tag] += 1

print("\nELEMENT COUNTS")
print("-" * 50)
for tag, count in tag_counts.most_common():
    print(f"{tag}: {count}")

print("\nTEXT ELEMENTS")
print("-" * 50)

found_text = False

for elem in root.iter():
    tag = elem.tag.split("}")[-1]

    if tag in ["text", "tspan"]:
        text = "".join(elem.itertext()).strip()
        if text:
            found_text = True
            print({
                "tag": tag,
                "id": elem.attrib.get("id"),
                "text": text,
                "x": elem.attrib.get("x"),
                "y": elem.attrib.get("y"),
                "transform": elem.attrib.get("transform"),
                "style": elem.attrib.get("style"),
            })

if not found_text:
    print("No readable text elements found. Text may have been converted to paths.")