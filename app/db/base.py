from app.db.session import Base
from app.documents.models import Document  # noqa: F401
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
    RadarEvaluation,
    RadarFeedback,
    RadarOpportunity,
    RadarRun,
    ScoreBreakdown,
    User,
)

__all__ = ["Base"]
