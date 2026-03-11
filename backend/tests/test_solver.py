"""Tests for network solver."""

import math

import pytest

from backend.models.channel import CircularChannel, RectangularChannel
from backend.models.chamber import Chamber
from backend.models.network import FluidNetwork
from backend.models.pump import Pump
from backend.solver.network_solver import NetworkSolver, SolverResult


class TestNetworkSolver:
    """Tests for NetworkSolver class."""

    @pytest.fixture
    def simple_network(self) -> FluidNetwork:
        """Create a simple two-element network."""
        network = FluidNetwork("test_network", "Test Network")

        # Create two channels connected in series
        channel1 = CircularChannel(
            element_id="inlet",
            name="Inlet Channel",
            radius=100e-6,
            length=0.01,
            viscosity=1e-3,
        )
        channel2 = CircularChannel(
            element_id="outlet",
            name="Outlet Channel",
            radius=100e-6,
            length=0.01,
            viscosity=1e-3,
        )

        network.add_element(channel1)
        network.add_element(channel2)
        network.connect("inlet", "outlet")

        return network

    @pytest.fixture
    def solver(self) -> NetworkSolver:
        """Create a solver instance."""
        return NetworkSolver()

    def test_simple_network_solves(
        self, simple_network: FluidNetwork, solver: NetworkSolver
    ) -> None:
        """Test that simple network solves successfully."""
        bc = {
            "inlet": {"pressure": 1000},
            "outlet": {"pressure": 0},
        }

        result = solver.solve(simple_network, bc)

        assert result.success
        assert "inlet" in result.pressures
        assert "outlet" in result.pressures
        assert result.pressures["inlet"] == 1000
        assert result.pressures["outlet"] == 0

    def test_flow_direction(
        self, simple_network: FluidNetwork, solver: NetworkSolver
    ) -> None:
        """Test that flow direction is correct (high to low pressure)."""
        bc = {
            "inlet": {"pressure": 1000},
            "outlet": {"pressure": 0},
        }

        result = solver.solve(simple_network, bc)

        # Flow should be positive from inlet to outlet
        flow_key = ("inlet", "outlet")
        if flow_key in result.flows:
            assert result.flows[flow_key] > 0
        else:
            # Check reverse direction
            flow_key = ("outlet", "inlet")
            assert result.flows[flow_key] < 0

    def test_mass_conservation(
        self, simple_network: FluidNetwork, solver: NetworkSolver
    ) -> None:
        """Test that mass is conserved (inflow = outflow)."""
        bc = {
            "inlet": {"pressure": 1000},
            "outlet": {"pressure": 0},
        }

        result = solver.solve(simple_network, bc)

        # For a series network, flow should be constant
        flows = list(result.flows.values())
        if len(flows) > 1:
            for flow in flows[1:]:
                assert math.isclose(abs(flow), abs(flows[0]), rel_tol=1e-6)

    def test_no_boundary_conditions_fails(
        self, simple_network: FluidNetwork, solver: NetworkSolver
    ) -> None:
        """Test that solver fails without boundary conditions."""
        result = solver.solve(simple_network, {})
        assert not result.success

    def test_insufficient_network_fails(self, solver: NetworkSolver) -> None:
        """Test that solver fails with insufficient network."""
        network = FluidNetwork("tiny", "Tiny")
        channel = CircularChannel(
            element_id="only_one",
            name="Only Channel",
            radius=100e-6,
            length=0.01,
            viscosity=1e-3,
        )
        network.add_element(channel)

        bc = {"only_one": {"pressure": 1000}}
        result = solver.solve(network, bc)

        assert not result.success

    def test_three_element_network(self, solver: NetworkSolver) -> None:
        """Test solver with three elements in series."""
        network = FluidNetwork("three_elem", "Three Element Network")

        for i, name in enumerate(["inlet", "middle", "outlet"]):
            channel = CircularChannel(
                element_id=name,
                name=f"{name.title()} Channel",
                radius=100e-6,
                length=0.01,
                viscosity=1e-3,
            )
            network.add_element(channel)

        network.connect("inlet", "middle")
        network.connect("middle", "outlet")

        bc = {
            "inlet": {"pressure": 2000},
            "outlet": {"pressure": 0},
        }

        result = solver.solve(network, bc)

        assert result.success
        # Middle pressure should be between inlet and outlet
        assert 0 < result.pressures["middle"] < 2000


class TestSolverPhysics:
    """Integration tests verifying physics correctness with analytical solutions."""

    @pytest.fixture
    def solver(self) -> NetworkSolver:
        return NetworkSolver()

    def _make_channel(self, element_id: str, radius: float = 100e-6,
                      length: float = 0.01, viscosity: float = 1e-3) -> CircularChannel:
        return CircularChannel(
            element_id=element_id,
            name=element_id,
            radius=radius,
            length=length,
            viscosity=viscosity,
        )

    def test_series_two_equal_channels_pressure_midpoint(self, solver: NetworkSolver) -> None:
        """Two equal channels in series: intermediate pressure must equal mean of BCs."""
        # Three nodes: inlet - middle - outlet, all identical channels
        network = FluidNetwork("series3", "Series3")
        for eid in ["inlet", "middle", "outlet"]:
            network.add_element(self._make_channel(eid))
        network.connect("inlet", "middle")
        network.connect("middle", "outlet")

        bc = {"inlet": {"pressure": 2000.0}, "outlet": {"pressure": 0.0}}
        result = solver.solve(network, bc)

        assert result.success
        # For 3 equal resistors in series the node between them is exactly at the mean
        assert math.isclose(result.pressures["middle"], 1000.0, rel_tol=1e-6)

    def test_series_two_equal_channels_flow_conservation(self, solver: NetworkSolver) -> None:
        """Flow through all connections in a series network must be identical."""
        network = FluidNetwork("series3_flow", "Flow Conservation")
        for eid in ["inlet", "middle", "outlet"]:
            network.add_element(self._make_channel(eid))
        network.connect("inlet", "middle")
        network.connect("middle", "outlet")

        bc = {"inlet": {"pressure": 1000.0}, "outlet": {"pressure": 0.0}}
        result = solver.solve(network, bc)

        assert result.success
        flows = list(result.flows.values())
        assert len(flows) == 2
        assert math.isclose(abs(flows[0]), abs(flows[1]), rel_tol=1e-6)

    def test_series_resistance_doubles_halves_flow(self, solver: NetworkSolver) -> None:
        """Doubling series resistance (same channel twice) halves the flow."""
        def solve_series(length: float) -> float:
            network = FluidNetwork("series_r", "Series R")
            ch_in = self._make_channel("inlet", length=length)
            ch_out = self._make_channel("outlet", length=length)
            network.add_element(ch_in)
            network.add_element(ch_out)
            network.connect("inlet", "outlet")
            bc = {"inlet": {"pressure": 1000.0}, "outlet": {"pressure": 0.0}}
            result = solver.solve(network, bc)
            assert result.success
            return list(result.flows.values())[0]

        flow_short = solve_series(0.01)   # length L
        flow_long = solve_series(0.02)    # length 2L → double resistance → half flow
        assert math.isclose(abs(flow_short), abs(flow_long) * 2, rel_tol=1e-5)

    def test_analytical_flow_value(self, solver: NetworkSolver) -> None:
        """Verify computed flow matches Hagen-Poiseuille formula analytically.

        For two equal channels (each R) in series: Q = ΔP / (2R).
        """
        import math as _math
        r = 100e-6
        L = 0.01
        eta = 1e-3
        R_single = (8 * eta * L) / (_math.pi * r**4)

        network = FluidNetwork("analytic", "Analytic")
        network.add_element(self._make_channel("inlet"))
        network.add_element(self._make_channel("outlet"))
        network.connect("inlet", "outlet")

        bc = {"inlet": {"pressure": 1000.0}, "outlet": {"pressure": 0.0}}
        result = solver.solve(network, bc)

        assert result.success
        q_expected = 1000.0 / (2 * R_single)
        q_computed = abs(list(result.flows.values())[0])
        assert math.isclose(q_computed, q_expected, rel_tol=1e-6)

    def test_disconnected_network_fails(self, solver: NetworkSolver) -> None:
        """Solver must fail gracefully for a disconnected network.

        Uses 3 elements: a-b connected, c isolated → 2 components, 1 connection.
        """
        network = FluidNetwork("disconnected", "Disconnected")
        network.add_element(self._make_channel("a"))
        network.add_element(self._make_channel("b"))
        network.add_element(self._make_channel("c"))
        network.connect("a", "b")  # c is isolated

        bc = {"a": {"pressure": 1000.0}, "b": {"pressure": 0.0}}
        result = solver.solve(network, bc)

        assert not result.success
        combined = " ".join(result.messages).lower()
        assert "disconnected" in combined or "component" in combined

    def test_pump_as_pressure_source(self, solver: NetworkSolver) -> None:
        """Pump pressure must appear as a pressure BC at the pump node."""
        network = FluidNetwork("pump_test", "Pump Test")
        pump = Pump(
            element_id="pump",
            name="Pump",
            area=1e-6,
            velocity=1e-3,
            pressure_generated=500.0,
            resistance=1e10,
        )
        outlet = self._make_channel("outlet")
        network.add_element(pump)
        network.add_element(outlet)
        network.connect("pump", "outlet")

        bc = {"outlet": {"pressure": 0.0}}
        result = solver.solve(network, bc)

        assert result.success
        # Pump node pressure must equal its generated pressure
        assert math.isclose(result.pressures["pump"], 500.0, rel_tol=1e-6)

    def test_pressure_distribution_monotonic_series(self, solver: NetworkSolver) -> None:
        """In a series network pressures must be monotonically decreasing."""
        network = FluidNetwork("mono", "Monotonic")
        names = ["n0", "n1", "n2", "n3"]
        for n in names:
            network.add_element(self._make_channel(n))
        for a, b in zip(names, names[1:]):
            network.connect(a, b)

        bc = {names[0]: {"pressure": 3000.0}, names[-1]: {"pressure": 0.0}}
        result = solver.solve(network, bc)

        assert result.success
        pressures = [result.pressures[n] for n in names]
        for p1, p2 in zip(pressures, pressures[1:]):
            assert p1 > p2


class TestSolverResult:
    """Tests for SolverResult dataclass."""

    def test_default_values(self) -> None:
        """Test default values are set correctly."""
        result = SolverResult(success=True)

        assert result.success
        assert result.pressures == {}
        assert result.flows == {}
        assert result.iterations == 0
        assert result.messages == []

    def test_with_data(self) -> None:
        """Test creation with actual data."""
        result = SolverResult(
            success=True,
            pressures={"a": 1000, "b": 500},
            flows={("a", "b"): 1e-9},
            messages=["Converged"],
        )

        assert result.pressures["a"] == 1000
        assert result.flows[("a", "b")] == 1e-9
        assert "Converged" in result.messages