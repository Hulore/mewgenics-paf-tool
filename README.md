# Mewgenics PAF tool

Tool for reconstructing original Mewgenics passive ability icons from separated game asset layers.

## Goal

Mewgenics stores passive ability icons as multiple pieces: background, main artwork, frame parts, overlays, and other layers. This project will combine those pieces back into the final in-game icon.

## Project status

Initial repository setup.

## Prototype

Build the current butcher passive icon prototype:

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
