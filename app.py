from __future__ import annotations

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
    fileDropped = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setMinimumHeight(118)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Drop main picture SVG here")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("or choose it with the button below")
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
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.suffix.lower() == ".svg":
                    self.fileDropped.emit(str(path))
                    event.acceptProposedAction()
                    return

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
        self.class_combo.addItem("butcher")

        self.main_input = QLineEdit()
        self.main_input.setPlaceholderText("Select or drop a main picture SVG")

        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Generated SVG output path")

        self.status = QLabel(f"Rules: {self.rules_path}")
        self.status.setObjectName("status")
        self.status.setWordWrap(True)

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(16)

        header = QLabel(APP_TITLE)
        header.setObjectName("header")
        root.addWidget(header)

        drop_area = DropArea()
        drop_area.fileDropped.connect(self.set_main_svg)
        root.addWidget(drop_area)

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(1, 1)

        grid.addWidget(QLabel("Class"), 0, 0)
        grid.addWidget(self.class_combo, 0, 1)

        grid.addWidget(QLabel("Main picture"), 1, 0)
        grid.addWidget(self.main_input, 1, 1)
        main_button = QPushButton("Browse")
        main_button.clicked.connect(self.pick_main_svg)
        grid.addWidget(main_button, 1, 2)

        grid.addWidget(QLabel("Output SVG"), 2, 0)
        grid.addWidget(self.output_input, 2, 1)
        output_button = QPushButton("Save as")
        output_button.clicked.connect(self.pick_output)
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
            QLineEdit, QComboBox {
                background: #ffffff;
                border: 1px solid #c8ced8;
                border-radius: 6px;
                min-height: 32px;
                padding: 4px 8px;
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

    def set_main_svg(self, path: str) -> None:
        self.main_input.setText(path)
        if not self.output_input.text().strip():
            source = Path(path)
            self.output_input.setText(str(source.with_name(f"{source.stem}_paf.svg")))

    def pick_main_svg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select main picture SVG",
            str(self.root_dir),
            "SVG files (*.svg);;All files (*.*)",
        )
        if path:
            self.set_main_svg(path)

    def pick_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save generated passive icon",
            self.output_input.text().strip() or str(self.root_dir / "output" / "manual_butcher.svg"),
            "SVG files (*.svg);;All files (*.*)",
        )
        if path:
            self.output_input.setText(path)

    def generate(self) -> None:
        main_svg = Path(self.main_input.text().strip())
        output_text = self.output_input.text().strip()

        if not self.rules_path.exists():
            QMessageBox.critical(self, APP_TITLE, f"Rules file not found:\n{self.rules_path}")
            return
        if not main_svg.exists() or main_svg.suffix.lower() != ".svg":
            QMessageBox.critical(self, APP_TITLE, "Select an existing main picture SVG.")
            return
        if not output_text:
            QMessageBox.critical(self, APP_TITLE, "Choose output SVG path.")
            return

        output = Path(output_text)

        try:
            build(self.rules_path, main_svg, self.class_combo.currentText(), output)
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
