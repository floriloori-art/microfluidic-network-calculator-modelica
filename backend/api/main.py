"""FastAPI application for microfluidic simulation service."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router

# Configure logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting Microfluidic Simulation API")
    yield
    logger.info("Shutting down Microfluidic Simulation API")


app = FastAPI(
    title="Microfluidic Network Simulation API",
    description="""
    Backend API for simulating microfluidic networks using
    hydraulic circuit analogies.
    
    ## Features
    
    - Create and manage fluid networks
    - Add various element types (channels, chambers, pumps, valves)
    - Connect elements to form networks
    - Run flow simulations with boundary conditions
    - Retrieve pressure and flow distributions
    
    ## Physics Models
    
    - **Circular Channels**: Hagen-Poiseuille equation
    - **Rectangular Channels**: Modified Poiseuille with series correction
    - **Chambers**: Hydrostatic pressure model
    - **Pumps**: Pressure-driven flow sources
    - **Valves**: Binary flow control

    """,
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS for frontend access

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes

app.include_router(router)


@app.get("/", tags=["health"])
async def root() -> dict[str, str]:
    """Root endpoint with API info."""
    return {
        "name": "Microfluidic Simulation API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)