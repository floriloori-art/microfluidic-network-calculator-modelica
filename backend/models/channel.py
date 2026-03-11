"""
Channel elements for microfluidic networks – Modelica two-port style.

Both channel classes now inherit from TwoPortElement and implement the
Modelica-style constitutive equation:

    pressure_drop(mass_flow) = R * Q = R * mass_flow / density

Key changes vs. the node-based version:
  - viscosity parameter replaced by shared FluidMedium object
  - pressure_drop(ṁ) is the primary physics method
  - calculate_resistance() and calculate_flow() are kept for solver
    backward compatibility (they delegate to pressure_drop)
  - port_a / port_b exposed for future port-based solver
"""

from __future__ import annotations

from typing import Any

from backend.models.medium import FluidMedium
from backend.models.two_port_base import TwoPortElement
from backend.physics.flow_calculations import (
    calculate_poiseuille_circular,
    calculate_poiseuille_rectangular,
    calculate_resistance_circular,
    calculate_resistance_rectangular,
)


class CircularChannel(TwoPortElement):
    """
    Circular cross-section microfluidic channel.

    Constitutive equation (Hagen-Poiseuille):
        ΔP = R · Q = (8ηL / πr⁴) · (ṁ / ρ)

    Modelica equivalent: Modelica.Fluid.Pipes.StaticPipe with
        WallFriction = Laminar (Hagen-Poiseuille).

    Attributes:
        radius: Channel radius [m].  Valid range: 10 µm – 500 µm.
        length: Channel length [m].
        medium: Shared fluid medium (carries η and ρ).

    Note:
        The legacy ``viscosity`` parameter is still accepted in
        ``from_dict`` for backward compatibility and is forwarded to
        a FluidMedium with that viscosity and water density.
    """

    MIN_RADIUS: float = 10e-6   # 10 µm
    MAX_RADIUS: float = 500e-6  # 500 µm

    def __init__(
        self,
        element_id: str,
        name: str,
        radius: float,
        length: float,
        medium: FluidMedium | None = None,
        connections: list[str] | None = None,
        # Legacy parameter kept for backward compatibility with existing tests
        viscosity: float | None = None,
    ) -> None:
        # If caller passes a raw viscosity (old API), wrap it in a medium
        if viscosity is not None and medium is None:
            medium = FluidMedium(dynamic_viscosity=viscosity)
        super().__init__(element_id, name, medium, connections)
        self.radius = radius
        self.length = length
        self.validate_parameters()

    # ------------------------------------------------------------------
    # Modelica constitutive equation
    # ------------------------------------------------------------------

    def pressure_drop(self, mass_flow: float) -> float:
        """
        ΔP = R · Q   (Hagen-Poiseuille, linear in flow).

        Args:
            mass_flow: Mass flow rate [kg/s], positive = port_a → port_b.

        Returns:
            Pressure drop [Pa]: port_a.p - port_b.p.
        """
        q = mass_flow / self.medium.density
        r = calculate_resistance_circular(
            self.radius, self.length, self.medium.dynamic_viscosity
        )
        return r * q

    # ------------------------------------------------------------------
    # Overrides for direct (non-linearised) resistance
    # ------------------------------------------------------------------

    def calculate_resistance(self) -> float:
        """R = 8ηL / (πr⁴)  [Pa·s/m³]."""
        return calculate_resistance_circular(
            self.radius, self.length, self.medium.dynamic_viscosity
        )

    def calculate_flow(self, pressure_drop: float) -> float:
        """Q = ΔP / R  [m³/s].  Raises ValueError for negative ΔP."""
        if pressure_drop < 0:
            raise ValueError(
                f"Pressure drop cannot be negative for passive element, got {pressure_drop}"
            )
        return calculate_poiseuille_circular(
            self.radius, self.length, self.medium.dynamic_viscosity, pressure_drop
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @property
    def viscosity(self) -> float:
        """Legacy accessor – delegates to medium.dynamic_viscosity."""
        return self.medium.dynamic_viscosity

    def validate_parameters(self) -> bool:
        if self.radius <= 0:
            raise ValueError(f"Radius must be positive, got {self.radius}")
        if not (self.MIN_RADIUS <= self.radius <= self.MAX_RADIUS):
            raise ValueError(
                f"Radius must be between {self.MIN_RADIUS * 1e6:.0f} µm and "
                f"{self.MAX_RADIUS * 1e6:.0f} µm, got {self.radius * 1e6:.2f} µm"
            )
        if self.length <= 0:
            raise ValueError(f"Length must be positive, got {self.length}")
        if self.medium.dynamic_viscosity <= 0:
            raise ValueError(
                f"Viscosity must be positive, got {self.medium.dynamic_viscosity}"
            )
        return True

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()  # includes port_a, port_b, medium from TwoPortElement
        data.update({
            "radius": self.radius,
            "length": self.length,
            "viscosity": self.medium.dynamic_viscosity,  # legacy field
            "resistance": self.calculate_resistance(),
        })
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CircularChannel":
        medium = FluidMedium(dynamic_viscosity=data["viscosity"])
        return cls(
            element_id=data["element_id"],
            name=data["name"],
            radius=data["radius"],
            length=data["length"],
            medium=medium,
            connections=data.get("connections"),
        )


class RectangularChannel(TwoPortElement):
    """
    Rectangular cross-section microfluidic channel.

    Constitutive equation (modified Poiseuille, series expansion):
        Q = (wh³ / 12ηL) · [1 - (192/π⁵) · Σ tanh(nπh/2w) / n⁵] · ΔP

    Modelica equivalent: Modelica.Fluid.Pipes.StaticPipe with
        WallFriction = Laminar and rectangular geometry correction.

    Attributes:
        width:   Channel width  [m].  Valid range: 10 µm – 500 µm.
        height:  Channel height [m].  Valid range: 10 µm – 500 µm.
        length:  Channel length [m].
        n_terms: Number of terms in the series expansion (default: 5).
        medium:  Shared fluid medium.
    """

    MIN_DIMENSION: float = 10e-6   # 10 µm
    MAX_DIMENSION: float = 500e-6  # 500 µm

    def __init__(
        self,
        element_id: str,
        name: str,
        width: float,
        height: float,
        length: float,
        medium: FluidMedium | None = None,
        connections: list[str] | None = None,
        n_terms: int = 5,
        # Legacy parameter
        viscosity: float | None = None,
    ) -> None:
        if viscosity is not None and medium is None:
            medium = FluidMedium(dynamic_viscosity=viscosity)
        super().__init__(element_id, name, medium, connections)
        self.width = width
        self.height = height
        self.length = length
        self.n_terms = n_terms
        self.validate_parameters()

    # ------------------------------------------------------------------
    # Modelica constitutive equation
    # ------------------------------------------------------------------

    def pressure_drop(self, mass_flow: float) -> float:
        """
        ΔP = R · Q   (modified Poiseuille for rectangular cross-section).

        Args:
            mass_flow: Mass flow rate [kg/s], positive = port_a → port_b.

        Returns:
            Pressure drop [Pa].
        """
        q = mass_flow / self.medium.density
        r = calculate_resistance_rectangular(
            self.width, self.height, self.length,
            self.medium.dynamic_viscosity, self.n_terms,
        )
        return r * q

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def calculate_resistance(self) -> float:
        """Hydraulic resistance from series expansion  [Pa·s/m³]."""
        return calculate_resistance_rectangular(
            self.width, self.height, self.length,
            self.medium.dynamic_viscosity, self.n_terms,
        )

    def calculate_flow(self, pressure_drop: float) -> float:
        """Q = ΔP / R  [m³/s]."""
        if pressure_drop < 0:
            raise ValueError(
                f"Pressure drop cannot be negative for passive element, got {pressure_drop}"
            )
        return calculate_poiseuille_rectangular(
            self.width, self.height, self.length,
            self.medium.dynamic_viscosity, pressure_drop, self.n_terms,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_parameters(self) -> bool:
        for name, val in [("Width", self.width), ("Height", self.height)]:
            if val <= 0:
                raise ValueError(f"{name} must be positive, got {val}")
        if self.length <= 0:
            raise ValueError(f"Length must be positive, got {self.length}")
        if self.medium.dynamic_viscosity <= 0:
            raise ValueError(
                f"Viscosity must be positive, got {self.medium.dynamic_viscosity}"
            )
        if self.n_terms < 1:
            raise ValueError(f"n_terms must be at least 1, got {self.n_terms}")
        return True

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update({
            "width": self.width,
            "height": self.height,
            "length": self.length,
            "viscosity": self.medium.dynamic_viscosity,
            "n_terms": self.n_terms,
            "resistance": self.calculate_resistance(),
        })
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RectangularChannel":
        medium = FluidMedium(dynamic_viscosity=data["viscosity"])
        return cls(
            element_id=data["element_id"],
            name=data["name"],
            width=data["width"],
            height=data["height"],
            length=data["length"],
            medium=medium,
            connections=data.get("connections"),
            n_terms=data.get("n_terms", 5),
        )
