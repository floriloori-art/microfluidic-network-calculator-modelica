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
        nonlinear_iterations: int = 30,
        nonlinear_tolerance: float = 1e-6,
        nonlinear_relaxation: float = 0.5,
    ) -> None:
        """Initialize the network solver.

        Args:
            max_iterations: Maximum solver iterations for the linear system
                (default: 1000).
            tolerance: Convergence tolerance for the linear system
                (default: 1e-10).
            nonlinear_iterations: Maximum Picard iterations for networks
                containing flow-dependent (nonlinear) elements (default: 30).
            nonlinear_tolerance: Relative tolerance on effective resistance
                change between Picard iterations (default: 1e-6).
            nonlinear_relaxation: Under-relaxation factor α in
                ``Q_eff = α · Q_new + (1-α) · Q_prev`` used to damp Picard
                oscillations on strongly nonlinear elements (default: 0.5,
                valid range (0, 1]; 1.0 = no relaxation).
        """
        if not (0.0 < nonlinear_relaxation <= 1.0):
            raise ValueError(
                f"nonlinear_relaxation must be in (0, 1], got {nonlinear_relaxation}"
            )
        self.max_iterations = max_iterations
        self.tolerance = tolerance
        self.nonlinear_iterations = nonlinear_iterations
        self.nonlinear_tolerance = nonlinear_tolerance
        self.nonlinear_relaxation = nonlinear_relaxation
        logger.info(
            f"NetworkSolver initialized (max_iter={max_iterations}, tol={tolerance}, "
            f"nl_iter={nonlinear_iterations}, nl_tol={nonlinear_tolerance}, "
            f"nl_relax={nonlinear_relaxation})"
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

        # Get node list and build index
        nodes = list(network.elements.keys())
        n_nodes = len(nodes)
        node_index = {node: i for i, node in enumerate(nodes)}

        # Identify flow-dependent (nonlinear) elements (e.g. turbulent channels)
        nonlinear_elems: dict[str, Any] = {
            eid: elem
            for eid, elem in network.elements.items()
            if getattr(elem, "is_nonlinear", False)
        }
        has_nonlinear = bool(nonlinear_elems)

        # Collect boundary conditions (shared across iterations)
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
        for elem_id, element in network.elements.items():
            if isinstance(element, Pump):
                known_pressures[elem_id] = element.pressure_generated

        # ── Picard iteration loop for nonlinear elements ─────────────────
        # For purely linear networks this runs exactly once.
        max_nl_iter = self.nonlinear_iterations if has_nonlinear else 1
        alpha = self.nonlinear_relaxation  # under-relaxation factor
        prev_resistances: dict[str, float] = {}
        prev_element_q: dict[str, float] = {eid: 0.0 for eid in nonlinear_elems}
        pressures: dict[str, float] = {}
        flows: dict[tuple[str, str], float] = {}
        residual: float = 0.0
        converged_nl = True
        nl_iter = 0
        picard_messages: list[str] = []

        for nl_iter in range(max_nl_iter):
            # Build conductance matrix (G = 1/R) using current resistances
            G = np.zeros((n_nodes, n_nodes))
            for src, tgt in network.connections:
                i, j = node_index[src], node_index[tgt]
                elem_src = network.elements[src]
                elem_tgt = network.elements[tgt]

                r_src = elem_src.calculate_resistance()
                r_tgt = elem_tgt.calculate_resistance()
                conductance = 1.0 / (r_src + r_tgt)

                G[i, j] -= conductance
                G[j, i] -= conductance
                G[i, i] += conductance
                G[j, j] += conductance

            # Build source vector
            b = np.zeros(n_nodes)

            # Apply Dirichlet BCs
            for elem_id, pressure in known_pressures.items():
                i = node_index[elem_id]
                G[i, :] = 0
                G[i, i] = 1
                b[i] = pressure

            # Solve linear system
            try:
                pressures_array = linalg.solve(G, b)
                residual = float(np.linalg.norm(G @ pressures_array - b))
            except linalg.LinAlgError as e:
                logger.error(f"Solver failed: {e}")
                return SolverResult(
                    success=False,
                    messages=pre_solve_messages + [f"Linear algebra error: {e}"],
                )

            # Build pressure dictionary
            pressures = {nodes[i]: float(pressures_array[i]) for i in range(n_nodes)}

            # Calculate flows through each connection
            flows = {}
            for src, tgt in network.connections:
                dp = pressures[src] - pressures[tgt]
                elem_src = network.elements[src]
                elem_tgt = network.elements[tgt]
                r_total = elem_src.calculate_resistance() + elem_tgt.calculate_resistance()
                flows[(src, tgt)] = dp / r_total

            # If no nonlinear elements, single iteration is enough
            if not has_nonlinear:
                break

            # ── Update nonlinear elements with new flow estimates ──
            # Average the flows going into and out of each nonlinear element
            # to get a representative Q through the element.
            element_flows: dict[str, list[float]] = {eid: [] for eid in nonlinear_elems}
            for (src, tgt), q in flows.items():
                if src in element_flows:
                    element_flows[src].append(abs(q))
                if tgt in element_flows:
                    element_flows[tgt].append(abs(q))

            # Snapshot resistances before update for convergence check
            current_resistances = {
                eid: elem.calculate_resistance()
                for eid, elem in nonlinear_elems.items()
            }

            # Re-linearise each nonlinear element with under-relaxation on Q
            # to damp Picard oscillations: Q_eff = α·Q_new + (1-α)·Q_prev
            for eid, elem in nonlinear_elems.items():
                q_list = element_flows[eid]
                avg_q = sum(q_list) / len(q_list) if q_list else 0.0
                q_eff = alpha * avg_q + (1.0 - alpha) * prev_element_q[eid]
                elem.update_resistance(q_eff)
                prev_element_q[eid] = q_eff

            # Check convergence (relative change in resistances)
            if prev_resistances:
                max_rel_change = 0.0
                for eid, elem in nonlinear_elems.items():
                    r_new = elem.calculate_resistance()
                    r_prev = prev_resistances[eid]
                    if r_prev > 0:
                        rel = abs(r_new - r_prev) / r_prev
                        max_rel_change = max(max_rel_change, rel)
                if max_rel_change < self.nonlinear_tolerance:
                    converged_nl = True
                    picard_messages.append(
                        f"Picard converged after {nl_iter + 1} iteration(s) "
                        f"(max rel change: {max_rel_change:.2e})"
                    )
                    break
            prev_resistances = {
                eid: elem.calculate_resistance()
                for eid, elem in nonlinear_elems.items()
            }
        else:
            # for-else: executed only if loop exhausted without break
            if has_nonlinear:
                converged_nl = False
                picard_messages.append(
                    f"WARNING: Picard did not converge in {max_nl_iter} iterations"
                )

        success = converged_nl

        # Build detailed element results
        element_results = self._build_element_results(network, pressures, flows)

        # Add Reynolds number to element_results for nonlinear channels
        for eid, elem in nonlinear_elems.items():
            if eid in element_results:
                q_list = [abs(q) for (s, t), q in flows.items() if s == eid or t == eid]
                avg_q = sum(q_list) / len(q_list) if q_list else 0.0
                if hasattr(elem, "get_reynolds"):
                    element_results[eid]["reynolds"] = elem.get_reynolds(avg_q)

        # Verify mass conservation
        conservation_error = self._check_mass_conservation(network, flows)

        messages = (
            pre_solve_messages
            + picard_messages
            + [f"Solver converged with residual: {residual:.2e}"]
        )
        if conservation_error > self.tolerance:
            messages.append(
                f"WARNING: Mass conservation error: {conservation_error:.2e}"
            )

        logger.info(
            f"Solver completed: success={success}, residual={residual:.2e}, "
            f"nl_iterations={nl_iter + 1}"
        )

        return SolverResult(
            success=success,
            pressures=pressures,
            flows=flows,
            element_results=element_results,
            iterations=nl_iter + 1,
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