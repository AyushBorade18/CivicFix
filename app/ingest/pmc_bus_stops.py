"""PMPML bus stops from PMC Open Data (PMC.zip) -> sensitive_sites, kind bus_stop.

Source: "BRT & Non BRT Route Details & Bus Stop LatLong.xls", the two
route-stop sheets (one row per stop per route, with LAT/LONG). The same
physical stop repeats on many routes with slightly different coordinates,
so rows are collapsed with the OSM loader's same-kind 30 m dedupe, and only
stops inside the 58 PMC wards are kept.

Run: python -m app.ingest.pmc_bus_stops
"""
import zipfile

import xlrd

from app.ingest.osm_sensitive_sites import deduplicate_sites, insert_sites_in_wards

ZIP_PATH = "PMC.zip"
XLS_MEMBER = "PMC/Road/BRT & Non BRT Route Details & Bus Stop LatLong.xls"
ROUTE_STOP_SHEETS = ("376  Rout name, Stage & LL", "Short Rout name Satge")
# Wide Pune-region box: anything outside is a blank, zero or swapped coordinate.
LAT_RANGE = (18.2, 18.9)
LON_RANGE = (73.5, 74.3)


def parse_stop_rows(rows: list[list]) -> list[dict]:
    """Route-stop sheet rows (first row is the header) -> site dicts in the
    shape deduplicate_sites()/insert_sites_in_wards() expect.
    """
    header = [str(h).strip() for h in rows[0]]
    code, name, lat_col, lon_col = (header.index(h) for h in ("Stop Code", "Stop Name", "LAT", "LONG"))
    sites = []
    for row in rows[1:]:
        lat, lon = row[lat_col], row[lon_col]
        if not isinstance(lat, float) or not isinstance(lon, float):
            continue
        if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
            continue
        sites.append({
            "source_id": f"pmc_pmpml:{str(row[code]).strip()}",
            "category": "bus_stop",
            "name": str(row[name]).strip() or None,
            "lat": lat,
            "lon": lon,
        })
    return sites


def read_stops(zip_path: str = ZIP_PATH) -> list[dict]:
    with zipfile.ZipFile(zip_path) as z:
        book = xlrd.open_workbook(file_contents=z.read(XLS_MEMBER))
    sites = []
    for sheet_name in ROUTE_STOP_SHEETS:
        sheet = book.sheet_by_name(sheet_name)
        sites.extend(parse_stop_rows([sheet.row_values(r) for r in range(sheet.nrows)]))
    return sites


def load_pmc_bus_stops(zip_path: str = ZIP_PATH, conn=None) -> int:
    rows = read_stops(zip_path)
    # ponytail: dedupe is O(n^2) over unique stops (~seconds); pre-collapsing exact repeats keeps n small
    unique = list({(s["name"], round(s["lat"], 4), round(s["lon"], 4)): s for s in rows}.values())
    sites = deduplicate_sites(unique)
    inserted = insert_sites_in_wards(sites, conn)
    print(f"{len(rows)} route-stop rows -> {len(sites)} physical stops -> {inserted} inside PMC wards")
    return inserted


if __name__ == "__main__":
    load_pmc_bus_stops()
