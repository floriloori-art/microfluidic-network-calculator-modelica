"""Pydantic models for API request/response validation."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ElementType(str, Enum):
    """Supported element types."""

    CIRCULAR_CHANNEL = "circular_channel"
    RECTANGULAR_CHANNEL = "rectangular_channel"
    CHAMBER = "chamber"
    PUMP = "pump"
    VALVE = "valve"


class ElementCreate(BaseModel):
    """Request model for creating a new element.

    Attributes:
        element_id: Unique identifier for the element.
        name: Human-readable name.
        element_type: Type of element to create.
        parameters: Type-specific parameters.
    """

    element_id: str = Field(..., min_length=1, description="Unique element identifier")
    name: str = Field(..., min_length=1, description="Element name")
    element_type: ElementType = Field(..., description="Type of element")
    parameters: dict[str, Any] = Field(..., description="Element parameters")

    model_config = {"json_schema_extra": {
        "examples": [
            {
                "element_id": "channel_1",
                "name": "Main Channel",
                "element_type": "circular_channel",
                "parameters": {
                    "radius": 100e-6,
                    "length": 0.01,
                    "viscosity": 1e-3,
                },
            }
        ]
    }}


class ConnectionCreate(BaseModel):
    """Request model for connecting two elements.

    Attributes:
        element_id_1: ID of first element.
        element_id_2: ID of second element.
    """

    element_id_1: str = Field(..., min_length=1)
    element_id_2: str = Field(..., min_length=1)

    @field_validator("element_id_2")
    @classmethod
    def elements_must_differ(cls, v: str, info) -> str:
        """Validate that elements are different."""
        if "element_id_1" in info.data and v == info.data["element_id_1"]:
            raise ValueError("Cannot connect element to itself")
        return v


class BoundaryCondition(BaseModel):
    """Boundary condition specification.

    Attributes:
        element_id: ID of element where BC applies.
        pressure: Fixed pressure in Pascal (optional).
        flow: Fixed flow rate in m³/s (optional).
    """

    element_id: str = Field(..., min_length=1)
    pressure: float | None = Field(None, description="Fixed pressure [Pa]")
    flow: float | None = Field(None, description="Fixed flow rate [m³/s]")

    @model_validator(mode="after")
    def at_least_one_required(self) -> "BoundaryCondition":
        """Validate that at least one BC type (pressure or flow) is specified."""
        if self.pressure is None and self.flow is None:
            raise ValueError(
                "At least one of 'pressure' or 'flow' must be specified in boundary condition"
            )
        return self


class SimulationRequest(BaseModel):
    """Request model for running a simulation.

    Attributes:
        boundary_conditions: List of boundary conditions.
    """

    boundary_conditions: list[BoundaryCondition] = Field(
        ..., min_length=1, description="Boundary conditions for simulation"
    )

    model_config = {"json_schema_extra": {
        "examples": [
            {
                "boundary_conditions": [
                    {"element_id": "inlet", "pressure": 1000},
                    {"element_id": "outlet", "pressure": 0},
                ]
            }
        ]
    }}


class ElementResponse(BaseModel):
    """Response model for element data.

    Attributes:
        element_id: Unique identifier.
        name: Element name.
        element_type: Type of element.
        parameters: Element parameters.
        resistance: Calculated hydraulic resistance.
        connections: Connected element IDs.
    """

    element_id: str
    name: str
    element_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    resistance: float
    connections: list[str]


class NetworkResponse(BaseModel):
    """Response model for network data.

    Attributes:
        network_id: Unique identifier.
        name: Network name.
        elements: Dictionary of elements.
        connections: List of connections.
        statistics: Network statistics.
    """

    network_id: str
    name: str
    elements: dict[str, ElementResponse]
    connections: list[tuple[str, str]]
    statistics: dict[str, Any]


class SimulationResultResponse(BaseModel):
    """Response model for simulation results.

    Attributes:
        success: Whether simulation succeeded.
        pressures: Pressure at each element [Pa].
        flows: Flow through each connection [m³/s].
        element_results: Detailed results per element.
        messages: Solver messages.
    """

    success: bool
    pressures: dict[str, float]
    flows: dict[str, float]  # Serialized as "elem1->elem2": flow
    element_results: dict[str, dict[str, Any]]
    messages: list[str]


class NetworkCreateRequest(BaseModel):
    """Request model for creating a new network.

    Attributes:
        name: Network name.
    """

    name: str = Field("", description="Network name")


class ErrorResponse(BaseModel):
    """Standard error response.

    Attributes:
        detail: Error message.
        error_code: Optional error code.
    """

    detail: str
    error_code: str | None = None