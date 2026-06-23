from app.db.session import Base
from app.models import (  # noqa: F401
    AppConfig,
    CandidateCV,
    CandidateProfile,
    Company,
    DetectedSignal,
    HumanDecision,
    JobAnalysis,
    JobLead,
    JobSource,
    ScoreBreakdown,
    User,
)

__all__ = ["Base"]
