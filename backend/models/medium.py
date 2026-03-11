"""
Central fluid medium model.

Replaces per-element viscosity/density parameters with a shared medium object,
following the Modelica.Media interface pattern.

Modelica equivalent: Modelica.Media.Interfaces.PartialMedium
Default preset:      Modelica.Media.Water.ConstantPropertyLiquidWater

In the Modelica Standard Library a medium is a package (not a class), but for
Python we use a simple dataclass that can be instantiated and passed around.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FluidMedium:
    """
    Incompressible, isothermal fluid medium.

    Holds all fluid properties needed for hydraulic calculations.
    Pass one shared instance to all elements in a network so that
    material properties are defined in a single place.

    Attributes:
        density:           Mass density ρ [kg/m³].
        dynamic_viscosity: Dynamic viscosity η [Pa·s].
        name:              Human-readable medium identifier.
    """

    density: float = 998.2           # ρ  [kg/m³]   water at 20 °C, 1 bar
    dynamic_viscosity: float = 1e-3  # η  [Pa·s]    water at 20 °C
    name: str = "Water_20C"

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def kinematic_viscosity(self) -> float:
        """Kinematic viscosity ν = η / ρ  [m²/s]."""
        return self.dynamic_viscosity / self.density

    # ------------------------------------------------------------------
    # Factory presets  (Modelica: predefined medium packages)
    # ------------------------------------------------------------------

    @classmethod
    def water_20c(cls) -> "FluidMedium":
        """Liquid water at 20 °C, 1 bar  (default microfluidic medium)."""
        return cls(density=998.2, dynamic_viscosity=1.002e-3, name="Water_20C")

    @classmethod
    def water_37c(cls) -> "FluidMedium":
        """Liquid water at 37 °C (body temperature, biomedical applications)."""
        return cls(density=993.3, dynamic_viscosity=0.692e-3, name="Water_37C")

    @classmethod
    def glycerol_50pct(cls) -> "FluidMedium":
        """50 % glycerol–water mixture at 20 °C (common viscosity standard)."""
        return cls(density=1126.0, dynamic_viscosity=6.0e-3, name="Glycerol50_20C")

    @classmethod
    def ethanol(cls) -> "FluidMedium":
        """Ethanol at 20 °C."""
        return cls(density=789.0, dynamic_viscosity=1.2e-3, name="Ethanol_20C")

    def __repr__(self) -> str:
        return (
            f"FluidMedium({self.name}: "
            f"ρ={self.density:.1f} kg/m³, "
            f"η={self.dynamic_viscosity:.3e} Pa·s)"
        )
