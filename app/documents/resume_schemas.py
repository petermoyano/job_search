from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


OptionalText = Annotated[str | None, Field(default=None, max_length=2000)]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResumeClassificationV1(StrictSchema):
    is_resume: bool
    confidence: float = Field(ge=0.0, le=1.0)
    document_language: str = Field(min_length=2, max_length=16)
    reason: str = Field(min_length=1, max_length=240)


class ResumeSkillV1(StrictSchema):
    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    confidence: float = Field(ge=0.0, le=1.0)


class ResumeExperienceV1(StrictSchema):
    company: OptionalText
    title: OptionalText
    location: OptionalText
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool
    description: OptionalText
    source_pages: list[int] = Field(default_factory=list)

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        return _validate_partial_date(value)

    @field_validator("source_pages")
    @classmethod
    def validate_pages(cls, value: list[int]) -> list[int]:
        if any(page < 1 for page in value):
            raise ValueError("source page numbers must be positive")
        return value


class ResumeEducationV1(StrictSchema):
    institution: OptionalText
    degree: OptionalText
    field_of_study: OptionalText
    start_date: str | None = None
    end_date: str | None = None
    source_pages: list[int] = Field(default_factory=list)

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        return _validate_partial_date(value)

    @field_validator("source_pages")
    @classmethod
    def validate_pages(cls, value: list[int]) -> list[int]:
        if any(page < 1 for page in value):
            raise ValueError("source page numbers must be positive")
        return value


class ResumeLanguageV1(StrictSchema):
    language: str = Field(min_length=1, max_length=100)
    level: str | None = Field(default=None, max_length=100)
    raw_level: str | None = Field(default=None, max_length=200)


class ResumeCertificationV1(StrictSchema):
    name: str = Field(min_length=1, max_length=300)
    issuer: str | None = Field(default=None, max_length=300)
    date: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        return _validate_partial_date(value)


class ResumeProfileDraftV1(StrictSchema):
    full_name: OptionalText
    headline: OptionalText
    professional_summary: OptionalText
    location: OptionalText
    email: OptionalText
    phone: OptionalText
    linkedin_url: OptionalText
    github_url: OptionalText
    skills: list[ResumeSkillV1] = Field(default_factory=list, max_length=40)
    experience: list[ResumeExperienceV1] = Field(default_factory=list, max_length=25)
    education: list[ResumeEducationV1] = Field(default_factory=list, max_length=15)
    languages: list[ResumeLanguageV1] = Field(default_factory=list, max_length=20)
    certifications: list[ResumeCertificationV1] = Field(
        default_factory=list,
        max_length=20,
    )


def _validate_partial_date(value: str | None) -> str | None:
    if value is None:
        return None
    parts = value.split("-")
    if len(parts) not in {1, 2} or len(parts[0]) != 4 or not parts[0].isdigit():
        raise ValueError("date must use YYYY or YYYY-MM")
    if len(parts) == 2:
        if len(parts[1]) != 2 or not parts[1].isdigit():
            raise ValueError("date must use YYYY or YYYY-MM")
        month = int(parts[1])
        if month < 1 or month > 12:
            raise ValueError("month must be between 01 and 12")
    return value
