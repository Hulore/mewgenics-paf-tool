from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from scripts.generate_from_rules import build


APP_TITLE = "Mewgenics PAF Tool"


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name.lower() == "dist":
            return exe_dir.parent
        return exe_dir
    return Path(__file__).resolve().parent


class DropArea(QFrame):
    filesDropped = Signal(list)

    def __init__(self, title_text: str, subtitle_text: str) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setMinimumHeight(104)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel(title_text)
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("dropSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._has_svg(event):
            self.setProperty("active", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._clear_active()
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self._clear_active()
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.suffix.lower() == ".svg":
                    paths.append(str(path))
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()

    def _has_svg(self, event: QDragEnterEvent) -> bool:
        return any(
            url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() == ".svg"
            for url in event.mimeData().urls()
        )

    def _clear_active(self) -> None:
        self.setProperty("active", False)
        self.style().unpolish(self)
        self.style().polish(self)


class DraggableSvgPreview(QSvgWidget):
    dragged = Signal(float, float)

    def __init__(self, canvas_width: float, canvas_height: float) -> None:
        super().__init__()
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.last_pos = None
        self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.last_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.last_pos is None:
            return

        current_pos = event.position()
        delta = current_pos - self.last_pos
        self.last_pos = current_pos
        scale = self.preview_scale()
        self.dragged.emit(delta.x() / scale, delta.y() / scale)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self.last_pos = None
            self.setCursor(Qt.OpenHandCursor)
            event.accept()

    def preview_scale(self) -> float:
        if self.canvas_width <= 0 or self.canvas_height <= 0:
            return 1
        return max(0.01, min(self.width() / self.canvas_width, self.height() / self.canvas_height))


class App(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.root_dir = project_root()
        self.rules_path = self.root_dir / "rules" / "butcher_manual.json"
        self.preview_path = self.root_dir / ".cache" / "adjust_preview.svg"
        self.rules = self.load_rules()

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(760, 560)
        self.resize(880, 640)

        self.class_combo = QComboBox()
        self.adjust_class_combo = QComboBox()
        self.populate_class_combo(self.class_combo)
        self.populate_class_combo(self.adjust_class_combo)

        self.file_list = QListWidget()
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)

        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("Optional. Empty means save next to each source file.")

        self.adjust_main_input = QLineEdit()
        self.adjust_main_input.setPlaceholderText("Select or drop one main picture SVG")
        self.adjust_output_input = QLineEdit()
        self.adjust_output_input.setPlaceholderText("Adjusted SVG output path")
        canvas = self.rules.get("canvas", {})
        self.preview = DraggableSvgPreview(float(canvas.get("width", 147)), float(canvas.get("height", 92)))
        self.preview.setObjectName("preview")
        self.preview.setMinimumSize(441, 276)
        self.preview.dragged.connect(self.drag_main_picture)

        self.x_spin = self.make_spin(-300, 300, self.default_main_value("x", 37))
        self.y_spin = self.make_spin(-300, 300, self.default_main_value("y", 26))
        self.scale_x_spin = self.make_spin(0.05, 5, self.default_main_value("scaleX", 1))
        self.scale_y_spin = self.make_spin(0.05, 5, self.default_main_value("scaleY", 1))

        self.status = QLabel(f"Rules: {self.rules_path}")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)

        self._build_ui()

    def load_rules(self) -> dict:
        try:
            return json.loads(self.rules_path.read_text(encoding="utf-8"))
        except Exception:
            return {"classes": {"butcher": {"color": "#ac4457"}}, "layers": []}

    def populate_class_combo(self, combo: QComboBox) -> None:
        combo.clear()
        for class_name in self.rules.get("classes", {}) or {"butcher": {}}:
            combo.addItem(class_name.title(), class_name)

    def default_main_value(self, key: str, fallback: float) -> float:
        for layer in self.rules.get("layers", []):
            if layer.get("id") == "main_picture":
                return float(layer.get(key, fallback))
        return fallback

    def make_spin(self, minimum: float, maximum: float, value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(3)
        spin.setSingleStep(0.25)
        spin.setValue(value)
        spin.valueChanged.connect(self.update_adjust_preview)
        return spin

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)

        header = QLabel(APP_TITLE)
        header.setObjectName("header")
        root.addWidget(header)

        tabs = QTabWidget()
        tabs.addTab(self.build_batch_tab(), "Batch generate")
        tabs.addTab(self.build_adjust_tab(), "Adjust main picture")
        root.addWidget(tabs)

        root.addWidget(self.status)
        self.apply_styles()

    def build_batch_tab(self) -> QWidget:
        tab = QWidget()
        root = QVBoxLayout(tab)
        root.setContentsMargins(0, 14, 0, 0)
        root.setSpacing(14)

        drop_area = DropArea("Drop main picture SVG files here", "single file or a whole batch")
        drop_area.filesDropped.connect(self.add_main_svgs)
        root.addWidget(drop_area)
        root.addWidget(self.file_list)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        grid.addWidget(QLabel("Class"), 0, 0)
        grid.addWidget(self.class_combo, 0, 1)

        grid.addWidget(QLabel("Main pictures"), 1, 0)
        main_button = QPushButton("Browse")
        main_button.clicked.connect(self.pick_main_svgs)
        grid.addWidget(main_button, 1, 1)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.file_list.clear)
        grid.addWidget(clear_button, 1, 2)

        grid.addWidget(QLabel("Output folder"), 2, 0)
        grid.addWidget(self.output_dir_input, 2, 1)
        output_button = QPushButton("Browse")
        output_button.clicked.connect(self.pick_output_dir)
        grid.addWidget(output_button, 2, 2)
        root.addLayout(grid)

        actions = QHBoxLayout()
        actions.addStretch(1)
        generate_button = QPushButton("Generate")
        generate_button.setObjectName("generateButton")
        generate_button.clicked.connect(self.generate)
        actions.addWidget(generate_button)
        root.addLayout(actions)

        return tab

    def build_adjust_tab(self) -> QWidget:
        tab = QWidget()
        root = QVBoxLayout(tab)
        root.setContentsMargins(0, 14, 0, 0)
        root.setSpacing(14)

        drop_area = DropArea("Drop one problem SVG here", "then adjust the main picture position")
        drop_area.filesDropped.connect(self.set_adjust_svg_from_drop)
        root.addWidget(drop_area)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        grid.addWidget(QLabel("Class"), 0, 0)
        grid.addWidget(self.adjust_class_combo, 0, 1)
        self.adjust_class_combo.currentIndexChanged.connect(self.update_adjust_preview)

        grid.addWidget(QLabel("Main picture"), 1, 0)
        grid.addWidget(self.adjust_main_input, 1, 1)
        main_button = QPushButton("Browse")
        main_button.clicked.connect(self.pick_adjust_svg)
        grid.addWidget(main_button, 1, 2)

        grid.addWidget(QLabel("Output SVG"), 2, 0)
        grid.addWidget(self.adjust_output_input, 2, 1)
        save_button = QPushButton("Save as")
        save_button.clicked.connect(self.pick_adjust_output)
        grid.addWidget(save_button, 2, 2)
        root.addLayout(grid)

        editor = QHBoxLayout()
        editor.setSpacing(14)
        editor.addWidget(self.preview, 1)

        controls = QGridLayout()
        controls.setHorizontalSpacing(8)
        controls.setVerticalSpacing(8)
        controls.addWidget(QLabel("X"), 0, 0)
        controls.addWidget(self.x_spin, 0, 1)
        controls.addWidget(QLabel("Y"), 1, 0)
        controls.addWidget(self.y_spin, 1, 1)
        controls.addWidget(QLabel("Scale X"), 2, 0)
        controls.addWidget(self.scale_x_spin, 2, 1)
        controls.addWidget(QLabel("Scale Y"), 3, 0)
        controls.addWidget(self.scale_y_spin, 3, 1)

        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self.reset_adjust_values)
        controls.addWidget(reset_button, 4, 0, 1, 2)

        update_button = QPushButton("Update preview")
        update_button.clicked.connect(self.update_adjust_preview)
        controls.addWidget(update_button, 5, 0, 1, 2)

        save_adjusted_button = QPushButton("Save adjusted SVG")
        save_adjusted_button.setObjectName("generateButton")
        save_adjusted_button.clicked.connect(self.save_adjusted_svg)
        controls.addWidget(save_adjusted_button, 6, 0, 1, 2)
        controls.setRowStretch(7, 1)
        editor.addLayout(controls)
        root.addLayout(editor, 1)

        return tab

    def apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #f6f7f9;
                color: #16191f;
                font-family: Segoe UI;
                font-size: 10pt;
            }
            QLabel#header {
                font-size: 20pt;
                font-weight: 650;
            }
            QTabWidget::pane {
                border: 0;
            }
            QTabBar::tab {
                background: #ffffff;
                border: 1px solid #c8ced8;
                border-bottom-color: #bfc6d1;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 7px 14px;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #fff5f7;
                border-color: #ac4457;
            }
            QFrame#dropArea {
                background: #ffffff;
                border: 2px dashed #b7bfca;
                border-radius: 8px;
            }
            QFrame#dropArea[active="true"] {
                border-color: #ac4457;
                background: #fff5f7;
            }
            QLabel#dropTitle {
                background: transparent;
                font-size: 14pt;
                font-weight: 650;
            }
            QLabel#dropSubtitle {
                background: transparent;
                color: #657080;
            }
            QLineEdit, QComboBox, QListWidget, QDoubleSpinBox {
                background: #ffffff;
                border: 1px solid #c8ced8;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QLineEdit, QComboBox, QDoubleSpinBox {
                min-height: 32px;
            }
            QListWidget {
                min-height: 92px;
            }
            QSvgWidget#preview {
                background: #ffffff;
                border: 1px solid #c8ced8;
                border-radius: 8px;
            }
            QPushButton {
                background: #ffffff;
                border: 1px solid #bfc6d1;
                border-radius: 6px;
                min-height: 34px;
                padding: 4px 14px;
            }
            QPushButton:hover {
                background: #f0f2f5;
            }
            QPushButton#generateButton {
                background: #ac4457;
                border-color: #ac4457;
                color: #ffffff;
                font-weight: 650;
                min-width: 150px;
            }
            QPushButton#generateButton:hover {
                background: #96384a;
            }
            QLabel#status {
                color: #657080;
            }
            """
        )

    def add_main_svgs(self, paths: list[str]) -> None:
        existing = {
            self.file_list.item(index).text()
            for index in range(self.file_list.count())
        }
        added = 0
        for path in paths:
            source = Path(path)
            if source.suffix.lower() != ".svg":
                continue
            normalized = str(source)
            if normalized in existing:
                continue
            self.file_list.addItem(normalized)
            existing.add(normalized)
            added += 1
        self.status.setText(f"Added {added} file(s). Total: {self.file_list.count()}")

    def pick_main_svgs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select main picture SVG files",
            str(self.root_dir),
            "SVG files (*.svg);;All files (*.*)",
        )
        if paths:
            self.add_main_svgs(paths)

    def pick_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select output folder",
            self.output_dir_input.text().strip() or str(self.root_dir / "output"),
        )
        if path:
            self.output_dir_input.setText(path)

    def generate(self) -> None:
        if not self.rules_path.exists():
            QMessageBox.critical(self, APP_TITLE, f"Rules file not found:\n{self.rules_path}")
            return
        if self.file_list.count() == 0:
            QMessageBox.critical(self, APP_TITLE, "Add at least one main picture SVG.")
            return

        class_name = self.class_combo.currentData() or self.class_combo.currentText().lower()
        output_dir_text = self.output_dir_input.text().strip()
        output_dir = Path(output_dir_text) if output_dir_text else None
        generated = []
        errors = []

        for index in range(self.file_list.count()):
            main_svg = Path(self.file_list.item(index).text())
            if not main_svg.exists() or main_svg.suffix.lower() != ".svg":
                errors.append(f"{main_svg}: source file not found or not SVG")
                continue

            target_dir = output_dir if output_dir is not None else main_svg.parent
            output = target_dir / f"{main_svg.stem}_{class_name}_paf.svg"
            try:
                build(self.rules_path, main_svg, class_name, output)
            except Exception as exc:
                errors.append(f"{main_svg.name}: {exc}")
                continue
            generated.append(output)

        if errors:
            QMessageBox.warning(
                self,
                APP_TITLE,
                "Some files were not generated:\n\n" + "\n".join(errors[:12]),
            )

        self.status.setText(f"Generated {len(generated)} file(s).")
        if generated:
            QMessageBox.information(self, APP_TITLE, f"Generated {len(generated)} file(s).")

    def set_adjust_svg_from_drop(self, paths: list[str]) -> None:
        if paths:
            self.set_adjust_svg(paths[0])

    def set_adjust_svg(self, path: str) -> None:
        source = Path(path)
        self.adjust_main_input.setText(str(source))
        if not self.adjust_output_input.text().strip():
            class_name = self.adjust_class_combo.currentData() or self.adjust_class_combo.currentText().lower()
            self.adjust_output_input.setText(str(source.with_name(f"{source.stem}_{class_name}_adjusted_paf.svg")))
        self.update_adjust_preview()

    def pick_adjust_svg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select main picture SVG",
            str(self.root_dir),
            "SVG files (*.svg);;All files (*.*)",
        )
        if path:
            self.set_adjust_svg(path)

    def pick_adjust_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save adjusted passive icon",
            self.adjust_output_input.text().strip() or str(self.root_dir / "output" / "adjusted_paf.svg"),
            "SVG files (*.svg);;All files (*.*)",
        )
        if path:
            self.adjust_output_input.setText(path)

    def main_picture_overrides(self) -> dict[str, dict[str, float]]:
        return {
            "main_picture": {
                "x": self.x_spin.value(),
                "y": self.y_spin.value(),
                "scaleX": self.scale_x_spin.value(),
                "scaleY": self.scale_y_spin.value(),
            }
        }

    def drag_main_picture(self, dx: float, dy: float) -> None:
        self.x_spin.blockSignals(True)
        self.y_spin.blockSignals(True)
        self.x_spin.setValue(self.x_spin.value() + dx)
        self.y_spin.setValue(self.y_spin.value() + dy)
        self.x_spin.blockSignals(False)
        self.y_spin.blockSignals(False)
        self.update_adjust_preview()

    def update_adjust_preview(self) -> None:
        main_svg = Path(self.adjust_main_input.text().strip())
        if not main_svg.exists() or main_svg.suffix.lower() != ".svg":
            return

        class_name = self.adjust_class_combo.currentData() or self.adjust_class_combo.currentText().lower()
        try:
            build(self.rules_path, main_svg, class_name, self.preview_path, self.main_picture_overrides())
        except Exception as exc:
            self.status.setText(f"Preview failed: {exc}")
            return

        self.preview.load(str(self.preview_path))
        self.status.setText(f"Preview: {main_svg.name}")

    def reset_adjust_values(self) -> None:
        self.x_spin.setValue(self.default_main_value("x", 37))
        self.y_spin.setValue(self.default_main_value("y", 26))
        self.scale_x_spin.setValue(self.default_main_value("scaleX", 1))
        self.scale_y_spin.setValue(self.default_main_value("scaleY", 1))
        self.update_adjust_preview()

    def save_adjusted_svg(self) -> None:
        main_svg = Path(self.adjust_main_input.text().strip())
        output_text = self.adjust_output_input.text().strip()
        if not main_svg.exists() or main_svg.suffix.lower() != ".svg":
            QMessageBox.critical(self, APP_TITLE, "Select an existing main picture SVG.")
            return
        if not output_text:
            QMessageBox.critical(self, APP_TITLE, "Choose output SVG path.")
            return

        class_name = self.adjust_class_combo.currentData() or self.adjust_class_combo.currentText().lower()
        output = Path(output_text)
        try:
            build(self.rules_path, main_svg, class_name, output, self.main_picture_overrides())
        except Exception as exc:
            QMessageBox.critical(self, APP_TITLE, str(exc))
            return

        self.status.setText(f"Generated: {output}")
        QMessageBox.information(self, APP_TITLE, f"Generated:\n{output}")


def main() -> None:
    qt_app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
