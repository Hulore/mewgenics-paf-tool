from __future__ import annotations

import argparse
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

Matrix = tuple[float, float, float, float, float, float]
IDENTITY: Matrix = (1, 0, 0, 1, 0, 0)


@dataclass
class DisplayObject:
    character_id: int
    depth: int
    matrix: Matrix = IDENTITY
    name: str | None = None


@dataclass
class SpriteDef:
    sprite_id: int
    frames: list[list[DisplayObject]] = field(default_factory=list)


@dataclass
class Library:
    sprites: dict[int, SpriteDef] = field(default_factory=dict)
    shapes: set[int] = field(default_factory=set)


@dataclass(frozen=True)
class SvgAsset:
    path: Path
    recolor: dict[str, str] | None = None


@dataclass(frozen=True)
class CompositeAsset:
    parts: tuple[SvgAsset, ...]


Asset = SvgAsset | CompositeAsset


def multiply(left: Matrix, right: Matrix) -> Matrix:
    la, lb, lc, ld, le, lf = left
    ra, rb, rc, rd, re, rf = right
    return (
        la * ra + lc * rb,
        lb * ra + ld * rb,
        la * rc + lc * rd,
        lb * rc + ld * rd,
        la * re + lc * rf + le,
        lb * re + ld * rf + lf,
    )


def matrix_to_svg(matrix: Matrix) -> str:
    a, b, c, d, e, f = matrix
    return f"matrix({a:.8g} {b:.8g} {c:.8g} {d:.8g} {e:.8g} {f:.8g})"


def parse_bool(value: str | None) -> bool:
    return value == "true"


def parse_matrix(place: ET.Element) -> Matrix:
    matrix = place.find("matrix")
    if matrix is None:
        return IDENTITY

    # FFDec writes 0.0 into scale fields even when hasScale=false. In SWF that
    # means an identity scale, not a collapsed object.
    has_scale = parse_bool(matrix.get("hasScale"))
    has_rotate = parse_bool(matrix.get("hasRotate"))
    scale_x = float(matrix.get("scaleX") or 1) if has_scale else 1
    scale_y = float(matrix.get("scaleY") or 1) if has_scale else 1
    skew_0 = float(matrix.get("rotateSkew0") or 0) if has_rotate else 0
    skew_1 = float(matrix.get("rotateSkew1") or 0) if has_rotate else 0
    translate_x = float(matrix.get("translateX") or 0) / 20
    translate_y = float(matrix.get("translateY") or 0) / 20

    # SVG matrix is [a c e; b d f], while FFDec stores scaleX, rotateSkew0,
    # rotateSkew1, scaleY.
    return (scale_x, skew_1, skew_0, scale_y, translate_x, translate_y)


def parse_display_object(place: ET.Element, previous: DisplayObject | None) -> DisplayObject | None:
    character_id = place.get("characterId")
    has_character = parse_bool(place.get("placeFlagHasCharacter"))

    if not character_id and previous is None:
        return None

    matrix = parse_matrix(place) if parse_bool(place.get("placeFlagHasMatrix")) else None
    return DisplayObject(
        character_id=int(character_id) if has_character and character_id else previous.character_id,
        depth=int(place.get("depth") or previous.depth),
        matrix=matrix if matrix is not None else (previous.matrix if previous else IDENTITY),
        name=place.get("name") or (previous.name if previous else None),
    )


def parse_sprite(sprite_node: ET.Element) -> SpriteDef:
    sprite_id = int(sprite_node.get("spriteId") or 0)
    display_list: dict[int, DisplayObject] = {}
    frames: list[list[DisplayObject]] = []

    sub_tags = sprite_node.find("subTags")
    if sub_tags is None:
        return SpriteDef(sprite_id=sprite_id)

    for item in sub_tags.findall("item"):
        item_type = item.get("type")
        if item_type == "PlaceObject2Tag":
            depth = int(item.get("depth") or 0)
            display_object = parse_display_object(item, display_list.get(depth))
            if display_object is not None:
                display_list[depth] = display_object
        elif item_type == "RemoveObject2Tag":
            depth = int(item.get("depth") or 0)
            display_list.pop(depth, None)
        elif item_type == "ShowFrameTag":
            frames.append([display_list[depth] for depth in sorted(display_list)])

    return SpriteDef(sprite_id=sprite_id, frames=frames)


def load_library(code_dir: Path) -> Library:
    library = Library()
    for frames_xml in code_dir.rglob("frames.xml"):
        root = ET.parse(frames_xml).getroot()
        tags = root.find("tags")
        if tags is None:
            continue
        for item in tags.findall("item"):
            item_type = item.get("type") or ""
            if item_type == "DefineSpriteTag":
                sprite = parse_sprite(item)
                library.sprites[sprite.sprite_id] = sprite
            elif item_type.startswith("DefineShape"):
                shape_id = item.get("shapeId")
                if shape_id:
                    library.shapes.add(int(shape_id))
    return library


def read_svg_children(asset: SvgAsset) -> list[ET.Element]:
    root = ET.parse(asset.path).getroot()
    if asset.recolor:
        for node in root.iter():
            for attr in ("fill", "stroke"):
                value = node.attrib.get(attr)
                if value in asset.recolor:
                    node.set(attr, asset.recolor[value])
    return [deepcopy(child) for child in list(root)]


def pick_asset(*candidates: Path, recolor: dict[str, str] | None = None) -> SvgAsset:
    for candidate in candidates:
        if candidate.exists():
            return SvgAsset(candidate, recolor)
    return SvgAsset(candidates[0], recolor)


def default_assets(test_svg_dir: Path, asset_root: Path) -> dict[int, Asset]:
    return {
        # The test export names do not all match the SWF character IDs, so this
        # table is intentionally explicit and easy to correct as we identify
        # more symbols.
        2756: pick_asset(asset_root / "2756" / "shapes" / "2756.svg"),
        2775: pick_asset(asset_root / "2775" / "shapes" / "2775.svg"),
        2841: pick_asset(
            test_svg_dir / "2841(whitepartframe)" / "shapes" / "2841.svg",
            asset_root / "2841" / "shapes" / "2841.svg",
        ),
        2842: CompositeAsset(
            (
                SvgAsset(test_svg_dir / "1WhiteBackground.svg"),
                SvgAsset(test_svg_dir / "196(mainpicture).svg"),
            )
        ),
        2844: pick_asset(
            test_svg_dir / "2844(blackpartframe)" / "shapes" / "2844.svg",
            asset_root / "2844" / "shapes" / "2844.svg",
            recolor={"#111111": "#b64055"},
        ),
        2845: pick_asset(
            test_svg_dir / "2845(blacksideframe)" / "shapes" / "2845.svg",
            asset_root / "2845" / "shapes" / "2845.svg",
            recolor={"#111111": "#b64055"},
        ),
        2847: pick_asset(
            asset_root / "2847(disorder)" / "shapes" / "2847.svg",
            asset_root / "2847" / "shapes" / "2847.svg",
            recolor={"#111111": "#b64055"},
        ),
    }


def render_character(
    parent: ET.Element,
    library: Library,
    assets: dict[int, Asset],
    character_id: int,
    matrix: Matrix,
    frame_index: int,
    path: str,
    hidden_names: set[str],
) -> None:
    group = ET.SubElement(
        parent,
        f"{{{SVG_NS}}}g",
        {
            "id": path,
            "data-character-id": str(character_id),
            "transform": matrix_to_svg(matrix),
        },
    )

    asset = assets.get(character_id)
    if asset is not None:
        parts = asset.parts if isinstance(asset, CompositeAsset) else (asset,)
        for part in parts:
            for child in read_svg_children(part):
                group.append(child)
        return

    sprite = library.sprites.get(character_id)
    if sprite is None:
        group.set("data-missing-character", str(character_id))
        return

    render_sprite(group, library, assets, sprite.sprite_id, IDENTITY, frame_index, hidden_names)


def render_sprite(
    parent: ET.Element,
    library: Library,
    assets: dict[int, Asset],
    sprite_id: int,
    matrix: Matrix = IDENTITY,
    frame_index: int = 0,
    hidden_names: set[str] | None = None,
) -> None:
    hidden_names = hidden_names or set()
    sprite = library.sprites[sprite_id]
    if not sprite.frames:
        return

    frame = sprite.frames[min(frame_index, len(sprite.frames) - 1)]
    for display_object in frame:
        if display_object.name in hidden_names:
            continue
        child_matrix = multiply(matrix, display_object.matrix)
        label = display_object.name or f"depth_{display_object.depth}"
        render_character(
            parent,
            library,
            assets,
            display_object.character_id,
            child_matrix,
            frame_index=0,
            path=f"sprite_{sprite_id}_{label}_{display_object.character_id}",
            hidden_names=hidden_names,
        )


def build(
    code_dir: Path,
    test_svg_dir: Path,
    asset_root: Path,
    output: Path,
    symbol_id: int,
    hidden_names: set[str],
) -> None:
    library = load_library(code_dir)
    if symbol_id not in library.sprites:
        raise KeyError(f"Sprite {symbol_id} was not found in {code_dir}")

    assets = default_assets(test_svg_dir, asset_root)
    asset_parts = [
        part
        for asset in assets.values()
        for part in (asset.parts if isinstance(asset, CompositeAsset) else (asset,))
    ]
    missing = [asset.path for asset in asset_parts if not asset.path.exists()]
    if missing:
        raise FileNotFoundError("Missing SVG source(s): " + ", ".join(str(path) for path in missing))

    root = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": "147",
            "height": "92",
            "viewBox": "-14 -22 130 92",
            "version": "1.1",
        },
    )
    title = ET.SubElement(root, f"{{{SVG_NS}}}title")
    title.text = "Mewgenics butcher passive prototype"
    render_sprite(root, library, assets, symbol_id, hidden_names=hidden_names)

    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)


def build_viewer(output_svg: Path, reference_png: Path, viewer_path: Path) -> None:
    viewer_dir = viewer_path.resolve().parent
    relative_svg = Path(os.path.relpath(output_svg.resolve(), viewer_dir))
    relative_ref = Path(os.path.relpath(reference_png.resolve(), viewer_dir))
    viewer_path.parent.mkdir(parents=True, exist_ok=True)
    viewer_path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mewgenics PAF prototype comparison</title>
  <style>
    body {{
      margin: 24px;
      background: #202020;
      color: #f0f0f0;
      font-family: Arial, sans-serif;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 24px;
      align-items: start;
      max-width: 760px;
    }}
    figure {{
      margin: 0;
      padding: 16px;
      background: #2a2a2a;
      border: 1px solid #3c3c3c;
    }}
    figcaption {{
      margin-bottom: 12px;
      font-size: 14px;
      color: #d0d0d0;
    }}
    img {{
      width: 294px;
      height: 184px;
      object-fit: contain;
      image-rendering: auto;
      background: transparent;
    }}
  </style>
</head>
<body>
  <div class="grid">
    <figure>
      <figcaption>Prototype</figcaption>
      <img src="{relative_svg.as_posix()}" alt="Generated butcher passive icon">
    </figure>
    <figure>
      <figcaption>Reference</figcaption>
      <img src="{relative_ref.as_posix()}" alt="Reference butcher passive icon">
    </figure>
  </div>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a prototype butcher passive icon SVG.")
    parser.add_argument(
        "--code-dir",
        type=Path,
        default=Path(r"..\Gamefiles\CodeForRules"),
        help="Path to the FFDec XML export directory.",
    )
    parser.add_argument(
        "--test-svg-dir",
        type=Path,
        default=Path(r"..\Gamefiles\testPassiveOrigSVG"),
        help="Path to the exported butcher test SVG directory.",
    )
    parser.add_argument(
        "--asset-root",
        type=Path,
        default=Path(r"..\OtherGameFiles\UnpackedImportant"),
        help="Path to additional FFDec SVG shape exports.",
    )
    parser.add_argument(
        "--symbol-id",
        type=int,
        default=2848,
        help="Sprite ID to render. 2848 is the passive icon shell used by Passive_154.",
    )
    parser.add_argument(
        "--hide-name",
        action="append",
        default=["up0", "up1"],
        help="Named display object to skip while rendering. Can be passed multiple times.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output") / "butcher_prototype.svg",
        help="Output SVG path.",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path(r"..\reference\Butcher Passive gameframe-Photoroom.png"),
        help="Reference PNG path used by the optional comparison viewer.",
    )
    parser.add_argument(
        "--viewer",
        type=Path,
        default=Path("output") / "butcher_compare.html",
        help="Output HTML comparison viewer path.",
    )
    args = parser.parse_args()

    build(
        args.code_dir.resolve(),
        args.test_svg_dir.resolve(),
        args.asset_root.resolve(),
        args.output.resolve(),
        args.symbol_id,
        set(args.hide_name or []),
    )
    if args.reference.exists():
        build_viewer(args.output.resolve(), args.reference.resolve(), args.viewer.resolve())
    print(args.output.resolve())


if __name__ == "__main__":
    main()
