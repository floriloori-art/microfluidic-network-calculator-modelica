"""Valve element for microfluidic networks."""

from typing import Any

from backend.models.base import FluidElement


class Valve(FluidElement):
    """Controllable valve element for flow control.

    Implements an ideal valve with binary state (open/closed)
    and configurable response time.

    Attributes:
        input_flow: Input flow rate in m³/s.
        state: Valve state (True=open, False=closed).
        response_time: Switching response time in seconds [s].
    """

    OPEN_RESISTANCE: float = 1e3  # Minimal resistance when open
    CLOSED_RESISTANCE: float = 1e15  # Very high resistance when closed

    def __init__(
        self,
        element_id: str,
        name: str,
        input_flow: float = 0.0,
        state: bool = True,
        response_time: float = 1e-3,
        connections: list[str] | None = None,
    ) -> None:
        """Initialize a valve.

        Args:
            element_id: Unique identifier for the element.
            name: Human-readable name for the element.
            input_flow: Input flow rate in m³/s (default: 0.0).
            state: Valve state, True=open, False=closed (default: True).
            response_time: Switching response time in seconds (default: 1ms).
            connections: List of connected element IDs.

        Raises:
            ValueError: If any parameter is invalid.
        """
        super().__init__(element_id, name, connections)
        self.input_flow = input_flow
        self.state = state
        self.response_time = response_time
        self.validate_parameters()

    def validate_parameters(self) -> bool:
        """Validate valve parameters.

        Returns:
            True if all parameters are valid.

        Raises:
            ValueError: If any parameter is out of valid range.
        """
        if self.input_flow < 0:
            raise ValueError(f"Input flow cannot be negative, got {self.input_flow}")
        if self.response_time < 0:
            raise ValueError(
                f"Response time cannot be negative, got {self.response_time}"
            )
        return True

    def calculate_resistance(self) -> float:
        """Calculate hydraulic resistance based on valve state.

        Returns:
            High resistance if closed, minimal if open.
        """
        return self.OPEN_RESISTANCE if self.state else self.CLOSED_RESISTANCE

    def calculate_flow(self, pressure_drop: float = 0.0) -> float:
        """Calculate output flow rate based on state.

        Q_out = Q_in · f(state)
        f(state) = 1 if open, 0 if closed

        Args:
            pressure_drop: Pressure difference (not used for ideal valve).

        Returns:
            Output volumetric flow rate in m³/s.
        """
        return self.input_flow * self._state_function()

    def _state_function(self) -> float:
        """Get state transfer function value.

        Returns:
            1.0 if open, 0.0 if closed.
        """
        return 1.0 if self.state else 0.0

    def open(self) -> None:
        """Open the valve."""
        self.state = True

    def close(self) -> None:
        """Close the valve."""
        self.state = False

    def toggle(self) -> None:
        """Toggle valve state."""
        self.state = not self.state

    def set_input_flow(self, flow: float) -> None:
        """Set input flow rate.

        Args:
            flow: Input flow rate in m³/s.

        Raises:
            ValueError: If flow is negative.
        """
        if flow < 0:
            raise ValueError(f"Input flow cannot be negative, got {flow}")
        self.input_flow = flow

    def get_output_flow(self) -> float:
        """Get current output flow rate.

        Returns:
            Output flow rate in m³/s (0 if closed).
        """
        return self.calculate_flow()

    def to_dict(self) -> dict[str, Any]:
        """Serialize valve to dictionary.

        Returns:
            Dictionary representation including all parameters.
        """
        data = super().to_dict()
        data.update({
            "input_flow": self.input_flow,
            "state": self.state,
            "state_name": "open" if self.state else "closed",
            "response_time": self.response_time,
            "output_flow": self.get_output_flow(),
            "resistance": self.calculate_resistance(),
        })
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Valve":
        """Create Valve from dictionary.

        Args:
            data: Dictionary with valve parameters.

        Returns:
            New Valve instance.
        """
        return cls(
            element_id=data["element_id"],
            name=data["name"],
            input_flow=data.get("input_flow", 0.0),
            state=data.get("state", True),
            response_time=data.get("response_time", 1e-3),
            connections=data.get("connections"),
        )