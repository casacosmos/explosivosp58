#!/usr/bin/env python3
"""
Offline smoke tests for excel_to_json_langgraph.py

These tests mock the LLM parsing step to avoid network access while
exercising the loader (CSV/Excel), flexible headers, and measurement-based
capacity calculation.
"""

import os
import math
from pathlib import Path
import pandas as pd


def _mock_parse_with_llm(self, state):
    """Monkeypatched replacement for LangGraphExcelParser._parse_with_llm.
    Builds Tank objects based on row_data heuristics (no network).
    """
    from excel_to_json_langgraph import Tank, TankType  # local import

    rd = state.get("row_data") or {}
    name = rd.get("Tank") or rd.get("Tanque") or rd.get("Tank Name") or rd.get("Nombre") or "Tank"

    # Site / Client
    site = rd.get("Client") or rd.get("Cliente") or rd.get("Site") or rd.get("Business") or rd.get("Empresa") or None

    # Volume direct (gal)
    vol = None
    for key in rd.keys():
        lk = str(key).lower()
        if any(k in lk for k in ["capacidad", "capacity", "volume", "volumen", "gal"]):
            try:
                # Extract first numeric substring
                import re
                m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(rd[key]))
                if m:
                    vol = float(m.group(1))
                    break
            except Exception:
                pass

    rect_dims = None
    if vol is None:
        # Try rectangular dims in feet
        def num(x):
            try:
                return float(x)
            except Exception:
                return None
        L = rd.get("Largo (ft)") or rd.get("Length (ft)") or rd.get("L (ft)")
        W = rd.get("Ancho (ft)") or rd.get("Width (ft)") or rd.get("W (ft)")
        H = rd.get("Altura (ft)") or rd.get("Alto (ft)") or rd.get("Height (ft)") or rd.get("H (ft)")
        L, W, H = num(L), num(W), num(H)
        if (L and W and H) and (L > 0 and W > 0 and H > 0):
            rect_dims = [L, W, H]
            vol = L * W * H * 7.48052

    has_dike = False
    dike = None
    dL = rd.get("Dique Largo (ft)") or rd.get("Dike Length (ft)")
    dW = rd.get("Dique Ancho (ft)") or rd.get("Dike Width (ft)")
    try:
        if dL is not None and dW is not None:
            dike = [float(dL), float(dW)]
            has_dike = True
    except Exception:
        pass

    if vol is None:
        # Signal error to trigger retry cycle in the workflow
        state["parsed_tanks"] = []
        state["errors"] = ["No volume detected"]
        return state

    t = Tank(
        name=str(name),
        volume=float(vol),
        type=TankType.DIESEL,
        has_dike=bool(has_dike),
        dike_dims=dike,
        site=str(site) if site else None,
        rect_dims_ft=rect_dims,
    )
    state["parsed_tanks"] = [t]
    state["errors"] = []
    return state


def test_excel_spanish_headers_capacity(tmp_path: Path = None):
    # Prepare a small Excel with Spanish headers and direct gallons
    tmp = Path("work/tests"); tmp.mkdir(parents=True, exist_ok=True)
    xlsx = tmp / "sample_spanish.xlsx"
    df = pd.DataFrame([
        {
            "Cliente": "Juncos Gas",
            "Tanque": "Diesel #1",
            "Capacidad (gal)": 1200,
            "Dique Largo (ft)": 4,
            "Dique Ancho (ft)": 3.5,
        }
    ])
    df.to_excel(xlsx, index=False)

    # Env key required by parser init; value doesn't matter here
    os.environ.setdefault("OPENAI_API_KEY", "test-key")

    import excel_to_json_langgraph as mod

    # Monkeypatch the LLM step
    orig = mod.LangGraphExcelParser._parse_with_llm
    mod.LangGraphExcelParser._parse_with_llm = _mock_parse_with_llm
    try:
        p = mod.LangGraphExcelParser(str(xlsx), start_row=1, max_rows=1)
        result = p.process_excel()
    finally:
        mod.LangGraphExcelParser._parse_with_llm = orig

    tanks = result.get("tanks", [])
    assert len(tanks) == 1
    t = tanks[0]
    assert t.get("volume") == 1200
    assert t.get("has_dike") is True
    assert t.get("dike_dims") == [4.0, 3.5]
    # Optional: site captured
    assert t.get("site") == "Juncos Gas"


def test_csv_measurements_compute_volume(tmp_path: Path = None):
    # Prepare a CSV with measurements only (feet)
    tmp = Path("work/tests"); tmp.mkdir(parents=True, exist_ok=True)
    csvp = tmp / "sample_dims.csv"
    L, W, H = 4.0, 3.0, 5.0
    df = pd.DataFrame([
        {
            "Client": "Acme Corp",
            "Tank Name": "Storage A",
            "Largo (ft)": L,
            "Ancho (ft)": W,
            "Altura (ft)": H,
        }
    ])
    df.to_csv(csvp, index=False)

    os.environ.setdefault("OPENAI_API_KEY", "test-key")

    import excel_to_json_langgraph as mod

    # Monkeypatch the LLM step
    orig = mod.LangGraphExcelParser._parse_with_llm
    mod.LangGraphExcelParser._parse_with_llm = _mock_parse_with_llm
    try:
        p = mod.LangGraphExcelParser(str(csvp), start_row=1, max_rows=1)
        result = p.process_excel()
    finally:
        mod.LangGraphExcelParser._parse_with_llm = orig

    tanks = result.get("tanks", [])
    assert len(tanks) == 1
    t = tanks[0]
    expected = L * W * H * 7.48052
    assert abs(t.get("volume") - expected) < 1e-6
    assert t.get("rect_dims_ft") == [L, W, H]
    assert t.get("site") == "Acme Corp"


if __name__ == "__main__":
    test_excel_spanish_headers_capacity()
    test_csv_measurements_compute_volume()
    print("All smoke tests passed.")
