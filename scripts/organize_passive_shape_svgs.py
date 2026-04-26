from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generate_all_passives import safe_name


def organize(
    manifest_path: Path,
    shapes_dir: Path,
    output_dir: Path,
) -> tuple[list[Path], list[str]]:
    copied: list[Path] = []
    errors: list[str] = []

    with manifest_path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            main_svg_id = row["main_svg_id"]
            source = shapes_dir / f"{main_svg_id}.svg"
            if not source.exists():
                errors.append(f"{row['passive_id']}: missing {source}")
                continue

            class_name = safe_name(row["tool_class"].lower())
            display_name = safe_name(row["display_name"] or row["passive_id"])
            passive_id = safe_name(row["passive_id"])
            target = output_dir / class_name / f"{display_name}__{passive_id}__{main_svg_id}.svg"

            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(target)

    return copied, errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy passive main SVGs into class folders with game names.")
    parser.add_argument("--manifest", type=Path, default=Path("output") / "passive_manifest.csv")
    parser.add_argument("--shapes-dir", type=Path, default=Path("Ability Passive Svg") / "shapes")
    parser.add_argument("--output-dir", type=Path, default=Path("Ability Passive Svg") / "passives_by_class")
    args = parser.parse_args()

    copied, errors = organize(args.manifest.resolve(), args.shapes_dir.resolve(), args.output_dir.resolve())
    print(f"copied={len(copied)} errors={len(errors)}")
    print(f"output={args.output_dir.resolve()}")
    if errors:
        print("errors:")
        for error in errors[:30]:
            print(error)


if __name__ == "__main__":
    main()
