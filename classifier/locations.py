"""Official barangays of Santa Maria, Ilocos Sur (for location / coverage pickers)."""

from __future__ import annotations

import math

SANTA_MARIA_BARANGAYS = (
    "Ag-agrao",
    "Ampuagan",
    "Baballasioan",
    "Baliw Daya",
    "Baliw Laud",
    "Bia-o",
    "Butir",
    "Cabaroan",
    "Danuman East",
    "Danuman West",
    "Dunglayan",
    "Gusing",
    "Langaoan",
    "Laslasong Norte",
    "Laslasong Sur",
    "Laslasong West",
    "Lesseb",
    "Lingsat",
    "Lubong",
    "Maynganay Norte",
    "Maynganay Sur",
    "Nagsayaoan",
    "Nagtupacan",
    "Nalvo",
    "Pacang",
    "Penned",
    "Poblacion Norte",
    "Poblacion Sur",
    "Silag",
    "Sumagui",
    "Suso",
    "Tangaoan",
    "Tinaan",
)

SANTA_MARIA_BARANGAY_SET = frozenset(SANTA_MARIA_BARANGAYS)

# Approximate barangay centers inside Santa Maria (for GPS → name resolution).
SANTA_MARIA_BARANGAY_COORDS = {
    "Ag-agrao": (17.3791, 120.5080),
    "Ampuagan": (17.3553, 120.4963),
    "Baballasioan": (17.3859, 120.5190),
    "Baliw Daya": (17.3697, 120.4840),
    "Baliw Laud": (17.3730, 120.4740),
    "Bia-o": (17.3848, 120.4556),
    "Butir": (17.3751, 120.5046),
    "Cabaroan": (17.3707, 120.4978),
    "Danuman East": (17.3755, 120.4695),
    "Danuman West": (17.3735, 120.4625),
    "Dunglayan": (17.3467, 120.4803),
    "Gusing": (17.3836, 120.5144),
    "Langaoan": (17.3644, 120.4973),
    "Laslasong Norte": (17.3905, 120.4944),
    "Laslasong Sur": (17.3860, 120.4975),
    "Laslasong West": (17.3880, 120.4895),
    "Lesseb": (17.3448, 120.5054),
    "Lingsat": (17.3769, 120.4540),
    "Lubong": (17.3513, 120.4800),
    "Maynganay Norte": (17.3861, 120.4951),
    "Maynganay Sur": (17.3807, 120.4764),
    "Nagsayaoan": (17.3520, 120.4680),
    "Nagtupacan": (17.3830, 120.4790),
    "Nalvo": (17.3631, 120.4551),
    "Pacang": (17.3566, 120.4944),
    "Penned": (17.3485, 120.4920),
    "Poblacion Norte": (17.3685, 120.4825),
    "Poblacion Sur": (17.3651, 120.4815),
    "Silag": (17.3609, 120.5091),
    "Sumagui": (17.3580, 120.4720),
    "Suso": (17.3594, 120.4611),
    "Tangaoan": (17.3364, 120.4804),
    "Tinaan": (17.3817, 120.4846),
}


def barangay_choices(*, blank_label="— Select barangay —", extra=""):
    """Dropdown choices: optional blank, then all Santa Maria barangays.

    `extra` keeps a legacy / free-text value selectable when editing old rows.
    """
    choices = [(name, name) for name in SANTA_MARIA_BARANGAYS]
    extra = (extra or "").strip()
    if extra and extra not in SANTA_MARIA_BARANGAY_SET:
        choices = [(extra, extra)] + choices
    if blank_label is None:
        return choices
    return [("", blank_label)] + choices


def normalize_barangay(value):
    """Return a known barangay name, or stripped free text, or empty string."""
    value = (value or "").strip()
    if not value:
        return ""
    for name in SANTA_MARIA_BARANGAYS:
        if name.casefold() == value.casefold():
            return name
    return value[:120]


def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_barangay(latitude, longitude, *, max_km=12.0):
    """Return the nearest Santa Maria barangay name for GPS coordinates, or "".

    `max_km` rejects fixes that are clearly outside the municipality.
    """
    try:
        lat = float(latitude)
        lon = float(longitude)
    except (TypeError, ValueError):
        return ""
    best_name = ""
    best_km = None
    for name, (blat, blon) in SANTA_MARIA_BARANGAY_COORDS.items():
        dist = _haversine_km(lat, lon, blat, blon)
        if best_km is None or dist < best_km:
            best_km = dist
            best_name = name
    if best_km is None or best_km > max_km:
        return ""
    return best_name
