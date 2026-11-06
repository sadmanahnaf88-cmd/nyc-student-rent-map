"""
Phase 4b: door-to-door weekday-morning subway commute from every NTA to every campus.

INPUT   data/raw/gtfs/gtfs_subway.zip     (p4a_download_gtfs.py)
        data/interim/nta_areas.csv        (p3b: one origin point per NTA)
        data/reference/campuses.csv       (destinations)
OUTPUT  data/interim/commute_times.csv/.xlsx   one row per campus x NTA
        data/interim/subway_stations.csv       stations with lat/lon (for maps)

THE MODEL (DECISIONS.md D-018 to D-020)
---------------------------------------
A commute is built from pieces that each have a time:

  home --walk--> station --wait--> train --ride--> ... --get off--> station --walk--> campus
                                     +--get off--> (transfer) --wait--> other train --+

We turn the subway into a GRAPH (nodes connected by edges with a time) and
let Dijkstra's shortest-path algorithm find the fastest combination.

Two kinds of nodes:
  * station node        ("st", "127")          a station complex (GTFS parent station)
  * route-at-platform   ("rs", "1", "127N")    e.g. "the 1 train at Times Sq, northbound"

Edges and their times:
  * board    station -> route-platform   = waiting time = half the AM-peak headway
  * ride     route-platform -> next one  = median scheduled time between the stops
  * get off  route-platform -> station   = time to walk off the platform (GTFS min_transfer_time)
  * transfer station -> other station    = walking transfer between complexes (GTFS transfers.txt)
  * walk     home -> station / station -> campus = straight-line distance x 1.3 at 80 m/min

Using HALF the headway as the wait is the standard assumption when people
don't time their arrival to the schedule: on average you wait half the gap.

Run from the project folder:
    python src/p4b_commute_times.py
"""
import zipfile

import networkx as nx
import numpy as np
import pandas as pd

import config

GTFS = config.DATA_RAW / "gtfs" / "gtfs_subway.zip"

# GTFS route IDs that riders know by another name. Express variants (6X etc.)
# stay separate in the graph (they have their own frequencies) but are
# labelled the way they appear on trains and maps.
RIDER_NAMES = {"6X": "6", "7X": "7", "FX": "F",
               "GS": "S (42 St)", "FS": "S (Franklin)", "H": "S (Rockaway)"}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def to_seconds(hhmmss: pd.Series) -> pd.Series:
    """GTFS times like '25:10:00' (after midnight) -> seconds since midnight."""
    parts = hhmmss.str.split(":", expand=True).astype(int)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def haversine_km(lat1, lon1, lat2, lon2):
    """Straight-line ('as the crow flies') distance in km. Works on arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def walk_minutes(km):
    return km * 1000 * config.WALK_DETOUR / config.WALK_M_PER_MIN


# ---------------------------------------------------------------------------
# 1. Read the GTFS feed
# ---------------------------------------------------------------------------
def load_gtfs():
    with zipfile.ZipFile(GTFS) as z:
        read = lambda name: pd.read_csv(z.open(name), dtype=str)
        stops, trips, stop_times, transfers = (read("stops.txt"), read("trips.txt"),
                                               read("stop_times.txt"), read("transfers.txt"))

    # Weekday trips only
    trips = trips[trips["service_id"] == "Weekday"]
    st = stop_times.merge(trips[["trip_id", "route_id"]], on="trip_id")
    st["stop_sequence"] = st["stop_sequence"].astype(int)
    st["arr"] = to_seconds(st["arrival_time"])
    st["dep"] = to_seconds(st["departure_time"])
    st = st.sort_values(["trip_id", "stop_sequence"])

    # Platform -> parent station lookup
    platforms = stops[stops["parent_station"].notna()].set_index("stop_id")["parent_station"]
    stations = stops[stops["location_type"] == "1"].copy()
    stations[["stop_lat", "stop_lon"]] = stations[["stop_lat", "stop_lon"]].astype(float)
    return st, platforms, stations, transfers


# ---------------------------------------------------------------------------
# 2. Turn the schedule into edges
# ---------------------------------------------------------------------------
def schedule_edges(st: pd.DataFrame):
    start, end = (to_seconds(pd.Series([t + ":00"])).iloc[0] for t in config.AM_PEAK)
    window_min = (end - start) / 60

    # RIDE edges: each stop and the next stop on the same trip
    nxt = st.groupby("trip_id").shift(-1)
    rides = pd.DataFrame({
        "route_id": st["route_id"], "from_platform": st["stop_id"],
        "to_platform": nxt["stop_id"], "dep": st["dep"],
        "minutes": (nxt["arr"] - st["dep"]) / 60,
    }).dropna(subset=["to_platform"])
    rides = rides[(rides["dep"] >= start) & (rides["dep"] < end)]
    rides = (rides.groupby(["route_id", "from_platform", "to_platform"], as_index=False)
                  ["minutes"].median())

    # BOARD edges: how often each route leaves each platform in the window
    in_window = st[(st["dep"] >= start) & (st["dep"] < end)]
    freq = in_window.groupby(["route_id", "stop_id"]).size().rename("departures").reset_index()
    freq["headway_min"] = window_min / freq["departures"]
    freq["wait_min"] = (freq["headway_min"] / 2).clip(upper=config.MAX_WAIT_MIN)
    return rides, freq


# ---------------------------------------------------------------------------
# 3. Build the graph
# ---------------------------------------------------------------------------
def build_graph(rides, freq, platforms, transfers) -> nx.DiGraph:
    G = nx.DiGraph()

    # Time to get off a train at each station (GTFS gives a same-station
    # "transfer" time, typically 180 s; that's the platform-change walk).
    tr = transfers.copy()
    tr["min"] = tr["min_transfer_time"].astype(float) / 60
    exit_min = tr[tr["from_stop_id"] == tr["to_stop_id"]].set_index("from_stop_id")["min"]

    for r in freq.itertuples():
        station = platforms[r.stop_id]
        rs = ("rs", r.route_id, r.stop_id)
        G.add_edge(("st", station), rs, minutes=r.wait_min, kind="wait", route=r.route_id)
        G.add_edge(rs, ("st", station), minutes=exit_min.get(station, config.STATION_EXIT_DEFAULT_MIN),
                   kind="get_off")

    for r in rides.itertuples():
        G.add_edge(("rs", r.route_id, r.from_platform), ("rs", r.route_id, r.to_platform),
                   minutes=r.minutes, kind="ride", route=r.route_id)

    for r in tr[tr["from_stop_id"] != tr["to_stop_id"]].itertuples():
        G.add_edge(("st", r.from_stop_id), ("st", r.to_stop_id), minutes=r.min, kind="transfer")
    return G


# ---------------------------------------------------------------------------
# 4. Shortest paths: every NTA -> one campus
# ---------------------------------------------------------------------------
def describe_path(G, path):
    """Split a path's time into walk / wait / ride / transfer and list the lines used."""
    parts = {"wait": 0.0, "ride": 0.0, "get_off": 0.0, "transfer": 0.0, "walk": 0.0}
    lines = []
    for a, b in zip(path, path[1:]):
        e = G.edges[a, b]
        parts[e["kind"]] += e["minutes"]
        if e["kind"] == "wait":
            lines.append(RIDER_NAMES.get(e["route"], e["route"]))
    return parts, lines


def commute_to_campus(G_base, campus, ntas, stations, station_names):
    G = G_base.copy()
    target = ("campus", campus.campus_id)

    # Egress: stations within walking distance of campus
    d_campus = haversine_km(stations["stop_lat"], stations["stop_lon"], campus.lat, campus.lon)
    near = (d_campus <= config.MAX_ACCESS_KM) | (d_campus.rank(method="first") <= config.MIN_ACCESS_STATIONS)
    for sid, km in d_campus[near].items():
        G.add_edge(("st", stations.at[sid, "stop_id"]), target,
                   minutes=walk_minutes(km), kind="walk")

    # One Dijkstra run on the REVERSED graph gives the fastest time from every
    # node TO the campus (instead of one run per NTA).
    dist, paths = nx.single_source_dijkstra(G.reverse(copy=False), target, weight="minutes")

    rows = []
    for n in ntas.itertuples():
        d_home = haversine_km(stations["stop_lat"], stations["stop_lon"], n.lat, n.lon)
        cand = (d_home <= config.MAX_ACCESS_KM) | (d_home.rank(method="first") <= config.MIN_ACCESS_STATIONS)

        best = None  # (total, access_walk, station_id)
        for sid, km in d_home[cand].items():
            node = ("st", stations.at[sid, "stop_id"])
            if node in dist:
                access = walk_minutes(km) + config.STATION_ENTRY_MIN
                total = access + dist[node]
                if best is None or total < best[0]:
                    best = (total, access, node)

        straight_km = haversine_km(n.lat, n.lon, campus.lat, campus.lon)
        direct_walk = walk_minutes(straight_km) if straight_km <= config.DIRECT_WALK_MAX_KM else np.inf

        row = {"campus_id": campus.campus_id, "nta2020": n.nta2020,
               "straight_line_km": round(straight_km, 2)}
        if best is None and direct_walk == np.inf:
            row.update(mode="unreachable")
        elif direct_walk <= (best[0] if best else np.inf):
            row.update(mode="walk", commute_min=direct_walk, walk_min=direct_walk,
                       access_walk_min=0, egress_walk_min=0,
                       wait_min=0, ride_min=0, transfer_min=0, n_transfers=0, lines="walk")
        else:
            total, access, node = best
            path = paths[node][::-1]  # reversed graph -> flip to home->campus order
            parts, lines = describe_path(G, path)
            row.update(mode="subway", commute_min=total,
                       walk_min=access + parts["walk"],
                       access_walk_min=access, egress_walk_min=parts["walk"],
                       wait_min=parts["wait"], ride_min=parts["ride"],
                       transfer_min=parts["get_off"] + parts["transfer"],
                       n_transfers=max(len(lines) - 1, 0),
                       lines=" > ".join(lines),
                       board_station=station_names[path[0][1]],
                       alight_station=station_names[path[-2][1]])
        rows.append(row)
    return rows


def main() -> None:
    st, platforms, stations, transfers = load_gtfs()
    rides, freq = schedule_edges(st)
    G = build_graph(rides, freq, platforms, transfers)
    print(f"Graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges "
          f"({len(stations)} stations, {freq['route_id'].nunique()} routes in AM peak)")

    stations = stations.reset_index(drop=True)
    station_names = stations.set_index("stop_id")["stop_name"].to_dict()
    stations[["stop_id", "stop_name", "stop_lat", "stop_lon"]].to_csv(
        config.DATA_INTERIM / "subway_stations.csv", index=False)

    ntas = pd.read_csv(config.DATA_INTERIM / "nta_areas.csv")
    ntas = ntas[(ntas["nta_type"] == "residential") & (ntas["boroname"] != "Staten Island")]
    campuses = pd.read_csv(config.CAMPUSES_FILE)

    rows = []
    for campus in campuses.itertuples():
        rows += commute_to_campus(G, campus, ntas, stations, station_names)
        print(f"  {campus.campus_name}: done")

    df = pd.DataFrame(rows)
    for c in ["commute_min", "walk_min", "access_walk_min", "egress_walk_min",
              "wait_min", "ride_min", "transfer_min"]:
        df[c] = df[c].round(1)

    # Flag trips where the model has to walk unrealistically far to/from the
    # subway. Real people there take a bus or the LIRR, which this model can't
    # see, so these times are an UPPER bound, not a real commute (D-020).
    df["needs_bus_or_rail"] = ((df["access_walk_min"] > config.MAX_SUBWAY_WALK_MIN)
                               | (df["egress_walk_min"] > config.MAX_SUBWAY_WALK_MIN))
    print(f"Trips flagged needs_bus_or_rail: {df['needs_bus_or_rail'].sum()} of {len(df)}")
    df.to_csv(config.DATA_INTERIM / "commute_times.csv", index=False)
    df.to_excel(config.DATA_INTERIM / "commute_times.xlsx", index=False)

    print(f"\nWrote {len(df):,} rows ({df['campus_id'].nunique()} campuses x {df['nta2020'].nunique()} NTAs)")
    print("Mode counts:", df["mode"].value_counts().to_dict())
    print(df.groupby("campus_id")["commute_min"].describe()[["min", "50%", "max"]].round(0).to_string())


if __name__ == "__main__":
    main()
