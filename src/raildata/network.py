"""Static description of the synthetic rail network.

Station names and approximate coordinates are real places; the operators,
lines, timetables and all realised events are synthetic.
"""

from __future__ import annotations

# stop_id -> (stop_name, lat, lon, is_hub)
STATIONS: dict[str, tuple[str, float, float, bool]] = {
    "PARIS_GDL": ("Paris Gare de Lyon", 48.8443, 2.3744, True),
    "MELUN": ("Melun", 48.5274, 2.6553, False),
    "FONTAINEBLEAU": ("Fontainebleau-Avon", 48.4170, 2.7260, False),
    "MORET": ("Moret-Veneux-les-Sablons", 48.3790, 2.7990, False),
    "SENS": ("Sens", 48.1990, 3.2830, False),
    "LAROCHE": ("Laroche-Migennes", 47.9590, 3.5200, False),
    "DIJON": ("Dijon-Ville", 47.3233, 5.0273, True),
    "BEAUNE": ("Beaune", 47.0230, 4.8440, False),
    "CHALON": ("Chalon-sur-Saone", 46.7810, 4.8430, False),
    "TOURNUS": ("Tournus", 46.5640, 4.9090, False),
    "MACON": ("Macon-Ville", 46.3010, 4.8270, False),
    "VILLEFRANCHE": ("Villefranche-sur-Saone", 45.9850, 4.7210, False),
    "LYON_PD": ("Lyon Part-Dieu", 45.7606, 4.8594, True),
    "LYON_PERRACHE": ("Lyon Perrache", 45.7487, 4.8264, False),
    "BOURGOIN": ("Bourgoin-Jallieu", 45.5880, 5.2790, False),
    "LA_TOUR_DU_PIN": ("La Tour-du-Pin", 45.5650, 5.4440, False),
    "VOIRON": ("Voiron", 45.3640, 5.5890, False),
    "GRENOBLE": ("Grenoble", 45.1913, 5.7145, True),
    "MARSEILLE_SC": ("Marseille Saint-Charles", 43.3027, 5.3806, True),
    "AUBAGNE": ("Aubagne", 43.2930, 5.5660, False),
    "LA_CIOTAT": ("La Ciotat", 43.2010, 5.6260, False),
    "BANDOL": ("Bandol", 43.1410, 5.7550, False),
    "TOULON": ("Toulon", 43.1281, 5.9300, True),
    "VITROLLES": ("Vitrolles Aeroport Marseille Provence", 43.4180, 5.2380, False),
    "MIRAMAS": ("Miramas", 43.5800, 5.0020, False),
    "ARLES": ("Arles", 43.6850, 4.6320, False),
    "NIMES": ("Nimes", 43.8325, 4.3660, True),
    "MONTPELLIER": ("Montpellier Saint-Roch", 43.6046, 3.8807, True),
    "LILLE_FL": ("Lille Flandres", 50.6365, 3.0711, True),
    "LENS": ("Lens", 50.4270, 2.8280, False),
    "ARRAS": ("Arras", 50.2870, 2.7820, False),
    "ALBERT": ("Albert", 50.0010, 2.6520, False),
    "AMIENS": ("Amiens", 49.8907, 2.3083, True),
    "STRASBOURG": ("Strasbourg", 48.5850, 7.7346, True),
    "SELESTAT": ("Selestat", 48.2600, 7.4430, False),
    "COLMAR": ("Colmar", 48.0730, 7.3470, False),
    "MULHOUSE": ("Mulhouse", 47.7420, 7.3430, True),
    "SAINT_LOUIS": ("Saint-Louis (Haut-Rhin)", 47.5900, 7.5560, False),
    "BASEL_SBB": ("Basel SBB", 47.5476, 7.5897, True),
    "BORDEAUX_SJ": ("Bordeaux Saint-Jean", 44.8258, -0.5562, True),
    "LIBOURNE": ("Libourne", 44.9150, -0.2390, False),
    "COUTRAS": ("Coutras", 45.0410, -0.1290, False),
    "ANGOULEME": ("Angouleme", 45.6530, 0.1650, True),
}

# route_id -> (agency_id, short_name, long_name, stops, base_headway_min, reliability)
# reliability < 1 means a line that is more delay-prone than average.
ROUTES: dict[str, tuple[str, str, str, list[str], int, float]] = {
    "R_BOU": (
        "SYN_REG",
        "R1",
        "Paris - Dijon (regional)",
        ["PARIS_GDL", "MELUN", "FONTAINEBLEAU", "MORET", "SENS", "LAROCHE", "DIJON"],
        60,
        0.85,
    ),
    "R_SAO": (
        "SYN_REG",
        "R2",
        "Dijon - Lyon (Saone valley)",
        [
            "DIJON",
            "BEAUNE",
            "CHALON",
            "TOURNUS",
            "MACON",
            "VILLEFRANCHE",
            "LYON_PD",
            "LYON_PERRACHE",
        ],
        60,
        1.0,
    ),
    "R_ALP": (
        "SYN_REG",
        "R3",
        "Lyon - Grenoble",
        ["LYON_PD", "BOURGOIN", "LA_TOUR_DU_PIN", "VOIRON", "GRENOBLE"],
        30,
        0.9,
    ),
    "R_COT": (
        "SYN_REG",
        "R4",
        "Marseille - Toulon",
        ["MARSEILLE_SC", "AUBAGNE", "LA_CIOTAT", "BANDOL", "TOULON"],
        30,
        0.75,
    ),
    "R_LAN": (
        "SYN_REG",
        "R5",
        "Marseille - Montpellier",
        ["MARSEILLE_SC", "VITROLLES", "MIRAMAS", "ARLES", "NIMES", "MONTPELLIER"],
        60,
        0.95,
    ),
    "R_NOR": (
        "SYN_REG",
        "R6",
        "Lille - Amiens",
        ["LILLE_FL", "LENS", "ARRAS", "ALBERT", "AMIENS"],
        60,
        1.05,
    ),
    "R_ALS": (
        "SYN_REG",
        "R7",
        "Strasbourg - Basel",
        ["STRASBOURG", "SELESTAT", "COLMAR", "MULHOUSE", "SAINT_LOUIS", "BASEL_SBB"],
        30,
        1.15,
    ),
    "R_AQU": (
        "SYN_REG",
        "R8",
        "Bordeaux - Angouleme",
        ["BORDEAUX_SJ", "LIBOURNE", "COUTRAS", "ANGOULEME"],
        60,
        1.0,
    ),
    "IC_PLM": (
        "SYN_IC",
        "IC1",
        "Paris - Lyon - Marseille (intercity)",
        ["PARIS_GDL", "DIJON", "MACON", "LYON_PD", "MARSEILLE_SC"],
        120,
        0.9,
    ),
}

AGENCIES = {
    "SYN_REG": ("Synthetic Regional Rail", "https://example.org/regional"),
    "SYN_IC": ("Synthetic Intercity", "https://example.org/intercity"),
}

# Average commercial speed in km/h used to derive scheduled running times.
SPEED_KMH = {"SYN_REG": 85.0, "SYN_IC": 140.0}
