"""Pump element for microfluidic networks."""

from typing import Any

from backend.models.base import FluidElement


class Pump(FluidElement):
    """Active pump element that generates pressure and flow.

    Implements a pressure-driven flow model where the pump
    generates pressure to overcome hydraulic resistance.

    Attributes:
        area: Cross-sectional area in m².
        velocity: Flow velocity in m/s.
        pressure_generated: Generated pressure in Pascal [Pa].
        resistance: Internal pump resistance in Pa·s/m³.
    """

    MIN_PRESSURE: float = 1e2  # 100 Pa
    MAX_PRESSURE: float = 1e5  # 100 kPa

    def __init__(
        self,
        element_id: str,
        name: str,
        area: float,
        velocity: float,
        pressure_generated: float,
        resistance: float,
        connections: list[str] | None = None,
    ) -> None:
        """Initialize a pump.

        Args:
            element_id: Unique identifier for the element.
            name: Human-readable name for the element.
            area: Cross-sectional area in m².
            velocity: Flow velocity in m/s.
            pressure_generated: Generated pressure in Pascal [Pa].
            resistance: Internal pump resistance in Pa·s/m³.
            connections: List of connected element IDs.

        Raises:
            ValueError: If any parameter is invalid.
        """
        super().__init__(element_id, name, connections)
        self.area = area
        self.velocity = velocity
        self.pressure_generated = pressure_generated
        self.resistance = resistance
        self.validate_parameters()

    def validate_parameters(self) -> bool:
        """Validate pump parameters.

        Returns:
            True if all parameters are valid.

        Raises:
            ValueError: If any parameter is out of valid range.
        """
        if self.area <= 0:
            raise ValueError(f"Area must be positive, got {self.area}")
        if self.velocity < 0:
            raise ValueError(f"Velocity cannot be negative, got {self.velocity}")
        if self.pressure_generated < 0:
            raise ValueError(
                f"Pressure generated cannot be negative, got {self.pressure_generated}"
            )
        if self.resistance < 0:
            raise ValueError(f"Resistance cannot be negative, got {self.resistance}")
        return True

    def calculate_resistance(self) -> float:
        """Get internal pump resistance.

        Returns:
            Hydraulic resistance in Pa·s/m³.
        """
        return self.resistance

    def calculate_flow(self, pressure_drop: float = 0.0) -> float:
        """Calculate volumetric flow rate from pump.

        Q = A · v

        For pumps, flow is primarily determined by area and velocity,
        not pressure drop (active element).

        Args:
            pressure_drop: External pressure drop (used for adjusted flow).

        Returns:
            Volumetric flow rate in m³/s.
        """
        base_flow = self.area * self.velocity
        if pressure_drop > 0 and self.resistance > 0:
            # Reduce flow based on back-pressure
            flow_reduction = pressure_drop / self.resistance
            return max(0.0, base_flow - flow_reduction)
        return base_flow

    def calculate_output_pressure(self, flow_rate: float) -> float:
        """Calculate output pressure for given flow rate.

        P_out = P_gen - R_h · Q

        Args:
            flow_rate: Volumetric flow rate in m³/s.

        Returns:
            Output pressure in Pascal [Pa].
        """
        return self.pressure_generated - self.resistance * flow_rate

    def get_nominal_flow(self) -> float:
        """Get nominal (maximum) flow rate.

        Returns:
            Nominal volumetric flow rate in m³/s.
        """
        return self.area * self.velocity

    def to_dict(self) -> dict[str, Any]:
        """Serialize pump to dictionary.

        Returns:
            Dictionary representation including all parameters.
        """
        data = super().to_dict()
        data.update({
            "area": self.area,
            "velocity": self.velocity,
            "pressure_generated": self.pressure_generated,
            "resistance": self.resistance,
            "nominal_flow": self.get_nominal_flow(),
            "is_active": True,
        })
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Pump":
        """Create Pump from dictionary.

        Args:
            data: Dictionary with pump parameters.

        Returns:
            New Pump instance.
        """
        return cls(
            element_id=data["element_id"],
            name=data["name"],
            area=data["area"],
            velocity=data["velocity"],
            pressure_generated=data["pressure_generated"],
            resistance=data["resistance"],
            connections=data.get("connections"),
        )