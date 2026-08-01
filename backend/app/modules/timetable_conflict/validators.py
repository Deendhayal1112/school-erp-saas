from app.exceptions.exceptions import BadRequestException


def validate_resolution_override(
    strategy: str,
    action_taken: str,
) -> None:
    """Validates parameters for manual conflict resolution overrides."""
    if not strategy or not action_taken:
        raise BadRequestException(message="Resolution strategy and details of action taken are required.")
