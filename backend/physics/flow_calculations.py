"""Flow calculation functions for microfluidic elements.

All functions use SI units:
- Length: meters [m]
- Pressure: Pascal [Pa]
- Viscosity: Pascal-seconds [Pa·s]
- Flow rate: cubic meters per second [m³/s]
- Resistance: Pa·s/m³

"""

import logging
import math
from typing import Final

import numpy as np

logger = logging.getLogger(__name__)

# Constants

PI: Final[float] = math.pi


def calculate_poiseuille_circular(
    radius: float,
    length: float,
    viscosity: float,
    pressure_drop: float,
) -> float:
    """Calculate volumetric flow rate for circular channel (Hagen-Poiseuille).

    Q = (ΔP · π · r⁴) / (8 · η · L)

    Args:
        radius: Channel radius in meters [m].
        length: Channel length in meters [m].
        viscosity: Dynamic viscosity in Pascal-seconds [Pa·s].
        pressure_drop: Pressure difference in Pascal [Pa].

    Returns:
        Volumetric flow rate in m³/s.

    Raises:
        ValueError: If any parameter is non-positive.

    Example:
        >>> # 100 µm radius, 1 cm length, water viscosity, 1000 Pa drop
        >>> Q = calculate_poiseuille_circular(100e-6, 0.01, 1e-3, 1000)
        >>> print(f"{Q:.2e} m³/s")  # ~3.93e-11 m³/s
    """
    _validate_positive(radius, "radius")
    _validate_positive(length, "length")
    _validate_positive(viscosity, "viscosity")
    _validate_non_negative(pressure_drop, "pressure_drop")

    return (pressure_drop * PI * radius**4) / (8 * viscosity * length)


def calculate_resistance_circular(
    radius: float,
    length: float,
    viscosity: float,
) -> float:
    """Calculate hydraulic resistance for circular channel.

    R = (8 · η · L) / (π · r⁴)

    Args:
        radius: Channel radius in meters [m].
        length: Channel length in meters [m].
        viscosity: Dynamic viscosity in Pascal-seconds [Pa·s].

    Returns:
        Hydraulic resistance in Pa·s/m³.

    Raises:
        ValueError: If any parameter is non-positive.
    """
    _validate_positive(radius, "radius")
    _validate_positive(length, "length")
    _validate_positive(viscosity, "viscosity")

    return (8 * viscosity * length) / (PI * radius**4)


def calculate_poiseuille_rectangular(
    width: float,
    height: float,
    length: float,
    viscosity: float,
    pressure_drop: float,
    n_terms: int = 5,
) -> float:
    """Calculate volumetric flow rate for rectangular channel.

    Q = (w·h³)/(12·η·L) · [1 - (192/π⁵) · Σ(1/n⁵ · tanh(nπh/2w)/(h/w))] · ΔP

    Uses series expansion with n_terms terms (n = 1, 3, 5, ...).

    Args:
        width: Channel width in meters [m].
        height: Channel height in meters [m].
        length: Channel length in meters [m].
        viscosity: Dynamic viscosity in Pascal-seconds [Pa·s].
        pressure_drop: Pressure difference in Pascal [Pa].
        n_terms: Number of terms in series expansion (default: 5).

    Returns:
        Volumetric flow rate in m³/s.

    Raises:
        ValueError: If any parameter is non-positive.

    Note:
        For accurate results, height should be the smaller dimension.
        The formula assumes h ≤ w; swap if necessary.
    """
    _validate_positive(width, "width")
    _validate_positive(height, "height")
    _validate_positive(length, "length")
    _validate_positive(viscosity, "viscosity")
    _validate_non_negative(pressure_drop, "pressure_drop")

    # Ensure h ≤ w for proper formula application
    if width < height:
        logger.warning(
            f"width ({width:.3e}) < height ({height:.3e}): swapping dimensions "
            "so that the smaller dimension is used as h in the Poiseuille formula."
        )
        w, h = height, width
    else:
        w, h = width, height

    # Base term: wh³/(12ηL)
    base_term = (w * h**3) / (12 * viscosity * length)

    # Series correction term
    aspect_ratio = h / w
    series_sum = 0.0

    for i in range(n_terms):
        n = 2 * i + 1  # n = 1, 3, 5, 7, 9, ...
        arg = n * PI * h / (2 * w)

        # Prevent overflow for large arguments
        if arg > 700:
            tanh_val = 1.0
        else:
            tanh_val = np.tanh(arg)

        series_sum += (1 / n**5) * tanh_val / aspect_ratio

    correction = 1 - (192 / PI**5) * series_sum

    return base_term * correction * pressure_drop


def calculate_resistance_rectangular(
    width: float,
    height: float,
    length: float,
    viscosity: float,
    n_terms: int = 5,
) -> float:
    """Calculate hydraulic resistance for rectangular channel.

    Args:
        width: Channel width in meters [m].
        height: Channel height in meters [m].
        length: Channel length in meters [m].
        viscosity: Dynamic viscosity in Pascal-seconds [Pa·s].
        n_terms: Number of terms in series expansion (default: 5).

    Returns:
        Hydraulic resistance in Pa·s/m³.

    Raises:
        ValueError: If any parameter is non-positive.
    """
    # Calculate flow for unit pressure drop
    flow_per_pressure = calculate_poiseuille_rectangular(
        width, height, length, viscosity, 1.0, n_terms
    )

    if flow_per_pressure <= 0:
        raise ValueError("Calculated flow rate is non-positive")

    return 1.0 / flow_per_pressure


def calculate_hydrostatic_pressure(
    density: float,
    height: float,
    gravity: float = 9.81,
) -> float:
    """Calculate hydrostatic pressure at given depth.

    ΔP = ρ · g · h

    Args:
        density: Fluid density in kg/m³.
        height: Fluid column height in meters [m].
        gravity: Gravitational acceleration in m/s² (default: 9.81).

    Returns:
        Hydrostatic pressure in Pascal [Pa].

    Raises:
        ValueError: If density or height is non-positive.
    """
    _validate_positive(density, "density")
    _validate_positive(height, "height")
    _validate_positive(gravity, "gravity")

    return density * gravity * height


def calculate_reynolds_number(
    velocity: float,
    characteristic_length: float,
    density: float,
    viscosity: float,
) -> float:
    """Calculate Reynolds number for flow characterization.

    Re = (ρ · v · L) / η

    Args:
        velocity: Flow velocity in m/s.
        characteristic_length: Characteristic dimension (e.g., diameter) in m.
        density: Fluid density in kg/m³.
        viscosity: Dynamic viscosity in Pa·s.

    Returns:
        Reynolds number (dimensionless).

    Raises:
        ValueError: If any parameter is non-positive.
    """
    _validate_positive(velocity, "velocity")
    _validate_positive(characteristic_length, "characteristic_length")
    _validate_positive(density, "density")
    _validate_positive(viscosity, "viscosity")

    return (density * velocity * characteristic_length) / viscosity


def is_laminar_flow(reynolds_number: float, threshold: float = 2300.0) -> bool:
    """Check if flow is laminar based on Reynolds number.

    Args:
        reynolds_number: Reynolds number value.
        threshold: Laminar/turbulent transition threshold (default: 2300).

    Returns:
        True if flow is laminar (Re < threshold).
    """
    return reynolds_number < threshold


def calculate_pressure_drop(
    flow_rate: float,
    resistance: float,
) -> float:
    """Calculate pressure drop from flow rate and resistance.

    ΔP = Q · R

    Args:
        flow_rate: Volumetric flow rate in m³/s.
        resistance: Hydraulic resistance in Pa·s/m³.

    Returns:
        Pressure drop in Pascal [Pa].

    Raises:
        ValueError: If any parameter is negative.
    """
    _validate_non_negative(flow_rate, "flow_rate")
    _validate_non_negative(resistance, "resistance")

    return flow_rate * resistance


def _validate_positive(value: float, name: str) -> None:
    """Validate that a value is strictly positive.

    Args:
        value: Value to validate.
        name: Parameter name for error message.

    Raises:
        ValueError: If value is not positive.
    """
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")


def _validate_non_negative(value: float, name: str) -> None:
    """Validate that a value is non-negative.

    Args:
        value: Value to validate.
        name: Parameter name for error message.

    Raises:
        ValueError: If value is negative.
    """
    if value < 0:
        raise ValueError(f"{name} cannot be negative, got {value}")