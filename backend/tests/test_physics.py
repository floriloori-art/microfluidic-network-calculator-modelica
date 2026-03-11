"""Tests for physics calculation functions."""

import math

import pytest

from backend.physics.flow_calculations import (
    calculate_hydrostatic_pressure,
    calculate_poiseuille_circular,
    calculate_poiseuille_rectangular,
    calculate_pressure_drop,
    calculate_resistance_circular,
    calculate_resistance_rectangular,
    calculate_reynolds_number,
    is_laminar_flow,
)


class TestPoiseurilleCircular:
    """Tests for circular channel Poiseuille flow."""

    def test_known_values(self) -> None:
        """Test against hand-calculated values."""
        # r = 100 µm, L = 1 cm, η = 1 mPa·s, ΔP = 1000 Pa
        r = 100e-6
        L = 0.01
        eta = 1e-3
        dp = 1000

        # Q = (ΔP * π * r⁴) / (8 * η * L)
        expected = (dp * math.pi * r**4) / (8 * eta * L)
        actual = calculate_poiseuille_circular(r, L, eta, dp)

        assert math.isclose(actual, expected, rel_tol=1e-12)

    @pytest.mark.parametrize(
        "radius,length,viscosity,pressure",
        [
            (50e-6, 0.005, 1e-3, 500),
            (200e-6, 0.02, 2e-3, 2000),
            (100e-6, 0.01, 0.5e-3, 1500),
        ],
    )
    def test_various_parameters(
        self, radius: float, length: float, viscosity: float, pressure: float
    ) -> None:
        """Test with various parameter combinations."""
        result = calculate_poiseuille_circular(radius, length, viscosity, pressure)
        assert result > 0

    def test_zero_pressure_gives_zero_flow(self) -> None:
        """Test that zero pressure drop gives zero flow."""
        result = calculate_poiseuille_circular(100e-6, 0.01, 1e-3, 0)
        assert result == 0

    @pytest.mark.parametrize(
        "radius,length,viscosity,pressure",
        [
            (0, 0.01, 1e-3, 1000),  # Zero radius
            (-100e-6, 0.01, 1e-3, 1000),  # Negative radius
            (100e-6, 0, 1e-3, 1000),  # Zero length
            (100e-6, 0.01, 0, 1000),  # Zero viscosity
            (100e-6, 0.01, 1e-3, -1000),  # Negative pressure
        ],
    )
    def test_invalid_parameters_raise(
        self, radius: float, length: float, viscosity: float, pressure: float
    ) -> None:
        """Test that invalid parameters raise ValueError."""
        with pytest.raises(ValueError):
            calculate_poiseuille_circular(radius, length, viscosity, pressure)


class TestPoiseurilleRectangular:
    """Tests for rectangular channel Poiseuille flow."""

    def test_positive_result(self) -> None:
        """Test that result is positive for valid inputs."""
        result = calculate_poiseuille_rectangular(
            width=200e-6,
            height=100e-6,
            length=0.01,
            viscosity=1e-3,
            pressure_drop=1000,
        )
        assert result > 0

    def test_symmetric_dimensions(self) -> None:
        """Test that swapping width and height gives same result."""
        result1 = calculate_poiseuille_rectangular(
            width=200e-6, height=100e-6, length=0.01, viscosity=1e-3, pressure_drop=1000
        )
        result2 = calculate_poiseuille_rectangular(
            width=100e-6, height=200e-6, length=0.01, viscosity=1e-3, pressure_drop=1000
        )
        # Should be identical due to h/w swap in implementation
        assert math.isclose(result1, result2, rel_tol=1e-10)

    def test_increases_with_pressure(self) -> None:
        """Test that flow increases with pressure drop."""
        result1 = calculate_poiseuille_rectangular(
            200e-6, 100e-6, 0.01, 1e-3, 1000
        )
        result2 = calculate_poiseuille_rectangular(
            200e-6, 100e-6, 0.01, 1e-3, 2000
        )
        assert result2 > result1

    def test_n_terms_convergence(self) -> None:
        """Test that more terms gives better convergence."""
        results = [
            calculate_poiseuille_rectangular(
                200e-6, 100e-6, 0.01, 1e-3, 1000, n_terms=n
            )
            for n in [1, 3, 5, 10]
        ]
        # Results should converge (differences decrease)
        diffs = [abs(results[i + 1] - results[i]) for i in range(len(results) - 1)]
        assert diffs[-1] < diffs[0]


class TestResistance:
    """Tests for resistance calculations."""

    def test_circular_resistance(self) -> None:
        """Test circular channel resistance."""
        r = 100e-6
        L = 0.01
        eta = 1e-3

        resistance = calculate_resistance_circular(r, L, eta)
        # R = 8 * η * L / (π * r⁴)
        expected = (8 * eta * L) / (math.pi * r**4)

        assert math.isclose(resistance, expected, rel_tol=1e-12)

    def test_resistance_flow_relationship(self) -> None:
        """Test that R = ΔP / Q."""
        r = 100e-6
        L = 0.01
        eta = 1e-3
        dp = 1000

        resistance = calculate_resistance_circular(r, L, eta)
        flow = calculate_poiseuille_circular(r, L, eta, dp)

        # ΔP = Q * R
        assert math.isclose(dp, flow * resistance, rel_tol=1e-10)


class TestHydrostaticPressure:
    """Tests for hydrostatic pressure calculation."""

    def test_known_values(self) -> None:
        """Test against known values."""
        # Water: ρ = 1000 kg/m³, h = 1 m, g = 9.81 m/s²
        pressure = calculate_hydrostatic_pressure(1000, 1, 9.81)
        assert math.isclose(pressure, 9810, rel_tol=1e-10)

    def test_microfluidic_scale(self) -> None:
        """Test at microfluidic scale."""
        # h = 500 µm
        pressure = calculate_hydrostatic_pressure(1000, 500e-6, 9.81)
        expected = 1000 * 9.81 * 500e-6
        assert math.isclose(pressure, expected, rel_tol=1e-10)


class TestReynoldsNumber:
    """Tests for Reynolds number calculation."""

    def test_laminar_detection(self) -> None:
        """Test laminar flow detection."""
        # Low velocity -> laminar
        re = calculate_reynolds_number(
            velocity=0.01,
            characteristic_length=100e-6,
            density=1000,
            viscosity=1e-3,
        )
        assert is_laminar_flow(re)

    def test_turbulent_detection(self) -> None:
        """Test turbulent flow detection."""
        # High velocity -> turbulent
        re = calculate_reynolds_number(
            velocity=100,
            characteristic_length=0.01,
            density=1000,
            viscosity=1e-3,
        )
        assert not is_laminar_flow(re)


class TestPressureDrop:
    """Tests for pressure drop calculation."""

    def test_basic_calculation(self) -> None:
        """Test basic pressure drop calculation."""
        flow = 1e-9  # 1 nL/s
        resistance = 1e12  # Pa·s/m³

        dp = calculate_pressure_drop(flow, resistance)
        assert math.isclose(dp, flow * resistance, rel_tol=1e-12)