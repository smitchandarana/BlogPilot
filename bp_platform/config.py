"""Platform configuration — all from environment variables."""

import os


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://blogpilot:changeme@localhost:5432/blogpilot_platform",
)

JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60 * 4  # 4 hours (short-lived; use refresh endpoint)

# Fail fast if secrets not configured in production
_IS_PRODUCTION = os.environ.get("BLOGPILOT_ENV") == "production"
if _IS_PRODUCTION and not JWT_SECRET:
    raise RuntimeError("FATAL: JWT_SECRET must be set in production")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

BLOGPILOT_IMAGE = os.environ.get("BLOGPILOT_IMAGE", "blogpilot-backend:latest")
VOLUME_BASE_PATH = os.environ.get("VOLUME_BASE_PATH", "./docker/volumes/users")
DOCKER_NETWORK = "blogpilot-net"

PORT_RANGE_START = int(os.environ.get("PORT_RANGE_START", "10000"))
PORT_RANGE_END = int(os.environ.get("PORT_RANGE_END", "10099"))

# Container resource limits
CONTAINER_MEMORY_LIMIT = os.environ.get("CONTAINER_MEMORY_LIMIT", "2g")
CONTAINER_CPU_LIMIT = float(os.environ.get("CONTAINER_CPU_LIMIT", "1.0"))

# Health monitoring
HEALTH_CHECK_INTERVAL_SECONDS = 30
HEALTH_CHECK_MAX_FAILURES = 3
HEALTH_CHECK_MAX_RESTARTS = 3

# Idle container auto-stop (seconds)
IDLE_TIMEOUT_SECONDS = int(os.environ.get("IDLE_TIMEOUT_SECONDS", "7200"))  # 2 hours

# Admin bootstrap
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@phoenixsolution.in")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
if _IS_PRODUCTION and not ADMIN_PASSWORD:
    raise RuntimeError("FATAL: ADMIN_PASSWORD must be set in production")

# Config templates
ADMIN_SETTINGS_TEMPLATE = os.environ.get(
    "ADMIN_SETTINGS_TEMPLATE",
    os.path.join(os.path.dirname(__file__), "..", "docker", "config-templates", "admin-settings.yaml"),
)
DEFAULT_SETTINGS_TEMPLATE = os.environ.get(
    "DEFAULT_SETTINGS_TEMPLATE",
    os.path.join(os.path.dirname(__file__), "..", "docker", "config-templates", "default-settings.yaml"),
)

# Signup approval mode — when True, new signups are set to pending and require admin approval
REQUIRE_SIGNUP_APPROVAL = os.environ.get("REQUIRE_SIGNUP_APPROVAL", "false").lower() == "true"
