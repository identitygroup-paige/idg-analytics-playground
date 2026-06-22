import subprocess
from pathlib import Path

sku = "88668"

eps_file = Path(f"input/{sku}-source.eps")
eps_json = Path(f"output/{sku}-eps-source.json")
field_params = Path(f"config/{sku}_field_parameters.json")
production_json = Path(f"output/{sku}-production-draft.json")

commands = [
    [
        "python",
        "scripts/eps_to_json.py",
        str(eps_file),
        str(eps_json),
    ],
    [
        "python",
        "scripts/merge_to_production_json.py",
        str(eps_json),
        str(field_params),
        str(production_json),
    ],
    [
        "python",
        "scripts/validate_production_json.py",
        str(production_json),
    ],
]

for command in commands:
    print("\nRunning:", " ".join(command))
    subprocess.run(command, check=True)

print("\nPipeline complete.")
print(f"Created: {production_json}")