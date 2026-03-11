"""Tests for fluid element classes."""

import math

import pytest

from backend.models.chamber import Chamber
from backend.models.channel import CircularChannel, RectangularChannel
from backend.models.pump import Pump
from backend.models.valve import Valve


class TestCircularChannel:
    """Tests for CircularChannel class."""

    @pytest.fixture
    def default_channel(self) -> CircularChannel:
        """Create a default circular channel for testing."""
        return CircularChannel(
            element_id="channel_1",
            name="Test Channel",
            radius=100e-6,  # 100 µm
            length=0.01,  # 1 cm
            viscosity=1e-3,  # Water
        )

    def test_creation(self, default_channel: CircularChannel) -> None:
        """Test channel creation with valid parameters."""
        assert default_channel.element_id == "channel_1"
        assert default_channel.name == "Test Channel"
        assert default_channel.radius == 100e-6
        assert default_channel.length == 0.01
        assert default_channel.viscosity == 1e-3

    def test_resistance_calculation(self, default_channel: CircularChannel) -> None:
        """Test hydraulic resistance calculation."""
        # R = 8 * η * L / (π * r⁴)
        expected = (8 * 1e-3 * 0.01) / (math.pi * (100e-6) ** 4)
        actual = default_channel.calculate_resistance()
        assert math.isclose(actual, expected, rel_tol=1e-10)

    def test_flow_calculation(self, default_channel: CircularChannel) -> None:
        """Test flow calculation with known pressure drop."""
        pressure_drop = 1000  # 1000 Pa
        # Q = (ΔP * π * r⁴) / (8 * η * L)
        expected = (pressure_drop * math.pi * (100e-6) ** 4) / (8 * 1e-3 * 0.01)
        actual = default_channel.calculate_flow(pressure_drop)
        assert math.isclose(actual, expected, rel_tol=1e-10)

    @pytest.mark.parametrize(
        "radius,length,viscosity",
        [
            (0, 0.01, 1e-3),  # Zero radius
            (-100e-6, 0.01, 1e-3),  # Negative radius
            (100e-6, 0, 1e-3),  # Zero length
            (100e-6, 0.01, 0),  # Zero viscosity
            (5e-6, 0.01, 1e-3),  # Radius too small
            (600e-6, 0.01, 1e-3),  # Radius too large
        ],
    )
    def test_invalid_parameters(
        self, radius: float, length: float, viscosity: float
    ) -> None:
        """Test validation rejects invalid parameters."""
        with pytest.raises(ValueError):
            CircularChannel(
                element_id="test",
                name="Test",
                radius=radius,
                length=length,
                viscosity=viscosity,
            )

    def test_negative_pressure_drop_raises(
        self, default_channel: CircularChannel
    ) -> None:
        """Test that negative pressure drop raises ValueError."""
        with pytest.raises(ValueError, match="negative"):
            default_channel.calculate_flow(-100)

    def test_to_dict(self, default_channel: CircularChannel) -> None:
        """Test serialization to dictionary."""
        data = default_channel.to_dict()
        assert data["element_id"] == "channel_1"
        assert data["element_type"] == "CircularChannel"
        assert data["radius"] == 100e-6
        assert "resistance" in data

    def test_from_dict(self, default_channel: CircularChannel) -> None:
        """Test deserialization from dictionary."""
        data = default_channel.to_dict()
        restored = CircularChannel.from_dict(data)
        assert restored.element_id == default_channel.element_id
        assert restored.radius == default_channel.radius


class TestRectangularChannel:
    """Tests for RectangularChannel class."""

    @pytest.fixture
    def default_channel(self) -> RectangularChannel:
        """Create a default rectangular channel for testing."""
        return RectangularChannel(
            element_id="rect_1",
            name="Rectangular Channel",
            width=200e-6,
            height=100e-6,
            length=0.01,
            viscosity=1e-3,
        )

    def test_creation(self, default_channel: RectangularChannel) -> None:
        """Test channel creation."""
        assert default_channel.width == 200e-6
        assert default_channel.height == 100e-6

    def test_flow_positive(self, default_channel: RectangularChannel) -> None:
        """Test that flow is positive for positive pressure drop."""
        flow = default_channel.calculate_flow(1000)
        assert flow > 0

    def test_resistance_positive(self, default_channel: RectangularChannel) -> None:
        """Test that resistance is positive."""
        resistance = default_channel.calculate_resistance()
        assert resistance > 0

    @pytest.mark.parametrize("pressure", [100, 1000, 10000])
    def test_flow_proportional_to_pressure(
        self, default_channel: RectangularChannel, pressure: float
    ) -> None:
        """Test that flow is proportional to pressure drop."""
        flow1 = default_channel.calculate_flow(pressure)
        flow2 = default_channel.calculate_flow(pressure * 2)
        assert math.isclose(flow2, flow1 * 2, rel_tol=1e-10)


class TestChamber:
    """Tests for Chamber class."""

    @pytest.fixture
    def default_chamber(self) -> Chamber:
        """Create a default chamber for testing."""
        return Chamber(
            element_id="chamber_1",
            name="Test Chamber",
            height=500e-6,
            density=1000,
        )

    def test_hydrostatic_pressure(self, default_chamber: Chamber) -> None:
        """Test hydrostatic pressure calculation."""
        # ΔP = ρ * g * h
        expected = 1000 * 9.81 * 500e-6
        actual = default_chamber.calculate_hydrostatic_pressure()
        assert math.isclose(actual, expected, rel_tol=1e-10)

    def test_minimal_resistance(self, default_chamber: Chamber) -> None:
        """Test that chamber has minimal resistance."""
        resistance = default_chamber.calculate_resistance()
        assert resistance == Chamber.MINIMAL_RESISTANCE


class TestPump:
    """Tests for Pump class."""

    @pytest.fixture
    def default_pump(self) -> Pump:
        """Create a default pump for testing."""
        return Pump(
            element_id="pump_1",
            name="Test Pump",
            area=1e-6,  # 1 mm²
            velocity=0.01,  # 1 cm/s
            pressure_generated=10000,  # 10 kPa
            resistance=1e9,
        )

    def test_nominal_flow(self, default_pump: Pump) -> None:
        """Test nominal flow calculation."""
        # Q = A * v
        expected = 1e-6 * 0.01
        actual = default_pump.get_nominal_flow()
        assert math.isclose(actual, expected, rel_tol=1e-10)

    def test_output_pressure(self, default_pump: Pump) -> None:
        """Test output pressure calculation."""
        flow = default_pump.get_nominal_flow()
        output_p = default_pump.calculate_output_pressure(flow)
        # P_out = P_gen - R * Q
        expected = 10000 - 1e9 * flow
        assert math.isclose(output_p, expected, rel_tol=1e-10)


class TestValve:
    """Tests for Valve class."""

    @pytest.fixture
    def default_valve(self) -> Valve:
        """Create a default valve for testing."""
        return Valve(
            element_id="valve_1",
            name="Test Valve",
            input_flow=1e-9,
            state=True,
        )

    def test_open_valve_flow(self, default_valve: Valve) -> None:
        """Test that open valve passes full flow."""
        output = default_valve.calculate_flow()
        assert output == default_valve.input_flow

    def test_closed_valve_flow(self, default_valve: Valve) -> None:
        """Test that closed valve blocks flow."""
        default_valve.close()
        output = default_valve.calculate_flow()
        assert output == 0

    def test_toggle(self, default_valve: Valve) -> None:
        """Test valve toggle."""
        initial_state = default_valve.state
        default_valve.toggle()
        assert default_valve.state != initial_state

    def test_resistance_changes_with_state(self, default_valve: Valve) -> None:
        """Test that resistance changes with valve state."""
        open_resistance = default_valve.calculate_resistance()
        default_valve.close()
        closed_resistance = default_valve.calculate_resistance()
        assert closed_resistance > open_resistance