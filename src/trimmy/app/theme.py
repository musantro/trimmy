"""Design tokens from DESIGN.md — colors, typography, spacing, radii."""

from pathlib import Path

from PySide6.QtGui import QFontDatabase

_FONTS_DIR = Path(__file__).parent / "fonts"


def load_fonts() -> None:
    """Register bundled font files with Qt so they're available by family name."""
    for ttf in _FONTS_DIR.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(ttf))


class Colors:
    """Color palette tokens from DESIGN.md."""

    LEVEL_0 = "#0F1115"
    LEVEL_1 = "#1A1D23"
    LEVEL_1_BORDER = "#2D323C"
    LEVEL_2 = "#252932"

    SURFACE = "#111317"
    SURFACE_DIM = "#111317"
    SURFACE_BRIGHT = "#37393e"
    SURFACE_CONTAINER_LOWEST = "#0c0e12"
    SURFACE_CONTAINER_LOW = "#1a1c20"
    SURFACE_CONTAINER = "#1e2024"
    SURFACE_CONTAINER_HIGH = "#282a2e"
    SURFACE_CONTAINER_HIGHEST = "#333539"
    SURFACE_VARIANT = "#333539"

    ON_SURFACE = "#e2e2e8"
    ON_SURFACE_VARIANT = "#b9cacb"

    PRIMARY = "#00f0ff"
    PRIMARY_DIM = "#00dbe9"
    PRIMARY_TEXT = "#dbfcff"
    PRIMARY_CONTAINER = "#00f0ff"
    ON_PRIMARY = "#00363a"
    ON_PRIMARY_CONTAINER = "#006970"

    SECONDARY = "#b6f700"
    SECONDARY_CONTAINER = "#b6f700"
    SECONDARY_FIXED = "#b6f700"
    ON_SECONDARY = "#253600"
    ON_SECONDARY_CONTAINER = "#4f6e00"

    TERTIARY = "#fff5de"
    TERTIARY_CONTAINER = "#fed639"
    ON_TERTIARY = "#3b2f00"
    ON_TERTIARY_CONTAINER = "#715d00"

    ERROR = "#ffb4ab"
    ERROR_CONTAINER = "#93000a"
    ON_ERROR_CONTAINER = "#ffdad6"

    OUTLINE = "#849495"
    OUTLINE_VARIANT = "#3b494b"

    SUCCESS = "#4ecdc4"
    SUCCESS_BG = "#0d2b28"
    WARNING = "#fed639"
    WARNING_BG = "#3a3520"
    ERROR_STATUS = "#ffb4ab"
    ERROR_STATUS_BG = "#3a1520"
    INFO = "#00dbe9"
    INFO_BG = "#0d2a2e"


class Typography:
    """Font family and size tokens from DESIGN.md."""

    DISPLAY = "Geist"
    HEADING = "Geist"
    BODY = "Atkinson Hyperlegible Next"
    MONO = "JetBrains Mono"

    DISPLAY_SIZE = 48
    HEADLINE_SIZE = 32
    HEADLINE_MOBILE_SIZE = 24
    BODY_LG_SIZE = 18
    BODY_MD_SIZE = 16
    LABEL_MD_SIZE = 14
    LABEL_SM_SIZE = 12

    DISPLAY_WEIGHT = 700
    HEADLINE_WEIGHT = 600
    BODY_WEIGHT = 400
    LABEL_MD_WEIGHT = 500
    LABEL_SM_WEIGHT = 600


class Spacing:
    """Spacing scale on a 4px baseline grid from DESIGN.md."""

    BASE = 4
    XS = 8
    SM = 16
    MD = 24
    LG = 40
    XL = 64
    GUTTER = 24
    MARGIN_DESKTOP = 48
    MARGIN_MOBILE = 16
    SECTION_GAP = 12
    COMPONENT_GAP = 10
    CONTAINER_PADDING = 20


class Radii:
    """Border radius tokens from DESIGN.md."""

    SM = 2
    DEFAULT = 4
    MD = 6
    LG = 8
    XL = 12


def build_stylesheet() -> str:
    """Return the global QSS stylesheet built from design tokens."""
    return f"""
/* ── Window & Central ─────────────────────────────────── */

QMainWindow {{
    background-color: {Colors.LEVEL_0};
}}

QWidget#central {{
    background-color: {Colors.LEVEL_0};
}}

/* ── Top Navigation Bar ───────────────────────────────── */

QWidget#topnav {{
    background-color: {Colors.SURFACE};
    min-height: 48px;
    border-bottom: 1px solid {Colors.OUTLINE_VARIANT};
}}

/* ── Generic Buttons ──────────────────────────────────── */

QPushButton {{
    background-color: {Colors.PRIMARY_CONTAINER};
    color: {Colors.ON_PRIMARY_CONTAINER};
    border: none;
    border-radius: {Radii.DEFAULT}px;
    font-family: "{Typography.MONO}";
    font-size: {Typography.LABEL_MD_SIZE}px;
    font-weight: {Typography.LABEL_MD_WEIGHT};
    padding: {Spacing.XS}px {Spacing.SM}px;
}}

QPushButton:hover {{
    background-color: {Colors.PRIMARY_DIM};
}}

QPushButton:checked {{
    background-color: {Colors.PRIMARY_CONTAINER};
    color: {Colors.ON_PRIMARY_CONTAINER};
}}

QPushButton:disabled {{
    background-color: {Colors.SURFACE_CONTAINER_HIGH};
    color: {Colors.OUTLINE};
}}

/* ── Labels ───────────────────────────────────────────── */

QLabel {{
    color: {Colors.ON_SURFACE};
}}

QLabel#section {{
    color: {Colors.OUTLINE};
    font-family: "{Typography.MONO}";
    font-size: {Typography.LABEL_SM_SIZE}px;
    font-weight: {Typography.LABEL_SM_WEIGHT};
    text-transform: uppercase;
}}

QLabel#info {{
    color: {Colors.ON_SURFACE_VARIANT};
    font-family: "{Typography.MONO}";
    font-size: {Typography.LABEL_MD_SIZE}px;
    font-weight: {Typography.LABEL_MD_WEIGHT};
}}

QLabel#version {{
    color: {Colors.OUTLINE};
    font-family: "{Typography.MONO}";
    font-size: {Typography.LABEL_SM_SIZE}px;
    font-weight: {Typography.LABEL_SM_WEIGHT};
}}

/* ── Menus ────────────────────────────────────────────── */

QMenu {{
    background-color: {Colors.LEVEL_2};
    color: {Colors.ON_SURFACE};
    border: 1px solid {Colors.LEVEL_1_BORDER};
}}

QMenu::item:selected {{
    background-color: {Colors.SURFACE_CONTAINER_HIGH};
}}

/* ── Sliders ──────────────────────────────────────────── */

QSlider::groove:horizontal {{
    background-color: {Colors.SURFACE_CONTAINER_LOW};
    height: 6px;
    border-radius: {Radii.SM}px;
}}

QSlider::handle:horizontal {{
    background-color: {Colors.PRIMARY_CONTAINER};
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
}}

QSlider::sub-page:horizontal {{
    background-color: {Colors.PRIMARY_DIM};
    height: 6px;
    border-radius: {Radii.SM}px;
}}

/* ── Scroll Area ──────────────────────────────────────── */

QScrollArea {{
    background-color: transparent;
    border: none;
}}

/* ── Progress Bar ─────────────────────────────────────── */

QWidget#progress-bar {{
    background-color: {Colors.SURFACE_CONTAINER_HIGHEST};
    border-radius: 9999px;
}}

QWidget#progress-fill {{
    background-color: {Colors.PRIMARY_CONTAINER};
    border-radius: 9999px;
}}
"""
