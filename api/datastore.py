#!/usr/bin/env python3
import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class SessionDataStore:
    """JSON-backed datastore to maintain a canonical session state across pipeline steps."""

    def __init__(self, session_dir: Path, session_id: str):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.store_path = self.session_dir / 'datastore.json'
        self.session_id = session_id
        self.data: Dict[str, Any] = {
            'session': session_id,
            'tanks': [],
            'meta': {},
            'field_study': {
                'date': None,
                'time': None,
                'weather': None,
                'team_lead': None,
                'team_members': [],
                'contacts': []  # People consulted at site
            },
            'updated_at': None,
        }
        self._index_by_name: Dict[str, int] = {}
        self.load()

    def load(self):
        if self.store_path.exists():
            try:
                self.data = json.loads(self.store_path.read_text())
            except Exception:
                pass
        self._reindex()

    def save(self):
        self.data['updated_at'] = datetime.utcnow().isoformat() + 'Z'
        self.store_path.write_text(json.dumps(self.data, indent=2))

    def _reindex(self):
        self._index_by_name = {}
        for i, t in enumerate(self.data.get('tanks', [])):
            name = (t.get('name') or '').strip()
            if name:
                self._index_by_name[name.lower()] = i

    def _upsert_tank(self, name: str) -> Dict[str, Any]:
        k = (name or '').strip().lower()
        if not k:
            k = f"tank_{len(self.data['tanks'])+1}"
        if k in self._index_by_name:
            return self.data['tanks'][self._index_by_name[k]]
        tank = {
            'name': name,
            'id': len(self.data['tanks']) + 1,
            'volume_gal': None,
            'measurements': None,
            'type': None,
            'has_dike': None,
            'dike_dims': None,
            'coords': None,
            'hud': None,
            'distance_to_polygon_ft': None,
            'closest_point': None,
            'point_location': None,
            'compliance': None,
            # Field study data
            'inspected_by': None,  # Person who inspected this tank
            'inspection_time': None,
            'contact_person': None,  # Site contact for this tank
            'field_notes': None,
        }
        self.data['tanks'].append(tank)
        self._reindex()
        return tank

    def update_meta(self, **kwargs):
        m = self.data.setdefault('meta', {})
        m.update({k: v for k, v in kwargs.items() if v is not None})

    def upsert_from_config(self, config: Dict[str, Any]):
        for t in config.get('tanks', []):
            name = t.get('name') or t.get('id') or f"tank_{len(self.data['tanks'])+1}"
            rec = self._upsert_tank(str(name))
            vol = t.get('volume')
            rec['volume_gal'] = float(vol) if isinstance(vol, (int, float)) else rec['volume_gal']
            rec['type'] = t.get('type') or rec['type']
            rec['has_dike'] = bool(t.get('has_dike')) if t.get('has_dike') is not None else rec['has_dike']
            if isinstance(t.get('dike_dims'), list) and len(t['dike_dims']) == 2:
                rec['dike_dims'] = [float(x) for x in t['dike_dims']]
            # optional
            if t.get('measurements'):
                rec['measurements'] = t['measurements']

    def merge_hud_results(self, results: List[Dict[str, Any]]):
        for r in results:
            name = r.get('name')
            if not name:
                continue
            rec = self._upsert_tank(name)
            res = r.get('results') or {}
            try:
                hud = {
                    'asdppu': float(str(res.get('asdppu')).replace('ft', '').strip()) if res.get('asdppu') else None,
                    'asdbpu': float(str(res.get('asdbpu')).replace('ft', '').strip()) if res.get('asdbpu') else None,
                    'asdpnpd': float(str(res.get('asdpnpd')).replace('ft', '').strip()) if res.get('asdpnpd') else None,
                    'asdbnpd': float(str(res.get('asdbnpd')).replace('ft', '').strip()) if res.get('asdbnpd') else None,
                }
                vals = [v for v in hud.values() if isinstance(v, (int, float))]
                hud['max_asd_ft'] = max(vals) if vals else None
                rec['hud'] = hud
                vol = r.get('volume')
                if isinstance(vol, (int, float)):
                    rec['volume_gal'] = float(vol)
            except Exception:
                pass

    def merge_distances_from_excel(self, excel_path: Path):
        import pandas as pd
        df = pd.read_excel(excel_path)
        if df.empty:
            return
        name_col = df.columns[0]
        def safe_num(x):
            try:
                return float(x)
            except Exception:
                return None
        for _, row in df.iterrows():
            name = str(row.get(name_col)) if row.get(name_col) is not None else None
            if not name:
                continue
            rec = self._upsert_tank(name)
            # coords
            lat = row.get('Latitude (NAD83)')
            lon = row.get('Longitude (NAD83)')
            if lat is not None and lon is not None:
                rec['coords'] = {'lat': safe_num(lat), 'lon': safe_num(lon)}
            # distances
            dist = row.get('Calculated Distance to Polygon (ft)') or row.get('Distance to Polygon Boundary (ft)')
            rec['distance_to_polygon_ft'] = safe_num(dist)
            cplat = row.get('Closest Point Lat') or row.get('Closest Boundary Point Lat')
            cplon = row.get('Closest Point Lon') or row.get('Closest Boundary Point Lon')
            if cplat is not None and cplon is not None:
                rec['closest_point'] = {'lat': safe_num(cplat), 'lon': safe_num(cplon)}
            rec['point_location'] = row.get('Point Location') or rec.get('point_location')
            # compliance
            status = row.get('Compliance')
            notes = row.get('Compliance Notes')
            if status or notes:
                rec['compliance'] = {'status': status, 'notes': notes}

    def update_field_study(self, field_data: Dict[str, Any]):
        """Update field study metadata"""
        fs = self.data.setdefault('field_study', {})
        for key in ['date', 'time', 'weather', 'team_lead']:
            if key in field_data and field_data[key]:
                fs[key] = field_data[key]

        # Handle arrays
        if 'team_members' in field_data:
            fs['team_members'] = field_data['team_members']
        if 'contacts' in field_data:
            fs['contacts'] = field_data['contacts']

        self.save()

    def add_contact(self, contact: Dict[str, Any]):
        """Add a person consulted during field study"""
        fs = self.data.setdefault('field_study', {})
        contacts = fs.setdefault('contacts', [])

        # Required: name, optional: role, company, phone, email, notes
        new_contact = {
            'name': contact.get('name'),
            'role': contact.get('role'),
            'company': contact.get('company'),
            'phone': contact.get('phone'),
            'email': contact.get('email'),
            'notes': contact.get('notes'),
            'timestamp': datetime.utcnow().isoformat()
        }

        contacts.append(new_contact)
        self.save()
        return new_contact

    def to_dict(self) -> Dict[str, Any]:
        return self.data


def load_store(work_root: Path, session: str) -> SessionDataStore:
    backend = os.getenv('DATASTORE_BACKEND', 'json').strip().lower()
    if backend == 'sqlite':
        return SQLiteSessionDataStore(work_root / session, session)
    return SessionDataStore(work_root / session, session)


class SQLiteSessionDataStore:
    """SQLite-backed datastore with same public API as SessionDataStore."""

    def __init__(self, session_dir: Path, session_id: str):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id
        self.db_path = self.session_dir / 'datastore.db'
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute('PRAGMA journal_mode=WAL;')
        self._init_schema()

    def _init_schema(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS tanks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                volume_gal REAL,
                measurements TEXT,
                type TEXT,
                has_dike INTEGER,
                dike_len REAL,
                dike_wid REAL,
                lat REAL,
                lon REAL,
                hud_asdppu REAL,
                hud_asdbpu REAL,
                hud_asdpnpd REAL,
                hud_asdbnpd REAL,
                hud_max_asd_ft REAL,
                distance_to_polygon_ft REAL,
                closest_lat REAL,
                closest_lon REAL,
                point_location TEXT,
                compliance_status TEXT,
                compliance_notes TEXT,
                updated_at TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tanks_name ON tanks(name)")
        self.conn.commit()

    def save(self):
        self._set_meta('updated_at', datetime.utcnow().isoformat() + 'Z')

    def _set_meta(self, key: str, value: Any):
        self.conn.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, json.dumps(value) if not isinstance(value, str) else value))
        self.conn.commit()

    def update_meta(self, **kwargs):
        for k, v in kwargs.items():
            if v is not None:
                self._set_meta(k, v)

    def _upsert_tank_id(self, name: str) -> int:
        name = (name or '').strip()
        if not name:
            name = f"tank_{int(datetime.utcnow().timestamp())}"
        cur = self.conn.cursor()
        cur.execute("INSERT OR IGNORE INTO tanks(name, updated_at) VALUES(?, ?)", (name, datetime.utcnow().isoformat() + 'Z'))
        self.conn.commit()
        cur.execute("SELECT id FROM tanks WHERE name=?", (name,))
        row = cur.fetchone()
        return int(row[0])

    def upsert_from_config(self, config: Dict[str, Any]):
        cur = self.conn.cursor()
        for t in config.get('tanks', []):
            name = str(t.get('name') or t.get('id') or '')
            tid = self._upsert_tank_id(name)
            vol = t.get('volume')
            has_dike = t.get('has_dike')
            dike = t.get('dike_dims') if isinstance(t.get('dike_dims'), list) else None
            measurements = t.get('measurements')
            cur.execute(
                """
                UPDATE tanks SET
                    volume_gal = COALESCE(?, volume_gal),
                    measurements = COALESCE(?, measurements),
                    type = COALESCE(?, type),
                    has_dike = COALESCE(?, has_dike),
                    dike_len = COALESCE(?, dike_len),
                    dike_wid = COALESCE(?, dike_wid),
                    updated_at = ?
                WHERE id=?
                """,
                (
                    float(vol) if isinstance(vol, (int, float)) else None,
                    measurements,
                    t.get('type'),
                    1 if has_dike is True else 0 if has_dike is False else None,
                    float(dike[0]) if dike and len(dike) == 2 else None,
                    float(dike[1]) if dike and len(dike) == 2 else None,
                    datetime.utcnow().isoformat() + 'Z',
                    tid,
                ),
            )
        self.conn.commit()

    def merge_hud_results(self, results: List[Dict[str, Any]]):
        cur = self.conn.cursor()
        for r in results:
            name = r.get('name')
            if not name:
                continue
            tid = self._upsert_tank_id(name)
            res = r.get('results') or {}
            def f(x):
                try:
                    return float(str(x).replace('ft','').strip()) if x is not None else None
                except Exception:
                    return None
            asdppu = f(res.get('asdppu'))
            asdbpu = f(res.get('asdbpu'))
            asdpnpd = f(res.get('asdpnpd'))
            asdbnpd = f(res.get('asdbnpd'))
            maxasd = max([v for v in [asdppu, asdbpu, asdpnpd, asdbnpd] if v is not None], default=None)
            vol = r.get('volume')
            cur.execute(
                """
                UPDATE tanks SET
                    hud_asdppu=?, hud_asdbpu=?, hud_asdpnpd=?, hud_asdbnpd=?, hud_max_asd_ft=?,
                    volume_gal=COALESCE(?, volume_gal), updated_at=?
                WHERE id=?
                """,
                (asdppu, asdbpu, asdpnpd, asdbnpd, maxasd, float(vol) if isinstance(vol,(int,float)) else None, datetime.utcnow().isoformat()+'Z', tid),
            )
        self.conn.commit()

    def merge_distances_from_excel(self, excel_path: Path):
        import pandas as pd
        df = pd.read_excel(excel_path)
        if df.empty:
            return
        name_col = df.columns[0]
        def fnum(x):
            try:
                return float(x)
            except Exception:
                return None
        cur = self.conn.cursor()
        for _, row in df.iterrows():
            name = row.get(name_col)
            if name is None or str(name).strip() == '':
                continue
            tid = self._upsert_tank_id(str(name))
            lat = fnum(row.get('Latitude (NAD83)'))
            lon = fnum(row.get('Longitude (NAD83)'))
            dist = fnum(row.get('Calculated Distance to Polygon (ft)') or row.get('Distance to Polygon Boundary (ft)'))
            cplat = fnum(row.get('Closest Point Lat') or row.get('Closest Boundary Point Lat'))
            cplon = fnum(row.get('Closest Point Lon') or row.get('Closest Boundary Point Lon'))
            loc = row.get('Point Location')
            status = row.get('Compliance')
            notes = row.get('Compliance Notes')
            cur.execute(
                """
                UPDATE tanks SET
                    lat=COALESCE(?, lat), lon=COALESCE(?, lon),
                    distance_to_polygon_ft=COALESCE(?, distance_to_polygon_ft),
                    closest_lat=COALESCE(?, closest_lat),
                    closest_lon=COALESCE(?, closest_lon),
                    point_location=COALESCE(?, point_location),
                    compliance_status=COALESCE(?, compliance_status),
                    compliance_notes=COALESCE(?, compliance_notes),
                    updated_at=?
                WHERE id=?
                """,
                (lat, lon, dist, cplat, cplon, loc, status, notes, datetime.utcnow().isoformat()+'Z', tid),
            )
        self.conn.commit()

    def to_dict(self) -> Dict[str, Any]:
        meta_rows = self.conn.execute("SELECT key, value FROM meta").fetchall()
        meta: Dict[str, Any] = {}
        for k, v in meta_rows:
            try:
                meta[k] = json.loads(v)
            except Exception:
                meta[k] = v
        tanks = []
        for row in self.conn.execute(
            """
            SELECT name, id, volume_gal, measurements, type, has_dike, dike_len, dike_wid,
                   lat, lon, hud_asdppu, hud_asdbpu, hud_asdpnpd, hud_asdbnpd, hud_max_asd_ft,
                   distance_to_polygon_ft, closest_lat, closest_lon, point_location,
                   compliance_status, compliance_notes
            FROM tanks
            ORDER BY id ASC
            """
        ).fetchall():
            (name, tid, vol, meas, typ, has_dike, dlen, dwid, lat, lon,
             asdppu, asdbpu, asdpnpd, asdbnpd, maxasd, dist, cplat, cplon, ploc,
             cstatus, cnotes) = row
            tank: Dict[str, Any] = {
                'name': name,
                'id': tid,
                'volume_gal': vol,
                'measurements': meas,
                'type': typ,
                'has_dike': bool(has_dike) if has_dike is not None else None,
                'dike_dims': [dlen, dwid] if dlen is not None and dwid is not None else None,
                'coords': {'lat': lat, 'lon': lon} if lat is not None and lon is not None else None,
                'hud': {
                    'asdppu': asdppu,
                    'asdbpu': asdbpu,
                    'asdpnpd': asdpnpd,
                    'asdbnpd': asdbnpd,
                    'max_asd_ft': maxasd,
                } if any(x is not None for x in [asdppu, asdbpu, asdpnpd, asdbnpd, maxasd]) else None,
                'distance_to_polygon_ft': dist,
                'closest_point': {'lat': cplat, 'lon': cplon} if cplat is not None and cplon is not None else None,
                'point_location': ploc,
                'compliance': {'status': cstatus, 'notes': cnotes} if cstatus or cnotes else None,
            }
            tanks.append(tank)
        updated_at = meta.get('updated_at')
        return {
            'session': self.session_id,
            'tanks': tanks,
            'meta': meta,
            'updated_at': updated_at,
        }

