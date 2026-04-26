from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

JESTER_GRADIENT_ID = "jester_ui_rainbow"


def read_svg_children(path: Path, recolor: dict[str, str]) -> list[ET.Element]:
    root = ET.parse(path).getroot()
    for node in root.iter():
        for attr in ("fill", "stroke"):
            value = node.attrib.get(attr)
            if value in recolor:
                node.set(attr, recolor[value])
    return [deepcopy(child) for child in list(root)]


def add_jester_gradient(root: ET.Element, canvas: dict) -> None:
    defs = ET.SubElement(root, f"{{{SVG_NS}}}defs")
    gradient = ET.SubElement(
        defs,
        f"{{{SVG_NS}}}linearGradient",
        {
            "id": JESTER_GRADIENT_ID,
            "gradientUnits": "userSpaceOnUse",
            "x1": "0",
            "y1": str(canvas["height"]),
            "x2": str(canvas["width"]),
            "y2": "0",
        },
    )
    for offset, color in (
        ("0%", "#f8aeae"),
        ("17%", "#f8d3ae"),
        ("34%", "#e8f8ae"),
        ("51%", "#aef8ca"),
        ("68%", "#aee8f8"),
        ("84%", "#c4aef8"),
        ("100%", "#f8aee5"),
    ):
        ET.SubElement(gradient, f"{{{SVG_NS}}}stop", {"offset": offset, "stop-color": color})


def resolve_source(source: str, rules_dir: Path, main_svg: Path) -> Path:
    if source == "$main":
        return main_svg.resolve()
    path = Path(source)
    if not path.is_absolute():
        path = (rules_dir / path).resolve()
    return path


def build(
    rules_path: Path,
    main_svg: Path,
    class_name: str,
    output: Path,
    layer_overrides: dict[str, dict[str, float]] | None = None,
) -> None:
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    build_from_rules(rules, rules_path.parent, main_svg, class_name, output, layer_overrides)


def build_from_rules(
    rules: dict,
    rules_dir: Path,
    main_svg: Path,
    class_name: str,
    output: Path,
    layer_overrides: dict[str, dict[str, float]] | None = None,
) -> None:
    class_data = rules.get("classes", {}).get(class_name)
    if class_data is None:
        known = ", ".join(sorted(rules.get("classes", {})))
        raise KeyError(f"Unknown class '{class_name}'. Known classes: {known}")

    class_color = class_data["color"]
    canvas = rules["canvas"]
    root = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": str(canvas["width"]),
            "height": str(canvas["height"]),
            "viewBox": canvas["viewBox"],
            "version": "1.1",
        },
    )
    class_shader = class_data.get("shader")
    if class_shader == "jester_rainbow":
        add_jester_gradient(root, canvas)

    for layer in rules["layers"]:
        if not layer.get("visible", True):
            continue
        if layer["id"] in class_data.get("hide_layers", []):
            continue
        layer = deepcopy(layer)
        if layer_overrides and layer["id"] in layer_overrides:
            layer.update(layer_overrides[layer["id"]])

        source = resolve_source(layer["source"], rules_dir, main_svg)
        if not source.exists():
            raise FileNotFoundError(source)

        recolor = {}
        for source_color, target_color in layer.get("recolor", {}).items():
            if target_color == "$classColor":
                if class_shader == "jester_rainbow":
                    recolor[source_color] = f"url(#{JESTER_GRADIENT_ID})"
                else:
                    recolor[source_color] = class_color
            elif target_color == "$classShader" and class_shader == "jester_rainbow":
                recolor[source_color] = f"url(#{JESTER_GRADIENT_ID})"
            else:
                recolor[source_color] = target_color

        transform = (
            f"translate({layer.get('x', 0)} {layer.get('y', 0)}) "
            f"rotate({layer.get('rotation', 0)}) "
            f"scale({layer.get('scaleX', 1)} {layer.get('scaleY', 1)})"
        )
        group = ET.SubElement(
            root,
            f"{{{SVG_NS}}}g",
            {
                "id": layer["id"],
                "transform": transform,
            },
        )
        for child in read_svg_children(source, recolor):
            group.append(child)

    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a passive icon from manual layout rules.")
    parser.add_argument("--rules", type=Path, default=Path("rules") / "butcher_manual.json")
    parser.add_argument("--main-svg", type=Path, required=True)
    parser.add_argument("--class-name", default="butcher")
    parser.add_argument("--output", type=Path, default=Path("output") / "manual_butcher.svg")
    args = parser.parse_args()

    build(args.rules.resolve(), args.main_svg.resolve(), args.class_name, args.output.resolve())
    print(args.output.resolve())


if __name__ == "__main__":
    main()
