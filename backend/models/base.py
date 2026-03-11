"""Abstract base class for all fluid network elements."""

from abc import ABC, abstractmethod
from typing import Any


class FluidElement(ABC):
    """Abstract base class for all microfluidic network elements.

    Provides common interface for hydraulic resistance calculation,
    flow computation, and parameter validation.

    Attributes:
        element_id: Unique identifier for the element.
        name: Human-readable name for the element.
        connections: List of connected element IDs.
    """

    def __init__(
        self,
        element_id: str,
        name: str,
        connections: list[str] | None = None,
    ) -> None:
        """Initialize a fluid element.

        Args:
            element_id: Unique identifier for the element.
            name: Human-readable name for the element.
            connections: List of connected element IDs. Defaults to empty list.

        Raises:
            ValueError: If element_id or name is empty.
        """
        if not element_id or not element_id.strip():
            raise ValueError("element_id cannot be empty")
        if not name or not name.strip():
            raise ValueError("name cannot be empty")

        self.element_id = element_id
        self.name = name
        self.connections: list[str] = connections if connections is not None else []

    @abstractmethod
    def calculate_resistance(self) -> float:
        """Calculate hydraulic resistance of the element.

        Returns:
            Hydraulic resistance in Pa·s/m³.
        """
        pass

    @abstractmethod
    def calculate_flow(self, pressure_drop: float) -> float:
        """Calculate volumetric flow rate for a given pressure drop.

        Args:
            pressure_drop: Pressure difference across the element in Pascal [Pa].

        Returns:
            Volumetric flow rate in m³/s.

        Raises:
            ValueError: If pressure_drop is negative (for passive elements).
        """
        pass

    @abstractmethod
    def validate_parameters(self) -> bool:
        """Validate all element parameters.

        Returns:
            True if all parameters are valid.

        Raises:
            ValueError: If any parameter is invalid with detailed message.
        """
        pass

    def to_dict(self) -> dict[str, Any]:
        """Serialize element to dictionary.

        Returns:
            Dictionary representation of the element.
        """
        return {
            "element_id": self.element_id,
            "name": self.name,
            "element_type": self.__class__.__name__,
            "connections": self.connections.copy(),
        }

    def add_connection(self, element_id: str) -> None:
        """Add a connection to another element.

        Args:
            element_id: ID of the element to connect to.

        Raises:
            ValueError: If element_id is empty or already connected.
        """
        if not element_id or not element_id.strip():
            raise ValueError("element_id cannot be empty")
        if element_id in self.connections:
            raise ValueError(f"Already connected to element {element_id}")
        self.connections.append(element_id)

    def remove_connection(self, element_id: str) -> None:
        """Remove a connection to another element.

        Args:
            element_id: ID of the element to disconnect from.

        Raises:
            ValueError: If not connected to the specified element.
        """
        if element_id not in self.connections:
            raise ValueError(f"Not connected to element {element_id}")
        self.connections.remove(element_id)

    def __repr__(self) -> str:
        """Return string representation of the element."""
        return f"{self.__class__.__name__}(id='{self.element_id}', name='{self.name}')"