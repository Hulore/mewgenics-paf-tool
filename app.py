from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
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

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setMinimumHeight(118)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Drop main picture SVG files here")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("single file or a whole batch")
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


class App(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.root_dir = project_root()
        self.rules_path = self.root_dir / "rules" / "butcher_manual.json"

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(680, 390)
        self.resize(760, 430)

        self.class_combo = QComboBox()
        self.load_classes()

        self.file_list = QListWidget()
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)

        self.output_dir_input = QLineEdit()
        self.output_dir_input.setPlaceholderText("Optional. Empty means save next to each source file.")

        self.status = QLabel(f"Rules: {self.rules_path}")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)

        self._build_ui()

    def load_classes(self) -> None:
        self.class_combo.clear()
        try:
            rules = json.loads(self.rules_path.read_text(encoding="utf-8"))
            class_names = list(rules.get("classes", {}))
        except Exception:
            class_names = ["butcher"]

        for class_name in class_names:
            self.class_combo.addItem(class_name.title(), class_name)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(16)

        header = QLabel(APP_TITLE)
        header.setObjectName("header")
        root.addWidget(header)

        drop_area = DropArea()
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

        root.addWidget(self.status)

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
            QLineEdit, QComboBox, QListWidget {
                background: #ffffff;
                border: 1px solid #c8ced8;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QLineEdit, QComboBox {
                min-height: 32px;
            }
            QListWidget {
                min-height: 92px;
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


def main() -> None:
    qt_app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
