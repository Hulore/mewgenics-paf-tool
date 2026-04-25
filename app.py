from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from scripts.generate_from_rules import build


APP_TITLE = "Mewgenics PAF Tool"


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name.lower() == "dist":
            return exe_dir.parent
        return exe_dir
    return Path(__file__).resolve().parent


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("560x260")
        self.minsize(520, 240)

        self.root_dir = project_root()
        self.rules_path = self.root_dir / "rules" / "butcher_manual.json"
        self.main_svg = tk.StringVar()
        self.class_name = tk.StringVar(value="butcher")
        self.output_path = tk.StringVar()

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Class").grid(row=0, column=0, sticky="w", pady=(0, 10))
        class_combo = ttk.Combobox(
            frame,
            textvariable=self.class_name,
            values=("butcher",),
            state="readonly",
        )
        class_combo.grid(row=0, column=1, sticky="ew", pady=(0, 10))

        ttk.Label(frame, text="Main picture").grid(row=1, column=0, sticky="w", pady=(0, 10))
        ttk.Entry(frame, textvariable=self.main_svg).grid(row=1, column=1, sticky="ew", pady=(0, 10))
        ttk.Button(frame, text="Browse", command=self.pick_main_svg).grid(row=1, column=2, padx=(8, 0), pady=(0, 10))

        ttk.Label(frame, text="Output SVG").grid(row=2, column=0, sticky="w", pady=(0, 10))
        ttk.Entry(frame, textvariable=self.output_path).grid(row=2, column=1, sticky="ew", pady=(0, 10))
        ttk.Button(frame, text="Save as", command=self.pick_output).grid(row=2, column=2, padx=(8, 0), pady=(0, 10))

        ttk.Separator(frame).grid(row=3, column=0, columnspan=3, sticky="ew", pady=8)

        ttk.Button(frame, text="Generate", command=self.generate).grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 0))

        self.status = tk.StringVar(value=f"Rules: {self.rules_path}")
        ttk.Label(frame, textvariable=self.status, wraplength=510).grid(row=5, column=0, columnspan=3, sticky="w", pady=(14, 0))

    def pick_main_svg(self) -> None:
        path = filedialog.askopenfilename(
            title="Select main picture SVG",
            filetypes=(("SVG files", "*.svg"), ("All files", "*.*")),
        )
        if not path:
            return

        self.main_svg.set(path)
        if not self.output_path.get():
            source = Path(path)
            self.output_path.set(str(source.with_name(f"{source.stem}_paf.svg")))

    def pick_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save generated passive icon",
            defaultextension=".svg",
            filetypes=(("SVG files", "*.svg"), ("All files", "*.*")),
        )
        if path:
            self.output_path.set(path)

    def generate(self) -> None:
        main_svg = Path(self.main_svg.get())
        output_text = self.output_path.get().strip()

        if not self.rules_path.exists():
            messagebox.showerror(APP_TITLE, f"Rules file not found:\n{self.rules_path}")
            return
        if not main_svg.exists():
            messagebox.showerror(APP_TITLE, "Select an existing main picture SVG.")
            return
        if not output_text:
            messagebox.showerror(APP_TITLE, "Choose output SVG path.")
            return

        output = Path(output_text)

        try:
            build(self.rules_path, main_svg, self.class_name.get(), output)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return

        self.status.set(f"Generated: {output}")
        messagebox.showinfo(APP_TITLE, f"Generated:\n{output}")


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
