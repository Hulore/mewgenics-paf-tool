from __future__ import annotations

import argparse
import csv
import re
import struct
import zlib
from collections import Counter
from pathlib import Path


SKIP_PASSIVE_FILES = {
    "colorless_passives.gon",
    "jester_passives.gon",
    "disorders.gon",
    "util_passives.gon",
}


def swf_rect_length(data: bytes, offset: int) -> int:
    nbits = data[offset] >> 3
    return (5 + 4 * nbits + 7) // 8


def swf_tags(data: bytes, offset: int, end: int | None = None):
    end = len(data) if end is None else end
    while offset < end:
        header = struct.unpack_from("<H", data, offset)[0]
        offset += 2
        tag_code = header >> 6
        length = header & 0x3F
        if length == 0x3F:
            length = struct.unpack_from("<I", data, offset)[0]
            offset += 4

        payload = data[offset : offset + length]
        offset += length
        yield tag_code, payload

        if tag_code == 0:
            break


def read_swf(path: Path) -> bytes:
    data = path.read_bytes()
    if data[:3] == b"CWS":
        return data[:8] + zlib.decompress(data[8:])
    if data[:3] == b"ZWS":
        raise ValueError("ZWS-compressed SWF is not supported by this extractor.")
    return data


def extract_sprite_payload(swf_data: bytes, sprite_id: int) -> bytes:
    tags_offset = 8 + swf_rect_length(swf_data, 8) + 4
    for tag_code, payload in swf_tags(swf_data, tags_offset):
        if tag_code != 39:
            continue
        current_id = struct.unpack_from("<H", payload, 0)[0]
        if current_id == sprite_id:
            return payload[4:]
    raise KeyError(f"DefineSprite {sprite_id} was not found.")


def extract_passive_icon_map(ability_icons_swf: Path, sprite_id: int = 515) -> dict[str, dict[str, int]]:
    swf_data = read_swf(ability_icons_swf)
    sprite_payload = extract_sprite_payload(swf_data, sprite_id)

    frame = 1
    labels: dict[int, str] = {}
    display: dict[int, int] = {}
    frame_main_shape: dict[int, int | None] = {}

    def current_main_shape() -> int | None:
        # Passive main art is placed in this range; different frames use different depths.
        for depth in (8, 7, 6, 5, 4, 3):
            if depth in display:
                return display[depth]
        return None

    for tag_code, payload in swf_tags(sprite_payload, 0, len(sprite_payload)):
        if tag_code == 1:  # ShowFrame
            frame_main_shape[frame] = current_main_shape()
            frame += 1
        elif tag_code == 43:  # FrameLabel
            labels[frame] = payload.split(b"\0", 1)[0].decode("utf-8", "replace")
        elif tag_code == 28 and len(payload) >= 2:  # RemoveObject2
            display.pop(struct.unpack_from("<H", payload, 0)[0], None)
        elif tag_code == 5 and len(payload) >= 4:  # RemoveObject
            display.pop(struct.unpack_from("<H", payload, 2)[0], None)
        elif tag_code in (26, 70):  # PlaceObject2 / PlaceObject3
            flags = payload[0]
            offset = 1 if tag_code == 26 else 2
            if len(payload) < offset + 2:
                continue
            depth = struct.unpack_from("<H", payload, offset)[0]
            offset += 2
            if flags & 0x02 and offset + 2 <= len(payload):
                display[depth] = struct.unpack_from("<H", payload, offset)[0]

    return {
        label: {
            "icon_frame": frame,
            "main_svg_id": frame_main_shape[frame],
        }
        for frame, label in labels.items()
        if label != "unknown"
    }


def read_english_names(passives_csv: Path) -> dict[str, str]:
    names: dict[str, str] = {}
    with passives_csv.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.reader(file):
            if len(row) >= 2:
                names[row[0]] = row[1]
    return names


def iter_passive_defs(passives_dir: Path):
    for path in sorted(passives_dir.glob("*_passives.gon")):
        if path.name in SKIP_PASSIVE_FILES:
            continue

        text = path.read_text(encoding="utf-8")
        starts = list(re.finditer(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)\s*\{.*$", text))
        for index, match in enumerate(starts):
            passive_id = match.group(1)
            line_end = text.find("\n", match.start())
            header_line = text[match.start() : line_end if line_end != -1 else len(text)]
            block_end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
            block = text[match.end() : block_end]

            name_match = re.search(r'(?m)^\s*name\s+"([^"]+)"', block)
            class_match = re.search(r"(?m)^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)", block)
            if not name_match or not class_match:
                continue

            yield {
                "passive_id": passive_id,
                "text_key": name_match.group(1),
                "source_class": class_match.group(1),
                "source_file": path.name,
                "cut": "CUT" in header_line,
            }


def build_manifest(project_root: Path, output: Path) -> tuple[int, int, int, Counter]:
    icon_map = extract_passive_icon_map(project_root / "Gamefiles" / "SWF" / "ability_icons.swf")
    names = read_english_names(project_root / "gpak-all" / "data" / "text" / "passives.csv")

    rows = []
    missing = 0
    cut = 0
    for passive in iter_passive_defs(project_root / "gpak-all" / "data" / "passives"):
        if passive["cut"]:
            cut += 1
            continue

        icon = icon_map.get(passive["passive_id"])
        main_svg_id = icon["main_svg_id"] if icon else None
        if main_svg_id is None:
            missing += 1

        source_class = passive["source_class"]
        tool_class = "cleric" if source_class.lower() == "medic" else source_class.lower()
        rows.append(
            {
                "passive_id": passive["passive_id"],
                "display_name": names.get(passive["text_key"], ""),
                "text_key": passive["text_key"],
                "source_class": source_class,
                "tool_class": tool_class,
                "icon_frame": icon["icon_frame"] if icon else "",
                "main_svg_id": main_svg_id or "",
                "main_svg_filename": f"{main_svg_id}(mainpicture).svg" if main_svg_id else "",
                "source_file": passive["source_file"],
            }
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    return len(rows), missing, cut, Counter(row["source_class"] for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract passive -> class -> main SVG id manifest.")
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output", type=Path, default=Path("output") / "passive_manifest.csv")
    args = parser.parse_args()

    rows, missing, cut, by_class = build_manifest(args.project_root.resolve(), args.output.resolve())
    print(f"rows={rows} missing={missing} cut={cut}")
    print(f"output={args.output.resolve()}")
    print("by_class=" + ", ".join(f"{key}:{value}" for key, value in sorted(by_class.items())))


if __name__ == "__main__":
    main()
