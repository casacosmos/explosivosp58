#!/usr/bin/env python3
"""
Create a uniform buffer around input geometry and export as KMZ (and optional GeoJSON).

Inputs supported:
- KMZ (.kmz) containing KML LineString/Polygon
- Session JSON (.json) in the project schema (EPSG:3857 rings/paths)

The buffer distance is specified in units (meters/feet/miles/km). For KMZ inputs, the
geometry is reprojected to EPSG:3857 (meters) before buffering. For Session JSON, the
geometry is already in EPSG:3857 so the numeric buffer matches meters directly.

Usage examples:
  python create_universal_buffer_kmz.py input.kmz -r 100 -u meters -o site_buffer -d output/
  python create_universal_buffer_kmz.py session.json -r 250 -u feet

Outputs:
- KMZ written to output dir (default cwd). If -o is omitted, a sensible default is used.
- Optionally a GeoJSON file is also written when --geojson is provided.
"""

from __future__ import annotations

import argparse
import json
import os
import zipfile
from typing import List, Tuple, Optional

from pyproj import Transformer
from shapely.geometry import Polygon, LineString, MultiPolygon, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid


def _units_to_meters(value: float, unit: str) -> float:
    unit = (unit or 'meters').lower()
    if unit in ('m', 'meter', 'meters'):
        return float(value)
    if unit in ('ft', 'foot', 'feet'):
        return float(value) * 0.3048
    if unit in ('mi', 'mile', 'miles'):
        return float(value) * 1609.344
    if unit in ('km', 'kilometer', 'kilometers'):
        return float(value) * 1000.0
    raise ValueError(f"Unsupported unit: {unit}")


def _safe_name(stem: str) -> str:
    safe = "".join(c for c in stem if c.isalnum() or c in (' ', '-', '_')).strip()
    return safe.replace(' ', '_') or 'buffer'


def _read_kmz_geoms_to_3857(kmz_path: str):
    """Extract LineString/Polygon coordinates from KMZ (KML) and return list of shapely geometries in EPSG:3857."""
    with zipfile.ZipFile(kmz_path, 'r') as kmz:
        kml_names = [n for n in kmz.namelist() if n.lower().endswith('.kml')]
        if not kml_names:
            raise ValueError('No .kml file found in KMZ')
        kml_text = kmz.read(kml_names[0]).decode('utf-8', errors='ignore')

    # Very lightweight KML parsing: we only look for <coordinates> inside LineString or Polygon rings
    # For robustness we use xml.etree
    import xml.etree.ElementTree as ET
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    root = ET.fromstring(kml_text)

    coords_blocks: List[Tuple[str, str]] = []  # (kind, text)
    # LineString
    for node in root.findall('.//kml:LineString/kml:coordinates', ns):
        txt = (node.text or '').strip()
        if txt:
            coords_blocks.append(('line', txt))
    # Polygon outer rings
    for node in root.findall('.//kml:Polygon/kml:outerBoundaryIs/kml:LinearRing/kml:coordinates', ns):
        txt = (node.text or '').strip()
        if txt:
            coords_blocks.append(('poly', txt))

    if not coords_blocks:
        raise ValueError('No LineString/Polygon coordinates found in KML')

    to_3857 = Transformer.from_crs('EPSG:4326', 'EPSG:3857', always_xy=True)
    geoms_3857 = []
    for kind, txt in coords_blocks:
        pts4326: List[Tuple[float, float]] = []
        for token in txt.split():
            parts = token.split(',')
            if len(parts) >= 2:
                try:
                    lon = float(parts[0]); lat = float(parts[1])
                    pts4326.append((lon, lat))
                except Exception:
                    continue
        if len(pts4326) < 2:
            continue
        pts3857 = [to_3857.transform(lon, lat) for lon, lat in pts4326]
        if kind == 'line':
            geoms_3857.append(LineString(pts3857))
        else:
            # Ensure ring closure
            if pts3857[0] != pts3857[-1]:
                pts3857 = pts3857 + [pts3857[0]]
            geoms_3857.append(Polygon(pts3857))

    if not geoms_3857:
        raise ValueError('No valid geometries could be built from the KMZ')
    return geoms_3857


def _read_session_json_geoms_to_3857(json_path: str):
    """Extract rings/paths from session JSON and return list of shapely geometries in EPSG:3857."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    geoms = []
    items = data if isinstance(data, list) else [data]
    for item in items:
        # Prefer layers.Project1
        for layer in item.get('layers', []):
            if layer.get('id') == 'Project1':
                src = layer.get('source') or []
                for feat in src:
                    geom = (feat or {}).get('geometry') or {}
                    if 'rings' in geom:
                        for ring in geom['rings']:
                            if len(ring) >= 3:
                                geoms.append(Polygon(ring))
                    if 'paths' in geom:
                        for path in geom['paths']:
                            if len(path) >= 2:
                                geoms.append(LineString(path))
        # Fallback: graphics
        for g in item.get('graphics', []):
            geom = (g or {}).get('geometry') or {}
            if 'rings' in geom:
                for ring in geom['rings']:
                    if len(ring) >= 3:
                        geoms.append(Polygon(ring))
            if 'paths' in geom:
                for path in geom['paths']:
                    if len(path) >= 2:
                        geoms.append(LineString(path))
    if not geoms:
        raise ValueError('No rings/paths found in session JSON')
    return geoms


def _kml_for_polygon(name: str, coords_4326: List[Tuple[float, float]]) -> str:
    # Ensure closure
    if coords_4326 and coords_4326[0] != coords_4326[-1]:
        coords_4326 = coords_4326 + [coords_4326[0]]
    coord_str = ' '.join([f"{lon},{lat},0" for lon, lat in coords_4326])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{name}</name>
    <Placemark>
      <name>{name}</name>
      <Style>
        <PolyStyle><color>4d0000ff</color></PolyStyle>
        <LineStyle><color>ff0000ff</color><width>2</width></LineStyle>
      </Style>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>{coord_str}</coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>
"""


def _write_kmz(kml_str: str, kmz_path: str) -> str:
    with zipfile.ZipFile(kmz_path, 'w', zipfile.ZIP_DEFLATED) as kmz:
        kmz.writestr('doc.kml', kml_str)
    return kmz_path


def _maybe_write_geojson(geom_4326: Polygon | MultiPolygon, out_path: Optional[str]):
    if not out_path:
        return
    import json as _json
    from shapely.geometry import mapping as _mapping
    fc = {
        'type': 'FeatureCollection',
        'features': [{
            'type': 'Feature',
            'properties': {},
            'geometry': _mapping(geom_4326)
        }]
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        _json.dump(fc, f)


def create_buffer_kmz(input_path: str, radius: float, unit: str = 'meters', output_name: Optional[str] = None,
                      output_dir: str = '.', segments: int = 16, geojson: bool = False) -> Tuple[str, Optional[str]]:
    """Create a buffer KMZ from KMZ or session JSON input.

    Returns (kmz_path, geojson_path_or_none)
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input not found: {input_path}")

    stem = os.path.splitext(os.path.basename(input_path))[0]
    base = _safe_name(output_name or f"{stem}_buffer_{int(radius)}{(unit or 'm')[0]}")
    os.makedirs(output_dir or '.', exist_ok=True)

    # Read input geometry in EPSG:3857
    ext = os.path.splitext(input_path)[1].lower()
    if ext == '.kmz':
        geoms_3857 = _read_kmz_geoms_to_3857(input_path)
    elif ext == '.json':
        geoms_3857 = _read_session_json_geoms_to_3857(input_path)
    else:
        raise ValueError('Unsupported input type. Provide a .kmz or session .json')

    # Union and buffer
    geom = unary_union(geoms_3857)
    # Fix if invalid
    geom = make_valid(geom)
    distance_m = _units_to_meters(radius, unit)
    # EPSG:3857 units are meters
    buffered = geom.buffer(distance_m, resolution=max(1, int(segments)))
    buffered = make_valid(buffered)

    # Choose a polygon to output: if MultiPolygon, take union; if still MultiPolygon, select largest
    if isinstance(buffered, MultiPolygon):
        # Keep the union as MultiPolygon but KML writer supports single polygon
        # choose the largest by area
        largest = max(buffered.geoms, key=lambda g: g.area)
        buffered = largest
    elif isinstance(buffered, LineString):
        # Very unlikely after buffer, but guard
        buffered = buffered.buffer(0.01)

    # Reproject to EPSG:4326 for KML
    to_4326 = Transformer.from_crs('EPSG:3857', 'EPSG:4326', always_xy=True)
    if isinstance(buffered, Polygon):
        exterior = list(buffered.exterior.coords)
        coords_4326 = [to_4326.transform(x, y) for x, y in exterior]
        kml = _kml_for_polygon(base, coords_4326)
    else:
        # For rare cases where make_valid returns GeometryCollection etc., coerce to polygon if possible
        poly = None
        try:
            if hasattr(buffered, 'geoms'):
                polys = [g for g in buffered.geoms if isinstance(g, Polygon)]
                if polys:
                    poly = max(polys, key=lambda g: g.area)
        except Exception:
            pass
        if not poly:
            raise ValueError('Buffered geometry is not a polygon and cannot be exported to KML polygon')
        exterior = list(poly.exterior.coords)
        coords_4326 = [to_4326.transform(x, y) for x, y in exterior]
        kml = _kml_for_polygon(base, coords_4326)

    kmz_path = os.path.join(output_dir, f"{base}.kmz")
    _write_kmz(kml, kmz_path)

    geojson_path = None
    if geojson:
        # Build GeoJSON in 4326
        # Reproject full polygon to 4326
        poly_4326 = Polygon([to_4326.transform(x, y) for x, y in list(buffered.exterior.coords)])
        geojson_path = os.path.join(output_dir, f"{base}.geojson")
        _maybe_write_geojson(poly_4326, geojson_path)

    return kmz_path, geojson_path


def main():
    p = argparse.ArgumentParser(description='Create a uniform buffer around geometry and export as KMZ.')
    p.add_argument('input', help='Input file (.kmz or session .json)')
    p.add_argument('-r', '--radius', type=float, required=True, help='Buffer radius value')
    p.add_argument('-u', '--units', default='meters', choices=['meters', 'm', 'feet', 'ft', 'miles', 'mi', 'km', 'kilometers', 'kilometer'], help='Units for radius (default: meters)')
    p.add_argument('-o', '--output', help='Output base name (without extension). Defaults to <stem>_buffer_<r><u>')
    p.add_argument('-d', '--output-dir', default='.', help='Output directory')
    p.add_argument('--segments', type=int, default=16, help='Segments per quarter circle for buffer (default: 16)')
    p.add_argument('--geojson', action='store_true', help='Also write GeoJSON of the buffer (EPSG:4326)')
    args = p.parse_args()

    try:
        kmz_path, gj = create_buffer_kmz(
            args.input, args.radius, unit=args.units, output_name=args.output,
            output_dir=args.output_dir, segments=args.segments, geojson=args.geojson
        )
        print(f"KMZ created: {kmz_path}")
        if gj:
            print(f"GeoJSON created: {gj}")
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == '__main__':
    main()

