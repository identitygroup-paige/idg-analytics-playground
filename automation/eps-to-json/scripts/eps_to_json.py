from pathlib import Path
import json
import re
import sys


if len(sys.argv) != 3:
    print("Usage: python scripts/eps_to_json.py <input_eps> <output_json>")
    sys.exit(1)


eps_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])

lines = eps_path.read_text(encoding="latin-1", errors="ignore").splitlines()

UNITS_PER_INCH = 54
PT_PER_UNIT = 72 / UNITS_PER_INCH


def to_points(value):
    return round(value * PT_PER_UNIT, 4) if value is not None else None


def parse_matrix(matrix_text):
    return [float(v) for v in matrix_text.split()]


def is_production_text(text):
    if not text:
        return False

    # Room numbers like 101, 245, 1024
    if re.fullmatch(r"\d+", text):
        return True

    # Explicit braille placeholder
    if text.upper() == "BRAILLE":
        return True

    return False


def classify_text(text):
    if re.fullmatch(r"\d+", text):
        return "room_number"

    if text.upper() == "BRAILLE":
        return "braille"

    return "unknown"


current_font = None
current_matrix = None
current_x = None
current_y = None
pending_text = None

raw_commands = []
production_commands = []

for line in lines:
    line = line.strip()

    # Capture font matrix, e.g.
    # /VKKPTQ+GalaxiePolaris-Medium*1 [69.7503 0 0 -69.7503 0 0 ]msf
    m = re.search(
        r"/?(?P<font>[A-Za-z0-9+_.\-*]+)\s+\[(?P<matrix>[^\]]+)\]\s*msf",
        line,
    )
    if m:
        current_font = m.group("font")
        current_matrix = parse_matrix(m.group("matrix"))
        continue

    # Capture move-to, e.g.
    # 88.415 215.527 mo
    m = re.search(
        r"(?P<x>-?\d+(?:\.\d+)?)\s+(?P<y>-?\d+(?:\.\d+)?)\s+mo",
        line,
    )
    if m:
        current_x = float(m.group("x"))
        current_y = float(m.group("y"))
        continue

    # Capture text in parentheses.
    m = re.search(r"\((?P<text>.*?)\)", line)
    if m:
        pending_text = m.group("text")

        # Case: text and sh are on the same line, e.g. (BRAILLE)sh
        if "sh" in line and "xsh" not in line:
            command = {
                "text": pending_text,
                "text_kind": classify_text(pending_text),
                "render_command": "sh",
                "font": current_font,
                "font_matrix": current_matrix,
                "font_size": abs(current_matrix[0]) if current_matrix else None,
                "start_x": current_x,
                "baseline_y": current_y,
                "ps_command": f"{current_x} {current_y} mo ({pending_text})sh",
            }

            raw_commands.append(command)

            if is_production_text(pending_text):
                production_commands.append(command)

            pending_text = None

        continue

    # Case: xshow/tracking command after pending text, e.g.
    # (245)
    # [36.478 36.4785 0 ]xsh
    m = re.search(r"\[(?P<advances>[^\]]+)\]\s*xsh", line)
    if m and pending_text:
        advances = [float(v) for v in m.group("advances").split()]

        command = {
            "text": pending_text,
            "text_kind": classify_text(pending_text),
            "render_command": "xsh",
            "font": current_font,
            "font_matrix": current_matrix,
            "font_size": abs(current_matrix[0]) if current_matrix else None,
            "start_x": current_x,
            "baseline_y": current_y,
            "glyph_advances": advances,
            "glyph_advance": advances[0] if advances else None,
            "ps_command": (
                f"{current_x} {current_y} mo "
                f"({pending_text}) [{m.group('advances')}] xsh"
            ),
        }

        raw_commands.append(command)

        if is_production_text(pending_text):
            production_commands.append(command)

        pending_text = None


eps_source = {}

for command in production_commands:
    if command["text_kind"] == "room_number":
        eps_source["room_number"] = {
            "ps_command": command["ps_command"],
            "start_x": command["start_x"],
            "baseline_y": command["baseline_y"],
            "font": command["font"],
            "font_matrix": command["font_matrix"],
            "font_size": command["font_size"],
            "glyph_advances": command.get("glyph_advances"),
            "glyph_advance": command.get("glyph_advance"),
            "value": command["text"],
            "start_x_pt": to_points(command["start_x"]),
            "baseline_y_pt": to_points(command["baseline_y"]),
            "font_size_pt": to_points(command["font_size"]),
            "glyph_advance_pt": to_points(command.get("glyph_advance")),
        }

    elif command["text_kind"] == "braille":
        eps_source["braille"] = {
            "ps_command": command["ps_command"],
            "start_x": command["start_x"],
            "baseline_y": command["baseline_y"],
            "font": command["font"],
            "font_matrix": command["font_matrix"],
            "font_size": command["font_size"],
            "value": command["text"],
            "start_x_pt": to_points(command["start_x"]),
            "baseline_y_pt": to_points(command["baseline_y"]),
            "font_size_pt": to_points(command["font_size"]),
        }


result = {
    "source_eps": eps_path.name,
    "eps_source": eps_source,
    "production_text_commands": production_commands,
    "raw_text_command_count": len(raw_commands),
    "production_text_command_count": len(production_commands),
}

output_path.write_text(json.dumps(result, indent=2))

print(f"Wrote {output_path}")
print(f"Raw text commands found: {len(raw_commands)}")
print(f"Production text commands found: {len(production_commands)}")

for command in production_commands:
    print(
        f"- {command['text_kind']}: {command['text']} "
        f"at ({command['start_x']}, {command['baseline_y']})"
    )