class QueueUnavailableError(RuntimeError):
    """Raised when the async queue is unavailable."""


class JobNotFoundError(KeyError):
    """Raised when a job_id does not exist in the job store."""
