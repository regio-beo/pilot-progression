"""Teaching map. Installation: python -m pip install earthkit-plots
Usage: python nordost_brasilien.py
"""

import re
from math import asin, ceil, cos, degrees, floor, isfinite, radians, sin, sqrt
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
from earthkit.plots import Map
from matplotlib.lines import Line2D


# Approximate city centers (longitude, latitude).
CITIES = {
    "Fortaleza": (-38.54, -3.72),
    "Natal": (-35.21, -5.79),
    "Caicó": (-37.10, -6.46),
    "Quixadá": (-39.02, -4.97),
    "Ipueiras": (-40.71, -4.54),
    "Piripiri": (-41.78, -4.27),
}
ROUTE = ("Caicó", "Quixadá", "Ipueiras", "Piripiri")

FLIGHT_ORANGE = "#e66a00"
FLIGHT_GOLD = "#d4a017"

#MAP_EXTENT = (-42.9, -36.0, -7.2, -1.9)
MAP_EXTENT = (-42.8, -34.6, -7.7, -1.9)


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
    """Draw the map with optional (IGC path, label, color) entries."""
    projection = ccrs.PlateCarree()
    chart = Map(domain=list(MAP_EXTENT), crs=projection)
    ax = chart.ax
    # Use one geometry for the land fill and its coastline.
    land = cfeature.NaturalEarthFeature("physical", "land", "10m")
    ax.add_feature(land, facecolor="#f6ecd6", edgecolor="#68868c",
                   linewidth=1.2, zorder=1)
    fig = ax.figure
    fig.set_size_inches(11, 8)
    fig.set_layout_engine("constrained")
    ax.set_facecolor("#e1f3fa")

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

    for path, label, track_color in flights:
        longitudes, latitudes = read_igc(path)
        ax.plot(longitudes, latitudes, color=track_color, linewidth=1.0,
                alpha=1.0, zorder=3)
        endpoint = next((lon, lat) for lon, lat in
                        zip(reversed(longitudes), reversed(latitudes))
                        if isfinite(lon))
        ax.scatter(*endpoint, s=18, color=track_color, zorder=5)
        ax.annotate(label, endpoint, xytext=(-3, 0),
                    textcoords="offset points", ha="right", va="top", fontsize=9, color=track_color,
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none",
                              alpha=0.93), zorder=6)

    for name, (lon, lat) in CITIES.items():
        ax.scatter(lon, lat, s=84 if name in ("Fortaleza", "Natal") else 42, color="#253847", edgecolor="white",
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

    ax.text(-35.8, -2.35, "Atlantic Ocean", color="#37687b", fontsize=14,
            fontstyle="italic")
    west, east, south, north = MAP_EXTENT
    # Compute the longitude span for a 100 km great-circle distance
    # between endpoints at the scale bar's latitude.
    scale_lat = south + 0.08 * (north - south)
    scale_east = east - 0.05 * (east - west)
    scale_span = degrees(2 * asin(sin(100 / (2 * 6371.0088))
                                  / cos(radians(scale_lat))))
    scale_west = scale_east - scale_span
    ax.plot([scale_west, scale_east], [scale_lat, scale_lat],
            color="#253847", linewidth=2, marker="|", markersize=8, zorder=9)
    ax.annotate("100 km", ((scale_west + scale_east) / 2, scale_lat),
                xytext=(0, 6), textcoords="offset points",
                ha="center", va="bottom", fontsize=9, color="#253847", zorder=9)

    longitude_ticks = range(ceil(west), floor(east) + 1)
    latitude_ticks = range(ceil(south), floor(north) + 1)
    ax.set_xticks(longitude_ticks, [f"{abs(n)}° W" for n in longitude_ticks])
    ax.set_yticks(latitude_ticks, [f"{abs(n)}° S" for n in latitude_ticks])
    ax.set_extent(MAP_EXTENT, crs=projection)
    ax.set_aspect(1 / cos(radians(5)))
    ax.grid(color="#6c8792", alpha=0.22, linestyle=":")
    ax.set_axisbelow(False)
    ax.legend(handles=[
        Line2D([], [], color="#b54d19", lw=2.6, label="Southeast Trade Wind"),
        Line2D([], [], color="#087597", lw=2.6, label="Sea Breeze"),
        Line2D([], [], color=FLIGHT_ORANGE, lw=2.6, label="Flight Track"),
        #Line2D([], [], color=FLIGHT_GOLD, lw=2.6, label="WR Flight")
    ], loc="lower left", framealpha=0.95)
    return fig


if __name__ == "__main__":
    flights = [
        ("2026-09-27-XCT-SRO-01.igc", "Serena", FLIGHT_ORANGE),
        ("2026-09-30-XCT-ODI-03.igc", "", FLIGHT_ORANGE),
        ("2026-09-30-XCT-SBE-01.igc", "Sebastian", FLIGHT_ORANGE),
        ("2026-10-04-XCT-BFA-09.igc", "", FLIGHT_ORANGE),
        ("2026-10-09-XNA-B742ED5D59ABC0A72F9D236491342B0D-01.igc", "", FLIGHT_ORANGE),
        ("2026-10-04-XCT-SWE-01.igc", "Stephanie", FLIGHT_ORANGE),
        ("2026-10-06-XCT-NSU-01.igc", "Nico", FLIGHT_GOLD),
        ("2026-10-08-XCT-PAE-01.igc", "Philipp", FLIGHT_ORANGE),
        ("2026-10-09-XCT-CRI-01.igc", "Christoph, Benjamin,\nOlivier, Dorian", FLIGHT_ORANGE),
    ]
    try:
        figure = draw_map(flights)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error
    figure.savefig(Path(__file__).with_name("nordost_brasilien.png"), dpi=600)
    plt.show()
