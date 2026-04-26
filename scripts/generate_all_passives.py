from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generate_from_rules import build


def safe_name(value: str) -> str:
    value = re.sub(r"[^\w\- ]+", "", value, flags=re.UNICODE).strip()
    value = re.sub(r"\s+", "_", value)
    return value or "passive"


def normalize_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value).lower()


def generate_all(
    manifest_path: Path,
    shapes_dir: Path,
    rules_path: Path,
    output_dir: Path,
    icon_overrides_path: Path | None = None,
) -> tuple[list[Path], list[str]]:
    generated: list[Path] = []
    errors: list[str] = []
    icon_overrides = {}
    if icon_overrides_path and icon_overrides_path.exists():
        icon_overrides = json.loads(icon_overrides_path.read_text(encoding="utf-8"))

    with manifest_path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            main_svg_id = row["main_svg_id"]
            main_svg = shapes_dir / f"{main_svg_id}.svg"
            if not main_svg.exists():
                errors.append(f"{row['passive_id']}: missing {main_svg}")
                continue

            class_name = row["tool_class"]
            display_name = safe_name(row["display_name"] or row["passive_id"])
            output = output_dir / class_name / f"{display_name}_{row['passive_id']}.svg"
            passive_key = f"{class_name}-{normalize_key(display_name + row['passive_id'])}"
            main_picture = icon_overrides.get(passive_key, {}).get("mainPicture")
            layer_overrides = {"main_picture": main_picture} if main_picture else None

            try:
                build(rules_path, main_svg, class_name, output, layer_overrides)
            except Exception as exc:
                errors.append(f"{row['passive_id']}: {exc}")
                continue

            generated.append(output)

    return generated, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate all passive icons from passive_manifest.csv.")
    parser.add_argument("--manifest", type=Path, default=Path("output") / "passive_manifest.csv")
    parser.add_argument("--shapes-dir", type=Path, default=Path("Ability Passive Svg") / "shapes")
    parser.add_argument("--rules", type=Path, default=Path("rules") / "butcher_manual.json")
    parser.add_argument("--output-dir", type=Path, default=Path("output") / "all_passives")
    parser.add_argument("--icon-overrides", type=Path)
    args = parser.parse_args()

    generated, errors = generate_all(
        args.manifest.resolve(),
        args.shapes_dir.resolve(),
        args.rules.resolve(),
        args.output_dir.resolve(),
        args.icon_overrides.resolve() if args.icon_overrides else None,
    )

    print(f"generated={len(generated)} errors={len(errors)}")
    print(f"output={args.output_dir.resolve()}")
    if errors:
        print("errors:")
        for error in errors[:30]:
            print(error)


if __name__ == "__main__":
    main()
