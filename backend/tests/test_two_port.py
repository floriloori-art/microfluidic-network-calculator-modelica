"""
Tests for the Modelica-style two-port architecture.

Covers:
  - FluidPort connector semantics
  - FluidMedium presets and properties
  - TwoPortElement interface (via CircularChannel)
  - Port state after solver update (update_ports)
  - Backward compatibility: existing solver still works with two-port elements
"""

from __future__ import annotations

import math

import pytest

from backend.models.channel import CircularChannel, RectangularChannel
from backend.models.medium import FluidMedium
from backend.models.network import FluidNetwork
from backend.ports.connector import FluidPort
from backend.solver.network_solver import NetworkSolver


# ---------------------------------------------------------------------------
# FluidPort
# ---------------------------------------------------------------------------


class TestFluidPort:
    """Modelica connector semantics."""

    def test_default_state_is_zero(self) -> None:
        port = FluidPort(element_id="ch1", port_name="port_a")
        assert port.pressure == 0.0
        assert port.mass_flow == 0.0

    def test_reset_clears_state(self) -> None:
        port = FluidPort(element_id="ch1", port_name="port_a", pressure=500.0, mass_flow=1e-9)
        port.reset()
        assert port.pressure == 0.0
        assert port.mass_flow == 0.0

    def test_repr_contains_key_info(self) -> None:
        port = FluidPort(element_id="ch1", port_name="port_a", pressure=1000.0)
        r = repr(port)
        assert "ch1" in r
        assert "port_a" in r

    def test_mass_flow_sign_convention(self) -> None:
        """Positive mass_flow means fluid enters the element at this port."""
        port_in = FluidPort(mass_flow=1e-9)   # entering
        port_out = FluidPort(mass_flow=-1e-9)  # leaving
        # Kirchhoff: sum of flows at a junction = 0
        assert math.isclose(port_in.mass_flow + port_out.mass_flow, 0.0, abs_tol=1e-20)


# ---------------------------------------------------------------------------
# FluidMedium
# ---------------------------------------------------------------------------


class TestFluidMedium:
    """Medium model presets and derived properties."""

    def test_default_is_water_20c(self) -> None:
        m = FluidMedium()
        assert math.isclose(m.density, 998.2, rel_tol=1e-3)
        assert math.isclose(m.dynamic_viscosity, 1e-3, rel_tol=1e-3)

    def test_factory_water_20c(self) -> None:
        m = FluidMedium.water_20c()
        assert m.name == "Water_20C"
        assert m.density > 990

    def test_factory_water_37c_less_viscous(self) -> None:
        cold = FluidMedium.water_20c()
        warm = FluidMedium.water_37c()
        # Water becomes less viscous at higher temperature
        assert warm.dynamic_viscosity < cold.dynamic_viscosity

    def test_factory_glycerol_more_viscous_than_water(self) -> None:
        water = FluidMedium.water_20c()
        glycerol = FluidMedium.glycerol_50pct()
        assert glycerol.dynamic_viscosity > water.dynamic_viscosity

    def test_kinematic_viscosity_derived(self) -> None:
        m = FluidMedium.water_20c()
        expected = m.dynamic_viscosity / m.density
        assert math.isclose(m.kinematic_viscosity, expected, rel_tol=1e-10)

    def test_repr_contains_name(self) -> None:
        m = FluidMedium.water_20c()
        assert "Water_20C" in repr(m)


# ---------------------------------------------------------------------------
# TwoPortElement via CircularChannel
# ---------------------------------------------------------------------------


class TestTwoPortInterface:
    """Two-port interface exposed by CircularChannel."""

    def _channel(self, eid: str = "ch", medium: FluidMedium | None = None) -> CircularChannel:
        return CircularChannel(
            element_id=eid,
            name=eid,
            radius=100e-6,
            length=0.01,
            medium=medium or FluidMedium.water_20c(),
        )

    def test_port_a_and_port_b_exist(self) -> None:
        ch = self._channel()
        assert isinstance(ch.port_a, FluidPort)
        assert isinstance(ch.port_b, FluidPort)

    def test_ports_initialised_to_zero(self) -> None:
        ch = self._channel()
        assert ch.port_a.pressure == 0.0
        assert ch.port_b.pressure == 0.0
        assert ch.port_a.mass_flow == 0.0
        assert ch.port_b.mass_flow == 0.0

    def test_ports_own_element_id(self) -> None:
        ch = self._channel("my_channel")
        assert ch.port_a.element_id == "my_channel"
        assert ch.port_b.element_id == "my_channel"

    def test_pressure_drop_positive_for_positive_flow(self) -> None:
        ch = self._channel()
        dp = ch.pressure_drop(1e-9)   # 1 nL/s → port_a.p > port_b.p
        assert dp > 0

    def test_pressure_drop_zero_for_zero_flow(self) -> None:
        ch = self._channel()
        assert ch.pressure_drop(0.0) == 0.0

    def test_pressure_drop_linear_in_flow(self) -> None:
        """ΔP must scale linearly with ṁ (Hagen-Poiseuille is linear)."""
        ch = self._channel()
        dp1 = ch.pressure_drop(1e-9)
        dp2 = ch.pressure_drop(2e-9)
        assert math.isclose(dp2 / dp1, 2.0, rel_tol=1e-6)

    def test_pressure_drop_consistent_with_resistance(self) -> None:
        """ΔP = R · Q = R · ṁ / ρ  must hold exactly."""
        ch = self._channel()
        mass_flow = 1e-9 * ch.medium.density   # ṁ for Q = 1 nL/s
        dp = ch.pressure_drop(mass_flow)
        r = ch.calculate_resistance()
        q = mass_flow / ch.medium.density
        assert math.isclose(dp, r * q, rel_tol=1e-6)

    def test_medium_viscosity_affects_resistance(self) -> None:
        """Higher viscosity → higher resistance."""
        ch_water = self._channel(medium=FluidMedium.water_20c())
        ch_glycerol = self._channel(medium=FluidMedium.glycerol_50pct())
        assert ch_glycerol.calculate_resistance() > ch_water.calculate_resistance()

    def test_to_dict_contains_ports(self) -> None:
        ch = self._channel()
        d = ch.to_dict()
        assert "port_a" in d
        assert "port_b" in d
        assert "pressure" in d["port_a"]
        assert "mass_flow" in d["port_a"]

    def test_to_dict_contains_medium(self) -> None:
        ch = self._channel()
        d = ch.to_dict()
        assert "medium" in d
        assert d["medium"] == "Water_20C"


# ---------------------------------------------------------------------------
# update_ports: solver populates port state after solving
# ---------------------------------------------------------------------------


class TestUpdatePorts:
    """Port state after solver calls update_ports()."""

    def _channel(self) -> CircularChannel:
        return CircularChannel(
            element_id="ch",
            name="ch",
            radius=100e-6,
            length=0.01,
            medium=FluidMedium.water_20c(),
        )

    def test_pressures_stored_correctly(self) -> None:
        ch = self._channel()
        ch.update_ports(pressure_a=1000.0, pressure_b=0.0)
        assert math.isclose(ch.port_a.pressure, 1000.0)
        assert math.isclose(ch.port_b.pressure, 0.0)

    def test_mass_flow_conservation(self) -> None:
        """port_a.mass_flow + port_b.mass_flow must equal zero."""
        ch = self._channel()
        ch.update_ports(pressure_a=1000.0, pressure_b=0.0)
        total = ch.port_a.mass_flow + ch.port_b.mass_flow
        assert math.isclose(total, 0.0, abs_tol=1e-20)

    def test_mass_flow_direction(self) -> None:
        """Fluid must enter at port_a when port_a.p > port_b.p."""
        ch = self._channel()
        ch.update_ports(pressure_a=1000.0, pressure_b=0.0)
        assert ch.port_a.mass_flow > 0   # entering at port_a
        assert ch.port_b.mass_flow < 0   # leaving at port_b

    def test_mass_flow_value_consistent_with_resistance(self) -> None:
        """Q = ΔP / R  →  ṁ = Q · ρ."""
        ch = self._channel()
        ch.update_ports(pressure_a=1000.0, pressure_b=0.0)
        r = ch.calculate_resistance()
        q_expected = 1000.0 / r
        mass_flow_expected = q_expected * ch.medium.density
        assert math.isclose(ch.port_a.mass_flow, mass_flow_expected, rel_tol=1e-6)

    def test_reset_ports_clears_state(self) -> None:
        ch = self._channel()
        ch.update_ports(1000.0, 0.0)
        ch.reset_ports()
        assert ch.port_a.pressure == 0.0
        assert ch.port_b.pressure == 0.0
        assert ch.port_a.mass_flow == 0.0
        assert ch.port_b.mass_flow == 0.0


# ---------------------------------------------------------------------------
# Backward compatibility: existing solver works with TwoPortElement channels
# ---------------------------------------------------------------------------


class TestSolverBackwardCompatibility:
    """
    Existing node-based solver must work unchanged with TwoPortElement channels.

    TwoPortElement exposes calculate_resistance() so the solver can treat
    two-port channels exactly like the old single-node channels.
    """

    def _channel(self, eid: str) -> CircularChannel:
        return CircularChannel(
            element_id=eid,
            name=eid,
            radius=100e-6,
            length=0.01,
            medium=FluidMedium.water_20c(),
        )

    def test_solver_accepts_two_port_channels(self) -> None:
        network = FluidNetwork("net", "Net")
        network.add_element(self._channel("inlet"))
        network.add_element(self._channel("outlet"))
        network.connect("inlet", "outlet")

        result = NetworkSolver().solve(
            network, {"inlet": {"pressure": 1000.0}, "outlet": {"pressure": 0.0}}
        )
        assert result.success

    def test_solver_result_matches_analytical_hagen_poiseuille(self) -> None:
        """Q = ΔP / (2R)  for two equal channels in series."""
        medium = FluidMedium.water_20c()
        r = 100e-6
        L = 0.01
        eta = medium.dynamic_viscosity
        R_single = (8 * eta * L) / (math.pi * r**4)

        network = FluidNetwork("net", "Net")
        network.add_element(self._channel("inlet"))
        network.add_element(self._channel("outlet"))
        network.connect("inlet", "outlet")

        result = NetworkSolver().solve(
            network, {"inlet": {"pressure": 1000.0}, "outlet": {"pressure": 0.0}}
        )
        assert result.success
        q_computed = abs(list(result.flows.values())[0])
        q_expected = 1000.0 / (2 * R_single)
        assert math.isclose(q_computed, q_expected, rel_tol=1e-5)

    def test_different_media_give_different_flows(self) -> None:
        """Higher viscosity medium → lower flow for same pressure drop."""
        def solve_with_medium(medium: FluidMedium) -> float:
            network = FluidNetwork("net", "Net")
            for eid in ["a", "b"]:
                network.add_element(
                    CircularChannel(element_id=eid, name=eid,
                                    radius=100e-6, length=0.01, medium=medium)
                )
            network.connect("a", "b")
            result = NetworkSolver().solve(
                network, {"a": {"pressure": 1000.0}, "b": {"pressure": 0.0}}
            )
            return abs(list(result.flows.values())[0])

        q_water = solve_with_medium(FluidMedium.water_20c())
        q_glycerol = solve_with_medium(FluidMedium.glycerol_50pct())
        assert q_water > q_glycerol


# ---------------------------------------------------------------------------
# Legacy API compatibility (viscosity= kwarg still works)
# ---------------------------------------------------------------------------


class TestLegacyViscosityParam:
    """Old tests that pass viscosity= directly must still work."""

    def test_circular_channel_accepts_viscosity_kwarg(self) -> None:
        ch = CircularChannel(
            element_id="ch",
            name="ch",
            radius=100e-6,
            length=0.01,
            viscosity=1e-3,
        )
        assert ch.medium.dynamic_viscosity == pytest.approx(1e-3)

    def test_rectangular_channel_accepts_viscosity_kwarg(self) -> None:
        ch = RectangularChannel(
            element_id="ch",
            name="ch",
            width=100e-6,
            height=50e-6,
            length=0.01,
            viscosity=1e-3,
        )
        assert ch.medium.dynamic_viscosity == pytest.approx(1e-3)
