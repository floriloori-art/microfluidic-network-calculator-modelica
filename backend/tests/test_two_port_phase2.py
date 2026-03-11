"""
Phase 2 tests: Chamber, Pump (quadratic curve), Valve (Kv coefficient).

Tests verify:
  - Two-port interface (port_a/port_b, pressure_drop, update_ports)
  - New physics (pump curve, Kv valve equation)
  - Backward compatibility with legacy API and existing solver
"""

from __future__ import annotations

import math

import pytest

from backend.models.chamber import Chamber
from backend.models.channel import CircularChannel
from backend.models.medium import FluidMedium
from backend.models.network import FluidNetwork
from backend.models.pump import Pump
from backend.models.valve import Valve
from backend.solver.network_solver import NetworkSolver


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _water() -> FluidMedium:
    return FluidMedium.water_20c()


def _channel(eid: str) -> CircularChannel:
    return CircularChannel(
        element_id=eid, name=eid, radius=100e-6, length=0.01, medium=_water()
    )


# ===========================================================================
# Chamber
# ===========================================================================


class TestChamberTwoPort:
    """Chamber as TwoPortElement."""

    def _chamber(self, height: float = 500e-6, density: float = 998.2) -> Chamber:
        return Chamber(
            element_id="ch", name="ch",
            height=height,
            medium=FluidMedium(density=density),
        )

    # --- Two-port interface ---

    def test_has_ports(self) -> None:
        from backend.ports.connector import FluidPort
        c = self._chamber()
        assert isinstance(c.port_a, FluidPort)
        assert isinstance(c.port_b, FluidPort)

    def test_pressure_drop_near_zero(self) -> None:
        """Chamber body has negligible pressure drop."""
        c = self._chamber()
        mass_flow = 1e-9 * c.medium.density
        dp = c.pressure_drop(mass_flow)
        # dp = R_min * Q = 1e3 * 1e-9 ≈ 1e-6 Pa  →  much less than ΔP in network
        assert dp < 1e-3

    def test_hydrostatic_pressure_formula(self) -> None:
        """ΔP = ρ · g · h."""
        c = self._chamber(height=500e-6, density=998.2)
        expected = 998.2 * 9.81 * 500e-6
        assert math.isclose(c.calculate_hydrostatic_pressure(), expected, rel_tol=1e-6)

    def test_hydrostatic_pressure_proportional_to_height(self) -> None:
        c1 = self._chamber(height=200e-6)
        c2 = self._chamber(height=400e-6)
        assert math.isclose(
            c2.calculate_hydrostatic_pressure() / c1.calculate_hydrostatic_pressure(),
            2.0, rel_tol=1e-6,
        )

    # --- Legacy API ---

    def test_legacy_density_kwarg(self) -> None:
        c = Chamber(element_id="c", name="c", height=500e-6, density=1000.0)
        assert c.medium.density == pytest.approx(1000.0)

    def test_legacy_density_property(self) -> None:
        c = self._chamber(density=1100.0)
        assert c.density == pytest.approx(1100.0)

    def test_to_dict_contains_hydrostatic(self) -> None:
        c = self._chamber()
        d = c.to_dict()
        assert "hydrostatic_pressure" in d
        assert d["hydrostatic_pressure"] > 0

    # --- Backward compat with solver ---

    def test_solver_accepts_chamber(self) -> None:
        network = FluidNetwork("net", "Net")
        network.add_element(_channel("inlet"))
        network.add_element(self._chamber())
        network.add_element(_channel("outlet"))
        network.connect("inlet", "ch")
        network.connect("ch", "outlet")

        result = NetworkSolver().solve(
            network,
            {"inlet": {"pressure": 1000.0}, "outlet": {"pressure": 0.0}},
        )
        assert result.success


# ===========================================================================
# Pump
# ===========================================================================


class TestPumpTwoPort:
    """Pump with quadratic characteristic curve."""

    def _pump(
        self,
        dp_max: float = 1000.0,
        flow_max: float = 1e-6,
        resistance: float = 1e10,
    ) -> Pump:
        return Pump(
            element_id="pump", name="pump",
            pressure_generated=dp_max,
            flow_max=flow_max,
            resistance=resistance,
            medium=_water(),
        )

    # --- Two-port interface ---

    def test_has_ports(self) -> None:
        from backend.ports.connector import FluidPort
        p = self._pump()
        assert isinstance(p.port_a, FluidPort)
        assert isinstance(p.port_b, FluidPort)

    def test_pressure_drop_negative_means_pressure_rise(self) -> None:
        """Pump adds pressure → pressure_drop must be ≤ 0."""
        p = self._pump(dp_max=1000.0, flow_max=1e-6)
        # Small mass flow → pump still near max pressure
        mass_flow = 1e-10 * p.medium.density
        dp = p.pressure_drop(mass_flow)
        assert dp <= 0, f"Expected negative pressure drop, got {dp}"

    def test_pressure_drop_zero_at_max_flow(self) -> None:
        """At Q_max the pump delivers zero pressure."""
        p = self._pump(dp_max=1000.0, flow_max=1e-6)
        mass_flow = 1e-6 * p.medium.density
        dp = p.pressure_drop(mass_flow)
        # dp_pump = dp_max - b*Q_max² = 1000 - 1000 = 0 → -max(0,0) = 0
        assert math.isclose(dp, 0.0, abs_tol=1e-6)

    # --- Characteristic curve ---

    def test_pressure_at_zero_flow_equals_dp_max(self) -> None:
        p = self._pump(dp_max=500.0, flow_max=1e-6)
        assert math.isclose(p.pressure_at_flow(0.0), 500.0, rel_tol=1e-6)

    def test_pressure_at_max_flow_is_zero(self) -> None:
        p = self._pump(dp_max=500.0, flow_max=1e-6)
        assert math.isclose(p.pressure_at_flow(1e-6), 0.0, abs_tol=1e-6)

    def test_pressure_decreases_with_flow(self) -> None:
        """Quadratic curve: higher flow → lower pressure."""
        p = self._pump(dp_max=1000.0, flow_max=2e-6)
        p1 = p.pressure_at_flow(0.5e-6)
        p2 = p.pressure_at_flow(1.0e-6)
        assert p1 > p2

    def test_flow_at_zero_back_pressure_equals_flow_max(self) -> None:
        p = self._pump(dp_max=1000.0, flow_max=1e-6)
        assert math.isclose(p.flow_at_pressure(0.0), 1e-6, rel_tol=1e-5)

    def test_flow_at_dp_max_back_pressure_is_zero(self) -> None:
        p = self._pump(dp_max=1000.0, flow_max=1e-6)
        assert math.isclose(p.flow_at_pressure(1000.0), 0.0, abs_tol=1e-12)

    def test_curve_is_symmetric(self) -> None:
        """flow_at_pressure(pressure_at_flow(Q)) must round-trip.

        pressure_at_flow(Q) returns the pump head dp delivered at flow Q.
        flow_at_pressure(dp) returns Q when the pump works against back-pressure dp.
        So: flow_at_pressure(pressure_at_flow(Q)) == Q.
        """
        p = self._pump(dp_max=800.0, flow_max=2e-6)
        q_orig = 1e-6
        dp_delivered = p.pressure_at_flow(q_orig)       # 800 - b·Q² = 600 Pa
        q_back = p.flow_at_pressure(dp_delivered)       # sqrt((800-600)/b) = 1e-6 ✓
        assert math.isclose(q_back, q_orig, rel_tol=1e-5)

    # --- Legacy API ---

    def test_legacy_area_velocity_constructor(self) -> None:
        p = Pump(
            element_id="p", name="p",
            pressure_generated=500.0,
            resistance=1e10,
            area=1e-6,
            velocity=1.0,
        )
        assert math.isclose(p.flow_max, 1e-6, rel_tol=1e-6)

    def test_legacy_nominal_flow(self) -> None:
        p = self._pump(flow_max=2e-6)
        assert math.isclose(p.get_nominal_flow(), 2e-6, rel_tol=1e-6)

    def test_legacy_calculate_output_pressure(self) -> None:
        """P_out = P_gen - R·Q (old linear formula still works)."""
        p = self._pump(dp_max=1000.0, resistance=1e9)
        p_out = p.calculate_output_pressure(1e-7)
        assert math.isclose(p_out, 1000.0 - 1e9 * 1e-7, rel_tol=1e-6)

    def test_to_dict_contains_curve_info(self) -> None:
        p = self._pump()
        d = p.to_dict()
        assert "flow_max" in d
        assert "curve_coefficient_b" in d
        assert d["is_active"] is True

    # --- Solver backward compatibility ---

    def test_solver_uses_pump_as_pressure_source(self) -> None:
        """Pump's pressure_generated must appear at pump node after solving."""
        network = FluidNetwork("net", "Net")
        pump = self._pump(dp_max=500.0)
        outlet = _channel("outlet")
        network.add_element(pump)
        network.add_element(outlet)
        network.connect("pump", "outlet")

        result = NetworkSolver().solve(
            network, {"outlet": {"pressure": 0.0}}
        )
        assert result.success
        assert math.isclose(result.pressures["pump"], 500.0, rel_tol=1e-6)


# ===========================================================================
# Valve
# ===========================================================================


class TestValveTwoPort:
    """Valve with Kv coefficient and continuous opening."""

    def _valve(self, opening: float = 1.0, kv: float | None = None) -> Valve:
        return Valve(
            element_id="valve", name="valve",
            opening=opening,
            kv=kv,
            medium=_water(),
        )

    # --- Two-port interface ---

    def test_has_ports(self) -> None:
        from backend.ports.connector import FluidPort
        v = self._valve()
        assert isinstance(v.port_a, FluidPort)
        assert isinstance(v.port_b, FluidPort)

    def test_pressure_drop_positive_for_positive_flow(self) -> None:
        v = self._valve(opening=1.0)
        dp = v.pressure_drop(1e-9 * v.medium.density)
        assert dp > 0

    def test_pressure_drop_increases_when_closing(self) -> None:
        """Smaller opening → higher pressure drop for same mass flow."""
        mass_flow = 1e-9 * _water().density
        v_open = self._valve(opening=1.0)
        v_half = self._valve(opening=0.5)
        assert v_half.pressure_drop(mass_flow) > v_open.pressure_drop(mass_flow)

    def test_pressure_drop_quadratic_in_opening(self) -> None:
        """ΔP ∝ 1/opening²: halving opening quadruples ΔP."""
        mass_flow = 1e-9 * _water().density
        v1 = self._valve(opening=1.0)
        v2 = self._valve(opening=0.5)
        ratio = v2.pressure_drop(mass_flow) / v1.pressure_drop(mass_flow)
        assert math.isclose(ratio, 4.0, rel_tol=1e-5)

    # --- Kv equation ---

    def test_kv_equation_round_trip(self) -> None:
        """flow_from_dp(pressure_drop(mass_flow)) must recover original Q."""
        v = self._valve(opening=0.7)
        q_in = 1e-9  # m³/s
        mass_flow = q_in * v.medium.density
        dp = v.pressure_drop(mass_flow)
        q_back = v.flow_from_dp(dp)
        assert math.isclose(q_back, q_in, rel_tol=1e-5)

    def test_resistance_formula(self) -> None:
        """R = 1 / (Kv · opening)²."""
        v = self._valve(opening=0.8)
        expected_r = 1.0 / (v.kv * 0.8) ** 2
        assert math.isclose(v.calculate_resistance(), expected_r, rel_tol=1e-6)

    def test_fully_closed_gives_very_high_resistance(self) -> None:
        v = self._valve(opening=0.0)
        assert v.calculate_resistance() > 1e10

    def test_opening_set_method(self) -> None:
        v = self._valve(opening=1.0)
        v.set_opening(0.3)
        assert math.isclose(v.opening, 0.3)

    def test_set_opening_rejects_out_of_range(self) -> None:
        v = self._valve()
        with pytest.raises(ValueError):
            v.set_opening(1.5)
        with pytest.raises(ValueError):
            v.set_opening(-0.1)

    # --- Legacy binary control ---

    def test_open_sets_opening_to_one(self) -> None:
        v = self._valve(opening=0.0)
        v.open()
        assert math.isclose(v.opening, 1.0)

    def test_close_sets_opening_to_zero(self) -> None:
        v = self._valve(opening=1.0)
        v.close()
        assert math.isclose(v.opening, 0.0)

    def test_toggle_from_open_closes(self) -> None:
        v = self._valve(opening=1.0)
        v.toggle()
        assert math.isclose(v.opening, 0.0)

    def test_toggle_from_closed_opens(self) -> None:
        v = self._valve(opening=0.0)
        v.toggle()
        assert math.isclose(v.opening, 1.0)

    def test_legacy_state_true_means_open(self) -> None:
        v = Valve(element_id="v", name="v", state=True)
        assert math.isclose(v.opening, 1.0)

    def test_legacy_state_false_means_closed(self) -> None:
        v = Valve(element_id="v", name="v", state=False)
        assert math.isclose(v.opening, 0.0)

    def test_resistance_changes_with_state(self) -> None:
        v = Valve(element_id="v", name="v", state=True)
        r_open = v.calculate_resistance()
        v.close()
        r_closed = v.calculate_resistance()
        assert r_closed > r_open

    # --- Solver backward compatibility ---

    def test_open_valve_allows_flow(self) -> None:
        network = FluidNetwork("net", "Net")
        network.add_element(_channel("inlet"))
        network.add_element(self._valve(opening=1.0))
        network.add_element(_channel("outlet"))
        network.connect("inlet", "valve")
        network.connect("valve", "outlet")

        result = NetworkSolver().solve(
            network,
            {"inlet": {"pressure": 1000.0}, "outlet": {"pressure": 0.0}},
        )
        assert result.success
        flow = abs(list(result.flows.values())[0])
        assert flow > 0

    def test_closed_valve_blocks_flow(self) -> None:
        """Nearly-closed valve should result in negligible flow."""
        network = FluidNetwork("net", "Net")
        network.add_element(_channel("inlet"))
        network.add_element(self._valve(opening=0.0))   # fully closed
        network.add_element(_channel("outlet"))
        network.connect("inlet", "valve")
        network.connect("valve", "outlet")

        result = NetworkSolver().solve(
            network,
            {"inlet": {"pressure": 1000.0}, "outlet": {"pressure": 0.0}},
        )
        assert result.success
        flow = abs(list(result.flows.values())[0])
        assert flow < 1e-12   # effectively zero

    def test_partial_opening_reduces_flow(self) -> None:
        """Half-open valve must give less flow than fully open."""
        def solve_flow(opening: float) -> float:
            network = FluidNetwork("net", "Net")
            network.add_element(_channel("inlet"))
            network.add_element(Valve(
                element_id="valve", name="valve",
                opening=opening, medium=_water(),
            ))
            network.add_element(_channel("outlet"))
            network.connect("inlet", "valve")
            network.connect("valve", "outlet")
            result = NetworkSolver().solve(
                network,
                {"inlet": {"pressure": 1000.0}, "outlet": {"pressure": 0.0}},
            )
            return abs(list(result.flows.values())[0])

        assert solve_flow(1.0) > solve_flow(0.5)
