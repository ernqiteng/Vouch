"""A small offline lookup from UK town names to coordinates.

Enough for the demo's distance ranking without calling a geocoding API.
Postcodes and unlisted towns aren't recognised; locate() returns None for them.
"""
import re

TOWNS: dict[str, tuple[float, float]] = {
    "Leeds": (53.8008, -1.5491),
    "Manchester": (53.4808, -2.2426),
    "London": (51.5072, -0.1276),
    "Birmingham": (52.4862, -1.8904),
    "Bristol": (51.4545, -2.5879),
    "Sheffield": (53.3811, -1.4701),
    "Liverpool": (53.4084, -2.9916),
    "Newcastle": (54.9783, -1.6178),
    "Nottingham": (52.9548, -1.1581),
    "Edinburgh": (55.9533, -3.1883),
    "Glasgow": (55.8642, -4.2518),
    "Cardiff": (51.4816, -3.1791),
    "Aberdeen": (57.1497, -2.0943),
    "Belfast": (54.5973, -5.9301),
    "Bradford": (53.7960, -1.7594),
    "Brighton": (50.8225, -0.1372),
    "Cambridge": (52.2053, 0.1218),
    "Coventry": (52.4068, -1.5197),
    "Derby": (52.9225, -1.4746),
    "Dundee": (56.4620, -2.9707),
    "Exeter": (50.7184, -3.5339),
    "Huddersfield": (53.6458, -1.7850),
    "Hull": (53.7676, -0.3274),
    "Leicester": (52.6369, -1.1398),
    "Newport": (51.5842, -2.9977),
    "Norwich": (52.6309, 1.2974),
    "Oxford": (51.7520, -1.2577),
    "Plymouth": (50.3755, -4.1427),
    "Portsmouth": (50.8198, -1.0880),
    "Reading": (51.4543, -0.9781),
    "Salford": (53.4875, -2.2901),
    "Southampton": (50.9097, -1.4044),
    "Stockport": (53.4106, -2.1575),
    "Sunderland": (54.9069, -1.3838),
    "Swansea": (51.6214, -3.9436),
    "Wakefield": (53.6833, -1.4977),
    "York": (53.9591, -1.0815),
}

_BY_NAME = {name.lower(): coords for name, coords in TOWNS.items()}


def locate(location: str | None) -> tuple[float, float] | None:
    """Coordinates for a town name, e.g. "Leeds" or "central Leeds, LS1"."""
    if not location:
        return None
    text = location.strip().lower()
    if text in _BY_NAME:
        return _BY_NAME[text]
    for word in re.findall(r"[a-z]+", text):
        if word in _BY_NAME:
            return _BY_NAME[word]
    return None
