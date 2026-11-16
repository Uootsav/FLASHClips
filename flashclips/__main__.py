import sys

if __name__ == "__main__":
    if len(sys.argv) > 1:
        from flashclips.cli import main
    else:
        from flashclips.gui.app import main
    main()
