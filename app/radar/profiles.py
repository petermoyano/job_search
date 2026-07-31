from __future__ import annotations

from pydantic import HttpUrl

from app.radar.models import (
    EligibilityPolicy,
    RoleTier,
    ScoringGroup,
    SearchProfile,
    SearchQuery,
    SearchSource,
)


ROMINA_SOURCE_REFERENCES = [
    HttpUrl(url)
    for url in [
        "https://www.zonajobs.com.ar",
        "https://www.infojobs.net",
        "https://ar.computrabajo.com",
        "https://www.trabajando.com",
        "https://www.bumeran.com.ar",
        "https://www.jobleads.com",
        "https://ar.jooble.org",
        "https://remolatam.com",
        "https://www.remlist.com",
        "https://es.indeed.com",
        "https://www.job.com",
        "https://www.adecco.com.ar",
        "https://www.randstad.com.ar",
        "https://www.manpower.com.ar",
        "https://www.grupogestion.com.ar",
        "https://www.bayton.com",
        "https://kaizenconsultora.com.ar",
        "https://bonder.com.ar",
        "https://puerinorrhh.com",
        "https://otium.ar",
        "https://talenua.com",
        "https://ripia.com.ar",
        "https://delfoi.com.ar",
        "https://www.linkedin.com/jobs",
        "https://empleos.clarin.com",
        "https://www.hiringroom.com",
        "https://www.workana.com/jobs",
        "https://www.infoempleo.com",
        "https://www.trabajos.com",
        "https://www.tecnoempleo.com",
        "https://www.domestika.org/jobs",
        "https://rrhhjobs.com",
        "https://www.getonbrd.com",
        "https://torre.ai",
        "https://wellfound.com",
        "https://jobicy.com",
        "https://remoteok.com",
        "https://www.michaelpage.com.ar",
        "https://www.pagepersonnel.com.ar",
        "https://www.cetacapitalhumano.com.ar",
        "https://www.pullmen.com.ar",
        "https://www.consultoresdeempresas.com",
        "https://www.servicemen.com.ar",
        "https://www.suministra.com.ar",
        "https://www.rhmaster.com.ar",
    ]
]

ROMINA_TIER_1_SOURCE_DOMAINS = [
    "infojobs.net",
    "linkedin.com",
    "ar.computrabajo.com",
    "bumeran.com.ar",
    "es.indeed.com",
]

ROMINA_ORDERED_SOURCES = [
    SearchSource(id="infojobs", label="InfoJobs", domains=["infojobs.net"], order=1),
    SearchSource(
        id="linkedin", label="LinkedIn Jobs", domains=["linkedin.com"], order=2
    ),
    SearchSource(
        id="computrabajo_ar",
        label="Computrabajo Argentina",
        domains=["ar.computrabajo.com"],
        order=3,
    ),
    SearchSource(id="bumeran", label="Bumeran", domains=["bumeran.com.ar"], order=4),
    SearchSource(
        id="indeed_es", label="Indeed España", domains=["es.indeed.com"], order=5
    ),
    SearchSource(
        id="getonboard",
        label="Get On Board",
        domains=["getonbrd.com"],
        order=6,
        primary=False,
    ),
    SearchSource(
        id="hiringroom",
        label="Hiring Room",
        domains=["hiringroom.com"],
        order=7,
        primary=False,
    ),
    SearchSource(
        id="torre", label="Torre", domains=["torre.ai"], order=8, primary=False
    ),
    SearchSource(
        id="wellfound",
        label="Wellfound",
        domains=["wellfound.com"],
        order=9,
        primary=False,
    ),
    SearchSource(
        id="remote_latam",
        label="Remote Latam",
        domains=["remolatam.com"],
        order=10,
        primary=False,
    ),
    SearchSource(
        id="workana_hr",
        label="Workana - RRHH",
        domains=["workana.com"],
        order=11,
        primary=False,
    ),
    SearchSource(
        id="talent",
        label="Talent.com",
        domains=["talent.com"],
        order=12,
        primary=False,
    ),
    SearchSource(
        id="jooble",
        label="Jooble",
        domains=["jooble.org", "ar.jooble.org"],
        order=13,
        primary=False,
    ),
]

ROMINA_EXCLUDED_SOURCE_DOMAINS = [
    "wikipedia.org",
    "adp.com",
    "glassdoor.com.ar",
    "calhr.ca.gov",
    "hrhouston.org",
    "hr.com",
    "hrcalifornia.calchamber.com",
    "reddit.com",
]

ROMINA_ROLE_TIERS = [
    RoleTier(
        tier=1,
        label="Strategic HR / Talent",
        titles=[
            "HR Business Partner",
            "HRBP",
            "Talent Acquisition Partner",
            "Talent Acquisition Specialist",
            "People Partner",
            "People Operations",
        ],
    ),
    RoleTier(
        tier=2,
        label="Recruiting / People specialist",
        titles=[
            "IT Recruiter",
            "Recruiter IT",
            "Especialista en Talent Acquisition",
            "Especialista de Talent Acquisition",
            "Especialista en Adquisición de Talento",
            "Tech Recruiter",
            "Recruitment Specialist",
            "People Specialist",
            "People Experience",
            "Analista de Talento",
            "Talent Partner",
            "Analista de Atracción de Talento",
            "Analista de Atraccion de Talento",
        ],
    ),
    RoleTier(
        tier=3,
        label="HR generalist / coordination",
        titles=[
            "Analista de Recursos Humanos",
            "Analista de RRHH",
            "Analista de Selección",
            "Analista de Seleccion",
            "Generalista de Recursos Humanos",
            "Generalista de RRHH",
            "HR Generalist",
            "Coordinador de Recursos Humanos",
            "Coordinadora de Recursos Humanos",
            "Coordinador de RRHH",
            "Coordinadora de RRHH",
            "Coordinador/a de Recursos Humanos",
            "Coordinador/a de RRHH",
            "Employer Branding Specialist",
            "Especialista en Recursos Humanos",
            "Responsable de Recursos Humanos",
        ],
    ),
]

HR_TARGET_ROLES = [title for tier in ROMINA_ROLE_TIERS for title in tier.titles]


HR_POSITIVE_GROUPS = [
    ScoringGroup(
        label="HR/recruiting role fit",
        points=18,
        terms=[
            "recursos humanos",
            "capital humano",
            "hr business partner",
            "talent acquisition",
            "recruiter it",
            "reclutamiento y seleccion",
            "reclutamiento y selección",
            "seleccion de personal",
            "selección de personal",
        ],
    ),
    ScoringGroup(
        label="HRBP and people operations scope",
        points=12,
        terms=[
            "hrbp",
            "business partner",
            "people operations",
            "employee experience",
            "clima laboral",
            "evaluacion de desempeño",
            "evaluación de desempeño",
            "kpis de rrhh",
        ],
    ),
    ScoringGroup(
        label="onboarding and process ownership",
        points=10,
        terms=[
            "onboarding",
            "offboarding",
            "induccion",
            "inducción",
            "capacitacion",
            "capacitación",
            "gestion integral",
            "gestión integral",
        ],
    ),
]

ENGLISH_REQUIRED_GROUP = ScoringGroup(
    label="required English",
    points=70,
    terms=[
        "ingles avanzado",
        "inglés avanzado",
        "ingles excluyente",
        "inglés excluyente",
        "advanced english",
        "english required",
        "bilingual",
        "bilingue",
        "bilingüe",
        "nivel avanzado de ingles",
        "nivel avanzado de inglés",
    ],
)

PETER_REMOTE_AI_FULLSTACK_PRODUCT = SearchProfile(
    id="peter-latam-remote-ai-fullstack-product",
    name="Peter - Remote AI / Full-Stack Product",
    owner_id="peter",
    owner_name="Pedro Moyano",
    description=(
        "Find fully remote, LATAM-friendly or globally remote direct employer roles "
        "with US-market compensation potential. Prioritize AI Engineer, Applied AI, "
        "full-stack product engineering, and ownership-heavy roles over backend-only work."
    ),
    target_roles=[
        "AI Engineer",
        "Applied AI Engineer",
        "Full-Stack AI Engineer",
        "Full Stack Engineer",
        "Full-stack Developer",
        "AI Product Engineer",
        "Product Engineer",
        "LLM Engineer",
        "RAG Engineer",
        "Software Engineer, AI",
        "Founding Engineer",
        "Forward Deployed Engineer",
    ],
    location_policy=(
        "Fully remote role that is open to Argentina, LATAM, Americas, global remote, "
        "or anywhere candidates. US-based companies are preferred for compensation, "
        "but the role should not require US residency."
    ),
    required_terms=["remote"],
    preferred_terms=[
        "LATAM",
        "Latin America",
        "Argentina",
        "Americas",
        "global remote",
        "anywhere",
        "worldwide",
        "US time zones",
        "AI Engineer",
        "Applied AI",
        "LLM",
        "RAG",
        "agents",
        "LangChain",
        "LlamaIndex",
        "Next.js",
        "React",
        "Node.js",
        "TypeScript",
        "Python",
    ],
    reject_terms=[
        "staff augmentation",
        "staffing",
        "agency",
        "hidden client",
        "confidential client",
        "onsite",
        "on-site",
        "hybrid",
        "clearance required",
        "C2C",
        "US only",
        "U.S. only",
        "United States only",
        "must be based in the US",
        "must be located in the US",
        "must reside in the US",
        "US work authorization required",
        "requires US work authorization",
        "sponsorship not available",
    ],
    positive_scoring_groups=[
        ScoringGroup(
            label="LATAM/global remote fit",
            points=20,
            terms=[
                "remote - us",
                "remote us",
                "americas",
                "latam",
                "latin america",
                "argentina",
                "global remote",
                "remote worldwide",
                "work from anywhere",
                "us time zones",
            ],
        ),
        ScoringGroup(
            label="AI/LLM depth",
            points=18,
            terms=[
                "ai engineer",
                "applied ai",
                "llm",
                "rag",
                "agents",
                "function calling",
                "tool calling",
                "langchain",
                "llamaindex",
                "openai",
                "hugging face",
                "fine-tuning",
            ],
        ),
        ScoringGroup(
            label="full-stack product stack",
            points=12,
            terms=["next.js", "react", "node.js", "typescript", "python"],
        ),
        ScoringGroup(
            label="product ownership",
            points=14,
            terms=[
                "product engineering",
                "product team",
                "our product",
                "our platform",
                "full ownership",
                "end-to-end",
                "0 to 1",
                "saas",
            ],
        ),
    ],
    negative_scoring_groups=[
        ScoringGroup(
            label="staffing or intermediary",
            points=35,
            terms=[
                "staff augmentation",
                "staffing",
                "our client",
                "end client",
                "confidential client",
                "third-party recruiter",
            ],
        ),
        ScoringGroup(
            label="US-only restriction",
            points=35,
            terms=[
                "us only",
                "united states only",
                "must be based in the us",
                "must reside in the us",
                "us work authorization required",
            ],
        ),
    ],
    queries=[
        SearchQuery(
            text='site:jobs.lever.co "AI Engineer" "Remote" "LATAM"',
            reason="Lever roles explicitly mentioning AI, remote work, and LATAM.",
        ),
        SearchQuery(
            text='site:boards.greenhouse.io "Applied AI Engineer" "Remote" "Americas"',
            reason="Greenhouse roles for applied AI that are Americas-friendly.",
        ),
        SearchQuery(
            text='site:jobs.ashbyhq.com "Full-Stack AI Engineer" "Remote"',
            reason="Ashby roles combining full-stack product work and AI engineering.",
        ),
        SearchQuery(
            text='"AI Product Engineer" "Remote" "Latin America" "careers"',
            reason="General web discovery for AI product roles open to Latin America.",
        ),
        SearchQuery(
            text='"Full Stack Engineer" "AI" "Remote" "Americas" "careers"',
            reason="Full-stack AI/product roles compatible with Americas time zones.",
        ),
        SearchQuery(
            text='"Founding Engineer" "AI" "Remote" "LATAM"',
            reason="Ownership-heavy early product engineering roles with AI focus.",
        ),
        SearchQuery(
            text='"LLM Engineer" "Remote" "Argentina"',
            reason="LLM roles explicitly open to Argentina-based candidates.",
        ),
    ],
    max_results_per_query=8,
)

ROMINA_REMOTE_SPANISH_HR = SearchProfile(
    id="romina-remote-spanish-hr",
    name="Romina - RRHH remoto en español",
    version="2026-07-30.1",
    owner_id="romina",
    owner_name="Romina Roby",
    candidate_summary=(
        "Profesional de RRHH con más de 8 años de experiencia, perfil HRBP y "
        "Talent Acquisition, con base legal y de relaciones laborales."
    ),
    description=(
        "Vacantes de RRHH completamente remotas, publicadas y postulables en español, "
        "para una candidata basada en Argentina. Se acepta inglés básico o intermedio; "
        "el inglés avanzado o fluido excluyente descalifica la oportunidad."
    ),
    target_roles=HR_TARGET_ROLES,
    role_tiers=ROMINA_ROLE_TIERS,
    location_policy=(
        "La publicación puede originarse en cualquier país, pero debe permitir trabajar "
        "desde Argentina mediante contratación local, LATAM, global o internacional. "
        "Las posiciones híbridas se evalúan en el perfil separado de Mendoza."
    ),
    eligibility_policy=EligibilityPolicy(
        require_fully_remote=True,
        eligible_remote_regions=[
            "Argentina",
            "LATAM",
            "Latin America",
            "América Latina",
            "America Latina",
            "global",
            "worldwide",
            "anywhere",
            "internacional",
            "international hiring",
            "contratación internacional",
            "contratacion internacional",
        ],
        required_description_language="es",
        require_spanish_application=True,
        reject_advanced_english=True,
        rejected_seniority_terms=[
            "junior",
            "jr",
            "trainee",
            "pasante",
            "pasantía",
            "pasantia",
            "prácticas",
            "practicas",
            "internship",
            "entry level",
            "assistant",
            "asistente",
            "auxiliar",
            "sin experiencia",
        ],
        excluded_role_terms=[
            "ventas",
            "vendedor",
            "vendedora",
            "ejecutivo comercial",
            "ejecutiva comercial",
            "call center",
            "telemarketer",
            "customer service",
            "atención al cliente",
            "atencion al cliente",
            "administrativo",
            "administrativa",
            "secretaria",
            "recepcionista",
        ],
        require_active_posting=True,
    ),
    required_terms=["remoto", "remote", "modalidad remota", "trabajo remoto"],
    preferred_terms=[
        "remoto",
        "trabajo remoto",
        "modalidad remota",
        "latam",
        "argentina",
        "recursos humanos",
        "reclutamiento",
        "selección",
        "talent acquisition",
        "hr business partner",
        "people partner",
        "people operations",
        "relaciones laborales",
        "legislación laboral",
        "derecho laboral",
    ],
    reject_terms=[
        *ENGLISH_REQUIRED_GROUP.terms,
        "presencial",
        "híbrido",
        "hibrido",
        "junior",
        "pasantía",
        "pasantia",
        "prácticas",
        "practicas",
        "ventas",
        "call center",
    ],
    positive_scoring_groups=[
        ScoringGroup(
            label="remote Argentina/LATAM fit",
            points=22,
            terms=[
                "100% remoto",
                "trabajo remoto",
                "modalidad remota",
                "latam",
                "argentina",
                "américa latina",
                "global",
                "contratación internacional",
            ],
        ),
        *HR_POSITIVE_GROUPS,
        ScoringGroup(
            label="legal and labor-relations background fit",
            points=15,
            terms=[
                "legislación laboral",
                "derecho laboral",
                "relaciones laborales",
                "compliance laboral",
                "relaciones sindicales",
                "convenios colectivos",
            ],
        ),
    ],
    negative_scoring_groups=[ENGLISH_REQUIRED_GROUP],
    source_references=ROMINA_SOURCE_REFERENCES,
    preferred_source_domains=[
        domain for source in ROMINA_ORDERED_SOURCES for domain in source.domains
    ],
    excluded_source_domains=ROMINA_EXCLUDED_SOURCE_DOMAINS,
    ordered_sources=ROMINA_ORDERED_SOURCES,
    queries=[
        SearchQuery(
            role_tier=1,
            text=(
                '("HR Business Partner" OR HRBP OR "Talent Acquisition Partner" OR '
                '"Talent Acquisition Specialist" OR "People Partner" OR "People Operations") '
                '(remoto OR remota) (Argentina OR LATAM OR "América Latina")'
            ),
            reason="Tier 1 strategic HR and Talent roles.",
        ),
        SearchQuery(
            role_tier=2,
            text=(
                '("IT Recruiter" OR "Recruiter IT" OR "Tech Recruiter" OR "Recruitment Specialist" OR '
                '"People Specialist" OR "People Experience" OR "Analista de Talento" OR '
                '"Talent Partner") (remoto OR remota) (Argentina OR LATAM)'
            ),
            reason="Tier 2 recruiting and People specialist roles.",
        ),
        SearchQuery(
            role_tier=3,
            text=(
                '("Analista de RRHH" OR "Analista de Recursos Humanos" OR '
                '"Analista de Selección" OR "Generalista de RRHH" OR '
                '"Coordinador de RRHH" OR "Employer Branding Specialist") '
                "(remoto OR remota) (Argentina OR LATAM)"
            ),
            reason="Tier 3 experienced HR generalist and coordination roles.",
        ),
    ],
    max_results_per_query=3,
    max_qualified_results=5,
)

ROMINA_MENDOZA_HR_ONSITE_HYBRID = SearchProfile(
    id="romina-mendoza-hr-onsite-hybrid",
    name="Romina - Mendoza HR Onsite/Hybrid",
    owner_id="romina",
    owner_name="Romina Roby",
    description=(
        "Find HR, recruiting, HRBP, and people operations roles in Mendoza or Gran "
        "Mendoza, prioritizing onsite or hybrid roles that are unlikely to require English."
    ),
    target_roles=HR_TARGET_ROLES,
    location_policy=(
        "Onsite or hybrid role in Mendoza, Gran Mendoza, or nearby Mendoza metro "
        "areas. English-required roles should be downgraded or rejected."
    ),
    required_terms=[
        "mendoza",
        "gran mendoza",
        "maipu",
        "maipú",
        "godoy cruz",
        "guaymallen",
        "guaymallén",
        "lujan de cuyo",
        "luján de cuyo",
    ],
    preferred_terms=[
        "mendoza",
        "gran mendoza",
        "presencial",
        "hibrido",
        "híbrido",
        "maipu",
        "maipú",
        "godoy cruz",
        "guaymallen",
        "guaymallén",
        "lujan de cuyo",
        "luján de cuyo",
        "recursos humanos",
        "capital humano",
        "hr business partner",
        "reclutamiento",
    ],
    reject_terms=[
        "buenos aires",
        "caba",
        "gba",
        "relocation required",
        "reubicacion",
        "reubicación",
        *ENGLISH_REQUIRED_GROUP.terms,
    ],
    positive_scoring_groups=[
        ScoringGroup(
            label="Mendoza local fit",
            points=25,
            terms=[
                "mendoza",
                "gran mendoza",
                "maipu",
                "maipú",
                "godoy cruz",
                "guaymallen",
                "guaymallén",
                "lujan de cuyo",
                "luján de cuyo",
            ],
        ),
        ScoringGroup(
            label="onsite or hybrid modality",
            points=15,
            terms=["presencial", "hibrido", "híbrido", "modalidad presencial"],
        ),
        *HR_POSITIVE_GROUPS,
    ],
    negative_scoring_groups=[
        ENGLISH_REQUIRED_GROUP,
        ScoringGroup(
            label="not local to Mendoza",
            points=45,
            terms=[
                "buenos aires",
                "caba",
                "gba",
                "cordoba",
                "córdoba",
                "rosario",
                "relocation required",
                "reubicacion",
                "reubicación",
            ],
        ),
        ScoringGroup(
            label="payroll/admin-only role",
            points=20,
            terms=[
                "liquidacion de sueldos exclusivamente",
                "liquidación de sueldos exclusivamente",
                "solo payroll",
                "payroll only",
                "administrativo exclusivamente",
            ],
        ),
    ],
    source_references=ROMINA_SOURCE_REFERENCES,
    preferred_source_domains=ROMINA_TIER_1_SOURCE_DOMAINS,
    excluded_source_domains=ROMINA_EXCLUDED_SOURCE_DOMAINS,
    queries=[
        SearchQuery(
            text='"Recursos Humanos" "Mendoza" "presencial" empleo',
            reason="Local onsite HR roles in Mendoza.",
        ),
        SearchQuery(
            text='"HR Business Partner" "Mendoza" "Argentina"',
            reason="Mendoza HRBP roles that may appear with English job titles.",
        ),
        SearchQuery(
            text='"Analista de Recursos Humanos" "Mendoza" "híbrido"',
            reason="Hybrid HR analyst roles around Mendoza.",
        ),
        SearchQuery(
            text='"Recruiter IT" "Mendoza" "Argentina"',
            reason="IT recruiter roles in Mendoza.",
        ),
        SearchQuery(
            text='"Capital Humano" "Mendoza" trabajo',
            reason="Capital humano postings in Mendoza.",
        ),
        SearchQuery(
            text='"Responsable de Recursos Humanos" "Mendoza"',
            reason="Senior HR ownership roles in Mendoza.",
        ),
    ],
    max_results_per_query=8,
)

# Backwards-compatible alias for imports/tests that still use the original name.
PETER_US_REMOTE_DIRECT_PRODUCT = PETER_REMOTE_AI_FULLSTACK_PRODUCT


PROFILES = {
    PETER_REMOTE_AI_FULLSTACK_PRODUCT.id: PETER_REMOTE_AI_FULLSTACK_PRODUCT,
    ROMINA_REMOTE_SPANISH_HR.id: ROMINA_REMOTE_SPANISH_HR,
    ROMINA_MENDOZA_HR_ONSITE_HYBRID.id: ROMINA_MENDOZA_HR_ONSITE_HYBRID,
}


def get_profile(profile_id: str) -> SearchProfile:
    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        supported = ", ".join(sorted(PROFILES))
        raise ValueError(
            f"Unknown radar profile '{profile_id}'. Supported: {supported}"
        ) from exc
