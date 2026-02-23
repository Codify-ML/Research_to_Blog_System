from pydantic import BaseModel, Field, model_validator


class EditorDecision(BaseModel):
    is_approved: bool
    feedback: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_feedback_for_rejection(self) -> "EditorDecision":
        if not self.is_approved and not self.feedback:
            raise ValueError("feedback is required when is_approved is False")
        return self
