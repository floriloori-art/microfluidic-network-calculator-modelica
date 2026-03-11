"""
Modelica-style fluid connector port.

Based on Modelica.Fluid.Interfaces.FluidPort convention:

    connector FluidPort
        flow Real m_flow [kg/s]   // Kirchhoff: sum = 0 at junction
        Real p         [Pa]       // potential: equal at connected ports
    end FluidPort;

Sign convention (Modelica standard):
    mass_flow > 0  →  fluid enters the element through this port
    mass_flow < 0  →  fluid leaves the element through this port

Connection semantics:
    Two connected ports satisfy:
        port_a.p == port_b.p          (equal pressures)
        port_a.mass_flow + port_b.mass_flow == 0   (flow conservation)
"""

from dataclasses import dataclass, field


@dataclass
class FluidPort:
    """
    Hydraulic fluid port – the fundamental connection point between elements.

    Equivalent to Modelica.Fluid.Interfaces.FluidPort (isothermal, incompressible
    simplification: no enthalpy stream variable needed).

    Attributes:
        pressure:   Static pressure at the port [Pa].
        mass_flow:  Mass flow rate through the port [kg/s].
                    Positive = fluid entering the owning element.
        element_id: ID of the element that owns this port.
        port_name:  "port_a" (inlet) or "port_b" (outlet) by convention.
    """

    pressure: float = 0.0
    mass_flow: float = 0.0
    element_id: str = ""
    port_name: str = ""

    def __repr__(self) -> str:
        return (
            f"FluidPort({self.element_id}.{self.port_name}: "
            f"p={self.pressure:.2f} Pa, "
            f"ṁ={self.mass_flow:.3e} kg/s)"
        )

    def reset(self) -> None:
        """Reset port state to zero (before a new solve)."""
        self.pressure = 0.0
        self.mass_flow = 0.0
