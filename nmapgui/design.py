"""Design tokens.

One place for spacing, radii, type and motion so the whole app stays on the
same rhythm. Radii follow the concentric rule — an outer surface's radius is
its inner surface's radius plus the padding between them — which is why the
values below are not round numbers picked by eye.
"""
from __future__ import annotations

# --------------------------------------------------------------------------
# spacing — everything is a multiple of 4
# --------------------------------------------------------------------------
SPACE = {"xs": 4, "sm": 6, "md": 8, "lg": 12, "xl": 16, "2xl": 24, "3xl": 32}

# --------------------------------------------------------------------------
# radii — concentric: control(7) + padding(3) = panel(10) + padding(4) = card(14)
# --------------------------------------------------------------------------
RADIUS = {"chip": 5, "control": 7, "panel": 10, "card": 14, "pill": 999}

# --------------------------------------------------------------------------
# type scale, in px at the default zoom
# --------------------------------------------------------------------------
TYPE = {
    "micro": 10,    # uppercase eyebrow labels
    "small": 11,    # secondary / help text
    "body": 12,     # default UI text
    "medium": 13,   # emphasised body, tab labels
    "title": 15,    # panel and dialog titles
    "display": 30,  # the countdown and stat numbers
}

WEIGHT = {"regular": 400, "medium": 500, "semibold": 600, "bold": 700}

# Uppercase eyebrow labels need letter-spacing or they read as a smudge.
TRACKING_CAPS = 0.08  # em

# --------------------------------------------------------------------------
# motion — enter is slower than exit, so dismissals never feel sluggish
# --------------------------------------------------------------------------
DURATION = {"instant": 90, "exit": 130, "enter": 200, "slow": 320, "sweep": 1100}

# --------------------------------------------------------------------------
# elevation — shadows are for things that float, borders are for separation
# --------------------------------------------------------------------------
ELEVATION = {
    "raised": (0, 2, 8, 70),      # dx, dy, blur, alpha
    "overlay": (0, 8, 28, 110),
    "toast": (0, 12, 36, 130),
}

# Minimum interactive size. Desktop pointer, so 32 is the floor and 36 the norm.
HIT = {"min": 32, "comfortable": 36, "large": 40}


def scaled(px: int, scale: float) -> int:
    """Scale a token with the user's text-size preference, never below 1px."""
    return max(1, round(px * scale))
