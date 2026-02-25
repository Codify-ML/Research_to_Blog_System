class QueueUnavailableError(RuntimeError):
    """Raised when the async queue is unavailable."""


class JobNotFoundError(KeyError):
    """Raised when a job_id does not exist in the job store."""


class SafetyUnavailableError(RuntimeError):
    """Raised when safety checks cannot complete in fail-closed mode."""


class RateLimitUnavailableError(RuntimeError):
    """Raised when rate-limit checks cannot complete in fail-closed mode."""
