import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from app.controllers.pattern_designer import PatternDesignerWindow

def main():
    app = QApplication(sys.argv)

    base = Path(__file__).parent
    for folder in ("resources", "ressources", "."):
        qss = base / folder / "style.qss" if folder != "." else base / "style.qss"
        if qss.exists():
            app.setStyleSheet(qss.read_text(encoding="utf-8"))
            break

    win = PatternDesignerWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()