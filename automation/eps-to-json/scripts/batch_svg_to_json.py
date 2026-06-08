import subprocess
from pathlib import Path

input_dir = Path("input")
output_dir = Path("output")

for svg_file in input_dir.glob("*.svg"):
    output_file = output_dir / f"{svg_file.stem}-specs.json"

    print(f"\nProcessing {svg_file} → {output_file}")

    subprocess.run(
        [
            "python",
            "scripts/svg_to_json.py",
            str(svg_file),
            str(output_file),
        ],
        check=True,
    )