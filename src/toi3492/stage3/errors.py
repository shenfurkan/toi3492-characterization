"""Stage-3 contract exceptions without import-cycle dependencies."""


class ContractError(RuntimeError):
    """Raised when a Stage-3 configuration or task violates its contract."""
