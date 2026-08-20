from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit

from app.radar.models import (
    EligibilityCheck,
    EligibilityStatus,
    JobActivityStatus,
    NormalizedJobCandidate,
    RadarJobFacts,
    SearchProfile,
    WorkModality,
)
from app.services.text import normalize_for_matching


REMOTE_STRONG_TERMS = [
    "100% remoto",
    "100 % remoto",
    "remoto 100%",
    "remoto 100 %",
    "trabajo remoto",
    "modalidad remota",
    "posición remota",
    "posicion remota",
    "teletrabajo",
    "fully remote",
    "remote position",
    "work from home",
]
REMOTE_TERMS = [*REMOTE_STRONG_TERMS, "remoto", "remota", "remote", "home office"]
HYBRID_TERMS = [
    "híbrido",
    "híbrida",
    "hibrido",
    "hibrida",
    "hybrid",
    "presencial y remoto",
    "remoto y presencial",
]
ONSITE_TERMS = [
    "presencial",
    "on-site",
    "onsite",
    "trabajo en oficina",
    "modalidad presencial",
]
SPANISH_APPLY_TERMS = [
    "postularme",
    "postúlate",
    "postulate",
    "solicitar empleo",
    "enviar cv",
    "aplicar a la oferta",
    "inscribirme",
]
ENGLISH_APPLY_TERMS = [
    "apply now",
    "apply for this job",
    "submit application",
    "job application",
]
CLOSED_TERMS = [
    "ya no se aceptan solicitudes",
    "ya no acepta solicitudes",
    "no se aceptan más solicitudes",
    "no se aceptan mas solicitudes",
    "vacante finalizada",
    "vacante cerrada",
    "oferta finalizada",
    "oferta expirada",
    "oferta cerrada",
    "esta oferta ya no está disponible",
    "esta oferta ya no esta disponible",
    "proceso de selección finalizado",
    "proceso de seleccion finalizado",
    "job is no longer available",
    "position has been filled",
    "position is no longer available",
    "no longer accepting applications",
    "applications are closed",
    "job expired",
]
ADVANCED_ENGLISH_TERMS = [
    "inglés avanzado",
    "ingles avanzado",
    "inglés fluido",
    "ingles fluido",
    "inglés excluyente",
    "ingles excluyente",
    "nivel avanzado de inglés",
    "nivel avanzado de ingles",
    "dominio avanzado del inglés",
    "dominio avanzado del ingles",
    "dominio del idioma inglés",
    "dominio del idioma ingles",
    "advanced english",
    "fluent english",
    "english fluency",
    "english required",
    "proficient in english",
    "bilingual",
    "bilingüe",
    "bilingue",
    "inglés c1",
    "ingles c1",
    "english c1",
    "inglés c2",
    "ingles c2",
    "english c2",
]
NON_MANDATORY_QUALIFIERS = [
    "deseable",
    "no excluyente",
    "preferentemente",
    "valorable",
    "nice to have",
    "preferred",
    "is a plus",
    "no se requiere",
    "no es requisito",
    "no obligatorio",
    "no obligatoria",
    "no requiere",
    "no es necesario",
    "no es necesaria",
    "no requerido",
    "no requerida",
]
LEGAL_LABOR_TERMS = [
    "legislación laboral",
    "legislacion laboral",
    "derecho laboral",
    "relaciones laborales",
    "cumplimiento laboral",
    "compliance laboral",
    "relaciones sindicales",
    "convenios colectivos",
    "employee relations",
    "labor law",
    "employment law",
]
SPANISH_WORDS = {
    "de",
    "la",
    "el",
    "los",
    "las",
    "para",
    "con",
    "en",
    "del",
    "una",
    "un",
    "que",
    "experiencia",
    "requisitos",
    "responsabilidades",
    "buscamos",
    "trabajo",
    "modalidad",
    "empresa",
    "puesto",
    "funciones",
    "ofrecemos",
    "equipo",
    "selección",
    "seleccion",
    "talento",
    "personas",
    "recursos",
    "humanos",
}
ENGLISH_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "in",
    "of",
    "to",
    "we",
    "are",
    "you",
    "your",
    "experience",
    "requirements",
    "responsibilities",
    "work",
    "company",
    "role",
    "team",
    "people",
    "human",
    "resources",
    "apply",
    "skills",
    "about",
    "will",
}
SENIOR_TERMS = [
    "senior",
    "sr",
    "ssr",
    "semi senior",
    "semisenior",
    "especialista",
    "specialist",
    "coordinador",
    "coordinadora",
    "coordinator",
    "business partner",
    "people partner",
    "generalista",
    "generalist",
]


@dataclass(frozen=True)
class EligibilityAssessment:
    facts: RadarJobFacts
    checks: list[EligibilityCheck]
    eligible: bool
    role_tier: int | None
    score: int
    rank_components: dict[str, int]
    positive_signals: list[str]
    negative_signals: list[str]


def assess_candidate_eligibility(
    candidate: NormalizedJobCandidate, profile: SearchProfile
) -> EligibilityAssessment | None:
    policy = profile.eligibility_policy
    if policy is None:
        return None

    title = candidate.title or ""
    text = candidate.searchable_text
    normalized_title = normalize_for_matching(title)
    normalized_text = normalize_for_matching(text)
    role_tier, role_hits = _detect_role_tier(normalized_title, profile)
    work_modality, modality_evidence = _detect_modality(candidate)
    hybrid_location_evidence = _allowed_hybrid_location_evidence(candidate, profile)
    if work_modality == WorkModality.hybrid and hybrid_location_evidence:
        hiring_scope = "mendoza_hybrid"
        scope_status = EligibilityStatus.passed
        scope_evidence = hybrid_location_evidence
    else:
        hiring_scope, scope_status, scope_evidence = _detect_hiring_scope(
            candidate, profile
        )
    description_language = detect_language(candidate.raw_text or text)
    application_text = str(candidate.metadata.get("application_text") or "")
    application_language = _detect_application_language(
        application_text, normalized_text
    )
    seniority, seniority_status, seniority_evidence = _detect_seniority(
        candidate, normalized_title, normalized_text, profile
    )
    activity, activity_evidence = _detect_activity(candidate)
    published_at = _parse_datetime(candidate.metadata.get("published_date"))
    application_url = _optional_string(candidate.metadata.get("application_url"))
    salary_text, salary_min, salary_max = _detect_usd_monthly_salary(candidate)

    facts = RadarJobFacts(
        source_domain=(urlsplit(candidate.canonical_url).hostname or "").removeprefix(
            "www."
        ),
        description_language=description_language,
        application_language=application_language,
        work_modality=work_modality,
        hiring_scope=hiring_scope,
        seniority=seniority,
        activity_status=activity,
        published_at=published_at,
        role_tier=role_tier,
        application_url=application_url,
        salary_text=salary_text,
        salary_min_usd_monthly=salary_min,
        salary_max_usd_monthly=salary_max,
    )

    checks: list[EligibilityCheck] = []
    if role_tier is None:
        checks.append(
            _check(
                "role",
                EligibilityStatus.failed,
                "The title does not match Romina's target HR roles.",
            )
        )
    else:
        checks.append(
            _check(
                "role",
                EligibilityStatus.passed,
                f"Matches role priority tier {role_tier}.",
                role_hits,
            )
        )

    excluded_hits = _excluded_role_hits(normalized_title, role_tier, profile)
    if excluded_hits:
        checks.append(
            _check(
                "role_exclusions",
                EligibilityStatus.failed,
                "The title belongs to an excluded role family.",
                excluded_hits,
            )
        )
    else:
        checks.append(
            _check(
                "role_exclusions",
                EligibilityStatus.passed,
                "No excluded sales, call-center, accounting, or tax title was detected.",
            )
        )

    if policy.require_fully_remote or policy.allowed_hybrid_locations:
        if work_modality == WorkModality.remote:
            modality_status = EligibilityStatus.passed
            modality_reason = "The vacancy is explicitly fully remote."
        elif work_modality == WorkModality.hybrid and hybrid_location_evidence:
            modality_status = EligibilityStatus.passed
            modality_reason = "The vacancy is hybrid and its onsite location is in Mendoza."
        elif work_modality == WorkModality.hybrid:
            modality_status = EligibilityStatus.failed
            modality_reason = "The vacancy is hybrid outside the allowed Mendoza locations."
        elif work_modality == WorkModality.onsite:
            modality_status = EligibilityStatus.failed
            modality_reason = "Onsite-only vacancies are excluded."
        else:
            modality_status = EligibilityStatus.unknown
            modality_reason = "The remote or Mendoza-hybrid modality could not be verified."
        checks.append(
            _check(
                "work_modality",
                modality_status,
                modality_reason,
                [*modality_evidence, *hybrid_location_evidence],
            )
        )

    checks.append(
        _check(
            "hiring_geography",
            scope_status,
            (
                "The vacancy can hire candidates based in Argentina."
                if scope_status == EligibilityStatus.passed
                else (
                    "The vacancy restricts remote hiring outside Argentina/LATAM."
                    if scope_status == EligibilityStatus.failed
                    else "Argentina/LATAM/global hiring eligibility could not be verified."
                )
            ),
            scope_evidence,
        )
    )

    if policy.required_description_language:
        if description_language == policy.required_description_language:
            language_status = EligibilityStatus.passed
            language_reason = "The vacancy description is in Spanish."
        elif description_language in {"en", "mixed"}:
            language_status = EligibilityStatus.failed
            language_reason = "The vacancy description is not fully in Spanish."
        else:
            language_status = EligibilityStatus.unknown
            language_reason = "The vacancy description language could not be verified."
        checks.append(_check("description_language", language_status, language_reason))

    if policy.require_spanish_application:
        if application_language == "es":
            application_status = EligibilityStatus.passed
            application_reason = "The application action is presented in Spanish."
        elif application_language in {"en", "mixed"}:
            application_status = EligibilityStatus.failed
            application_reason = "The application flow is not fully in Spanish."
        else:
            application_status = EligibilityStatus.unknown
            application_reason = "The application flow language could not be verified."
        checks.append(
            _check("application_language", application_status, application_reason)
        )

    english_hits = _required_english_evidence(
        normalize_for_matching(f"{normalized_text}\n{application_text}")
    )
    if policy.reject_advanced_english and english_hits:
        checks.append(
            _check(
                "advanced_english",
                EligibilityStatus.failed,
                "Advanced or fluent English appears to be required.",
                english_hits,
            )
        )
    else:
        checks.append(
            _check(
                "advanced_english",
                EligibilityStatus.passed,
                "No mandatory advanced/fluent English requirement was detected.",
            )
        )

    checks.append(
        _check(
            "seniority",
            seniority_status,
            (
                "The role is semi-senior, senior, specialist, or equivalent."
                if seniority_status == EligibilityStatus.passed
                else (
                    "The role is junior, entry-level, trainee, or an internship."
                    if seniority_status == EligibilityStatus.failed
                    else "The required seniority could not be verified."
                )
            ),
            seniority_evidence,
        )
    )

    if policy.minimum_salary_usd_monthly is not None:
        if salary_min is not None and salary_min < policy.minimum_salary_usd_monthly:
            salary_status = EligibilityStatus.failed
            salary_reason = (
                f"The disclosed minimum salary is USD {salary_min}/month, below the "
                f"USD {policy.minimum_salary_usd_monthly}/month floor."
            )
        elif salary_min is not None:
            salary_status = EligibilityStatus.passed
            salary_reason = (
                f"The disclosed minimum salary is USD {salary_min}/month and meets the floor."
            )
        else:
            salary_status = EligibilityStatus.passed
            salary_reason = "No explicit below-floor USD salary was detected."
        checks.append(
            _check(
                "minimum_salary",
                salary_status,
                salary_reason,
                [salary_text] if salary_text else [],
            )
        )

    if policy.require_active_posting:
        if activity == JobActivityStatus.open:
            activity_status = EligibilityStatus.passed
            activity_reason = "The individual vacancy has an active application action."
        elif activity == JobActivityStatus.closed:
            activity_status = EligibilityStatus.failed
            activity_reason = (
                "The vacancy is closed or no longer accepting applications."
            )
        else:
            activity_status = EligibilityStatus.unknown
            activity_reason = "The application could not be verified as open."
        checks.append(
            _check(
                "active_posting", activity_status, activity_reason, activity_evidence
            )
        )

    eligible = all(check.status == EligibilityStatus.passed for check in checks)
    rank_components = _rank_components(
        role_tier=role_tier,
        seniority_status=seniority_status,
        normalized_text=normalized_text,
        published_at=published_at,
        checks=checks,
    )
    score = min(100, sum(rank_components.values())) if eligible else 0
    positive = [
        check.reason for check in checks if check.status == EligibilityStatus.passed
    ]
    negative = [
        check.reason for check in checks if check.status != EligibilityStatus.passed
    ]
    return EligibilityAssessment(
        facts=facts,
        checks=checks,
        eligible=eligible,
        role_tier=role_tier,
        score=score,
        rank_components=rank_components,
        positive_signals=positive,
        negative_signals=negative,
    )


def detect_language(text: str) -> str | None:
    words = re.findall(r"[a-záéíóúüñ]+", text.casefold())
    if len(words) < 8:
        return None
    spanish = sum(word in SPANISH_WORDS for word in words)
    english = sum(word in ENGLISH_WORDS for word in words)
    if spanish >= 4 and spanish >= english * 1.35:
        return "es"
    if english >= 4 and english >= spanish * 1.35:
        return "en"
    if spanish >= 3 and english >= 3:
        return "mixed"
    return None


def _detect_role_tier(
    normalized_title: str, profile: SearchProfile
) -> tuple[int | None, list[str]]:
    title_variants = {
        normalized_title,
        _without_role_seniority_modifiers(normalized_title),
    }
    for tier in sorted(profile.role_tiers, key=lambda item: item.tier):
        title_hits = [
            title
            for title in tier.titles
            if any(
                _contains_phrase(variant, normalize_for_matching(title))
                for variant in title_variants
            )
        ]
        if title_hits:
            return tier.tier, title_hits
    return None, []


def _without_role_seniority_modifiers(normalized_title: str) -> str:
    without_punctuation = re.sub(r"[./_-]+", " ", normalized_title)
    return normalize_for_matching(
        re.sub(
            r"\b(?:semi\s*senior|semisenior|senior|ssr|sr)\b",
            " ",
            without_punctuation,
        )
    )


def _excluded_role_hits(
    normalized_title: str, role_tier: int | None, profile: SearchProfile
) -> list[str]:
    policy = profile.eligibility_policy
    if policy is None:
        return []
    hits = [
        term
        for term in policy.excluded_role_terms
        if _contains_phrase(normalized_title, normalize_for_matching(term))
    ]
    if role_tier is not None:
        hits = [
            hit
            for hit in hits
            if normalize_for_matching(hit)
            not in {
                "administracion",
                "administrativo",
                "administrativa",
                "assistant",
                "asistente",
            }
        ]
    return hits


def _detect_modality(
    candidate: NormalizedJobCandidate,
) -> tuple[WorkModality, list[str]]:
    normalized = normalize_for_matching(
        "\n".join(
            part
            for part in [
                candidate.title,
                candidate.location_text,
                candidate.raw_text,
                str(candidate.metadata.get("workplace_type") or ""),
            ]
            if part
        )
    )
    strong_remote = _hits(normalized, REMOTE_STRONG_TERMS)
    hybrid = _hits(normalized, HYBRID_TERMS)
    onsite = _hits(normalized, ONSITE_TERMS)
    remote = _hits(normalized, REMOTE_TERMS)
    if hybrid or (remote and onsite):
        return WorkModality.hybrid, [*hybrid, *remote[:1], *onsite[:1]]
    if onsite:
        return WorkModality.onsite, onsite
    if candidate.metadata.get("provider_remote_claim_trusted") is True:
        return WorkModality.remote, ["trusted provider remote classification"]
    if strong_remote:
        return WorkModality.remote, strong_remote
    if remote:
        return WorkModality.remote, remote
    return WorkModality.unknown, []


def _allowed_hybrid_location_evidence(
    candidate: NormalizedJobCandidate, profile: SearchProfile
) -> list[str]:
    policy = profile.eligibility_policy
    if policy is None or not policy.allowed_hybrid_locations:
        return []
    normalized = normalize_for_matching(
        "\n".join(
            part
            for part in [candidate.title, candidate.location_text, candidate.raw_text]
            if part
        )
    )
    return _hits(normalized, policy.allowed_hybrid_locations)


def _detect_hiring_scope(
    candidate: NormalizedJobCandidate, profile: SearchProfile
) -> tuple[str | None, EligibilityStatus, list[str]]:
    policy = profile.eligibility_policy
    if policy is None:
        return None, EligibilityStatus.unknown, []
    normalized = normalize_for_matching(
        "\n".join(
            part
            for part in [candidate.title, candidate.location_text, candidate.raw_text]
            if part
        )
    )
    eligible_hits = _hits(normalized, policy.eligible_remote_regions)
    restricted_terms = [
        "solo españa",
        "solo espana",
        "residir en españa",
        "residir en espana",
        "residencia en españa",
        "residencia en espana",
        "permiso de trabajo en españa",
        "permiso de trabajo en espana",
        "spain only",
        "solo estados unidos",
        "us only",
        "united states only",
        "must be based in the us",
        "mexico only",
        "solo méxico",
        "solo mexico",
        "solo para residentes de mexico",
        "residir en mexico",
        "residencia en mexico",
        "chile only",
        "solo chile",
        "solo para residentes de chile",
        "residir en chile",
        "residencia en chile",
        "colombia only",
        "solo colombia",
        "solo para residentes de colombia",
        "residir en colombia",
        "residencia en colombia",
    ]
    restricted_hits = _hits(normalized, restricted_terms)
    if restricted_hits:
        return "restricted", EligibilityStatus.failed, restricted_hits
    provider_locations = candidate.metadata.get("applicant_locations")
    if candidate.metadata.get("provider_worldwide") is True:
        return "global", EligibilityStatus.passed, ["provider: worldwide"]
    if isinstance(provider_locations, list) and provider_locations:
        locations = [str(value) for value in provider_locations if value]
        normalized_locations = normalize_for_matching(" ".join(locations))
        provider_hits = _hits(
            normalized_locations,
            [*policy.eligible_remote_regions, "argentina", "latin america", "latam"],
        )
        if provider_hits:
            return "argentina_latam", EligibilityStatus.passed, locations[:5]
        return "restricted", EligibilityStatus.failed, locations[:5]
    if eligible_hits:
        return "argentina_latam_or_global", EligibilityStatus.passed, eligible_hits
    return None, EligibilityStatus.unknown, []


def _parse_salary_number(value: str) -> int | None:
    compact = value.strip().replace(" ", "")
    if not compact:
        return None
    if "." in compact and "," in compact:
        decimal_separator = "." if compact.rfind(".") > compact.rfind(",") else ","
        thousands_separator = "," if decimal_separator == "." else "."
        compact = compact.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif re.search(r"[.,]\d{3}$", compact):
        compact = compact.replace(".", "").replace(",", "")
    else:
        compact = compact.replace(",", ".")
    try:
        return round(float(compact))
    except ValueError:
        return None


def _detect_usd_monthly_salary(
    candidate: NormalizedJobCandidate,
) -> tuple[str | None, int | None, int | None]:
    currency = str(candidate.metadata.get("salary_currency") or "").upper()
    provider_min = candidate.metadata.get("salary_min")
    provider_max = candidate.metadata.get("salary_max")
    provider_values = [
        round(value)
        for value in [provider_min, provider_max]
        if isinstance(value, (int, float)) and value > 0
    ]
    if currency == "USD" and provider_values:
        period = str(candidate.metadata.get("salary_period") or "annual").casefold()
        if period in {"annual", "year", "yearly", "per year"}:
            monthly = [round(value / 12) for value in provider_values]
        elif period in {"hour", "hourly", "per hour"}:
            monthly = [round(value * 173) for value in provider_values]
        elif period in {"week", "weekly", "per week"}:
            monthly = [round(value * 4.33) for value in provider_values]
        elif period in {"day", "daily", "per day"}:
            monthly = [round(value * 21.67) for value in provider_values]
        else:
            monthly = provider_values
        evidence = f"Provider salary: USD {min(provider_values)}-{max(provider_values)} {period}"
        return evidence, min(monthly), max(monthly)
    text = "\n".join(
        part
        for part in [
            candidate.title,
            candidate.raw_text,
            str(candidate.metadata.get("salary") or ""),
            str(candidate.metadata.get("compensation") or ""),
        ]
        if part
    )
    matches = list(
        re.finditer(r"(?i)(?:USD|US\$|U\$S)\s*([0-9][0-9.,]*)", text)
    )
    monthly_values: list[int] = []
    evidence: list[str] = []
    for match in matches:
        amount = _parse_salary_number(match.group(1))
        if amount is None:
            continue
        context = text[max(0, match.start() - 50) : min(len(text), match.end() + 60)]
        normalized_context = normalize_for_matching(context)
        if _hits(
            normalized_context,
            [
                "budget",
                "presupuesto",
                "allowance",
                "stipend",
                "bonus",
                "bono",
                "reward",
                "reimbursement",
                "reintegro",
            ],
        ):
            continue
        if _hits(normalized_context, ["hora", "hour", "diario", "daily", "por día", "por dia"]):
            continue
        if _hits(normalized_context, ["anual", "annual", "per year", "por año", "por ano"]):
            amount = round(amount / 12)
        elif not _hits(normalized_context, ["mensual", "monthly", "per month", "por mes"]):
            if amount > 10000:
                continue
        monthly_values.append(amount)
        evidence.append(" ".join(context.split()))
    if not monthly_values:
        return None, None, None
    return " | ".join(dict.fromkeys(evidence))[:500], min(monthly_values), max(monthly_values)


def _detect_application_language(
    application_text: str, normalized_text: str
) -> str | None:
    if application_text:
        normalized_application = normalize_for_matching(application_text)
        spanish_hits = _hits(normalized_application, SPANISH_APPLY_TERMS)
        english_hits = _hits(normalized_application, ENGLISH_APPLY_TERMS)
        if spanish_hits and not english_hits:
            return "es"
        if english_hits and not spanish_hits:
            return "en"
        if spanish_hits and english_hits:
            return "mixed"
        detected = detect_language(application_text)
        if detected in {"es", "en", "mixed"}:
            return detected
        return None
    spanish_hits = _hits(normalized_text, SPANISH_APPLY_TERMS)
    english_hits = _hits(normalized_text, ENGLISH_APPLY_TERMS)
    if spanish_hits and not english_hits:
        return "es"
    if english_hits and not spanish_hits:
        return "en"
    if spanish_hits and english_hits:
        return "mixed"
    return None


def _detect_seniority(
    candidate: NormalizedJobCandidate,
    normalized_title: str,
    normalized_text: str,
    profile: SearchProfile,
) -> tuple[str | None, EligibilityStatus, list[str]]:
    policy = profile.eligibility_policy
    rejected_terms = policy.rejected_seniority_terms if policy else []
    title_rejections = _hits(normalized_title, rejected_terms)
    body_rejections = _hits(
        normalized_text,
        [
            "sin experiencia",
            "primer empleo",
            "pasantía",
            "pasantia",
            "pasantías",
            "pasantias",
            "prácticas",
            "practicas",
            "internship",
            "entry level",
            "trainee",
        ],
    )
    if title_rejections or body_rejections:
        return (
            "junior_or_entry",
            EligibilityStatus.failed,
            [*title_rejections, *body_rejections],
        )
    provider_seniority = normalize_for_matching(
        str(candidate.metadata.get("seniority") or "")
    )
    provider_rejections = _hits(provider_seniority, rejected_terms)
    if provider_rejections:
        return "junior_or_entry", EligibilityStatus.failed, provider_rejections
    senior_hits = [
        *_hits(normalized_title, SENIOR_TERMS),
        *_hits(provider_seniority, SENIOR_TERMS),
    ]
    if senior_hits:
        return "semi_senior_or_above", EligibilityStatus.passed, senior_hits
    years_match = re.search(
        r"(?<!\d)([3-9]|1\d)\+?\s*(?:años|anos|years)", normalized_text
    )
    if years_match:
        return "experienced", EligibilityStatus.passed, [years_match.group(0)]
    return None, EligibilityStatus.unknown, []


def _detect_activity(
    candidate: NormalizedJobCandidate,
) -> tuple[JobActivityStatus, list[str]]:
    normalized = normalize_for_matching(
        "\n".join(
            [
                candidate.searchable_text,
                str(candidate.metadata.get("application_text") or ""),
            ]
        )
    )
    closed_hits = _hits(normalized, CLOSED_TERMS)
    http_status = candidate.metadata.get("page_http_status")
    if http_status in {404, 410}:
        closed_hits.append(f"HTTP {http_status}")
    valid_through = _parse_datetime(candidate.metadata.get("valid_through"))
    if valid_through is not None:
        if valid_through.tzinfo is None:
            valid_through = valid_through.replace(tzinfo=timezone.utc)
        if valid_through < datetime.now(timezone.utc):
            closed_hits.append(
                f"validThrough expired on {valid_through.date().isoformat()}"
            )
    provider_status = str(candidate.metadata.get("provider_status") or "").casefold()
    if provider_status in {"closed", "filled", "expired", "inactive"}:
        closed_hits.append(f"provider status: {provider_status}")
    if closed_hits:
        return JobActivityStatus.closed, closed_hits
    if (
        provider_status == "active"
        and candidate.metadata.get("application_url")
    ):
        return JobActivityStatus.open, ["provider: active application URL"]
    apply_hits = [
        *_hits(normalized, SPANISH_APPLY_TERMS),
        *_hits(normalized, ENGLISH_APPLY_TERMS),
    ]
    if http_status == 200 and apply_hits:
        return JobActivityStatus.open, apply_hits
    if candidate.metadata.get("page_fetched") is True and apply_hits:
        return JobActivityStatus.open, apply_hits
    return JobActivityStatus.unknown, []


def _required_english_evidence(normalized_text: str) -> list[str]:
    hits: list[str] = []
    for term in ADVANCED_ENGLISH_TERMS:
        normalized_term = normalize_for_matching(term)
        for match in re.finditer(re.escape(normalized_term), normalized_text):
            start = max(0, match.start() - 60)
            end = min(len(normalized_text), match.end() + 60)
            context = normalized_text[start:end]
            if any(qualifier in context for qualifier in NON_MANDATORY_QUALIFIERS):
                continue
            hits.append(term)
            break
    return list(dict.fromkeys(hits))


def _rank_components(
    *,
    role_tier: int | None,
    seniority_status: EligibilityStatus,
    normalized_text: str,
    published_at: datetime | None,
    checks: list[EligibilityCheck],
) -> dict[str, int]:
    role_points = 0 if role_tier is None else {1: 45, 2: 35, 3: 25}.get(role_tier, 0)
    seniority_points = 15 if seniority_status == EligibilityStatus.passed else 0
    legal_points = 15 if _hits(normalized_text, LEGAL_LABOR_TERMS) else 0
    freshness_points = 0
    if published_at is not None:
        published = published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age_days = max(0, (datetime.now(timezone.utc) - published).days)
        freshness_points = (
            15
            if age_days <= 7
            else 10
            if age_days <= 30
            else 5
            if age_days <= 60
            else 0
        )
    completeness_points = min(
        10, sum(check.status == EligibilityStatus.passed for check in checks)
    )
    return {
        "role_priority": role_points,
        "seniority_fit": seniority_points,
        "legal_labor_fit": legal_points,
        "freshness": freshness_points,
        "evidence_completeness": completeness_points,
    }


def _check(
    criterion: str,
    status: EligibilityStatus,
    reason: str,
    evidence: list[str] | None = None,
) -> EligibilityCheck:
    return EligibilityCheck(
        criterion=criterion,
        status=status,
        reason=reason,
        evidence=list(dict.fromkeys(evidence or []))[:5],
    )


def _hits(normalized_text: str, terms: list[str]) -> list[str]:
    return [
        term
        for term in terms
        if _contains_phrase(normalized_text, normalize_for_matching(term))
    ]


def _contains_phrase(normalized_text: str, normalized_phrase: str) -> bool:
    pattern = re.escape(normalized_phrase).replace(r"\ ", r"[\s\-]+")
    return bool(re.search(rf"(?<!\w){pattern}(?!\w)", normalized_text))


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _optional_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
