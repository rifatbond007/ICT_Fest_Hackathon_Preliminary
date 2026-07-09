"""Human-facing booking reference codes.

Codes are derived from the booking's own primary key so they are unique
across restarts and concurrent creation.
"""


def reference_code_for(booking_id: int) -> str:
    return f"CW-{booking_id:06d}"
