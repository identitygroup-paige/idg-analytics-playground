import subprocess
from pathlib import Path

INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
SCRIPTS_DIR = Path("scripts")

OUTPUT_DIR.mkdir(exist_ok=True)

def run(command):
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True
    )

def convert_eps_to_svg(eps_file):
    svg_file = OUTPUT_DIR / f"{eps_file.stem}.svg"

    print(f"Converting EPS to SVG: {eps_file.name}")

    # EPS -> PDF
    pdf_file = OUTPUT_DIR / f"{eps_file.stem}.pdf"

    run([
        "gs",
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-dEPSCrop",
        "-sDEVICE=pdfwrite",
        f"-sOutputFile={pdf_file}",
        str(eps_file)
    ])

    # PDF -> SVG
    run([
        "inkscape",
        str(pdf_file),
        "--export-type=svg",
        f"--export-filename={svg_file}"
    ])

    return svg_file

def svg_to_json(svg_file):
    json_file = OUTPUT_DIR / f"{svg_file.stem}-specs.json"

    print(f"Extracting specs: {svg_file.name}")

    run([
        "python",
        str(SCRIPTS_DIR / "svg_to_json.py"),
        str(svg_file),
        str(json_file)
    ])

    run([
        "python",
        str(SCRIPTS_DIR / "validate_specs.py"),
        str(json_file)
    ])

    return json_file

def main():
    svg_files = list(INPUT_DIR.glob("*.svg"))
    eps_files = list(INPUT_DIR.glob("*.eps"))

    generated_jsons = []

    for svg_file in svg_files:
        generated_jsons.append(svg_to_json(svg_file))

    failed_files = []

    for eps_file in eps_files:
        try:
            converted_svg = convert_eps_to_svg(eps_file)
            generated_jsons.append(svg_to_json(converted_svg))
        except subprocess.CalledProcessError as e:
            failed_files.append(eps_file.name)
            print(f"Failed to extract reliable specs from EPS: {eps_file.name}")
            print("Reason: EPS conversion did not preserve required SVG metadata.")

    print("\nDone.")
    print("-" * 50)

    if not generated_jsons:
        print("No .svg or .eps files found in input/")
    else:
        for json_file in generated_jsons:
            print(f"Created: {json_file}")
    if failed_files:
        print("\nFiles needing review:")
        for file_name in failed_files:
            print(f"- {file_name}")

if __name__ == "__main__":
    main()

