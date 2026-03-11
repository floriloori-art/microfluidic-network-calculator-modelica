"""Fluid network management for microfluidic simulations."""

import logging
from typing import Any

import networkx as nx

from backend.models.base import FluidElement

logger = logging.getLogger(__name__)


class FluidNetwork:
    """Manages a network of connected fluid elements.

    Provides methods for adding elements, connecting them,
    and converting to graph representation for solving.

    Attributes:
        network_id: Unique identifier for the network.
        elements: Dictionary of elements by ID.
        connections: List of connection tuples (source_id, target_id).
    """

    def __init__(self, network_id: str, name: str = "") -> None:
        """Initialize an empty fluid network.

        Args:
            network_id: Unique identifier for the network.
            name: Optional descriptive name for the network.
        """
        self.network_id = network_id
        self.name = name
        self.elements: dict[str, FluidElement] = {}
        self.connections: list[tuple[str, str]] = []
        logger.info(f"Created new FluidNetwork: {network_id}")

    def add_element(self, element: FluidElement) -> None:
        """Add an element to the network.

        Args:
            element: FluidElement to add.

        Raises:
            ValueError: If element with same ID already exists.
        """
        if element.element_id in self.elements:
            raise ValueError(
                f"Element with ID '{element.element_id}' already exists in network"
            )
        self.elements[element.element_id] = element
        logger.debug(f"Added element: {element.element_id}")

    def remove_element(self, element_id: str) -> None:
        """Remove an element from the network.

        Also removes all connections involving this element.

        Args:
            element_id: ID of element to remove.

        Raises:
            KeyError: If element not found in network.
        """
        if element_id not in self.elements:
            raise KeyError(f"Element '{element_id}' not found in network")

        # Remove all connections involving this element
        self.connections = [
            (src, tgt) for src, tgt in self.connections
            if src != element_id and tgt != element_id
        ]

        # Remove element from other elements' connection lists
        for elem in self.elements.values():
            if element_id in elem.connections:
                elem.connections.remove(element_id)

        del self.elements[element_id]
        logger.debug(f"Removed element: {element_id}")

    def connect(self, elem_id_1: str, elem_id_2: str) -> None:
        """Connect two elements bidirectionally.

        Args:
            elem_id_1: ID of first element.
            elem_id_2: ID of second element.

        Raises:
            KeyError: If either element not found in network.
            ValueError: If elements are already connected or same element.
        """
        if elem_id_1 not in self.elements:
            raise KeyError(f"Element '{elem_id_1}' not found in network")
        if elem_id_2 not in self.elements:
            raise KeyError(f"Element '{elem_id_2}' not found in network")
        if elem_id_1 == elem_id_2:
            raise ValueError("Cannot connect element to itself")

        connection = (elem_id_1, elem_id_2)
        reverse_connection = (elem_id_2, elem_id_1)

        if connection in self.connections or reverse_connection in self.connections:
            raise ValueError(
                f"Elements '{elem_id_1}' and '{elem_id_2}' are already connected"
            )

        self.connections.append(connection)
        self.elements[elem_id_1].add_connection(elem_id_2)
        self.elements[elem_id_2].add_connection(elem_id_1)
        logger.debug(f"Connected: {elem_id_1} <-> {elem_id_2}")

    def disconnect(self, elem_id_1: str, elem_id_2: str) -> None:
        """Disconnect two elements.

        Args:
            elem_id_1: ID of first element.
            elem_id_2: ID of second element.

        Raises:
            ValueError: If elements are not connected.
        """
        connection = (elem_id_1, elem_id_2)
        reverse_connection = (elem_id_2, elem_id_1)

        if connection in self.connections:
            self.connections.remove(connection)
        elif reverse_connection in self.connections:
            self.connections.remove(reverse_connection)
        else:
            raise ValueError(
                f"Elements '{elem_id_1}' and '{elem_id_2}' are not connected"
            )

        self.elements[elem_id_1].remove_connection(elem_id_2)
        self.elements[elem_id_2].remove_connection(elem_id_1)
        logger.debug(f"Disconnected: {elem_id_1} <-> {elem_id_2}")

    def get_element(self, element_id: str) -> FluidElement:
        """Get element by ID.

        Args:
            element_id: ID of element to retrieve.

        Returns:
            The requested FluidElement.

        Raises:
            KeyError: If element not found.
        """
        if element_id not in self.elements:
            raise KeyError(f"Element '{element_id}' not found in network")
        return self.elements[element_id]

    def to_graph(self) -> nx.Graph:
        """Convert network to NetworkX graph.

        Creates an undirected graph where nodes are elements
        and edges are connections with resistance as weight.

        Returns:
            NetworkX Graph representation of the network.
        """
        graph = nx.Graph()

        # Add nodes with element properties
        for elem_id, element in self.elements.items():
            graph.add_node(
                elem_id,
                element=element,
                resistance=element.calculate_resistance(),
                element_type=element.__class__.__name__,
            )

        # Add edges with resistance as weight
        for src, tgt in self.connections:
            # Average resistance of connected elements
            r1 = self.elements[src].calculate_resistance()
            r2 = self.elements[tgt].calculate_resistance()
            avg_resistance = (r1 + r2) / 2

            graph.add_edge(src, tgt, resistance=avg_resistance)

        return graph

    def to_directed_graph(self) -> nx.DiGraph:
        """Convert network to directed NetworkX graph.

        Creates a directed graph for flow analysis.

        Returns:
            NetworkX DiGraph representation of the network.
        """
        digraph = nx.DiGraph()

        for elem_id, element in self.elements.items():
            digraph.add_node(
                elem_id,
                element=element,
                resistance=element.calculate_resistance(),
            )

        # Add edges in both directions
        for src, tgt in self.connections:
            r1 = self.elements[src].calculate_resistance()
            r2 = self.elements[tgt].calculate_resistance()
            digraph.add_edge(src, tgt, resistance=r1)
            digraph.add_edge(tgt, src, resistance=r2)

        return digraph

    def validate_network(self) -> tuple[bool, list[str]]:
        """Validate network structure.

        Checks for:
        - Isolated nodes (no connections)
        - Cycles (warning only)
        - Minimum elements

        Returns:
            Tuple of (is_valid, list of warning/error messages).
        """
        messages: list[str] = []
        is_valid = True

        # Check minimum elements
        if len(self.elements) < 2:
            messages.append("ERROR: Network must have at least 2 elements")
            is_valid = False

        # Check for isolated nodes
        graph = self.to_graph()
        isolated = list(nx.isolates(graph))
        if isolated:
            messages.append(f"WARNING: Isolated elements found: {isolated}")

        # Check connectivity
        if len(self.elements) >= 2:
            if not nx.is_connected(graph):
                components = list(nx.connected_components(graph))
                messages.append(
                    f"WARNING: Network has {len(components)} disconnected components"
                )

        # Check for cycles (informational)
        try:
            cycles = nx.cycle_basis(graph)
            if cycles:
                messages.append(f"INFO: Network contains {len(cycles)} cycle(s)")
        except nx.NetworkXError:
            pass

        return is_valid, messages

    def get_statistics(self) -> dict[str, Any]:
        """Get network statistics.

        Returns:
            Dictionary with network statistics.
        """
        graph = self.to_graph()
        element_types: dict[str, int] = {}
        for elem in self.elements.values():
            type_name = elem.__class__.__name__
            element_types[type_name] = element_types.get(type_name, 0) + 1

        return {
            "network_id": self.network_id,
            "name": self.name,
            "num_elements": len(self.elements),
            "num_connections": len(self.connections),
            "element_types": element_types,
            "is_connected": nx.is_connected(graph) if self.elements else False,
            "num_components": nx.number_connected_components(graph) if self.elements else 0,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize network to dictionary.

        Returns:
            Dictionary representation of the network.
        """
        return {
            "network_id": self.network_id,
            "name": self.name,
            "elements": {
                elem_id: elem.to_dict()
                for elem_id, elem in self.elements.items()
            },
            "connections": self.connections,
            "statistics": self.get_statistics(),
        }

    def __len__(self) -> int:
        """Return number of elements in network."""
        return len(self.elements)

    def __contains__(self, element_id: str) -> bool:
        """Check if element ID exists in network."""
        return element_id in self.elements

    def __repr__(self) -> str:
        """Return string representation of network."""
        return (
            f"FluidNetwork(id='{self.network_id}', "
            f"elements={len(self.elements)}, "
            f"connections={len(self.connections)})"
        )