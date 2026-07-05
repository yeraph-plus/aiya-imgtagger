import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt6.QtWidgets import QApplication
from ui.gallery_window import GalleryWindow
from ui.batch_window import BatchTaggerWindow
from ui.preset_editor import PresetEditorWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["gallery", "batch", "editor"], default="gallery",
                        help="Window mode (default: gallery)")
    parser.add_argument("--entry", type=str, default=None,
                        help="Entry folder path (batch mode)")
    parser.add_argument("--preset", type=str, default=None,
                        help="Preset template name")

    args, _ = parser.parse_known_args()

    app = QApplication(sys.argv)
    app.setApplicationName("Aiya ImgTagger")

    if args.mode == "batch":
        window = BatchTaggerWindow(entry_path=args.entry, preset_name=args.preset)
    elif args.mode == "editor":
        window = PresetEditorWindow(preset_name=args.preset)
    else:
        window = GalleryWindow()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
