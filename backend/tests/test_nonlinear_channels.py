"""Tests for nonlinear (Reynolds-dependent) channel elements.

Covers:
  - Laminar-regime behaviour matches CircularChannel / RectangularChannel
  - Turbulent branch uses Blasius friction factor (Darcy-Weisbach)
  - Smooth blending in the transition zone (Re 2300 - 4000)
  - Picard iteration in the solver converges for nonlinear networks
  - Reynolds-number reporting via get_reynolds / element_results
  - Legacy (viscosity, density) API still works

Unit system: SI.  All tolerances chosen for 64-bit float arithmetic.
"""

from __future__ import annotations

import math

import pytest

from backend.models.channel import (
    CircularChannel,
    NonlinearCircularChannel,
    NonlinearRectangularChannel,
    RectangularChannel,
    _blend_resistance,
    _RE_LAMINAR,
    _RE_TURBULENT,
)
from backend.models.medium import FluidMedium
from backend.models.network import FluidNetwork
from backend.solver.network_solver import NetworkSolver


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

WATER = FluidMedium(dynamic_viscosity=1e-3, density=998.2)


def _re_for_circular(radius: float, flow: float, medium: FluidMedium) -> float:
    """Analytical Reynolds number for a circular pipe."""
    D = 2.0 * radius
    A = math.pi * radius ** 2
    v = abs(flow) / A
    return medium.density * v * D / medium.dynamic_viscosity


# ---------------------------------------------------------------------------
# Laminar branch: nonlinear ≡ linear below Re = 2300
# ---------------------------------------------------------------------------


class TestLaminarRegime:
    """Below Re = 2300 the nonlinear model must agree with the linear one."""

    def test_circular_matches_laminar_at_zero_flow(self) -> None:
        nl = NonlinearCircularChannel(
            "ch1", "ch1", radius=100e-6, length=0.01, medium=WATER,
        )
        lin = CircularChannel(
            "ch1", "ch1", radius=100e-6, length=0.01, medium=WATER,
        )
        # At zero flow the Picard linearisation must give the Hagen-Poiseuille
        # resistance exactly.
        nl.update_resistance(0.0)
        assert math.isclose(
            nl.calculate_resistance(), lin.calculate_resistance(), rel_tol=1e-12
        )

    def test_rectangular_matches_laminar_at_zero_flow(self) -> None:
        nl = NonlinearRectangularChannel(
            "ch1", "ch1", width=100e-6, height=50e-6, length=0.01, medium=WATER,
        )
        lin = RectangularChannel(
            "ch1", "ch1", width=100e-6, height=50e-6, length=0.01, medium=WATER,
        )
        nl.update_resistance(0.0)
        assert math.isclose(
            nl.calculate_resistance(), lin.calculate_resistance(), rel_tol=1e-12
        )

    def test_circular_small_flow_stays_laminar(self) -> None:
        """A 100 µm channel at 1 nL/s is deeply laminar (Re << 2300)."""
        nl = NonlinearCircularChannel(
            "ch1", "ch1", radius=100e-6, length=0.01, medium=WATER,
        )
        q = 1e-12  # 1 pL/s
        re = _re_for_circular(100e-6, q, WATER)
        assert re < _RE_LAMINAR
        nl.update_resistance(q)
        lin_r = CircularChannel(
            "ch1", "ch1", radius=100e-6, length=0.01, medium=WATER,
        ).calculate_resistance()
        assert math.isclose(nl.calculate_resistance(), lin_r, rel_tol=1e-12)

    def test_is_nonlinear_flag(self) -> None:
        nl = NonlinearCircularChannel(
            "ch1", "ch1", radius=100e-6, length=0.01, medium=WATER,
        )
        assert nl.is_nonlinear is True
        lin = CircularChannel(
            "ch1", "ch1", radius=100e-6, length=0.01, medium=WATER,
        )
        assert getattr(lin, "is_nonlinear", False) is False


# ---------------------------------------------------------------------------
# Turbulent branch: Blasius friction factor
# ---------------------------------------------------------------------------


class TestTurbulentRegime:
    """Above Re = 4000 the resistance must follow the Blasius correlation."""

    def test_circular_turbulent_blasius(self) -> None:
        """R_turb = f · L · ρ · |Q| / (2 · D · A²) with f = 0.316 · Re^(-0.25)."""
        radius = 500e-6  # large enough to reach turbulence at reasonable Q
        length = 0.05
        # Pick a flow that gives Re ≈ 8000 (well inside Blasius range)
        target_re = 8000.0
        D = 2.0 * radius
        A = math.pi * radius ** 2
        v = target_re * WATER.dynamic_viscosity / (WATER.density * D)
        q = v * A

        nl = NonlinearCircularChannel(
            "ch", "ch", radius=radius, length=length, medium=WATER,
        )
        nl.update_resistance(q)

        # Compute expected Blasius resistance analytically
        re = _re_for_circular(radius, q, WATER)
        assert re > _RE_TURBULENT  # precondition
        f = 0.316 * re ** (-0.25)
        r_expected = f * length * WATER.density * q / (2.0 * D * A ** 2)

        assert math.isclose(nl.calculate_resistance(), r_expected, rel_tol=1e-9)

    def test_turbulent_greater_than_laminar(self) -> None:
        """At high Re the effective resistance exceeds the laminar value."""
        radius = 500e-6
        length = 0.05
        nl = NonlinearCircularChannel(
            "ch", "ch", radius=radius, length=length, medium=WATER,
        )
        lin_r = CircularChannel(
            "ch", "ch", radius=radius, length=length, medium=WATER,
        ).calculate_resistance()

        # Flow large enough for Re > 4000
        q = 1e-5  # 10 mL/s — certainly turbulent in a 500 µm channel
        nl.update_resistance(q)
        assert nl.calculate_resistance() > lin_r

    def test_rectangular_turbulent_uses_hydraulic_diameter(self) -> None:
        """Rectangular channel must use D_h = 2·w·h / (w+h) for Re."""
        width, height = 500e-6, 500e-6
        length = 0.05
        nl = NonlinearRectangularChannel(
            "ch", "ch",
            width=width, height=height, length=length, medium=WATER,
        )

        q = 5e-6  # should be turbulent for these dims
        nl.update_resistance(q)
        re = nl.get_reynolds(q)

        D_h = 2.0 * width * height / (width + height)
        A = width * height
        v = q / A
        re_expected = WATER.density * v * D_h / WATER.dynamic_viscosity
        assert math.isclose(re, re_expected, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# Transition-zone blending
# ---------------------------------------------------------------------------


class TestBlending:
    """Resistance must be continuous across the transition zone."""

    def test_blend_at_lower_bound_is_laminar(self) -> None:
        r = _blend_resistance(r_lam=1.0, r_turb=2.0, re=_RE_LAMINAR)
        assert math.isclose(r, 1.0, rel_tol=1e-12)

    def test_blend_at_upper_bound_is_turbulent(self) -> None:
        r = _blend_resistance(r_lam=1.0, r_turb=2.0, re=_RE_TURBULENT)
        assert math.isclose(r, 2.0, rel_tol=1e-12)

    def test_blend_midpoint(self) -> None:
        mid = 0.5 * (_RE_LAMINAR + _RE_TURBULENT)
        r = _blend_resistance(r_lam=1.0, r_turb=3.0, re=mid)
        assert math.isclose(r, 2.0, rel_tol=1e-12)

    def test_blend_below_laminar_clamped(self) -> None:
        r = _blend_resistance(r_lam=1.0, r_turb=2.0, re=100.0)
        assert r == 1.0

    def test_blend_above_turbulent_clamped(self) -> None:
        r = _blend_resistance(r_lam=1.0, r_turb=2.0, re=1e6)
        assert r == 2.0


# ---------------------------------------------------------------------------
# Reynolds-number reporting
# ---------------------------------------------------------------------------


class TestReynoldsReporting:
    def test_get_reynolds_zero_flow(self) -> None:
        nl = NonlinearCircularChannel(
            "ch", "ch", radius=100e-6, length=0.01, medium=WATER,
        )
        assert nl.get_reynolds(0.0) == 0.0

    def test_get_reynolds_matches_analytical(self) -> None:
        nl = NonlinearCircularChannel(
            "ch", "ch", radius=100e-6, length=0.01, medium=WATER,
        )
        q = 1e-7
        expected = _re_for_circular(100e-6, q, WATER)
        assert math.isclose(nl.get_reynolds(q), expected, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# Solver integration: Picard iteration
# ---------------------------------------------------------------------------


class TestPicardIteration:
    """End-to-end: solver must converge and report Reynolds numbers."""

    def _build_single_channel_network(
        self, channel_cls, inlet_pressure: float, **channel_kwargs,
    ) -> tuple[FluidNetwork, dict]:
        """inlet -(channel)- outlet network with Dirichlet BCs."""
        # A cheap way to get Dirichlet-only BCs: use a short linear resistance
        # as an inlet-node stand-in.  But the solver expects each connection
        # to connect two elements; easiest is to chain two channels and put
        # BCs on the end nodes.
        net = FluidNetwork("nl_test", "Nonlinear test network")
        # Very short "wire" resistor at inlet/outlet so we can place BCs there
        inlet = CircularChannel(
            "inlet", "inlet", radius=500e-6, length=1e-6, medium=WATER,
        )
        outlet = CircularChannel(
            "outlet", "outlet", radius=500e-6, length=1e-6, medium=WATER,
        )
        channel = channel_cls("ch", "ch", medium=WATER, **channel_kwargs)
        net.add_element(inlet)
        net.add_element(channel)
        net.add_element(outlet)
        net.connect("inlet", "ch")
        net.connect("ch", "outlet")
        bc = {
            "inlet": {"pressure": inlet_pressure},
            "outlet": {"pressure": 0.0},
        }
        return net, bc

    def test_linear_network_runs_one_picard_iteration(self) -> None:
        """With no nonlinear elements the solver must do exactly one pass."""
        net, bc = self._build_single_channel_network(
            CircularChannel, inlet_pressure=100.0,
            radius=100e-6, length=0.01,
        )
        solver = NetworkSolver()
        result = solver.solve(net, bc)
        assert result.success
        # Implementation detail: iterations counter corresponds to the number
        # of Picard iterations run (1 for linear networks).
        assert result.iterations == 1

    def test_nonlinear_laminar_matches_linear(self) -> None:
        """At low ΔP, nonlinear network reproduces the linear solution."""
        # Linear
        net_lin, bc = self._build_single_channel_network(
            CircularChannel, inlet_pressure=10.0,
            radius=100e-6, length=0.01,
        )
        r_lin = NetworkSolver().solve(net_lin, bc)

        # Nonlinear
        net_nl, _ = self._build_single_channel_network(
            NonlinearCircularChannel, inlet_pressure=10.0,
            radius=100e-6, length=0.01,
        )
        r_nl = NetworkSolver().solve(net_nl, bc)

        q_lin = r_lin.flows[("inlet", "ch")]
        q_nl = r_nl.flows[("inlet", "ch")]
        assert math.isclose(q_lin, q_nl, rel_tol=1e-6)

    def test_nonlinear_turbulent_flow_reduced_vs_laminar_model(self) -> None:
        """At high ΔP a turbulent channel carries less flow than the laminar
        model would predict (because R grows with |Q|)."""
        # Large radius + high pressure → turbulent
        net_lin, bc = self._build_single_channel_network(
            CircularChannel, inlet_pressure=1e6,
            radius=500e-6, length=0.05,
        )
        r_lin = NetworkSolver().solve(net_lin, bc)

        net_nl, _ = self._build_single_channel_network(
            NonlinearCircularChannel, inlet_pressure=1e6,
            radius=500e-6, length=0.05,
        )
        r_nl = NetworkSolver().solve(net_nl, bc)

        q_lin = abs(r_lin.flows[("inlet", "ch")])
        q_nl = abs(r_nl.flows[("inlet", "ch")])
        assert q_nl < q_lin, (
            f"Nonlinear flow ({q_nl:.3e}) should be < linear flow ({q_lin:.3e})"
        )
        # And the Picard loop must have actually iterated > 1 time
        assert r_nl.iterations > 1

    def test_element_results_contain_reynolds(self) -> None:
        net, bc = self._build_single_channel_network(
            NonlinearCircularChannel, inlet_pressure=1e6,
            radius=500e-6, length=0.05,
        )
        result = NetworkSolver().solve(net, bc)
        assert result.success
        ch_result = result.element_results["ch"]
        assert "reynolds" in ch_result
        assert ch_result["reynolds"] > 0.0

    def test_picard_converges_within_tolerance(self) -> None:
        net, bc = self._build_single_channel_network(
            NonlinearCircularChannel, inlet_pressure=5e5,
            radius=300e-6, length=0.02,
        )
        result = NetworkSolver(
            nonlinear_iterations=50, nonlinear_tolerance=1e-8,
        ).solve(net, bc)
        assert result.success
        # Should converge well before hitting the iteration cap
        assert result.iterations < 50

    def test_rectangular_nonlinear_end_to_end(self) -> None:
        net = FluidNetwork("rect_nl", "Rectangular nonlinear")
        inlet = CircularChannel(
            "inlet", "inlet", radius=500e-6, length=1e-6, medium=WATER,
        )
        outlet = CircularChannel(
            "outlet", "outlet", radius=500e-6, length=1e-6, medium=WATER,
        )
        ch = NonlinearRectangularChannel(
            "ch", "ch", width=500e-6, height=500e-6, length=0.05, medium=WATER,
        )
        for e in (inlet, ch, outlet):
            net.add_element(e)
        net.connect("inlet", "ch")
        net.connect("ch", "outlet")
        bc = {"inlet": {"pressure": 5e5}, "outlet": {"pressure": 0.0}}
        result = NetworkSolver().solve(net, bc)
        assert result.success
        assert "reynolds" in result.element_results["ch"]


# ---------------------------------------------------------------------------
# Legacy (viscosity, density) constructor API
# ---------------------------------------------------------------------------


class TestLegacyAPI:
    """The old (viscosity=, density=) kwargs must still work."""

    def test_legacy_circular_kwargs(self) -> None:
        nl = NonlinearCircularChannel(
            "ch", "ch",
            radius=100e-6, length=0.01,
            viscosity=1.2e-3, density=1050.0,
        )
        assert math.isclose(nl.medium.dynamic_viscosity, 1.2e-3, rel_tol=1e-12)
        assert math.isclose(nl.medium.density, 1050.0, rel_tol=1e-12)
        assert math.isclose(nl.density, 1050.0, rel_tol=1e-12)

    def test_legacy_rectangular_kwargs(self) -> None:
        nl = NonlinearRectangularChannel(
            "ch", "ch",
            width=200e-6, height=50e-6, length=0.01,
            viscosity=1.2e-3, density=1050.0,
        )
        assert math.isclose(nl.medium.dynamic_viscosity, 1.2e-3, rel_tol=1e-12)
        assert math.isclose(nl.medium.density, 1050.0, rel_tol=1e-12)

    def test_density_only_uses_default_viscosity(self) -> None:
        nl = NonlinearCircularChannel(
            "ch", "ch", radius=100e-6, length=0.01, density=1200.0,
        )
        assert math.isclose(nl.medium.density, 1200.0, rel_tol=1e-12)
        # Viscosity falls back to the FluidMedium default (water 20 °C ≈ 1e-3)
        assert nl.medium.dynamic_viscosity > 0


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------


class TestSerialisation:
    def test_circular_roundtrip(self) -> None:
        nl = NonlinearCircularChannel(
            "ch", "ch", radius=150e-6, length=0.02, medium=WATER,
        )
        data = nl.to_dict()
        assert data["is_nonlinear"] is True
        assert data["density"] == WATER.density
        restored = NonlinearCircularChannel.from_dict(data)
        assert restored.radius == nl.radius
        assert restored.length == nl.length
        assert math.isclose(
            restored.medium.dynamic_viscosity, nl.medium.dynamic_viscosity,
            rel_tol=1e-12,
        )
        assert math.isclose(restored.density, nl.density, rel_tol=1e-12)

    def test_rectangular_roundtrip(self) -> None:
        nl = NonlinearRectangularChannel(
            "ch", "ch",
            width=200e-6, height=60e-6, length=0.03, medium=WATER, n_terms=7,
        )
        data = nl.to_dict()
        assert data["is_nonlinear"] is True
        restored = NonlinearRectangularChannel.from_dict(data)
        assert restored.width == nl.width
        assert restored.height == nl.height
        assert restored.n_terms == nl.n_terms
