"""
TwoPortElement – Modelica-style two-port base class.

Modelica equivalent: Modelica.Fluid.Interfaces.PartialTwoPort

Each element exposes two FluidPort connectors:

    port_a  ──[element physics]──  port_b

Constitutive equation (must be implemented by subclasses):

    port_a.p - port_b.p  =  pressure_drop(port_a.mass_flow)

Mass conservation (automatically guaranteed by port sign convention):

    port_a.mass_flow + port_b.mass_flow = 0

Backward compatibility:
    TwoPortElement still implements calculate_resistance() and
    calculate_flow() so that the existing node-based solver works
    unchanged during the incremental migration.
"""

from __future__ import annotations

from abc import abstractmethod

from backend.models.base import FluidElement
from backend.models.medium import FluidMedium
from backend.ports.connector import FluidPort


class TwoPortElement(FluidElement):
    """
    Abstract base for two-port fluid elements.

    Subclasses implement pressure_drop(mass_flow) which encodes the
    element's constitutive physics equation.  The solver calls
    calculate_resistance() for backward compatibility; once the solver
    is migrated it will call pressure_drop() directly.

    Args:
        element_id: Unique identifier string.
        name:       Human-readable label.
        medium:     Fluid properties (shared across the network).
                    Defaults to water at 20 °C.
        connections: List of connected element IDs (managed by network).
    """

    def __init__(
        self,
        element_id: str,
        name: str,
        medium: FluidMedium | None = None,
        connections: list[str] | None = None,
    ) -> None:
        super().__init__(element_id, name, connections)
        self.medium: FluidMedium = medium or FluidMedium.water_20c()
        self.port_a = FluidPort(element_id=element_id, port_name="port_a")
        self.port_b = FluidPort(element_id=element_id, port_name="port_b")

    # ------------------------------------------------------------------
    # Abstract interface  (Modelica: equations section)
    # ------------------------------------------------------------------

    @abstractmethod
    def pressure_drop(self, mass_flow: float) -> float:
        """
        Constitutive equation:  ΔP = f(ṁ).

        Encodes the element's physics as a function from mass flow to
        pressure drop.  This is the single equation that replaces the
        Modelica 'equations' block for incompressible isothermal flow.

        Args:
            mass_flow: Mass flow rate [kg/s].
                       Positive = fluid flows from port_a to port_b.

        Returns:
            Pressure drop [Pa]:  port_a.p - port_b.p.
            Positive for normal (resistive) flow in the nominal direction.
        """
        ...

    # ------------------------------------------------------------------
    # Backward-compatible solver interface
    # ------------------------------------------------------------------

    def calculate_resistance(self) -> float:
        """
        Linearised hydraulic resistance R = ΔP / Q  [Pa·s/m³].

        Derived from pressure_drop() so subclasses only need to implement
        the physics once.  Keeps the existing node-based solver working
        without modification.
        """
        # Evaluate at a representative microfluidic flow (1 pL/s)
        # to stay in the linear Hagen-Poiseuille regime.
        test_mass_flow = 1e-12 * self.medium.density  # ṁ for Q = 1 pL/s
        dp = self.pressure_drop(test_mass_flow)
        q = test_mass_flow / self.medium.density
        if q <= 0:
            return 1e15
        return dp / q

    def calculate_flow(self, pressure_drop: float) -> float:
        """
        Volumetric flow for a given pressure drop  [m³/s].

        Inverts the linear resistance: Q = ΔP / R.
        """
        r = self.calculate_resistance()
        if r <= 0 or r >= 1e14:
            return 0.0
        return pressure_drop / r

    # ------------------------------------------------------------------
    # Port state management  (called by solver after solving)
    # ------------------------------------------------------------------

    def update_ports(self, pressure_a: float, pressure_b: float) -> None:
        """
        Set port pressures and derive mass flows from the solution.

        Called by the solver after the linear system is solved to populate
        the port objects with physically meaningful values.

        Args:
            pressure_a: Solved pressure at port_a [Pa].
            pressure_b: Solved pressure at port_b [Pa].
        """
        self.port_a.pressure = pressure_a
        self.port_b.pressure = pressure_b

        dp = pressure_a - pressure_b
        r = self.calculate_resistance()
        q = dp / r if r > 0 else 0.0
        mass_flow = q * self.medium.density

        # Sign convention: positive ṁ enters port_a and leaves port_b
        self.port_a.mass_flow = mass_flow
        self.port_b.mass_flow = -mass_flow

    def reset_ports(self) -> None:
        """Reset both ports to zero before a new solve."""
        self.port_a.reset()
        self.port_b.reset()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Extend base dict with port state and medium information."""
        d = super().to_dict()
        d["port_a"] = {
            "pressure": self.port_a.pressure,
            "mass_flow": self.port_a.mass_flow,
        }
        d["port_b"] = {
            "pressure": self.port_b.pressure,
            "mass_flow": self.port_b.mass_flow,
        }
        d["medium"] = self.medium.name
        return d
