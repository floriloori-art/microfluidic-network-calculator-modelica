"""
Valve element for microfluidic networks – Modelica two-port style.

Replaces the old binary resistance (1e3 / 1e15) with a proper
Cv-coefficient model following the ISA S75 / IEC 60534 standard,
which is also used in Modelica.Fluid.Valves.

Modelica equivalent: Modelica.Fluid.Valves.ValveLinear

Constitutive equation (incompressible liquid, ISA):
    Q = Cv · opening · sqrt(ΔP / (rho/rho_ref))

For incompressible isothermal flow simplified to:
    Q = Kv · opening · sqrt(ΔP)
    ΔP = (Q / (Kv · opening))²

where:
    Kv  = valve flow coefficient [m³/s / sqrt(Pa)]
    opening ∈ [0, 1]  – 0 = fully closed, 1 = fully open

Legacy compatibility:
    - state: bool (True=open → opening=1, False=closed → opening=0)
    - open() / close() / toggle() still work
    - input_flow attribute kept (not used in physics anymore)
"""

from __future__ import annotations

import math
from typing import Any

from backend.models.medium import FluidMedium
from backend.models.two_port_base import TwoPortElement


class Valve(TwoPortElement):
    """
    Proportionally controlled valve with Kv flow coefficient.

    The pressure drop follows ISA S75 for incompressible liquid:
        ΔP = (Q / (Kv · opening))²  · rho / rho_ref

    For isothermal incompressible flow (microfluidics):
        ΔP = (ṁ / (rho · Kv · opening))²

    A fully open valve with Kv = 1e-9 m³/(s·√Pa) and opening=1.0
    gives roughly the same resistance as the old OPEN_RESISTANCE = 1e3.

    Attributes:
        kv:           Flow coefficient Kv [m³/s / sqrt(Pa)].
        opening:      Fractional opening ∈ [0, 1].  0=closed, 1=open.
        response_time: Switching time [s] (informational, not enforced).
        medium:       Fluid medium.
    """

    # Reference density for Kv normalisation (water at 20 °C)
    RHO_REF: float = 998.2  # kg/m³

    # Default Kv gives ~1e3 Pa·s/m³ at fully open (same as old OPEN_RESISTANCE)
    # R_open = 1 / Kv²  →  Kv = 1/sqrt(1e3) ≈ 3.16e-2 (volumetric)
    # For mass-flow form: Kv_mass = Kv · rho  (absorbed into formula below)
    DEFAULT_KV: float = math.sqrt(1.0 / 1e3)   # ≈ 0.0316 m³/(s·√Pa)

    # Minimum opening to avoid division by zero (numerically "closed")
    MIN_OPENING: float = 1e-10

    def __init__(
        self,
        element_id: str,
        name: str,
        kv: float | None = None,
        opening: float = 1.0,
        response_time: float = 1e-3,
        medium: FluidMedium | None = None,
        connections: list[str] | None = None,
        # Legacy parameters
        state: bool | None = None,
        input_flow: float = 0.0,
    ) -> None:
        super().__init__(element_id, name, medium, connections)

        self.kv = kv if kv is not None else self.DEFAULT_KV
        self.response_time = response_time
        self.input_flow = input_flow  # legacy attribute

        # Initialise opening from legacy bool state or direct value
        if state is not None:
            self.opening = 1.0 if state else 0.0
        else:
            self.opening = float(opening)

        self.validate_parameters()

    # ------------------------------------------------------------------
    # Modelica constitutive equation
    # ------------------------------------------------------------------

    def pressure_drop(self, mass_flow: float) -> float:
        """
        ISA Kv equation (inverted):  ΔP = (ṁ / (ρ · Kv · opening))²

        Args:
            mass_flow: Mass flow rate [kg/s], positive = port_a → port_b.

        Returns:
            Pressure drop [Pa].  Very large when nearly closed.
        """
        eff_opening = max(self.opening, self.MIN_OPENING)
        q = mass_flow / self.medium.density
        # ΔP = (Q / (Kv · opening))²
        return (q / (self.kv * eff_opening)) ** 2

    def flow_from_dp(self, dp: float) -> float:
        """
        ISA Kv equation (forward):  Q = Kv · opening · sqrt(ΔP)

        Args:
            dp: Pressure drop [Pa].

        Returns:
            Volumetric flow rate [m³/s].
        """
        if dp < 0:
            return 0.0
        eff_opening = max(self.opening, self.MIN_OPENING)
        return self.kv * eff_opening * math.sqrt(dp)

    # ------------------------------------------------------------------
    # Backward-compatible resistance
    # ------------------------------------------------------------------

    def calculate_resistance(self) -> float:
        """
        Linearised resistance R = ΔP / Q  [Pa·s/m³].

        R = 1 / (Kv · opening)²

        Returns very high value when nearly closed.
        """
        eff_opening = max(self.opening, self.MIN_OPENING)
        return 1.0 / (self.kv * eff_opening) ** 2

    def calculate_flow(self, pressure_drop: float = 0.0) -> float:
        """Q = Kv · opening · sqrt(ΔP)  [m³/s]."""
        return self.flow_from_dp(max(pressure_drop, 0.0))

    # ------------------------------------------------------------------
    # Control interface  (Modelica: input signal)
    # ------------------------------------------------------------------

    def set_opening(self, opening: float) -> None:
        """
        Set fractional opening ∈ [0, 1].

        Modelica equivalent: connecting a Real signal to
        Modelica.Fluid.Valves.ValveLinear.opening.

        Args:
            opening: 0.0 = fully closed, 1.0 = fully open.

        Raises:
            ValueError: If opening is outside [0, 1].
        """
        if not (0.0 <= opening <= 1.0):
            raise ValueError(f"opening must be in [0, 1], got {opening}")
        self.opening = opening

    # Legacy binary control
    @property
    def state(self) -> bool:
        """Legacy boolean state: True = open (opening > 0.5)."""
        return self.opening > 0.5

    @state.setter
    def state(self, value: bool) -> None:
        self.opening = 1.0 if value else 0.0

    def open(self) -> None:
        """Fully open the valve (opening = 1.0)."""
        self.opening = 1.0

    def close(self) -> None:
        """Fully close the valve (opening = 0.0)."""
        self.opening = 0.0

    def toggle(self) -> None:
        """Toggle between fully open and fully closed."""
        self.opening = 0.0 if self.opening > 0.5 else 1.0

    def set_input_flow(self, flow: float) -> None:
        """Legacy setter – stores input_flow but does not affect physics."""
        if flow < 0:
            raise ValueError(f"Input flow cannot be negative, got {flow}")
        self.input_flow = flow

    def get_output_flow(self) -> float:
        """Legacy getter – returns flow for stored input_flow."""
        return self.input_flow * (1.0 if self.opening > 0.5 else 0.0)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_parameters(self) -> bool:
        if self.kv <= 0:
            raise ValueError(f"kv must be positive, got {self.kv}")
        if not (0.0 <= self.opening <= 1.0):
            raise ValueError(f"opening must be in [0, 1], got {self.opening}")
        if self.response_time < 0:
            raise ValueError(
                f"response_time cannot be negative, got {self.response_time}"
            )
        return True

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update({
            "kv": self.kv,
            "opening": self.opening,
            "state": self.state,
            "state_name": "open" if self.state else "closed",
            "response_time": self.response_time,
            "input_flow": self.input_flow,
            "output_flow": self.get_output_flow(),
            "resistance": self.calculate_resistance(),
        })
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Valve":
        return cls(
            element_id=data["element_id"],
            name=data["name"],
            kv=data.get("kv"),
            opening=data.get("opening", 1.0),
            state=data.get("state"),
            response_time=data.get("response_time", 1e-3),
            input_flow=data.get("input_flow", 0.0),
            connections=data.get("connections"),
        )
