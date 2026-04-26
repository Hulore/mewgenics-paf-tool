# Mewgenics PAF tool

Tool for reconstructing original Mewgenics passive ability icons from separated game asset layers.

## Goal

Mewgenics stores passive ability icons as multiple pieces: background, main artwork, frame parts, overlays, and other layers. This project will combine those pieces back into the final in-game icon.

## Project status

Initial repository setup.

## Prototype

Manual layout workflow:

Run the desktop app:

```text
H:\Mewgenics Projects\Passive Abilities Frame\Mewgenics PAF tool\dist\Mewgenics PAF Tool.exe
```

The app lets you select main picture SVG files, choose a class, and generate SVG outputs.
You can also drag and drop one or many main picture SVG files into the app window.
Use the `Adjust main picture` tab to fine-tune a single problem SVG before saving it. The main picture can be dragged in the preview or adjusted with numeric fields.
Use the `Generate all` tab with `output\passive_manifest.csv` and `Ability Passive Svg\shapes` to generate every regular class passive.

1. Open the visual editor:

```text
H:\Mewgenics Projects\Passive Abilities Frame\Mewgenics PAF tool\tools\layout_editor.html
```

2. Move and scale layers until the generated layout matches the reference.
3. Click `Export JSON`.
4. Save the exported JSON into `rules/butcher_manual.json`.
5. Generate the final SVG:

```powershell
python scripts\generate_from_rules.py `
  --rules rules\butcher_manual.json `
  --main-svg "H:\Mewgenics Projects\Passive Abilities Frame\Gamefiles\testPassiveOrigSVG\196(mainpicture).svg" `
  --class-name butcher `
  --output output\manual_butcher.svg
```

Build the desktop app:

```powershell
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "Mewgenics PAF Tool" app.py
```

Generate the passive manifest and all regular class passives from the command line:

```powershell
python scripts\extract_passive_manifest.py
python scripts\generate_all_passives.py
```

Older FFDec timeline prototype:

```powershell
python scripts\build_butcher_prototype.py `
  --code-dir "H:\Mewgenics Projects\Passive Abilities Frame\Gamefiles\CodeForRules" `
  --test-svg-dir "H:\Mewgenics Projects\Passive Abilities Frame\Gamefiles\testPassiveOrigSVG" `
  --asset-root "H:\Mewgenics Projects\Passive Abilities Frame\OtherGameFiles\UnpackedImportant" `
  --reference "H:\Mewgenics Projects\Passive Abilities Frame\reference\Butcher Passive gameframe-Photoroom.png"
```

Generated files are written to `output/`:

- `butcher_prototype.svg`
- `butcher_compare.html`

The prototype renderer reads FFDec `frames.xml` files, resolves nested sprites,
applies SWF matrices, and skips `up0`/`up1` by default because those named layers
belong to the generic shell state and are not visible in the passive reference.
