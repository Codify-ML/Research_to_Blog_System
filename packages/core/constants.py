from enum import StrEnum


class AgentStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


class LLMMode(StrEnum):
    MOCK = "mock"
    OPENAI = "openai"
