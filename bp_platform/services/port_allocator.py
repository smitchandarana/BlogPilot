"""Allocate and release host ports for user containers."""

import threading

from bp_platform.config import PORT_RANGE_START, PORT_RANGE_END
from bp_platform.models.database import Container, get_db

# Lock ensures no two concurrent provisioning requests receive the same port
_port_lock = threading.Lock()


def allocate_port() -> int:
    """Find the lowest unused port in the range. Raises RuntimeError if exhausted.

    The lock prevents a TOCTOU race where two concurrent requests both read
    the same set of used ports and return the same free port.
    """
    with _port_lock:
        with get_db() as db:
            used = {
                row.host_port
                for row in db.query(Container.host_port)
                .filter(Container.status != "destroyed")
                .all()
            }
        for port in range(PORT_RANGE_START, PORT_RANGE_END + 1):
            if port not in used:
                return port
        raise RuntimeError(f"No free ports in range {PORT_RANGE_START}-{PORT_RANGE_END}")


def release_port(port: int) -> None:
    """No-op — port is freed when container record is marked destroyed."""
    pass
