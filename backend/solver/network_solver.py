"""Network solver for microfluidic flow simulations.

Uses Kirchhoff's circuit analogy:
- Mass conservation at nodes: Σ Q_in = Σ Q_out
- Pressure-flow relationship: ΔP = Q · R

"""

import logging
from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import numpy as np
from scipy import linalg

from backend.models.network import FluidNetwork
from backend.models.pump import Pump

logger = logging.getLogger(__name__)


@dataclass
class SolverResult:
    """Result container for network solver.

    Attributes:
        success: Whether the solver converged successfully.
        pressures: Dictionary mapping element IDs to pressure values.
        flows: Dictionary mapping connection tuples to flow rates.
        element_results: Detailed results per element.
        iterations: Number of solver iterations.
        residual: Final residual error.
        messages: Solver messages and warnings.
    """

    success: bool
    pressures: dict[str, float] = field(default_factory=dict)
    flows: dict[tuple[str, str], float] = field(default_factory=dict)
    element_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    iterations: int = 0
    residual: float = 0.0
    messages: list[str] = field(default_factory=list)


class NetworkSolver:
    """Solves for pressure and flow distribution in fluid networks.

    Uses the hydraulic-electrical analogy:
    - Pressure ↔ Voltage
    - Flow rate ↔ Current
    - Hydraulic resistance ↔ Electrical resistance

    Applies Kirchhoff's laws:
    1. Node law: Sum of flows at each node = 0 (mass conservation)
    2. Loop law: Sum of pressure drops around any loop = 0

    """

    def __init__(
        self,
        max_iterations: int = 1000,
        tolerance: float = 1e-10,
    ) -> None:
        """Initialize the network solver.

        Args:
            max_iterations: Maximum solver iterations (default: 1000).
            tolerance: Convergence tolerance (default: 1e-10).
        """
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        logger.info(
            f"NetworkSolver initialized (max_iter={max_iterations}, tol={tolerance})"
        )

    def solve(
        self,
        network: FluidNetwork,
        boundary_conditions: dict[str, dict[str, float]],
    ) -> SolverResult:
        """Solve for pressure and flow distribution in the network.

        Args:
            network: FluidNetwork to solve.
            boundary_conditions: Boundary conditions specifying known
                pressures or flows at specific nodes.
                Format: {element_id: {"pressure": value} or {"flow": value}}

        Returns:
            SolverResult containing pressures and flows for all elements.

        Example:
            >>> solver = NetworkSolver()
            >>> bc = {
            ...     "inlet": {"pressure": 1000},  # 1000 Pa at inlet
            ...     "outlet": {"pressure": 0},    # 0 Pa at outlet
            ... }
            >>> result = solver.solve(network, bc)
        """
        logger.info(f"Starting solver for network: {network.network_id}")

        # Validate network and boundary conditions
        validation_result = self._validate_inputs(network, boundary_conditions)
        if not validation_result.success:
            return validation_result
        # Carry over any validation warnings (INFO/WARNING messages)
        pre_solve_messages: list[str] = validation_result.messages

        # Get node list and build matrices
        nodes = list(network.elements.keys())
        n_nodes = len(nodes)
        node_index = {node: i for i, node in enumerate(nodes)}

        # Build conductance matrix (G = 1/R)
        G = np.zeros((n_nodes, n_nodes))
        for src, tgt in network.connections:
            i, j = node_index[src], node_index[tgt]
            elem_src = network.elements[src]
            elem_tgt = network.elements[tgt]

            # Conductance for series connection: G = 1 / (R_src + R_tgt)
            r_src = elem_src.calculate_resistance()
            r_tgt = elem_tgt.calculate_resistance()
            conductance = 1.0 / (r_src + r_tgt)

            G[i, j] -= conductance
            G[j, i] -= conductance
            G[i, i] += conductance
            G[j, j] += conductance

        # Build source vector (for pressure sources like pumps)
        b = np.zeros(n_nodes)

        # Apply boundary conditions
        known_pressures: dict[str, float] = {}
        known_flows: dict[str, float] = {}

        for elem_id, bc in boundary_conditions.items():
            if elem_id not in node_index:
                logger.warning(f"Boundary condition element '{elem_id}' not in network")
                continue

            if "pressure" in bc:
                known_pressures[elem_id] = bc["pressure"]
            if "flow" in bc:
                known_flows[elem_id] = bc["flow"]

        # Handle pumps as pressure sources (Dirichlet BC at pump node)
        # A pump maintains its generated pressure at its outlet node.
        for elem_id, element in network.elements.items():
            if isinstance(element, Pump):
                known_pressures[elem_id] = element.pressure_generated

        # Modify system for known pressures (Dirichlet BCs)
        for elem_id, pressure in known_pressures.items():
            i = node_index[elem_id]
            # Zero out row and set diagonal to 1
            G[i, :] = 0
            G[i, i] = 1
            b[i] = pressure

        # Solve linear system
        try:
            pressures_array = linalg.solve(G, b)
            success = True
            residual = float(np.linalg.norm(G @ pressures_array - b))
        except linalg.LinAlgError as e:
            logger.error(f"Solver failed: {e}")
            return SolverResult(
                success=False,
                messages=[f"Linear algebra error: {e}"],
            )

        # Build pressure dictionary
        pressures = {nodes[i]: float(pressures_array[i]) for i in range(n_nodes)}

        # Calculate flows through each connection
        flows: dict[tuple[str, str], float] = {}
        for src, tgt in network.connections:
            i, j = node_index[src], node_index[tgt]
            dp = pressures[src] - pressures[tgt]

            elem_src = network.elements[src]
            elem_tgt = network.elements[tgt]
            r_total = elem_src.calculate_resistance() + elem_tgt.calculate_resistance()

            flow = dp / r_total
            flows[(src, tgt)] = flow

        # Build detailed element results
        element_results = self._build_element_results(network, pressures, flows)

        # Verify mass conservation
        conservation_error = self._check_mass_conservation(network, flows)

        messages = pre_solve_messages + [f"Solver converged with residual: {residual:.2e}"]
        if conservation_error > self.tolerance:
            messages.append(
                f"WARNING: Mass conservation error: {conservation_error:.2e}"
            )

        logger.info(f"Solver completed: success={success}, residual={residual:.2e}")

        return SolverResult(
            success=success,
            pressures=pressures,
            flows=flows,
            element_results=element_results,
            iterations=1,  # Direct solver
            residual=residual,
            messages=messages,
        )

    def _validate_inputs(
        self,
        network: FluidNetwork,
        boundary_conditions: dict[str, dict[str, float]],
    ) -> SolverResult:
        """Validate solver inputs.

        Args:
            network: Network to validate.
            boundary_conditions: Boundary conditions to validate.

        Returns:
            SolverResult with success=False if validation fails.
        """
        messages: list[str] = []

        # Check network has elements
        if len(network.elements) < 2:
            return SolverResult(
                success=False,
                messages=["Network must have at least 2 elements"],
            )

        # Check network has connections
        if len(network.connections) < 1:
            return SolverResult(
                success=False,
                messages=["Network must have at least 1 connection"],
            )

        # Check boundary conditions exist
        if not boundary_conditions:
            return SolverResult(
                success=False,
                messages=["At least one boundary condition required"],
            )

        # Check for at least one pressure BC (needed for unique solution)
        has_pressure_bc = any(
            "pressure" in bc for bc in boundary_conditions.values()
        )
        # Pumps also provide a pressure reference
        has_pump = any(
            isinstance(elem, Pump) for elem in network.elements.values()
        )
        if not has_pressure_bc and not has_pump:
            return SolverResult(
                success=False,
                messages=["At least one pressure boundary condition required"],
            )

        # Check network connectivity using NetworkX
        graph = network.to_graph()
        if len(network.elements) >= 2 and not nx.is_connected(graph):
            components = list(nx.connected_components(graph))
            return SolverResult(
                success=False,
                messages=[
                    f"Network has {len(components)} disconnected components. "
                    "All elements must be connected before solving."
                ],
            )

        # Run structural validation and collect warnings
        _, validation_messages = network.validate_network()
        for msg in validation_messages:
            if msg.startswith("ERROR"):
                return SolverResult(success=False, messages=[msg])
            else:
                messages.append(msg)

        return SolverResult(success=True, messages=messages)

    def _build_element_results(
        self,
        network: FluidNetwork,
        pressures: dict[str, float],
        flows: dict[tuple[str, str], float],
    ) -> dict[str, dict[str, Any]]:
        """Build detailed results for each element.

        Args:
            network: The fluid network.
            pressures: Calculated pressure at each node.
            flows: Calculated flow through each connection.

        Returns:
            Dictionary mapping element IDs to detailed results.
        """
        results: dict[str, dict[str, Any]] = {}

        for elem_id, element in network.elements.items():
            # Calculate net flow through element
            inflow = sum(
                abs(flow) for (src, tgt), flow in flows.items()
                if tgt == elem_id and flow > 0
            )
            outflow = sum(
                abs(flow) for (src, tgt), flow in flows.items()
                if src == elem_id and flow > 0
            )

            results[elem_id] = {
                "element_type": element.__class__.__name__,
                "pressure": pressures.get(elem_id, 0.0),
                "inflow": inflow,
                "outflow": outflow,
                "net_flow": inflow - outflow,
                "resistance": element.calculate_resistance(),
            }

        return results

    def _check_mass_conservation(
        self,
        network: FluidNetwork,
        flows: dict[tuple[str, str], float],
    ) -> float:
        """Check mass conservation at all nodes.

        Args:
            network: The fluid network.
            flows: Calculated flows through connections.

        Returns:
            Maximum absolute imbalance at any node.
        """
        max_imbalance = 0.0

        for elem_id in network.elements:
            # Sum incoming and outgoing flows
            balance = 0.0

            for (src, tgt), flow in flows.items():
                if tgt == elem_id:
                    balance += flow
                if src == elem_id:
                    balance -= flow

            # Pumps generate flow
            element = network.elements[elem_id]
            if isinstance(element, Pump):
                balance += element.get_nominal_flow()

            max_imbalance = max(max_imbalance, abs(balance))

        return max_imbalance