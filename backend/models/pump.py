"""
Pump element for microfluidic networks – Modelica two-port style.

Replaces the old "fixed pressure node" (Dirichlet hack) with a proper
two-port active element that has a realistic pump characteristic curve.

Modelica equivalent: Modelica.Fluid.Machines.Pump

Pump characteristic curve (quadratic, as in Modelica):
    dp = dp_max - b · Q²
    where:
        dp_max  = maximum pressure at zero flow  [Pa]
        Q_max   = maximum flow at zero pressure   [m³/s]
        b       = dp_max / Q_max²                 [Pa·s²/m⁶]

This gives:
    Q = sqrt((dp_max - dp) / b)    for dp ≤ dp_max
    dp = dp_max - b · Q²           (pressure drop ≡ negative, pump adds pressure)

For the solver the pump still behaves as a Dirichlet pressure BC at its
node (pressure_generated = dp_max), so backward compatibility is preserved.
The two-port interface additionally lets callers query the operating point.
"""

from __future__ import annotations

import math
from typing import Any

from backend.models.medium import FluidMedium
from backend.models.two_port_base import TwoPortElement


class Pump(TwoPortElement):
    """
    Active pump element with quadratic head-flow characteristic.

    The characteristic curve follows the Modelica.Fluid convention:
        H(Q) = dp_max · (1 - (Q / Q_max)²)
        dp   = rho · g · H   →   dp(Q) = dp_max - b · Q²

    where b = dp_max / Q_max².

    For the existing node-based solver the pump still sets a fixed pressure
    (Dirichlet BC) equal to dp_max.  Once the port-based solver is in place
    the full characteristic will be used automatically.

    Attributes:
        pressure_generated: Maximum pressure at zero flow  dp_max [Pa].
        flow_max:           Maximum flow at zero pressure  Q_max  [m³/s].
        resistance:         Internal hydraulic resistance  R_int  [Pa·s/m³].
                            Used as fallback for calculate_resistance().
        area:               Nominal cross-section [m²]  (legacy).
        velocity:           Nominal velocity [m/s]  (legacy).
        medium:             Fluid medium.
    """

    MIN_PRESSURE: float = 1e2   # 100 Pa
    MAX_PRESSURE: float = 1e5   # 100 kPa

    def __init__(
        self,
        element_id: str,
        name: str,
        pressure_generated: float,
        flow_max: float | None = None,
        resistance: float = 1e10,
        medium: FluidMedium | None = None,
        connections: list[str] | None = None,
        # Legacy parameters
        area: float | None = None,
        velocity: float | None = None,
    ) -> None:
        super().__init__(element_id, name, medium, connections)

        self.pressure_generated = pressure_generated   # dp_max [Pa]
        self.resistance = resistance                   # R_int  [Pa·s/m³]

        # Derive Q_max from legacy area·velocity if not given directly
        if flow_max is not None:
            self.flow_max = flow_max
        elif area is not None and velocity is not None:
            self.flow_max = area * velocity
        else:
            # Fallback: Q_max from resistance  Q_max = dp_max / R_int
            self.flow_max = pressure_generated / resistance if resistance > 0 else 1e-6

        # Legacy attributes kept for backward compat
        self.area = area if area is not None else self.flow_max
        self.velocity = velocity if velocity is not None else 1.0

        # Quadratic curve coefficient  b = dp_max / Q_max²
        self._b: float = (
            pressure_generated / (self.flow_max ** 2)
            if self.flow_max > 0
            else float("inf")
        )

        self.validate_parameters()

    # ------------------------------------------------------------------
    # Modelica constitutive equation  (active element: negative ΔP = pressure rise)
    # ------------------------------------------------------------------

    def pressure_drop(self, mass_flow: float) -> float:
        """
        Pump characteristic: ΔP = dp_max - b · Q²  (negative = pressure rise).

        For the solver: a pump with dp_max = 1000 Pa and mass_flow through it
        returns a *negative* pressure drop (it adds pressure).

        Args:
            mass_flow: Mass flow rate [kg/s], positive = port_a → port_b.

        Returns:
            Effective pressure drop [Pa].
            Negative for a working pump (port_b.p > port_a.p).
        """
        q = mass_flow / self.medium.density
        # Quadratic characteristic: dp_pump = dp_max - b·Q²
        # As a two-port element, the pump provides negative "drop"
        dp_pump = self.pressure_generated - self._b * q ** 2
        return -max(dp_pump, 0.0)  # negative = adds pressure

    # ------------------------------------------------------------------
    # Operating-point queries (Modelica: operating point equations)
    # ------------------------------------------------------------------

    def flow_at_pressure(self, back_pressure: float) -> float:
        """
        Operating flow from the pump characteristic for a given back-pressure.

        Solves:  dp_max - b · Q² = back_pressure
            →   Q = sqrt((dp_max - back_pressure) / b)

        Args:
            back_pressure: Pressure the pump works against [Pa].

        Returns:
            Volumetric flow rate [m³/s].  Zero if back_pressure ≥ dp_max.
        """
        delta = self.pressure_generated - back_pressure
        if delta <= 0:
            return 0.0
        return math.sqrt(delta / self._b) if self._b > 0 else self.flow_max

    def pressure_at_flow(self, flow_rate: float) -> float:
        """
        Pump head for a given volumetric flow (characteristic curve).

        dp(Q) = dp_max - b · Q²

        Args:
            flow_rate: Volumetric flow rate [m³/s].

        Returns:
            Generated pressure [Pa].  Zero if Q > Q_max.
        """
        dp = self.pressure_generated - self._b * flow_rate ** 2
        return max(dp, 0.0)

    def get_nominal_flow(self) -> float:
        """Maximum (nominal) volumetric flow rate at zero back-pressure [m³/s]."""
        return self.flow_max

    def calculate_output_pressure(self, flow_rate: float) -> float:
        """Legacy method: output pressure for given flow  P_out = P_gen - R·Q."""
        return self.pressure_generated - self.resistance * flow_rate

    # ------------------------------------------------------------------
    # Backward-compatible resistance  (used by node-based solver)
    # ------------------------------------------------------------------

    def calculate_resistance(self) -> float:
        """
        Internal resistance [Pa·s/m³].

        The node-based solver uses this for conductance-matrix construction.
        The pump also registers as a Dirichlet BC (pressure_generated),
        so this value mainly affects the diagonal entry at the pump node.
        """
        return self.resistance

    def calculate_flow(self, pressure_drop: float = 0.0) -> float:
        """
        Legacy flow calculation.  Active element: returns nominal flow
        reduced by any back-pressure.
        """
        return self.flow_at_pressure(max(pressure_drop, 0.0))

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_parameters(self) -> bool:
        if self.pressure_generated < 0:
            raise ValueError(
                f"pressure_generated cannot be negative, got {self.pressure_generated}"
            )
        if self.flow_max <= 0:
            raise ValueError(f"flow_max must be positive, got {self.flow_max}")
        if self.resistance < 0:
            raise ValueError(f"resistance cannot be negative, got {self.resistance}")
        return True

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update({
            "pressure_generated": self.pressure_generated,
            "flow_max": self.flow_max,
            "resistance": self.resistance,
            "area": self.area,
            "velocity": self.velocity,
            "nominal_flow": self.get_nominal_flow(),
            "curve_coefficient_b": self._b,
            "is_active": True,
        })
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Pump":
        return cls(
            element_id=data["element_id"],
            name=data["name"],
            pressure_generated=data["pressure_generated"],
            flow_max=data.get("flow_max"),
            resistance=data.get("resistance", 1e10),
            area=data.get("area"),
            velocity=data.get("velocity"),
            connections=data.get("connections"),
        )
