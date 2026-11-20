"""Точка входа для PyInstaller/Nuitka (Grasp.exe)."""

import sys

from grasp.app import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))
