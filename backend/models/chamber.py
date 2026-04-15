"""
Chamber element for microfluidic networks – Modelica two-port style.

A chamber is modelled as a hydrostatic pressure source in series with a
negligible resistance.  In Modelica terms it behaves like:

    Modelica.Fluid.Sources.FixedBoundary  (pressure = rho*g*h)

with an internal resistance set to MINIMAL_RESISTANCE for numerical
stability.

Constitutive equations:
    port_a.p - port_b.p  = MINIMAL_RESISTANCE * Q     (near-zero ΔP)
    Hydrostatic reference: P_abs = rho * g * h

The hydrostatic pressure is exposed as a property so the solver can use
it as a Dirichlet boundary condition (same as the original behaviour).
"""

from __future__ import annotations

from typing import Any

from backend.models.medium import FluidMedium
from backend.models.two_port_base import TwoPortElement
from backend.physics.flow_calculations import calculate_hydrostatic_pressure


class Chamber(TwoPortElement):
    """
    Fluid reservoir / chamber with hydrostatic pressure.

    Modelica equivalent: Modelica.Fluid.Vessels.ClosedVolume or
    Modelica.Fluid.Sources.FixedBoundary.

    The chamber has essentially zero hydraulic resistance (MINIMAL_RESISTANCE
    for numerical stability).  Its pressure contribution comes from the
    fluid column height above the outlet: ΔP = ρ · g · h.

    Attributes:
        height:  Fluid column height [m].  Valid: 10 µm – 1000 µm.
        gravity: Gravitational acceleration [m/s²] (default 9.81).
        medium:  Fluid medium (carries density ρ).
    """

    MIN_HEIGHT: float = 10e-6    # 10 µm
    MAX_HEIGHT: float = 1000e-6  # 1 mm
    MINIMAL_RESISTANCE: float = 1e3  # Pa·s/m³ – numerical floor

    def __init__(
        self,
        element_id: str,
        name: str,
        height: float,
        medium: FluidMedium | None = None,
        gravity: float = 9.81,
        connections: list[str] | None = None,
        # Legacy parameter: density was a separate arg before FluidMedium
        density: float | None = None,
    ) -> None:
        # If caller passes raw density, build a medium from it
        if density is not None and medium is None:
            medium = FluidMedium(density=density)
        super().__init__(element_id, name, medium, connections)
        self.height = height
        self.gravity = gravity
        self.validate_parameters()

    # ------------------------------------------------------------------
    # Modelica constitutive equation
    # ------------------------------------------------------------------

    def pressure_drop(self, mass_flow: float) -> float:
        """
        ΔP across the chamber body ≈ 0 (minimal internal resistance).

        The hydrostatic pressure is exposed separately via
        calculate_hydrostatic_pressure() and used by the solver as a
        boundary condition, not as a pressure drop across the element.

        Args:
            mass_flow: Mass flow rate [kg/s].

        Returns:
            Near-zero pressure drop [Pa].
        """
        q = mass_flow / self.medium.density
        return self.MINIMAL_RESISTANCE * q

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def calculate_resistance(self) -> float:
        """Minimal resistance [Pa·s/m³] – chamber body has no flow loss."""
        return self.MINIMAL_RESISTANCE

    def calculate_flow(self, pressure_drop: float) -> float:
        """Q = ΔP / R_min  [m³/s]."""
        return pressure_drop / self.MINIMAL_RESISTANCE

    def calculate_hydrostatic_pressure(self) -> float:
        """
        Hydrostatic pressure at the chamber outlet:  ΔP = ρ · g · h  [Pa].

        Returns 0 if height=0 (outlet at reference level).
        Used by the solver to set the absolute pressure reference at this node.
        """
        if self.height == 0.0:
            return 0.0
        return calculate_hydrostatic_pressure(
            self.medium.density, self.height, self.gravity
        )

    # Legacy accessors for backward compatibility
    @property
    def density(self) -> float:
        """Legacy accessor – delegates to medium.density."""
        return self.medium.density

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_parameters(self) -> bool:
        if self.height < 0:
            raise ValueError(f"Height cannot be negative, got {self.height}")
        if self.medium.density <= 0:
            raise ValueError(f"Density must be positive, got {self.medium.density}")
        if self.gravity <= 0:
            raise ValueError(f"Gravity must be positive, got {self.gravity}")
        return True

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update({
            "height": self.height,
            "density": self.medium.density,
            "gravity": self.gravity,
            "hydrostatic_pressure": self.calculate_hydrostatic_pressure(),
            "resistance": self.calculate_resistance(),
        })
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chamber":
        medium = FluidMedium(density=data["density"])
        return cls(
            element_id=data["element_id"],
            name=data["name"],
            height=data["height"],
            medium=medium,
            gravity=data.get("gravity", 9.81),
            connections=data.get("connections"),
        )
