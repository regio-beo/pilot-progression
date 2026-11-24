"""Teaching map. Installation: python -m pip install matplotlib
Usage: python nordost_brasilien.py
"""

import argparse
import re
from math import asin, cos, isfinite, radians, sin, sqrt
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


# Approximate city centers (longitude, latitude).
CITIES = {
    "Fortaleza": (-38.54, -3.72),
    "Caicó": (-37.10, -6.46),
    "Quixadá": (-39.02, -4.97),
    "Ipueiras": (-40.71, -4.54),
    "Piripiri": (-41.78, -4.27),
}
ROUTE = ("Caicó", "Quixadá", "Ipueiras", "Piripiri")

# Approximate Atlantic coastline points from west to east.
COASTLINE = [
    (-43.4, -2.3), (-42.8, -2.7), (-42.1, -2.76), (-41.7, -2.82),
    (-41.3, -2.9), (-40.5, -2.8), (-40.2, -2.88), (-39.9, -3.12),
    (-39.25, -3.28), (-38.8, -3.52), (-38.54, -3.70), (-38.3, -3.81),
    (-37.8, -4.31), (-37.3, -4.65), (-36.75, -5.09), (-36.1, -5.08),
    (-35.5, -5.12), (-35.24, -5.62), (-35.18, -5.82), (-35.10, -6.4),
    (-34.98, -7.2), (-34.85, -7.85),
]


def great_circle_km(start, end):
    """Great-circle distance between two points (longitude, latitude)."""
    lon1, lat1 = map(radians, start)
    lon2, lat2 = map(radians, end)
    a = sin((lat2 - lat1) / 2)**2
    a += cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2)**2
    return 2 * 6371.0088 * asin(sqrt(min(1, a)))


IGC_FIX = re.compile(rb"^B[0-9]{6}([0-9]{2})([0-9]{5})([NS])"
                     rb"([0-9]{3})([0-9]{5})([EW])([AV])")


def read_igc(path):
    """Read GPS positions, leaving gaps at invalid fixes."""
    longitudes, latitudes = [], []
    with Path(path).open("rb") as file:
        for line in file:
            if not line.startswith(b"B"):
                continue
            lon = lat = float("nan")
            fix = IGC_FIX.match(line)
            if fix:
                lat_deg, lat_min, ns, lon_deg, lon_min, ew, status = fix.groups()
                lat_deg, lat_min, lon_deg, lon_min = map(
                    int, (lat_deg, lat_min, lon_deg, lon_min))
                if (status == b"A" and lat_min < 60000 and lon_min < 60000
                        and lat_deg + lat_min / 60000 <= 90
                        and lon_deg + lon_min / 60000 <= 180):
                    lat = (lat_deg + lat_min / 60000) * (-1 if ns == b"S" else 1)
                    lon = (lon_deg + lon_min / 60000) * (-1 if ew == b"W" else 1)
            longitudes.append(lon)
            latitudes.append(lat)
    if not any(map(isfinite, longitudes)):
        raise ValueError(f"{path}: no valid GPS positions")
    return longitudes, latitudes


def draw_map(flights=()):
    """Draw the map with optional (IGC path, label) pairs."""
    fig, ax = plt.subplots(figsize=(11, 8), layout="constrained")
    ax.set_facecolor("#e1f3fa")
    longitudes, latitudes = zip(*COASTLINE)
    ax.fill([*longitudes, -34.85, -43.4], [*latitudes, -8.2, -8.2],
            color="#f6ecd6", zorder=1)
    ax.plot(longitudes, latitudes, color="#68868c", linewidth=1.2, zorder=2)

    route_color = "#773d50"
    ax.plot(*zip(*(CITIES[name] for name in ROUTE)),
            color=route_color, linewidth=2, zorder=4)
    total_km = 0
    for start_name, end_name in zip(ROUTE, ROUTE[1:]):
        start, end = CITIES[start_name], CITIES[end_name]
        segment_km = great_circle_km(start, end)
        total_km += segment_km
        ax.annotate(f"{total_km:.0f} km",
                    end, xytext=(0, -9), textcoords="offset points",
                    ha="center", va="top", fontsize=10, color=route_color,
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none",
                              alpha=0.93), zorder=7)

    for path, label in flights:
        longitudes, latitudes = read_igc(path)
        track_color = "#e66a00"
        ax.plot(longitudes, latitudes, color=track_color, linewidth=1.0,
                alpha=1.0, zorder=3)
        endpoint = next((lon, lat) for lon, lat in
                        zip(reversed(longitudes), reversed(latitudes))
                        if isfinite(lon))
        ax.scatter(*endpoint, s=18, color=track_color, zorder=5)
        ax.annotate(label, endpoint, xytext=(-3, 0),
                    textcoords="offset points", ha="right", va="top", fontsize=9, color="#9b4600",
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none",
                              alpha=0.93), zorder=6)

    for name, (lon, lat) in CITIES.items():
        ax.scatter(lon, lat, s=84 if name == "Fortaleza" else 42, color="#253847", edgecolor="white",
                   linewidth=0.8, zorder=5)
        ax.annotate(name, (lon, lat), xytext=(6, 8), textcoords="offset points",
                    fontsize=11, fontweight="bold", zorder=6)

    # Equal spacing between arrow tails, with bearings from WNW to NW.
    trade_wind_arrows = [
        (-41.2, -6.3, 292.5),
        (-39.35, -6.65, 303.75),
        (-37.5, -7.0, 315),
    ]
    for x, y, bearing in trade_wind_arrows:
        angle = radians(bearing)
        dx = sin(angle) * 0.72 * sqrt(2)
        dy = cos(angle) * 0.72 * sqrt(2)
        ax.annotate("", xy=(x + dx, y + dy), xytext=(x, y),
                    arrowprops=dict(arrowstyle="-|>", color="#b54d19",
                                    lw=2.6, mutation_scale=17), zorder=3)
    for x, y in [(-40.15, -2.32), (-36.35, -4.43)]:
        ax.annotate("", xy=(x - 0.4, y - 0.20), xytext=(x, y),
                    arrowprops=dict(arrowstyle="-|>", color="#087597",
                                    lw=2.6, mutation_scale=17), zorder=3)

    ax.text(-37.8, -2.35, "Atlantic Ocean", color="#37687b", fontsize=14,
            fontstyle="italic")
    ax.set(xlim=(-42.8, -34.6), ylim=(-7.7, -1.9))
    ax.set_aspect(1 / cos(radians(5)))
    ax.set_xticks(range(-42, -34), [f"{n}° W" for n in range(42, 34, -1)])
    ax.set_yticks(range(-7, -1), [f"{n}° S" for n in range(7, 1, -1)])
    ax.grid(color="#6c8792", alpha=0.22, linestyle=":")
    ax.set_axisbelow(False)
    ax.legend(handles=[
        Line2D([], [], color="#b54d19", lw=2.6, label="Southeast Trade Wind"),
        Line2D([], [], color="#087597", lw=2.6, label="Sea Breeze"),
        Line2D([], [], color="#e66a00", lw=2.6, label="Longest Flight")
    ], loc="lower left", framealpha=0.95)
    return fig


if __name__ == "__main__":
    #parser = argparse.ArgumentParser(description="Map with optional IGC flight tracks")
    #parser.add_argument("--igc", nargs=2, action="append", default=[],
    #                    metavar=("FILE", "LABEL"), help="Repeat for each flight")
    #args = parser.parse_args()
    #flights = args.igc
    flights = [
        ("2026-09-27-XCT-SRO-01.igc", "Serena"),
        ("2026-09-30-XCT-ODI-03.igc", ""),
        ("2026-09-30-XCT-SBE-01.igc", "Sebastian"),
        ("2026-10-04-XCT-BFA-09.igc", ""),
        ("2026-10-09-XNA-B742ED5D59ABC0A72F9D236491342B0D-01.igc", ""),
        ("2026-10-04-XCT-SWE-01.igc", "Stephanie"),
        ("2026-10-06-XCT-NSU-01.igc", "Nico"),
        ("2026-10-08-XCT-PAE-01.igc", "Philipp"),
        ("2026-10-09-XCT-CRI-01.igc", "Christoph, Benjamin,\nOlivier, Dorian")
    ]
    flights = []
    try:
        figure = draw_map(flights)
    except (OSError, ValueError) as error:
        print(str(error))
    figure.savefig(Path(__file__).with_name("nordost_brasilien.png"), dpi=600)
    plt.show()
