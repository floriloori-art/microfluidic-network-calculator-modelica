"""Physical constants for microfluidic simulations."""

import math

# Water properties at 20°C

WATER_VISCOSITY: float = 1.002e-3  # Pa·s (Dynamic viscosity)
WATER_DENSITY: float = 998.2  # kg/m³

# Standard constants

STANDARD_GRAVITY: float = 9.80665  # m/s²
PI: float = math.pi

# Microfluidic typical ranges

TYPICAL_CHANNEL_RADIUS_MIN: float = 10e-6  # 10 µm
TYPICAL_CHANNEL_RADIUS_MAX: float = 500e-6  # 500 µm
TYPICAL_CHANNEL_LENGTH_MIN: float = 1e-3  # 1 mm
TYPICAL_CHANNEL_LENGTH_MAX: float = 1e-1  # 10 cm

# Pressure ranges

TYPICAL_PRESSURE_MIN: float = 1e2  # 100 Pa
TYPICAL_PRESSURE_MAX: float = 1e5  # 100 kPa

# Reynolds number threshold for laminar flow

LAMINAR_RE_THRESHOLD: float = 2300.0

# Numerical constants

EPSILON: float = 1e-15  # Small number for numerical stability