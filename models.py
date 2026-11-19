"""Data models for reverse-engineered user stories and business rules.

Design rule: a business rule without evidence is rejected. Every rule must point
to the files and line ranges that support it, so the output can be verified.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class Evidence(BaseModel):
    """Where in the repository a rule was found."""

    file: str = Field(min_length=1, description="Path relative to the repository root, using forward slashes.")
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)

    @model_validator(mode="after")
    def _check_range(self) -> "Evidence":
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line")
        return self


class BusinessRule(BaseModel):
    """One atomic business rule and the code that proves it."""

    statement: str = Field(min_length=5)
    evidence: list[Evidence] = Field(min_length=1)


class UserStory(BaseModel):
    """A user story in the form: As <actor>, I want <goal> so that <benefit>."""

    actor: str = Field(min_length=2, description='Includes the article, for example "a registered customer".')
    goal: str = Field(min_length=2)
    benefit: str = Field(min_length=2)

    def as_text(self) -> str:
        return f"As {self.actor}, I want {self.goal} so that {self.benefit}."


class Feature(BaseModel):
    """A functional feature: its user story, its rules and the open questions."""

    name: str = Field(min_length=2)
    module: str = Field(min_length=1)
    user_story: UserStory
    rules: list[BusinessRule] = Field(min_length=1)
    open_questions: list[str] = Field(default_factory=list)

    def acceptance_criteria(self) -> list[str]:
        return [rule.statement for rule in self.rules]

    def to_generator_payload(self) -> dict:
        """Request body for the AI Test Case Generator (title, user_story, acceptance_criteria)."""
        return {
            "title": self.name,
            "user_story": self.user_story.as_text(),
            "acceptance_criteria": self.acceptance_criteria(),
        }
