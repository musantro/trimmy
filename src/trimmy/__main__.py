"""Entry point for the Trimmy application."""

import sys


def main() -> None:
    """Launch the Trimmy main window."""
    from trimmy.presentation.main_window import run  # noqa: PLC0415

    path = sys.argv[1] if len(sys.argv) > 1 else None
    run(path)


if __name__ == "__main__":
    main()
