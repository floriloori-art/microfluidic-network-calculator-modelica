"""
End-to-end tests against the live backend (http://localhost:8000).
Uses stdlib urllib (no requests) to avoid Windows connection-pool hang with many sequential requests.

Run with: python backend/tests/test_e2e_api.py
or via pytest: pytest backend/tests/test_e2e_api.py -v
"""
import sys
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
TIMEOUT = 10  # seconds per request


# ── helpers ──────────────────────────────────────────────────────────────────

def http(method: str, path: str, body=None) -> dict | None:
    """Make an HTTP request and return parsed JSON body (or None for no-content)."""
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raw = e.read()
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {raw.decode()}") from e


def check(name: str, cond: bool, got=None) -> bool:
    if cond:
        print(f"  PASS  {name}", flush=True)
    else:
        detail = f"  ->  {got}" if got is not None else ""
        print(f"  FAIL  {name}{detail}", flush=True)
    return cond


# ── test scenarios ────────────────────────────────────────────────────────────

def test_simple_channel() -> bool:
    """Pump(1000 Pa) -> CircularChannel -> Outlet(0 Pa)"""
    print("\n[1] Simple Channel: Pump -> Channel -> Outlet", flush=True)
    d = http("POST", "/network/create", {})
    nid = d["network_id"]
    try:
        http("POST", f"/network/{nid}/element", {"element_id": "pump1",   "name": "Pump 1",   "element_type": "pump",             "parameters": {"pressure_generated": 1000, "flow_max": 1e-6}})
        http("POST", f"/network/{nid}/element", {"element_id": "ch1",     "name": "Channel 1","element_type": "circular_channel", "parameters": {"radius": 100e-6, "length": 0.01, "viscosity": 1e-3}})
        http("POST", f"/network/{nid}/element", {"element_id": "outlet1",  "name": "Outlet 1", "element_type": "chamber",          "parameters": {"height": 0.0, "density": 998.2}})
        http("POST", f"/network/{nid}/connect", {"element_id_1": "pump1",  "element_id_2": "ch1"})
        http("POST", f"/network/{nid}/connect", {"element_id_1": "ch1",    "element_id_2": "outlet1"})
        result = http("POST", f"/network/{nid}/simulate", {"boundary_conditions": [
            {"element_id": "pump1",   "pressure": 1000.0},
            {"element_id": "outlet1", "pressure": 0.0},
        ]})
        p, q = result.get("pressures", {}), result.get("flows", {})
        ok  = check("success flag",                 result.get("success") is True)
        ok &= check("pump pressure ~1000 Pa",       abs(p.get("pump1",   -1) - 1000) < 1, p.get("pump1"))
        ok &= check("outlet pressure ~0 Pa",        abs(p.get("outlet1", -1)       ) < 1, p.get("outlet1"))
        ok &= check("channel pressure in (0,1000)", 0 < p.get("ch1", -1) < 1000,          p.get("ch1"))
        ok &= check("flow > 0",                     any(v > 0 for v in q.values()),        q)
        return ok
    finally:
        try: http("DELETE", f"/network/{nid}")
        except Exception: pass


def test_pump_valve() -> bool:
    """Pump(2000 Pa) -> Valve(0.75) -> Channel -> Outlet(0 Pa)"""
    print("\n[2] Pump + Valve: Pump -> Valve -> Channel -> Outlet", flush=True)
    d = http("POST", "/network/create", {})
    nid = d["network_id"]
    try:
        http("POST", f"/network/{nid}/element", {"element_id": "pump1",   "name": "Pump 1",   "element_type": "pump",             "parameters": {"pressure_generated": 2000, "flow_max": 2e-6}})
        http("POST", f"/network/{nid}/element", {"element_id": "valve1",  "name": "Valve 1",  "element_type": "valve",            "parameters": {"opening": 0.75, "kv": 0.031623}})
        http("POST", f"/network/{nid}/element", {"element_id": "ch1",     "name": "Channel 1","element_type": "circular_channel", "parameters": {"radius": 80e-6, "length": 0.02, "viscosity": 1e-3}})
        http("POST", f"/network/{nid}/element", {"element_id": "outlet1",  "name": "Outlet 1", "element_type": "chamber",          "parameters": {"height": 0.0, "density": 998.2}})
        http("POST", f"/network/{nid}/connect", {"element_id_1": "pump1",  "element_id_2": "valve1"})
        http("POST", f"/network/{nid}/connect", {"element_id_1": "valve1", "element_id_2": "ch1"})
        http("POST", f"/network/{nid}/connect", {"element_id_1": "ch1",    "element_id_2": "outlet1"})
        result = http("POST", f"/network/{nid}/simulate", {"boundary_conditions": [
            {"element_id": "pump1",   "pressure": 2000.0},
            {"element_id": "outlet1", "pressure": 0.0},
        ]})
        p = result.get("pressures", {})
        ok  = check("success flag",         result.get("success") is True)
        ok &= check("pump ~2000 Pa",        abs(p.get("pump1",   -1) - 2000) < 1, p.get("pump1"))
        ok &= check("outlet ~0 Pa",         abs(p.get("outlet1", -1)       ) < 1, p.get("outlet1"))
        pv = p.get("valve1", -1)
        ok &= check("valve pressure < pump", 0 < pv < 2000, pv)
        return ok
    finally:
        try: http("DELETE", f"/network/{nid}")
        except Exception: pass


def test_t_junction() -> bool:
    """Pump -> [ch_a(short), ch_b(long)] -> Outlet  (parallel)"""
    print("\n[3] T-Junction: Pump -> [ch_a(short), ch_b(long)] -> Outlet", flush=True)
    d = http("POST", "/network/create", {})
    nid = d["network_id"]
    try:
        http("POST", f"/network/{nid}/element", {"element_id": "pump1",   "name": "Pump 1",   "element_type": "pump",             "parameters": {"pressure_generated": 1000, "flow_max": 1e-6}})
        http("POST", f"/network/{nid}/element", {"element_id": "ch_a",    "name": "Channel A","element_type": "circular_channel", "parameters": {"radius": 100e-6, "length": 0.01, "viscosity": 1e-3}})
        http("POST", f"/network/{nid}/element", {"element_id": "ch_b",    "name": "Channel B","element_type": "circular_channel", "parameters": {"radius": 100e-6, "length": 0.02, "viscosity": 1e-3}})
        http("POST", f"/network/{nid}/element", {"element_id": "outlet1",  "name": "Outlet 1", "element_type": "chamber",          "parameters": {"height": 0.0, "density": 998.2}})
        http("POST", f"/network/{nid}/connect", {"element_id_1": "pump1",  "element_id_2": "ch_a"})
        http("POST", f"/network/{nid}/connect", {"element_id_1": "pump1",  "element_id_2": "ch_b"})
        http("POST", f"/network/{nid}/connect", {"element_id_1": "ch_a",   "element_id_2": "outlet1"})
        http("POST", f"/network/{nid}/connect", {"element_id_1": "ch_b",   "element_id_2": "outlet1"})
        result = http("POST", f"/network/{nid}/simulate", {"boundary_conditions": [
            {"element_id": "pump1",   "pressure": 1000.0},
            {"element_id": "outlet1", "pressure": 0.0},
        ]})
        q = result.get("flows", {})
        ok  = check("success flag", result.get("success") is True)
        flow_a = next((v for k, v in q.items() if "ch_a" in k), None)
        flow_b = next((v for k, v in q.items() if "ch_b" in k), None)
        ok &= check("flow through ch_a exists", flow_a is not None, flow_a)
        ok &= check("flow through ch_b exists", flow_b is not None, flow_b)
        if flow_a is not None and flow_b is not None:
            ok &= check("ch_a flow > ch_b (shorter = less resistance)",
                        flow_a > flow_b, f"ch_a={flow_a:.3e}  ch_b={flow_b:.3e}")
        return ok
    finally:
        try: http("DELETE", f"/network/{nid}")
        except Exception: pass


def test_hydrostatic_inlet() -> bool:
    """Chamber(h=0.5m, density=998.2) -> Channel -> Outlet  => BC ~ 4893 Pa"""
    print("\n[4] Hydrostatic Inlet: Chamber(0.5m water) -> Channel -> Outlet", flush=True)
    d = http("POST", "/network/create", {})
    nid = d["network_id"]
    try:
        rho, g, h = 998.2, 9.81, 0.5
        expected_p = rho * g * h   # ~4893 Pa
        http("POST", f"/network/{nid}/element", {"element_id": "inlet",   "name": "Inlet",    "element_type": "chamber",          "parameters": {"height": h,   "density": rho}})
        http("POST", f"/network/{nid}/element", {"element_id": "ch1",     "name": "Channel 1","element_type": "circular_channel", "parameters": {"radius": 100e-6, "length": 0.01, "viscosity": 1e-3}})
        http("POST", f"/network/{nid}/element", {"element_id": "outlet1",  "name": "Outlet 1", "element_type": "chamber",          "parameters": {"height": 0.0, "density": 998.2}})
        http("POST", f"/network/{nid}/connect", {"element_id_1": "inlet",  "element_id_2": "ch1"})
        http("POST", f"/network/{nid}/connect", {"element_id_1": "ch1",    "element_id_2": "outlet1"})
        result = http("POST", f"/network/{nid}/simulate", {"boundary_conditions": [
            {"element_id": "inlet",   "pressure": expected_p},
            {"element_id": "outlet1", "pressure": 0.0},
        ]})
        p = result.get("pressures", {})
        ok  = check("success flag", result.get("success") is True)
        ok &= check(
            f"inlet pressure ~{expected_p:.1f} Pa (+/- 5 Pa)",
            abs(p.get("inlet", -1) - expected_p) < 5,
            p.get("inlet"),
        )
        ok &= check("outlet pressure ~0 Pa", abs(p.get("outlet1", -1)) < 1, p.get("outlet1"))
        return ok
    finally:
        try: http("DELETE", f"/network/{nid}")
        except Exception: pass


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    try:
        d = http("GET", "/health")
        print(f"Backend health: {d}", flush=True)
    except Exception as e:
        print(f"ERROR: Cannot reach backend at {BASE}: {e}")
        sys.exit(1)

    tests = [test_simple_channel, test_pump_valve, test_t_junction, test_hydrostatic_inlet]
    results = [t() for t in tests]

    passed = sum(results)
    failed  = len(results) - passed
    print(f"\n{'='*50}", flush=True)
    print(f"Results: {passed} passed, {failed} failed", flush=True)
    print("="*50, flush=True)
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
