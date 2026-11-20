"""Точка входа: ``python -m grasp`` и Grasp.exe (PyInstaller)."""

import sys


def _run() -> int:
    from grasp.app import main

    return main(sys.argv)


if __name__ == "__main__":
    sys.exit(_run())
