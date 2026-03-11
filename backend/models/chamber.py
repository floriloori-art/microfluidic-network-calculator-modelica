"""Chamber element for microfluidic networks."""

from typing import Any

from backend.models.base import FluidElement
from backend.physics.flow_calculations import calculate_hydrostatic_pressure


class Chamber(FluidElement):
    """Fluid chamber with hydrostatic pressure.

    Implements a static chamber element where pressure is determined
    by fluid column height. Minimal flow resistance assumed.

    Attributes:
        height: Fluid column height in meters [m].
        density: Fluid density in kg/m³.
        gravity: Gravitational acceleration in m/s² (default: 9.81).
    """

    MIN_HEIGHT: float = 10e-6  # 10 µm
    MAX_HEIGHT: float = 1000e-6  # 1000 µm
    MINIMAL_RESISTANCE: float = 1e3  # Minimal resistance for numerical stability

    def __init__(
        self,
        element_id: str,
        name: str,
        height: float,
        density: float,
        gravity: float = 9.81,
        connections: list[str] | None = None,
    ) -> None:
        """Initialize a chamber.

        Args:
            element_id: Unique identifier for the element.
            name: Human-readable name for the element.
            height: Fluid column height in meters [m].
            density: Fluid density in kg/m³.
            gravity: Gravitational acceleration in m/s² (default: 9.81).
            connections: List of connected element IDs.

        Raises:
            ValueError: If any parameter is invalid.
        """
        super().__init__(element_id, name, connections)
        self.height = height
        self.density = density
        self.gravity = gravity
        self.validate_parameters()

    def validate_parameters(self) -> bool:
        """Validate chamber parameters.

        Returns:
            True if all parameters are valid.

        Raises:
            ValueError: If any parameter is out of valid range.
        """
        if self.height <= 0:
            raise ValueError(f"Height must be positive, got {self.height}")
        if self.density <= 0:
            raise ValueError(f"Density must be positive, got {self.density}")
        if self.gravity <= 0:
            raise ValueError(f"Gravity must be positive, got {self.gravity}")
        return True

    def calculate_resistance(self) -> float:
        """Calculate hydraulic resistance of chamber.

        Chambers have minimal resistance (quasi no pressure loss).

        Returns:
            Minimal hydraulic resistance in Pa·s/m³.
        """
        return self.MINIMAL_RESISTANCE

    def calculate_flow(self, pressure_drop: float) -> float:
        """Calculate volumetric flow rate through chamber.

        Due to minimal resistance, flow is determined by
        pressure drop / minimal resistance.

        Args:
            pressure_drop: Pressure difference in Pascal [Pa].

        Returns:
            Volumetric flow rate in m³/s.
        """
        return pressure_drop / self.MINIMAL_RESISTANCE

    def calculate_hydrostatic_pressure(self) -> float:
        """Calculate hydrostatic pressure at chamber bottom.

        ΔP = ρ · g · h

        Returns:
            Hydrostatic pressure in Pascal [Pa].
        """
        return calculate_hydrostatic_pressure(
            self.density, self.height, self.gravity
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize chamber to dictionary.

        Returns:
            Dictionary representation including all parameters.
        """
        data = super().to_dict()
        data.update({
            "height": self.height,
            "density": self.density,
            "gravity": self.gravity,
            "hydrostatic_pressure": self.calculate_hydrostatic_pressure(),
            "resistance": self.calculate_resistance(),
        })
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chamber":
        """Create Chamber from dictionary.

        Args:
            data: Dictionary with chamber parameters.

        Returns:
            New Chamber instance.
        """
        return cls(
            element_id=data["element_id"],
            name=data["name"],
            height=data["height"],
            density=data["density"],
            gravity=data.get("gravity", 9.81),
            connections=data.get("connections"),
        )