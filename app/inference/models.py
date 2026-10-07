"""
Purpose:
    Defines the data exchanged between prompt assembly and local model inference.

Place in the system:
    These models form the inference boundary and keep provider-specific HTTP
    details out of the rest of the application.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InferenceRequest:
    """Provider-independent request passed to the local model client."""

    system_prompt: str
    user_prompt: str


class InferenceError(RuntimeError):
    """Raised when the local inference service cannot complete a request."""