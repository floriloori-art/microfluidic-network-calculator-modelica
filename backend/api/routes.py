"""API routes for microfluidic simulation service."""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.api.models import (
    BoundaryCondition,
    ConnectionCreate,
    ElementCreate,
    ElementResponse,
    ElementType,
    ErrorResponse,
    NetworkCreateRequest,
    NetworkResponse,
    SimulationRequest,
    SimulationResultResponse,
)
from backend.models.chamber import Chamber
from backend.models.channel import CircularChannel, RectangularChannel
from backend.models.network import FluidNetwork
from backend.models.pump import Pump
from backend.models.valve import Valve
from backend.solver.network_solver import NetworkSolver, SolverResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/network", tags=["network"])

# In-memory storage for networks (replace with database in production)

networks: dict[str, FluidNetwork] = {}
simulation_results: dict[str, SolverResult] = {}


def _create_element(data: ElementCreate) -> Any:
    """Factory function to create element from request data.

    Raises:
        ValueError: If a required parameter is missing or invalid.
    """
    params = data.parameters

    try:
        if data.element_type == ElementType.CIRCULAR_CHANNEL:
            return CircularChannel(
                element_id=data.element_id,
                name=data.name,
                radius=params["radius"],
                length=params["length"],
                viscosity=params["viscosity"],
            )
        elif data.element_type == ElementType.RECTANGULAR_CHANNEL:
            return RectangularChannel(
                element_id=data.element_id,
                name=data.name,
                width=params["width"],
                height=params["height"],
                length=params["length"],
                viscosity=params["viscosity"],
                n_terms=params.get("n_terms", 5),
            )
        elif data.element_type == ElementType.CHAMBER:
            return Chamber(
                element_id=data.element_id,
                name=data.name,
                height=params["height"],
                density=params["density"],
                gravity=params.get("gravity", 9.81),
            )
        elif data.element_type == ElementType.PUMP:
            return Pump(
                element_id=data.element_id,
                name=data.name,
                pressure_generated=params["pressure_generated"],
                flow_max=params.get("flow_max"),
                resistance=params.get("resistance", 1e10),
                area=params.get("area"),
                velocity=params.get("velocity"),
            )
        elif data.element_type == ElementType.VALVE:
            return Valve(
                element_id=data.element_id,
                name=data.name,
                kv=params.get("kv"),
                opening=params.get("opening", 1.0),
                state=params.get("state"),
                input_flow=params.get("input_flow", 0.0),
                response_time=params.get("response_time", 1e-3),
            )
        else:
            raise ValueError(f"Unknown element type: {data.element_type}")
    except KeyError as e:
        raise ValueError(
            f"Missing required parameter {e} for element type '{data.element_type}'"
        )


def _element_to_response(element) -> ElementResponse:
    """Convert element to response model."""
    data = element.to_dict()
    return ElementResponse(
        element_id=data["element_id"],
        name=data["name"],
        element_type=data["element_type"],
        parameters={k: v for k, v in data.items()
                    if k not in ["element_id", "name", "element_type", "connections"]},
        resistance=element.calculate_resistance(),
        connections=data["connections"],
    )


@router.post(
    "/create",
    response_model=NetworkResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}},
)
async def create_network(request: NetworkCreateRequest) -> NetworkResponse:
    """Create a new fluid network.

    Args:
        request: Network creation request with optional name.

    Returns:
        Created network data.
    """
    network_id = str(uuid.uuid4())
    network = FluidNetwork(network_id=network_id, name=request.name)
    networks[network_id] = network

    logger.info(f"Created network: {network_id}")

    return NetworkResponse(
        network_id=network_id,
        name=network.name,
        elements={},
        connections=[],
        statistics=network.get_statistics(),
    )


@router.get(
    "/{network_id}",
    response_model=NetworkResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_network(network_id: str) -> NetworkResponse:
    """Get network by ID.

    Args:
        network_id: Unique network identifier.

    Returns:
        Network data.

    Raises:
        HTTPException: If network not found.
    """
    if network_id not in networks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network '{network_id}' not found",
        )

    network = networks[network_id]
    elements = {
        elem_id: _element_to_response(elem)
        for elem_id, elem in network.elements.items()
    }

    return NetworkResponse(
        network_id=network.network_id,
        name=network.name,
        elements=elements,
        connections=network.connections,
        statistics=network.get_statistics(),
    )


@router.delete(
    "/{network_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def delete_network(network_id: str) -> None:
    """Delete a network.

    Args:
        network_id: Network to delete.

    Raises:
        HTTPException: If network not found.
    """
    if network_id not in networks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network '{network_id}' not found",
        )

    del networks[network_id]
    simulation_results.pop(network_id, None)
    logger.info(f"Deleted network: {network_id}")


@router.post(
    "/{network_id}/element",
    response_model=ElementResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def add_element(network_id: str, element: ElementCreate) -> ElementResponse:
    """Add an element to the network.

    Args:
        network_id: Target network ID.
        element: Element creation data.

    Returns:
        Created element data.

    Raises:
        HTTPException: If network not found or element invalid.
    """
    if network_id not in networks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network '{network_id}' not found",
        )

    network = networks[network_id]

    try:
        new_element = _create_element(element)
        network.add_element(new_element)
        logger.info(f"Added element '{element.element_id}' to network '{network_id}'")
        return _element_to_response(new_element)

    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{network_id}/element/{element_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
async def remove_element(network_id: str, element_id: str) -> None:
    """Remove an element from the network.

    Args:
        network_id: Network ID.
        element_id: Element to remove.

    Raises:
        HTTPException: If network or element not found.
    """
    if network_id not in networks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network '{network_id}' not found",
        )

    network = networks[network_id]

    try:
        network.remove_element(element_id)
        logger.info(f"Removed element '{element_id}' from network '{network_id}'")
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Element '{element_id}' not found in network",
        )


@router.post(
    "/{network_id}/connect",
    status_code=status.HTTP_201_CREATED,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def connect_elements(
    network_id: str, connection: ConnectionCreate
) -> dict[str, str]:
    """Connect two elements in the network.

    Args:
        network_id: Network ID.
        connection: Connection specification.

    Returns:
        Confirmation message.

    Raises:
        HTTPException: If connection invalid.
    """
    if network_id not in networks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network '{network_id}' not found",
        )

    network = networks[network_id]

    try:
        network.connect(connection.element_id_1, connection.element_id_2)
        logger.info(
            f"Connected '{connection.element_id_1}' <-> "
            f"'{connection.element_id_2}' in network '{network_id}'"
        )
        return {
            "message": f"Connected {connection.element_id_1} to {connection.element_id_2}"
        }

    except KeyError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except ValueError as e:
        if "already connected" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{network_id}/simulate",
    response_model=SimulationResultResponse,
    responses={
        404: {"model": ErrorResponse},
        400: {"model": ErrorResponse},
    },
)
async def run_simulation(
    network_id: str, request: SimulationRequest
) -> SimulationResultResponse:
    """Run flow simulation on the network.

    Args:
        network_id: Network to simulate.
        request: Simulation parameters including boundary conditions.

    Returns:
        Simulation results with pressures and flows.

    Raises:
        HTTPException: If simulation fails.
    """
    if network_id not in networks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network '{network_id}' not found",
        )

    network = networks[network_id]

    # Convert boundary conditions to solver format
    bc_dict: dict[str, dict[str, float]] = {}
    for bc in request.boundary_conditions:
        bc_dict[bc.element_id] = {}
        if bc.pressure is not None:
            bc_dict[bc.element_id]["pressure"] = bc.pressure
        if bc.flow is not None:
            bc_dict[bc.element_id]["flow"] = bc.flow

    # Run solver
    solver = NetworkSolver()
    result = solver.solve(network, bc_dict)

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Simulation failed: {', '.join(result.messages)}",
        )

    # Store result
    simulation_results[network_id] = result

    # Serialize flows (tuple keys to string)
    flows_serialized = {
        f"{src}->{tgt}": flow for (src, tgt), flow in result.flows.items()
    }

    logger.info(f"Simulation completed for network '{network_id}'")

    return SimulationResultResponse(
        success=result.success,
        pressures=result.pressures,
        flows=flows_serialized,
        element_results=result.element_results,
        messages=result.messages,
    )


@router.get(
    "/{network_id}/results",
    response_model=SimulationResultResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_results(network_id: str) -> SimulationResultResponse:
    """Get last simulation results for a network.

    Args:
        network_id: Network ID.

    Returns:
        Last simulation results.

    Raises:
        HTTPException: If no results available.
    """
    if network_id not in networks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network '{network_id}' not found",
        )

    if network_id not in simulation_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No simulation results for network '{network_id}'",
        )

    result = simulation_results[network_id]

    flows_serialized = {
        f"{src}->{tgt}": flow for (src, tgt), flow in result.flows.items()
    }

    return SimulationResultResponse(
        success=result.success,
        pressures=result.pressures,
        flows=flows_serialized,
        element_results=result.element_results,
        messages=result.messages,
    )


@router.get("/", response_model=list[NetworkResponse])
async def list_networks() -> list[NetworkResponse]:
    """List all networks.

    Returns:
        List of all networks.
    """
    return [
        NetworkResponse(
            network_id=network.network_id,
            name=network.name,
            elements={
                elem_id: _element_to_response(elem)
                for elem_id, elem in network.elements.items()
            },
            connections=network.connections,
            statistics=network.get_statistics(),
        )
        for network in networks.values()
    ]