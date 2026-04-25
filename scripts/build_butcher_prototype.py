from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


@dataclass(frozen=True)
class Layer:
    name: str
    source: Path
    matrix: tuple[float, float, float, float, float, float]
    recolor: dict[str, str] | None = None


def svg_children(path: Path, recolor: dict[str, str] | None = None) -> list[ET.Element]:
    tree = ET.parse(path)
    root = tree.getroot()
    if recolor:
        for node in root.iter():
            for attr in ("fill", "stroke"):
                value = node.attrib.get(attr)
                if value in recolor:
                    node.set(attr, recolor[value])
    return list(root)


def matrix_to_svg(matrix: tuple[float, float, float, float, float, float]) -> str:
    a, b, c, d, e, f = matrix
    return f"matrix({a:.8g} {b:.8g} {c:.8g} {d:.8g} {e:.8g} {f:.8g})"


def append_layer(parent: ET.Element, layer: Layer) -> None:
    group = ET.SubElement(
        parent,
        f"{{{SVG_NS}}}g",
        {
            "id": layer.name,
            "transform": matrix_to_svg(layer.matrix),
        },
    )
    for child in svg_children(layer.source, layer.recolor):
        group.append(child)


def build(test_svg_dir: Path, output: Path) -> None:
    layers = [
        # 2848 frame 1 order, simplified to the exported test SVGs.
        # SWF translates are twips, so the script divides them by 20.
        Layer(
            "up1_background_2757",
            test_svg_dir / "1WhiteBackground.svg",
            (1.1071625, 0.056030273, -0.036346436, 0.9984131, -40 / 20, -404 / 20),
        ),
        Layer(
            "white_frame_2841",
            test_svg_dir / "2841(whitepartframe)" / "shapes" / "2841.svg",
            (1, 0, 0, 1, 0, 0),
        ),
        Layer(
            "main_picture_196",
            test_svg_dir / "196(mainpicture).svg",
            (1, 0, 0, 1, 177 / 20, 149 / 20),
        ),
        Layer(
            "black_frame_part_2844",
            test_svg_dir / "2844(blackpartframe)" / "shapes" / "2844.svg",
            (1, 0, 0, 1, 0, 0),
        ),
        Layer(
            "black_side_frame_2845",
            test_svg_dir / "2845(blacksideframe)" / "shapes" / "2845.svg",
            (1, 0, 0, 1, 11 / 20, 126 / 20),
            {"#111111": "#b64055"},
        ),
        # Exported separately; not present in the same exact 2848 chain, but useful
        # as a first visual comparison layer for the visible black outline.
        Layer(
            "black_outline_test_3",
            test_svg_dir / "3(BlackFrame).svg",
            (1, 0, 0, 1, 0, 0),
        ),
    ]

    missing = [layer.source for layer in layers if not layer.source.exists()]
    if missing:
        raise FileNotFoundError("Missing SVG source(s): " + ", ".join(str(path) for path in missing))

    root = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": "147",
            "height": "92",
            "viewBox": "-18 -24 140 96",
            "version": "1.1",
        },
    )
    title = ET.SubElement(root, f"{{{SVG_NS}}}title")
    title.text = "Mewgenics butcher passive prototype"

    for layer in layers:
        append_layer(root, layer)

    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)


def build_viewer(output_svg: Path, reference_png: Path, viewer_path: Path) -> None:
    viewer_dir = viewer_path.resolve().parent
    relative_svg = Path(os.path.relpath(output_svg.resolve(), viewer_dir))
    relative_ref = Path(os.path.relpath(reference_png.resolve(), viewer_dir))
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
        "--test-svg-dir",
        type=Path,
        default=Path(r"..\Gamefiles\testPassiveOrigSVG"),
        help="Path to the exported butcher test SVG directory.",
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

    build(args.test_svg_dir.resolve(), args.output.resolve())
    if args.reference.exists():
        build_viewer(args.output.resolve(), args.reference.resolve(), args.viewer.resolve())
    print(args.output.resolve())


if __name__ == "__main__":
    main()
