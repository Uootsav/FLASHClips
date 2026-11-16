"""Entry point for PyInstaller / double-click."""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if len(sys.argv) > 1:
        from flashclips.cli import main
    else:
        from flashclips.gui.app import main
    main()
