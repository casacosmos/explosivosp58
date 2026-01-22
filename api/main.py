#!/usr/bin/env python3
import os
import json
import shutil
import uuid
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

import subprocess
import re
from api.datastore import load_store

ROOT = Path(__file__).resolve().parent.parent
OUT_ROOT = ROOT / "output"
WORK_ROOT = ROOT / "work"
PLAYWRIGHT_DIR = ROOT / ".playwright-mcp"

app = FastAPI(title="HUD Tank Pipeline API", version="0.1.0")

# Note: Environment variables must be provided by the shell. The API does not load .env files.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS: Dict[str, Dict[str, Any]] = {}
FIRST_COLUMN = 'Site Name or Business Name '


def _ensure_dirs():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    PLAYWRIGHT_DIR.mkdir(parents=True, exist_ok=True)

def _get_store(session: str):
    try:
        from api.datastore import load_store as _ls
        return _ls(WORK_ROOT, session)
    except Exception:
        return None


def _run(cmd: list, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True)

# Canonical Excel columns to enforce consistent formatting across pipeline
TARGET_COLUMNS: List[str] = [
    # Match the example final table structure, plus Tank Measurements
    'Person Contacted',
    'Tank Capacity',
    'Tank Measurements',
    'Dike Measurements',
    'Acceptable Separation Distance Calculated ',
    'Approximate Distance to Site (appoximately) ',
    'Compliance',
    'Additional information ',
    'Latitude (NAD83)',
    'Longitude (NAD83)',
    'Calculated Distance to Polygon (ft)',
    'Closest Point Lat',
    'Closest Point Lon',
    'Point Location',
]

# Flexible header alias mapping for uploaded Excel files.
# Keys are normalized (lowercased, stripped, non-alnum collapsed) header forms.
HEADER_ALIASES = {
    # Site name
    'sitenameorbusinessname': 'Site Name or Business Name ',
    'sitename': 'Site Name or Business Name ',
    'businessname': 'Site Name or Business Name ',
    'name': 'Site Name or Business Name ',
    'facilityname': 'Site Name or Business Name ',

    # Capacity and measurements
    'tankcapacity': 'Tank Capacity',
    'capacity': 'Tank Capacity',
    'capacitygal': 'Tank Capacity',
    'volume': 'Tank Capacity',
    'tankvolume': 'Tank Capacity',
    'tanksize': 'Tank Capacity',
    'tankmeasurements': 'Tank Measurements',
    'measurements': 'Tank Measurements',
    'dims': 'Tank Measurements',
    'dimensions': 'Tank Measurements',
    'lxwxh': 'Tank Measurements',
    'lwh': 'Tank Measurements',
    'lengthxwidthxheight': 'Tank Measurements',
    'tankcapacitygal': 'Tank Capacity (gal)',

    # Dike/containment
    'dikemeasurements': 'Dike Measurements',
    'dikedimensions': 'Dike Measurements',
    'dikedims': 'Dike Measurements',
    'containmentdimensions': 'Dike Measurements',
    'containment': 'Dike Measurements',
    'berm': 'Dike Measurements',

    # Coordinates
    'latitude': 'Latitude (NAD83)',
    'lat': 'Latitude (NAD83)',
    'latitude(nad83)': 'Latitude (NAD83)',
    'longitude': 'Longitude (NAD83)',
    'long': 'Longitude (NAD83)',
    'lon': 'Longitude (NAD83)',
    'longitude(nad83)': 'Longitude (NAD83)',

    # Distances to polygon
    'distancetopolygonboundaryft': 'Calculated Distance to Polygon (ft)',
    'calculateddistancetopolygonft': 'Calculated Distance to Polygon (ft)',
    'distanceft': 'Calculated Distance to Polygon (ft)',
    'closestboundarypointlat': 'Closest Point Lat',
    'closestboundarypointlon': 'Closest Point Lon',
    'locationrelativetopolygon': 'Point Location',
    'insidepolygon': 'Point Location',

    # ASD and distances
    'acceptableseparationdistancecalculated': 'Acceptable Separation Distance Calculated ',
    'asd': 'Acceptable Separation Distance Calculated ',
    'asdppu': 'ASDPPU (ft)',
    'asdbpu': 'ASDBPU (ft)',
    'asdpnpd': 'ASDPNPD (ft)',
    'asdbnpd': 'ASDBNPD (ft)',
    'maximumrequiredasd': 'Maximum Required ASD (ft)',
    'approximatedistancetosite(appoximately)': 'Approximate Distance to Site (appoximately) ',
    'approximatedistancetosite': 'Approximate Distance to Site (appoximately) ',
    'distancetosite': 'Approximate Distance to Site (appoximately) ',

    # Compliance and notes
    'compliance': 'Compliance',
    'compliancenotes': 'Compliance Notes',
    'additionalinformation': 'Additional information ',
    'notes': 'Additional information ',
    'comments': 'Additional information ',

    # Misc
    'personcontacted': 'Person Contacted',
    'tanktype': 'Tank Type',
    'hasdike': 'Has Dike',
}

def _norm_header(h: str) -> str:
    import re
    s = (h or '').strip().lower()
    # remove non-alphanumeric
    s = re.sub(r'[^a-z0-9]+', '', s)
    return s

def _normalize_headers_inplace(path: Path) -> Path:
    """Rename headers in the Excel file based on HEADER_ALIASES and ensure core coordinate duplication.
    This is idempotent and only affects headers, not data order.
    """
    import pandas as pd
    try:
        df = pd.read_excel(path)
    except Exception:
        return path
    cols = list(df.columns)
    rename_map = {}
    used_targets = set()
    for c in cols:
        key = _norm_header(str(c))
        target = HEADER_ALIASES.get(key)
        if target and target not in used_targets and c != target:
            rename_map[c] = target
            used_targets.add(target)
    if rename_map:
        df.rename(columns=rename_map, inplace=True)
    # Do not duplicate Latitude/Longitude; keep NAD83 columns only to match final table
    df.to_excel(path, index=False)
    return path

def _parse_bool(v: Optional[str]) -> bool:
    if v is None:
        return False
    s = str(v).strip().lower()
    return s in {"1", "true", "t", "yes", "y", "on"}

def _normalize_excel(path: Path, preserve_columns: bool = False) -> Path:
    import pandas as pd
    # First, normalize headers for flexible uploads
    _normalize_headers_inplace(path)
    df = pd.read_excel(path)
    cols = list(df.columns)
    if not cols:
        return path
    first_col = cols[0]
    present_all = all(col in df.columns for col in TARGET_COLUMNS)
    if preserve_columns and present_all:
        # nothing to add or reorder
        df.to_excel(path, index=False)
        return path
    # ensure target columns exist
    for col in TARGET_COLUMNS:
        if col not in df.columns:
            df[col] = None
    if not preserve_columns:
        # reorder to canonical shape: first column, then target columns, then extras
        ordered = [first_col]
        for col in TARGET_COLUMNS:
            if col != first_col:
                ordered.append(col)
        for col in cols[1:]:
            if col not in TARGET_COLUMNS:
                ordered.append(col)
        df = df[ordered]
    df.to_excel(path, index=False)
    return path

def _preview_excel(path: Path, limit: int = 25) -> dict:
    import pandas as pd
    import numpy as np
    df = pd.read_excel(path)
    # Replace non-JSON-safe values (NaN/NaT/Inf) with None and format datetimes
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype('datetime64[ns]')
            df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')
    df = df.replace({np.nan: None, np.inf: None, -np.inf: None})
    rows = df.head(limit).to_dict(orient='records')
    return {"columns": list(df.columns), "rows": rows}

def _headers_report(path: Path) -> dict:
    import pandas as pd
    cols = list(pd.read_excel(path).columns)
    rename_map = {}
    for c in cols:
        key = _norm_header(str(c))
        tgt = HEADER_ALIASES.get(key)
        if tgt and tgt != c:
            rename_map[str(c)] = tgt
    missing = [c for c in TARGET_COLUMNS if c not in cols]
    extras = [c for c in cols if c not in TARGET_COLUMNS and c != cols[0]]
    return {
        'original_columns': cols,
        'proposed_renames': rename_map,
        'missing_target_columns': missing,
        'extra_columns': extras,
    }

def _export_datastore_excel(session: str) -> Path:
    """Export current datastore (canonical schema) as a one-row-per-tank Excel with final table columns."""
    import pandas as pd
    out_dir = OUT_ROOT / session
    out_dir.mkdir(parents=True, exist_ok=True)
    store = _get_store(session)
    if not store:
        raise HTTPException(status_code=500, detail='datastore unavailable')
    data = store.to_dict()
    rows = []
    for t in data.get('tanks', []):
        name = t.get('name')
        vol = t.get('volume_gal')
        meas = t.get('measurements')
        dike = t.get('dike_dims') or [None, None]
        coords = t.get('coords') or {}
        hud = t.get('hud') or {}
        dist = t.get('distance_to_polygon_ft')
        cp = t.get('closest_point') or {}
        comp = t.get('compliance') or {}
        # Build ASD combined string if possible
        parts = []
        if hud.get('asdppu') is not None:
            parts.append(f"ASDPPU - {hud.get('asdppu')} ft")
        if hud.get('asdbpu') is not None:
            parts.append(f"ASDBPU - {hud.get('asdbpu')} ft")
        if hud.get('asdpnpd') is not None:
            parts.append(f"ASDPNPD - {hud.get('asdpnpd')} ft")
        if hud.get('asdbnpd') is not None:
            parts.append(f"ASDBNPD - {hud.get('asdbnpd')} ft")
        asd_combined = ' ; '.join(parts) if parts else ''
        # Dike measurements formatted as Length/Width ft if present
        dike_str = ''
        if isinstance(dike, list) and len(dike) == 2 and all(x is not None for x in dike):
            dike_str = f"Length {dike[0]} ft ; Width {dike[1]} ft"
        row = {
            FIRST_COLUMN: name,
            'Person Contacted': '',
            'Tank Capacity': (f"{vol:.0f} gal" if isinstance(vol, (int, float)) else ''),
            'Tank Measurements': meas or '',
            'Dike Measurements': dike_str,
            'Acceptable Separation Distance Calculated ': asd_combined,
            'Approximate Distance to Site (appoximately) ': dist,
            'Compliance': comp.get('status') if isinstance(comp, dict) else '',
            'Additional information ': '',
            'Latitude (NAD83)': coords.get('lat'),
            'Longitude (NAD83)': coords.get('lon'),
            'Calculated Distance to Polygon (ft)': dist,
            'Closest Point Lat': cp.get('lat'),
            'Closest Point Lon': cp.get('lon'),
            'Point Location': t.get('point_location') or '',
        }
        rows.append(row)
    # Create DataFrame with canonical headers and order
    headers = [FIRST_COLUMN] + [c for c in TARGET_COLUMNS if c != FIRST_COLUMN]
    df = pd.DataFrame(rows)
    for col in headers:
        if col not in df.columns:
            df[col] = None
    df = df[headers]
    out_path = out_dir / 'datastore_export.xlsx'
    df.to_excel(out_path, index=False)
    return out_path

    

def _ensure_capacity_columns(excel_path: Path):
    import pandas as pd
    import numpy as np
    df = pd.read_excel(excel_path)
    # Ensure columns exist
    if 'Tank Measurements' not in df.columns:
        df['Tank Measurements'] = None
    # Determine source columns
    cap_col = None
    for c in df.columns:
        if c.strip().lower() in ['tank capacity', 'capacity', 'volume', 'tank size', 'capacity (gal)']:
            cap_col = c
            break
    # Fill per row
    for idx, row in df.iterrows():
        meas_val = None
        if cap_col and pd.notna(row.get(cap_col)):
            meas_val = str(row.get(cap_col))
        # Use existing Tank Measurements if set
        if pd.notna(row.get('Tank Measurements')) and str(row.get('Tank Measurements')).strip():
            meas_val = str(row.get('Tank Measurements'))
        if meas_val:
            df.at[idx, 'Tank Measurements'] = meas_val
    # Save back
    df.to_excel(excel_path, index=False)

def _build_hud_input_config(session: str) -> Dict[str, Any]:
    """Create a filtered HUD input config that only includes tanks with valid gallons volume (>0)."""
    sess_dir = WORK_ROOT / session
    state_path = sess_dir / 'state.json'
    if not state_path.exists():
        raise HTTPException(status_code=404, detail='session not found')
    st = json.loads(state_path.read_text())
    cfg_path = st.get('tank_config')
    if not cfg_path or not Path(cfg_path).exists():
        raise HTTPException(status_code=400, detail='no validated tank_config for session')
    with open(cfg_path, 'r') as f:
        cfg = json.load(f)
    tanks = cfg.get('tanks', [])
    filtered = []
    for t in tanks:
        try:
            v = t.get('volume', 0)
            if isinstance(v, (int, float)) and v > 0:
                # keep only necessary fields for HUD
                keep = {
                    'id': t.get('id'),
                    'name': t.get('name'),
                    'volume': float(v),
                    'type': t.get('type', 'diesel'),
                    'has_dike': bool(t.get('has_dike', False)),
                }
                if keep['has_dike'] and isinstance(t.get('dike_dims'), list) and len(t.get('dike_dims')) == 2:
                    keep['dike_dims'] = t['dike_dims']
                filtered.append(keep)
        except Exception:
            continue
    hud_cfg = {
        'tanks': filtered,
        'settings': cfg.get('settings', { 'headless': False, 'screenshot_full_page': True, 'output_pdf': 'HUD_ASD_Results.pdf' })
    }
    out_path = sess_dir / 'tank_config_hud_input.json'
    with open(out_path, 'w') as f:
        json.dump(hud_cfg, f, indent=2)
    # persist in session state
    st['hud_input_config'] = str(out_path)
    state_path.write_text(json.dumps(st, indent=2))
    return { 'path': str(out_path), 'count': len(filtered) }



@app.get("/health")
def health():
    return {"ok": True}


@app.post("/excel-to-json")
async def excel_to_json(
    file: Optional[UploadFile] = File(None),
    session: Optional[str] = Form(None),
    preserve_columns: Optional[str] = Form(None),
    normalize_copy: Optional[str] = Form(None),
    use_improved: Optional[str] = Form("true"),  # Use improved parser by default
):
    _ensure_dirs()
    # Enforce environment-only configuration for LLM parsing
    if not os.getenv('OPENAI_API_KEY'):
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY is not set in the server environment. Excel→JSON requires an API key.")
    session = session or uuid.uuid4().hex
    sess_dir = WORK_ROOT / session
    sess_dir.mkdir(parents=True, exist_ok=True)
    if file is None:
        # find in session
        try:
            st = json.loads((sess_dir / "state.json").read_text())
            excel_path = Path(st.get("excel_filled")) if st.get("excel_filled") else None
        except Exception:
            excel_path = None
        if not excel_path:
            raise HTTPException(status_code=400, detail="No Excel provided and none found in session")
    else:
        excel_path = sess_dir / file.filename
        with excel_path.open("wb") as f:
            f.write(await file.read())
        # store
        try:
            p = sess_dir / "state.json"
            st = json.loads(p.read_text()) if p.exists() else {}
            st["excel_filled"] = str(excel_path)
            p.write_text(json.dumps(st, indent=2))
        except Exception:
            pass

    # Normalize Excel to keep consistent columns
    try:
        _normalize_excel(excel_path, preserve_columns=_parse_bool(preserve_columns))
    except Exception:
        pass
    # Ensure Tank Measurements and Tank Capacity (gal) are present and populated when possible
    try:
        _ensure_capacity_columns(excel_path)
    except Exception:
        pass

    out_json = sess_dir / "tank_config.json"
    
    # Choose parser based on use_improved flag
    if _parse_bool(use_improved):
        # Use improved parser with VolumeCalculator (validates internally)
        proc = _run(["python", "excel_to_json_improved.py", str(excel_path), "-o", str(out_json)], cwd=ROOT)
        if proc.returncode != 0:
            # Check if VolumeCalculator module is available
            if "volume_calculator" in proc.stderr:
                # Fallback to original parser if module missing
                print(f"VolumeCalculator not found, falling back to original parser")
                proc = _run(["python", "excel_to_json_langgraph.py", str(excel_path), "-o", str(out_json)], cwd=ROOT)
            if proc.returncode != 0:
                raise HTTPException(status_code=400, detail=proc.stderr)
    else:
        # Use original parser
        proc = _run(["python", "excel_to_json_langgraph.py", str(excel_path), "-o", str(out_json)], cwd=ROOT)
        if proc.returncode != 0:
            raise HTTPException(status_code=400, detail=proc.stderr)
        
        # External validation for original parser only
        v = _run(["python", "validate_tank_json.py", str(out_json)], cwd=ROOT)
        if v.returncode != 0:
            raise HTTPException(status_code=400, detail=f"Validation failed: {v.stderr}")

    try:
        data = json.loads(out_json.read_text())
    except Exception:
        data = None

    # store config
    try:
        p = sess_dir / "state.json"
        st = json.loads(p.read_text()) if p.exists() else {}
        st.update({"tank_config": str(out_json), "validated": True})
        p.write_text(json.dumps(st, indent=2))
    except Exception:
        pass

    tanks_count = 0
    try:
        tanks_count = len(data.get('tanks', [])) if data else 0
    except Exception:
        tanks_count = 0

    # Update datastore with validated config (backbone store)
    try:
        store = _get_store(session)
        if store and data:
            store.upsert_from_config(data)
            store.update_meta(excel_path=str(excel_path), tank_config=str(out_json))
            store.save()
    except Exception:
        pass

    # Optionally emit a normalized copy without changing the working file
    normalized_copy_path = None
    if _parse_bool(normalize_copy):
        out_dir = OUT_ROOT / session
        out_dir.mkdir(parents=True, exist_ok=True)
        normalized_copy_path = out_dir / f"normalized_{Path(excel_path).name}"
        try:
            import shutil as _sh
            _sh.copy(excel_path, normalized_copy_path)
            _normalize_excel(normalized_copy_path, preserve_columns=_parse_bool(preserve_columns))
        except Exception:
            normalized_copy_path = None

    return {
        "session": session,
        "json_path": str(out_json),
        "json": data,
        "validated": True,
        "tanks_count": tanks_count,
        "preview": _preview_excel(excel_path, 25) if True else None,
        "normalized_copy": str(normalized_copy_path) if normalized_copy_path else None,
    }


@app.post("/kmz/parse")
async def kmz_parse(file: UploadFile = File(...), session: Optional[str] = Form(None)):
    """Parse KMZ/KML using kmz_parser_agent.py and save outputs."""
    _ensure_dirs()

    session = session or uuid.uuid4().hex
    sess_dir = WORK_ROOT / session
    out_dir = OUT_ROOT / session
    sess_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    kmz_path = sess_dir / file.filename
    with kmz_path.open("wb") as f:
        f.write(await file.read())

    parser_script = ROOT / "kmz_parser_agent.py"
    if not parser_script.exists():
        raise HTTPException(status_code=500, detail="kmz_parser_agent.py not found in isolated folder")

    args = ["python", str(parser_script), str(kmz_path), "-o", str(out_dir)]
    proc = _run(args, cwd=ROOT)
    if proc.returncode != 0:
        raise HTTPException(status_code=400, detail=proc.stderr)

    # List outputs for client convenience and update session state
    files = []
    polygon_path = None
    excel_template = None
    for pth in out_dir.rglob("*"):
        if pth.is_file():
            files.append(str(pth))
            lname = pth.name.lower()
            if lname.startswith('polygon_') and lname.endswith('.txt') and polygon_path is None:
                polygon_path = str(pth)
            if lname.startswith('tank_locations_') and (lname.endswith('.xlsx') or lname.endswith('.xls')) and excel_template is None:
                excel_template = str(pth)
    # Compute quick counts for feedback
    polygons_count = 0
    points_count = 0
    try:
        # Find a kmz_parse_result json to read counts from
        result_json = None
        for pth in out_dir.glob('kmz_parse_result_*.json'):
            result_json = pth
        if result_json and result_json.exists():
            with open(result_json, 'r') as f:
                j = json.load(f)
                polygons_count = len(j.get('polygons', []))
                points_count = len(j.get('points', []))
    except Exception:
        pass

    try:
        state_path = Path('work') / session / 'state.json'
        st = json.loads(state_path.read_text()) if state_path.exists() else {}
        st.update({'kmz': str(kmz_path), 'polygon': polygon_path, 'excel_template': excel_template, 'kmz_outputs': files, 'polygons_count': polygons_count, 'points_count': points_count})
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(st, indent=2))
    except Exception:
        pass
    return {"session": session, "output_dir": str(out_dir), "files": files, "polygons_count": polygons_count, "points_count": points_count, "stdout": proc.stdout}


@app.post("/kmz/from-excel")
async def kmz_from_excel(
    file: Optional[UploadFile] = File(None),
    session: Optional[str] = Form(None),
    polygon_text: Optional[str] = Form(None),
    polygon_file: Optional[UploadFile] = File(None),
):
    """Generate a KMZ directly from an Excel/CSV file.

    Accepts either an uploaded Excel or reuses the session's stored Excel template.
    Optionally includes a boundary polygon provided as text (one coordinate pair per line)
    or as an uploaded file.
    """
    _ensure_dirs()
    session = session or uuid.uuid4().hex
    sess_dir = WORK_ROOT / session
    out_dir = OUT_ROOT / session
    sess_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Resolve Excel path
    if file is not None:
        excel_path = out_dir / file.filename
        with excel_path.open("wb") as f:
            f.write(await file.read())
        try:
            sp = sess_dir / "state.json"
            st = json.loads(sp.read_text()) if sp.exists() else {}
            st["excel_filled"] = str(excel_path)
            sp.write_text(json.dumps(st, indent=2))
        except Exception:
            pass
    else:
        # Prefer an uploaded filled Excel, fallback to template
        excel_path = None
        try:
            st = json.loads((sess_dir / "state.json").read_text())
            excel_path = Path(st.get("excel_filled") or st.get("excel_template")) if st.get("excel_filled") or st.get("excel_template") else None
        except Exception:
            excel_path = None
        if not excel_path:
            raise HTTPException(status_code=400, detail="No Excel provided and none found in session")

    # Prepare polygon if provided
    polygon_path = None
    try:
        # Uploaded file has priority
        if polygon_file is not None:
            polygon_path = out_dir / (polygon_file.filename or f"polygon_{session}.txt")
            with polygon_path.open("wb") as f:
                f.write(await polygon_file.read())
        elif polygon_text:
            polygon_path = out_dir / f"polygon_{session}.txt"
            polygon_path.write_text(polygon_text)
        else:
            # Use previously parsed polygon if present
            st = json.loads((sess_dir / "state.json").read_text()) if (sess_dir / "state.json").exists() else {}
            if st.get("polygon") and Path(st["polygon"]).exists():
                polygon_path = Path(st["polygon"])  # already absolute
    except Exception:
        polygon_path = None

    # Target KMZ path
    kmz_path = out_dir / f"kmz_from_{Path(excel_path).stem}.kmz"

    # Run converter
    args = ["python", "excel_to_kmz.py", str(excel_path), "-o", str(kmz_path)]
    if polygon_path and Path(polygon_path).exists():
        args.extend(["-p", str(polygon_path)])
    proc = _run(args, cwd=ROOT)
    if proc.returncode != 0:
        raise HTTPException(status_code=400, detail=proc.stderr)

    # Extract placemark count from stdout
    count = 0
    m = re.search(r"placemarks:\s*(\d+)", proc.stdout or "")
    if m:
        try:
            count = int(m.group(1))
        except Exception:
            count = 0

    # Update session state
    try:
        sp = sess_dir / "state.json"
        st = json.loads(sp.read_text()) if sp.exists() else {}
        st.update({"kmz_from_excel": str(kmz_path), "kmz_points_count": count})
        sp.write_text(json.dumps(st, indent=2))
    except Exception:
        pass

    return {"session": session, "kmz": str(kmz_path), "points_count": count, "stdout": proc.stdout}


@app.post("/excel/upload")
async def excel_upload(file: UploadFile = File(...), session: Optional[str] = Form(None)):
    """Upload an Excel file directly and prepare it for processing."""
    _ensure_dirs()

    session = session or uuid.uuid4().hex
    sess_dir = WORK_ROOT / session
    out_dir = OUT_ROOT / session
    sess_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save the uploaded Excel file
    excel_path = out_dir / file.filename
    with excel_path.open("wb") as f:
        f.write(await file.read())

    # Also save it as the template file
    template_path = out_dir / f"tank_locations_{session}.xlsx"
    shutil.copy2(excel_path, template_path)

    # Initialize datastore with tank information from Excel
    try:
        import pandas as pd
        df = pd.read_excel(excel_path)

        # Extract minimal tank records and persist via datastore API (works for JSON/SQLite)
        cfg_tanks = []
        name_col = df.columns[0] if len(df.columns) else 'name'
        for idx, row in df.iterrows():
            name = str(row.get('Site Name or Business Name ', row.get(name_col, f'Tank_{idx+1}')))
            vol = row.get('Tank Capacity', None)
            cfg_tanks.append({"name": name, "volume": vol})

        store = load_store(WORK_ROOT, session)
        # Upsert basic tank info, then merge coords/distances from the Excel columns
        try:
            store.upsert_from_config({"tanks": cfg_tanks})
        except Exception:
            pass
        try:
            store.merge_distances_from_excel(excel_path)
        except Exception:
            pass
        try:
            store.update_meta(excel_template=str(template_path))
            store.save()
        except Exception:
            pass

        # Update session state
        state_path = sess_dir / 'state.json'
        st = json.loads(state_path.read_text()) if state_path.exists() else {}
        st.update({
            'excel_upload': str(excel_path),
            'excel_filled': str(excel_path),
            'excel_template': str(template_path),
            'tanks_count': len(tanks)
        })
        state_path.write_text(json.dumps(st, indent=2))

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process Excel file: {str(e)}")

    return {
        "session": session,
        "output_dir": str(out_dir),
        "excel_path": str(excel_path),
        "tanks_count": len(tanks),
        "message": "Excel file uploaded successfully. Proceed to Field Info."
    }


@app.post("/validate-json")
async def validate_json(file: UploadFile = File(...)):
    _ensure_dirs()
    sess_dir = WORK_ROOT / uuid.uuid4().hex
    sess_dir.mkdir(parents=True, exist_ok=True)
    json_path = sess_dir / file.filename
    with json_path.open("wb") as f:
        f.write(await file.read())

    proc = _run(["python", "validate_tank_json.py", str(json_path)], cwd=ROOT)
    ok = proc.returncode == 0
    return {"ok": ok, "stdout": proc.stdout, "stderr": proc.stderr}


async def _hud_job_async(job_id: str, config_json_path: Path, sess_dir: Path):
    JOBS[job_id].update(status="running")

    # Launch subprocess with config flag; stream stdout
    proc = await asyncio.create_subprocess_exec(
        "python", "fast_hud_processor.py", "--config", str(config_json_path),
        cwd=str(ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def _pump(stream, label: str):
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode(errors="ignore").rstrip()
            # store and broadcast
            JOBS[job_id]["log"].append(f"[{label}] {text}")
            # keep log bounded
            if len(JOBS[job_id]["log"]) > 1000:
                JOBS[job_id]["log"] = JOBS[job_id]["log"][-1000:]
            await JOBS[job_id]["queue"].put({"type": "log", "data": text, "stream": label})

    await asyncio.gather(_pump(proc.stdout, "stdout"), _pump(proc.stderr, "stderr"))
    returncode = await proc.wait()

    # Move outputs into session output folder
    session = JOBS[job_id].get("session") or job_id
    out_session = OUT_ROOT / session
    out_session.mkdir(parents=True, exist_ok=True)

    # fast_results.json
    fr = ROOT / "fast_results.json"
    if fr.exists():
        shutil.copy(fr, out_session / fr.name)
        JOBS[job_id]["fast_results"] = str(out_session / fr.name)
        # Merge into datastore
        try:
            session_id = JOBS[job_id].get("session") or job_id
            store = _get_store(session_id)
            if store:
                results = json.loads(fr.read_text())
                if isinstance(results, list):
                    store.merge_hud_results(results)
                    store.update_meta(fast_results=str(out_session / fr.name))
                    store.save()
        except Exception:
            pass

    # HUD PDF
    pdf = ROOT / "HUD_ASD_Results.pdf"
    if pdf.exists():
        shutil.copy(pdf, out_session / pdf.name)
        JOBS[job_id]["pdf"] = str(out_session / pdf.name)
        try:
            session_id = JOBS[job_id].get("session") or job_id
            store = _get_store(session_id)
            if store:
                store.update_meta(hud_pdf=str(out_session / pdf.name))
                store.save()
        except Exception:
            pass

    # screenshots
    if PLAYWRIGHT_DIR.exists():
        shots_dir = out_session / ".playwright-mcp"
        shots_dir.mkdir(exist_ok=True)
        for p in PLAYWRIGHT_DIR.glob("*.png"):
            shutil.copy(p, shots_dir / p.name)
        JOBS[job_id]["screenshots_dir"] = str(shots_dir)

    # update session state
    try:
        from pathlib import Path as _P
        state_update = {}
        if fr.exists():
            state_update["fast_results"] = str(out_session / fr.name)
        if pdf.exists():
            hud = {"pdf": str(out_session / pdf.name)}
            if "fast_results" in state_update:
                hud["fast_results"] = state_update["fast_results"]
            state_update["hud"] = hud
        if state_update:
            p = _P("work") / session / "state.json"
            try:
                existing = json.loads(p.read_text()) if p.exists() else {}
            except Exception:
                existing = {}
            existing.update(state_update)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(existing, indent=2))
    except Exception:
        pass

    JOBS[job_id].update(status="completed", returncode=returncode)
    await JOBS[job_id]["queue"].put({"type": "status", "status": "completed", "returncode": returncode})


@app.post("/hud/run")
async def hud_run(background: BackgroundTasks, file: Optional[UploadFile] = File(None), session: Optional[str] = Form(None)):
    _ensure_dirs()
    job_id = uuid.uuid4().hex
    session = session or uuid.uuid4().hex
    sess_dir = WORK_ROOT / session
    sess_dir.mkdir(parents=True, exist_ok=True)
    if file is not None:
        json_path = sess_dir / file.filename
        with json_path.open("wb") as f:
            f.write(await file.read())
        # save into session state
        try:
            p = WORK_ROOT / session / "state.json"
            st = json.loads(p.read_text()) if p.exists() else {}
            st["tank_config"] = str(json_path)
            p.write_text(json.dumps(st, indent=2))
        except Exception:
            pass
    else:
        # try to use session state
        cfg = None
        try:
            p = WORK_ROOT / session / "state.json"
            if p.exists():
                st = json.loads(p.read_text())
                cfg = st.get("tank_config")
        except Exception:
            cfg = None
        if not cfg:
            raise HTTPException(status_code=400, detail="No config provided and none found in session")
        # Build filtered HUD input config to ensure only valid tanks are processed
        built = _build_hud_input_config(session)
        json_path = Path(built['path'])

    JOBS[job_id] = {"status": "queued", "log": [], "queue": asyncio.Queue(), "session": session}
    # schedule async background task
    asyncio.create_task(_hud_job_async(job_id, json_path, sess_dir))
    return {"job_id": job_id, "status": "queued", "session": session, "input_config": str(json_path)}


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


@app.websocket("/ws/jobs/{job_id}")
async def ws_job(websocket: WebSocket, job_id: str):
    await websocket.accept()
    job = JOBS.get(job_id)
    if not job:
        await websocket.send_json({"type": "error", "message": "job not found"})
        await websocket.close()
        return
    # replay existing logs
    for entry in job.get("log", []):
        await websocket.send_json({"type": "log", "data": entry})
    # stream new updates
    try:
        while True:
            msg = await job["queue"].get()
            await websocket.send_json(msg)
            # close on completion message
            if msg.get("type") == "status" and msg.get("status") == "completed":
                break
    except WebSocketDisconnect:
        return


@app.post("/pdf/generate")
async def pdf_generate(output_name: Optional[str] = Form(None), session: Optional[str] = Form(None)):
    _ensure_dirs()
    session = session or uuid.uuid4().hex
    out_dir = OUT_ROOT / session
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (output_name or "HUD_ASD_Results.pdf")
    proc = _run(["python", "generate_pdf.py", "-o", str(out_path)], cwd=ROOT)
    if proc.returncode != 0:
        raise HTTPException(status_code=400, detail=proc.stderr)
    return {"ok": True, "pdf": str(out_path)}


@app.post("/excel/update-with-results")
async def excel_update_with_results(excel: Optional[UploadFile] = File(None), hud_results: Optional[UploadFile] = File(None), session: Optional[str] = Form(None)):
    _ensure_dirs()
    session = session or uuid.uuid4().hex
    sess_dir = WORK_ROOT / session
    sess_dir.mkdir(parents=True, exist_ok=True)
    # resolve excel
    if excel is None:
        ex = None
        try:
            st = json.loads((sess_dir / "state.json").read_text())
            ex = st.get("excel_filled") or st.get("with_hud_excel")
        except Exception:
            ex = None
        if not ex:
            raise HTTPException(status_code=400, detail="No Excel provided and none found in session")
        excel_path = Path(ex)
    else:
        excel_path = sess_dir / excel.filename
        with excel_path.open("wb") as f:
            f.write(await excel.read())
        # store
        try:
            p = sess_dir / "state.json"
            st = json.loads(p.read_text()) if p.exists() else {}
            st["excel_filled"] = str(excel_path)
            p.write_text(json.dumps(st, indent=2))
        except Exception:
            pass
    # resolve results
    if hud_results is None:
        res = None
        try:
            st = json.loads((sess_dir / "state.json").read_text())
            res = st.get("fast_results") or (st.get("hud") or {}).get("fast_results")
        except Exception:
            res = None
        if not res:
            raise HTTPException(status_code=400, detail="No HUD results provided and none in session")
        results_path = Path(res)
    else:
        results_path = sess_dir / hud_results.filename
        with results_path.open("wb") as f:
            f.write(await hud_results.read())
        # store
        try:
            p = sess_dir / "state.json"
            st = json.loads(p.read_text()) if p.exists() else {}
            st["fast_results"] = str(results_path)
            p.write_text(json.dumps(st, indent=2))
        except Exception:
            pass

    out_xlsx = OUT_ROOT / session / "with_hud.xlsx"
    proc = _run(["python", "update_excel_with_results.py", str(excel_path), str(results_path), "-o", str(out_xlsx)], cwd=ROOT)
    if proc.returncode != 0:
        raise HTTPException(status_code=400, detail=proc.stderr)
    # store output
    try:
        p = sess_dir / "state.json"
        st = json.loads(p.read_text()) if p.exists() else {}
        st["with_hud_excel"] = str(out_xlsx)
        p.write_text(json.dumps(st, indent=2))
    except Exception:
        pass
    return {"ok": True, "excel": str(out_xlsx), "session": session}


@app.post("/compliance/check")
async def compliance_check(excel: Optional[UploadFile] = File(None), hud_results: Optional[UploadFile] = File(None), polygon: Optional[UploadFile] = File(None), session: Optional[str] = Form(None)):
    _ensure_dirs()
    session = session or uuid.uuid4().hex
    sess_dir = WORK_ROOT / session
    sess_dir.mkdir(parents=True, exist_ok=True)
    # excel
    if excel is None:
        ex = None
        try:
            st = json.loads((sess_dir / "state.json").read_text())
            ex = st.get("with_hud_excel") or st.get("excel_filled")
        except Exception:
            ex = None
        if not ex:
            raise HTTPException(status_code=400, detail="No Excel provided and none found in session")
        excel_path = Path(ex)
    else:
        excel_path = sess_dir / excel.filename
        with excel_path.open("wb") as f:
            f.write(await excel.read())
        # store
        try:
            p = sess_dir / "state.json"
            st = json.loads(p.read_text()) if p.exists() else {}
            st["with_hud_excel"] = str(excel_path)
            p.write_text(json.dumps(st, indent=2))
        except Exception:
            pass
    # hud results
    if hud_results is None:
        res = None
        try:
            st = json.loads((sess_dir / "state.json").read_text())
            res = st.get("fast_results") or (st.get("hud") or {}).get("fast_results")
        except Exception:
            res = None
        if not res:
            raise HTTPException(status_code=400, detail="No HUD results provided and none in session")
        results_path = Path(res)
    else:
        results_path = sess_dir / hud_results.filename
        with results_path.open("wb") as f:
            f.write(await hud_results.read())
        try:
            p = sess_dir / "state.json"
            st = json.loads(p.read_text()) if p.exists() else {}
            st["fast_results"] = str(results_path)
            p.write_text(json.dumps(st, indent=2))
        except Exception:
            pass
    # polygon
    polygon_path = None
    if polygon is None:
        try:
            st = json.loads((sess_dir / "state.json").read_text())
            polygon_path = st.get("polygon")
        except Exception:
            polygon_path = None
    else:
        poly = sess_dir / polygon.filename
        with poly.open("wb") as f:
            f.write(await polygon.read())
        polygon_path = str(poly)
        try:
            p = sess_dir / "state.json"
            st = json.loads(p.read_text()) if p.exists() else {}
            st["polygon"] = polygon_path
            p.write_text(json.dumps(st, indent=2))
        except Exception:
            pass

    args = ["python", "compliance_checker.py", str(excel_path), str(results_path)]
    out_path = OUT_ROOT / session / "final_compliance.xlsx"
    if polygon_path:
        args.extend(["--polygon", polygon_path])
    else:
        args.append("--no-distances")
    args.extend(["-o", str(out_path)])

    proc = _run(args, cwd=ROOT)
    if proc.returncode != 0:
        raise HTTPException(status_code=400, detail=proc.stderr)
    # store
    try:
        p = sess_dir / "state.json"
        st = json.loads(p.read_text()) if p.exists() else {}
        st["compliance_report"] = str(out_path)
        p.write_text(json.dumps(st, indent=2))
    except Exception:
        pass
    # Update datastore with distances/compliance
    try:
        store = _get_store(session)
        if store:
            store.merge_distances_from_excel(out_path)
            store.update_meta(compliance_report=str(out_path))
            store.save()
    except Exception:
        pass
    return {"ok": True, "report": str(out_path), "session": session}


@app.get("/files")
def list_files():
    _ensure_dirs()
    files = []
    for p in OUT_ROOT.rglob("*"):
        if p.is_file():
            files.append(str(p.relative_to(OUT_ROOT)))
    return {"root": str(OUT_ROOT), "files": files}


@app.get("/files/{path:path}")
def get_file(path: str):
    full = OUT_ROOT / path
    if not full.exists():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(str(full))


@app.get("/config/json")
def get_validated_config(session: str):
    """Return the validated tank_config.json for a session (downloadable)."""
    state_path = WORK_ROOT / session / 'state.json'
    if not state_path.exists():
        raise HTTPException(status_code=404, detail='session not found')
    try:
        st = json.loads(state_path.read_text())
        cfg = st.get('tank_config')
        if not cfg or not Path(cfg).exists():
            raise HTTPException(status_code=404, detail='validated JSON not found for session')
        return FileResponse(cfg, media_type='application/json', filename='tank_config.json')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'failed to read config: {e}')


@app.post("/config/prepare_hud_input")
def prepare_hud_input(session: str):
    """Prepare and persist the HUD input config filtered for valid tanks; return path and count."""
    built = _build_hud_input_config(session)
    return { 'ok': True, 'session': session, 'path': built['path'], 'count': built['count'] }


@app.get("/config/hud_input")
def get_hud_input_config(session: str):
    state_path = WORK_ROOT / session / 'state.json'
    if not state_path.exists():
        raise HTTPException(status_code=404, detail='session not found')
    try:
        st = json.loads(state_path.read_text())
        cfg = st.get('hud_input_config')
        if not cfg or not Path(cfg).exists():
            # build on-the-fly if missing
            built = _build_hud_input_config(session)
            cfg = built['path']
        return FileResponse(cfg, media_type='application/json', filename='tank_config_hud_input.json')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'failed to read hud input config: {e}')


@app.get("/session/{session}")
def session_state(session: str):
    p = WORK_ROOT / session / 'state.json'
    if not p.exists():
        raise HTTPException(status_code=404, detail='session not found')
    try:
        return json.loads(p.read_text())
    except Exception:
        raise HTTPException(status_code=500, detail='failed to read session state')


@app.get("/session/{session}/datastore")
def session_datastore(session: str):
    try:
        store = _get_store(session)
        if not store:
            raise HTTPException(status_code=500, detail='datastore unavailable')
        return JSONResponse(store.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'failed to read datastore: {e}')


@app.get("/session/{session}/export_excel")
def session_export_excel(session: str):
    try:
        out_path = _export_datastore_excel(session)
        return FileResponse(str(out_path), filename='datastore_export.xlsx')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'export failed: {e}')


@app.get("/excel/preview")
def excel_preview(session: str, limit: int = 25):
    p = WORK_ROOT / session / 'state.json'
    if not p.exists():
        raise HTTPException(status_code=404, detail='session not found')
    st = json.loads(p.read_text())
    ex = st.get('with_hud_excel') or st.get('excel_filled') or st.get('excel_upload') or st.get('excel_template')
    if not ex:
        raise HTTPException(status_code=400, detail='no excel found in session')
    try:
        return _preview_excel(Path(ex), limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'preview failed: {e}')


@app.post("/excel/apply_edits")
async def excel_apply_edits(
    session: str = Form(...),
    edits_json: str = Form(...),  # JSON string: list of { name: str, updates: { col: value, ... } }
):
    """Apply targeted cell edits to the session Excel by tank name (first column match).

    Writes a new Excel under output/<session>/excel_edited.xlsx, updates session excel_filled, and returns a preview.
    """
    import pandas as pd
    try:
        edits = json.loads(edits_json)
        if not isinstance(edits, list):
            raise ValueError('edits_json must be a JSON list')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f'invalid edits_json: {e}')

    state_path = WORK_ROOT / session / 'state.json'
    if not state_path.exists():
        raise HTTPException(status_code=404, detail='session not found')

    st = json.loads(state_path.read_text())
    src = st.get('with_hud_excel') or st.get('excel_filled') or st.get('excel_upload') or st.get('excel_template')
    if not src:
        raise HTTPException(status_code=400, detail='no excel found in session')
    src_path = Path(src)
    if not src_path.exists():
        raise HTTPException(status_code=404, detail='excel path missing on disk')

    try:
        df = pd.read_excel(src_path)
        if df.empty:
            raise HTTPException(status_code=400, detail='excel is empty')
        name_col = df.columns[0]
        # apply edits
        applied = 0
        for item in edits:
            name = (item or {}).get('name')
            updates = (item or {}).get('updates') or {}
            if not name or not isinstance(updates, dict):
                continue
            mask = df[name_col].astype(str).str.strip().str.lower() == str(name).strip().lower()
            idxs = df.index[mask].tolist()
            if not idxs:
                continue
            for col, val in updates.items():
                if col not in df.columns:
                    df[col] = None
                for idx in idxs:
                    df.at[idx, col] = val
                applied += 1
        # write new edited copy
        out_dir = OUT_ROOT / session
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / 'excel_edited.xlsx'
        df.to_excel(out_path, index=False)
        # update session state to use edited excel going forward
        st['excel_filled'] = str(out_path)
        state_path.write_text(json.dumps(st, indent=2))
        return {
            'ok': True,
            'applied': applied,
            'excel': str(out_path),
            'preview': _preview_excel(out_path, 25)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'apply edits failed: {e}')


# Tank data management endpoints
@app.get("/session/{session}/tanks")
def get_tanks(session: str):
    """Get all tanks from the datastore"""
    store = load_store(WORK_ROOT, session)
    if not store:
        raise HTTPException(status_code=404, detail='Session not found')
    return JSONResponse({"tanks": store.data.get('tanks', [])})


@app.post("/session/{session}/tank")
def add_tank(session: str, tank: dict):
    """Add a new tank to the datastore"""
    store = load_store(WORK_ROOT, session)
    if not store:
        raise HTTPException(status_code=404, detail='Session not found')

    name = tank.get('name', f"Tank-{len(store.data.get('tanks', [])) + 1}")
    new_tank = store._upsert_tank(name)

    # Update with provided data
    for key in ['volume_gal', 'type', 'has_dike', 'dike_dims', 'measurements', 'coords']:
        if key in tank:
            new_tank[key] = tank[key]

    store.save()
    return JSONResponse({"status": "created", "tank": new_tank})


@app.put("/session/{session}/tank/{tank_name}")
def update_tank(session: str, tank_name: str, updates: dict):
    """Update an existing tank in the datastore"""
    store = load_store(WORK_ROOT, session)
    if not store:
        raise HTTPException(status_code=404, detail='Session not found')

    # Find tank by name
    tank = None
    for t in store.data.get('tanks', []):
        if t.get('name', '').lower() == tank_name.lower():
            tank = t
            break

    if not tank:
        raise HTTPException(status_code=404, detail='Tank not found')

    # Update fields
    for key in ['volume_gal', 'type', 'has_dike', 'dike_dims', 'measurements', 'coords']:
        if key in updates:
            tank[key] = updates[key]

    store.save()
    return JSONResponse({"status": "updated", "tank": tank})


@app.delete("/session/{session}/tank/{tank_name}")
def delete_tank(session: str, tank_name: str):
    """Delete a tank from the datastore"""
    store = load_store(WORK_ROOT, session)
    if not store:
        raise HTTPException(status_code=404, detail='Session not found')

    # Find and remove tank
    tanks = store.data.get('tanks', [])
    for i, t in enumerate(tanks):
        if t.get('name', '').lower() == tank_name.lower():
            removed = tanks.pop(i)
            store.data['tanks'] = tanks
            store._reindex()
            store.save()
            return JSONResponse({"status": "deleted", "tank": removed})

    raise HTTPException(status_code=404, detail='Tank not found')


@app.post("/session/{session}/tanks/bulk_update")
def bulk_update_tanks(session: str, tanks: list):
    """Update multiple tanks at once"""
    store = load_store(WORK_ROOT, session)
    if not store:
        raise HTTPException(status_code=404, detail='Session not found')

    updated = []
    for tank_data in tanks:
        name = tank_data.get('name')
        if not name:
            continue

        tank = store._upsert_tank(name)
        # Include field study fields
        for key in ['volume_gal', 'type', 'has_dike', 'dike_dims', 'measurements', 'coords',
                   'inspected_by', 'inspection_time', 'contact_person', 'field_notes']:
            if key in tank_data:
                tank[key] = tank_data[key]
        updated.append(tank)

    store.save()
    return JSONResponse({"status": "updated", "count": len(updated), "tanks": updated})


# Field study endpoints
@app.get("/session/{session}/field_study")
def get_field_study(session: str):
    """Get field study metadata"""
    store = load_store(WORK_ROOT, session)
    if not store:
        raise HTTPException(status_code=404, detail='Session not found')
    return JSONResponse(store.data.get('field_study', {}))


@app.put("/session/{session}/field_study")
def update_field_study(session: str, field_data: dict):
    """Update field study metadata"""
    store = load_store(WORK_ROOT, session)
    if not store:
        raise HTTPException(status_code=404, detail='Session not found')

    store.update_field_study(field_data)
    return JSONResponse({"status": "updated", "field_study": store.data.get('field_study')})


@app.post("/session/{session}/contact")
def add_contact(session: str, contact: dict):
    """Add a person consulted during field study"""
    store = load_store(WORK_ROOT, session)
    if not store:
        raise HTTPException(status_code=404, detail='Session not found')

    if not contact.get('name'):
        raise HTTPException(status_code=400, detail='Contact name required')

    new_contact = store.add_contact(contact)
    return JSONResponse({"status": "added", "contact": new_contact})


@app.get("/session/{session}/contacts")
def get_contacts(session: str):
    """Get all contacts from field study"""
    store = load_store(WORK_ROOT, session)
    if not store:
        raise HTTPException(status_code=404, detail='Session not found')

    fs = store.data.get('field_study', {})
    return JSONResponse({"contacts": fs.get('contacts', [])})


@app.delete("/session/{session}/contact/{contact_name}")
def delete_contact(session: str, contact_name: str):
    """Delete a contact"""
    store = load_store(WORK_ROOT, session)
    if not store:
        raise HTTPException(status_code=404, detail='Session not found')

    fs = store.data.get('field_study', {})
    contacts = fs.get('contacts', [])

    for i, c in enumerate(contacts):
        if c.get('name', '').lower() == contact_name.lower():
            removed = contacts.pop(i)
            store.save()
            return JSONResponse({"status": "deleted", "contact": removed})

    raise HTTPException(status_code=404, detail='Contact not found')


@app.post("/excel/normalize")
async def excel_normalize(
    session: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    preserve_columns: Optional[str] = Form(None),
):
    session = session or uuid.uuid4().hex
    sess_dir = WORK_ROOT / session
    sess_dir.mkdir(parents=True, exist_ok=True)
    if file is not None:
        path = sess_dir / file.filename
        with path.open('wb') as f:
            f.write(await file.read())
        st = {"excel_filled": str(path)}
    else:
        st_path = sess_dir / 'state.json'
        st = json.loads(st_path.read_text()) if st_path.exists() else {}
        ex = st.get('with_hud_excel') or st.get('excel_filled') or st.get('excel_upload') or st.get('excel_template')
        if not ex:
            raise HTTPException(status_code=400, detail='no excel to normalize in session')
        path = Path(ex)
    try:
        _normalize_excel(path, preserve_columns=_parse_bool(preserve_columns))
        prev = _preview_excel(path, 25)
        # persist session state
        st_path = sess_dir / 'state.json'
        old = json.loads(st_path.read_text()) if st_path.exists() else {}
        old.update(st)
        st_path.write_text(json.dumps(old, indent=2))
        return {"ok": True, "session": session, "excel": str(path), "preview": prev}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'normalize failed: {e}')


@app.post("/excel/normalize_copy")
async def excel_normalize_copy(
    session: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    preserve_columns: Optional[str] = Form(None),
):
    session = session or uuid.uuid4().hex
    sess_dir = WORK_ROOT / session
    sess_dir.mkdir(parents=True, exist_ok=True)
    # Resolve source
    if file is not None:
        src = sess_dir / file.filename
        with src.open('wb') as f:
            f.write(await file.read())
    else:
        st_path = sess_dir / 'state.json'
        st = json.loads(st_path.read_text()) if st_path.exists() else {}
        ex = st.get('with_hud_excel') or st.get('excel_filled') or st.get('excel_upload') or st.get('excel_template')
        if not ex:
            raise HTTPException(status_code=400, detail='no excel found in session')
        src = Path(ex)
    # Create copy in outputs and normalize
    out_dir = OUT_ROOT / session
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"normalized_{src.name}"
    try:
        import shutil
        shutil.copy(src, dst)
        _normalize_excel(dst, preserve_columns=_parse_bool(preserve_columns))
        prev = _preview_excel(dst, 25)
        return {"ok": True, "session": session, "excel": str(dst), "preview": prev}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'normalize copy failed: {e}')


@app.post("/excel/normalize_report")
async def excel_normalize_report(session: Optional[str] = Form(None), file: Optional[UploadFile] = File(None)):
    session = session or uuid.uuid4().hex
    sess_dir = WORK_ROOT / session
    sess_dir.mkdir(parents=True, exist_ok=True)
    if file is not None:
        path = sess_dir / f"_normalize_report_{file.filename}"
        with path.open('wb') as f:
            f.write(await file.read())
    else:
        st_path = sess_dir / 'state.json'
        st = json.loads(st_path.read_text()) if st_path.exists() else {}
        ex = st.get('with_hud_excel') or st.get('excel_filled') or st.get('excel_upload') or st.get('excel_template')
        if not ex:
            raise HTTPException(status_code=400, detail='no excel found in session')
        path = Path(ex)
    try:
        report = _headers_report(path)
        return {"ok": True, "session": session, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'report failed: {e}')
