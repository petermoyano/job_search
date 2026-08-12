from __future__ import annotations

from pydantic import HttpUrl

from app.radar.models import (
    AcquisitionMode,
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
        "https://www.upwork.com",
        "https://www.multitrabajos.com",
        "https://jobspresso.co",
        "https://jobgether.com",
        "https://himalayas.app",
        "https://weworkremotely.com",
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
    SearchSource(
        id="himalayas", label="Himalayas", domains=["himalayas.app"], order=1,
        max_results=10, acquisition_mode=AcquisitionMode.himalayas_api,
        attribution_url="https://himalayas.app",
    ),
    SearchSource(
        id="we_work_remotely", label="We Work Remotely",
        domains=["weworkremotely.com"], order=2, max_results=10,
        acquisition_mode=AcquisitionMode.we_work_remotely_rss,
        attribution_url="https://weworkremotely.com",
    ),
    SearchSource(
        id="remote_ok", label="Remote OK", domains=["remoteok.com"], order=3,
        max_results=15, acquisition_mode=AcquisitionMode.remote_ok_api,
        attribution_url="https://remoteok.com",
    ),
    SearchSource(id="linkedin", label="LinkedIn Jobs", domains=["linkedin.com"], order=4),
    SearchSource(id="computrabajo_ar", label="Computrabajo Argentina", domains=["ar.computrabajo.com"], order=5),
    SearchSource(id="bumeran", label="Bumeran", domains=["bumeran.com.ar"], order=6),
    SearchSource(id="getonboard", label="Get On Board", domains=["getonbrd.com"], order=7),
    SearchSource(id="hiringroom", label="Hiring Room", domains=["hiringroom.com"], order=8),
    SearchSource(id="torre", label="Torre", domains=["torre.ai"], order=9),
    SearchSource(id="remote_latam", label="Remote Latam", domains=["remolatam.com"], order=10),
    SearchSource(id="jobgether", label="Jobgether", domains=["jobgether.com"], order=11),
    SearchSource(id="zonajobs", label="Zonajobs", domains=["zonajobs.com.ar"], order=12, enabled=False),
    SearchSource(id="jobspresso", label="Jobspresso", domains=["jobspresso.co"], order=13, enabled=False),
    SearchSource(id="indeed_es", label="Indeed España", domains=["es.indeed.com"], order=14, enabled=False),
    SearchSource(id="infojobs", label="InfoJobs", domains=["infojobs.net"], order=15, enabled=False),
    SearchSource(id="wellfound", label="Wellfound", domains=["wellfound.com"], order=16, enabled=False),
    SearchSource(id="workana_hr", label="Workana - RRHH", domains=["workana.com"], order=17, enabled=False),
    SearchSource(id="talent", label="Talent.com", domains=["talent.com"], order=18, enabled=False),
    SearchSource(id="jooble", label="Jooble", domains=["jooble.org", "ar.jooble.org"], order=19, enabled=False),
    SearchSource(id="multitrabajos", label="Multitrabajos", domains=["multitrabajos.com"], order=20, enabled=False),
    SearchSource(id="adecco_ar", label="Adecco Argentina", domains=["adecco.com.ar"], order=21, enabled=False),
    SearchSource(id="randstad_ar", label="Randstad Argentina", domains=["randstad.com.ar"], order=22, enabled=False),
    SearchSource(id="manpower_ar", label="Manpower Argentina", domains=["manpower.com.ar"], order=23, enabled=False),
    SearchSource(id="michael_page_ar", label="Michael Page Argentina", domains=["michaelpage.com.ar"], order=24, enabled=False),
    SearchSource(id="upwork", label="Upwork", domains=["upwork.com"], order=25, enabled=False),
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
        label="Socios estratégicos y liderazgo de talento",
        titles=[
            "HR Business Partner", "HRBP", "Business Partner de RRHH",
            "Socio Estratégico de RRHH", "Talent Acquisition Partner",
            "Especialista en Atracción de Talento", "Responsable de Reclutamiento y Selección",
            "Coordinador de Atracción de Talento", "Coordinadora de Atracción de Talento",
            "People Partner", "Socio de Personas", "Jefe de Recursos Humanos",
            "Jefa de Recursos Humanos", "Analista Senior de RRHH",
            "Analista Senior de Recursos Humanos",
        ],
    ),
    RoleTier(
        tier=2,
        label="Recruiting, experiencia y cultura",
        titles=[
            "IT Recruiter", "Recruiter IT", "Tech Recruiter", "Reclutador IT", "Reclutadora IT",
            "Recruitment Specialist", "People Operations",
            "People Operations Specialist", "Especialista en Selección de Personal",
            "People Specialist", "People Experience", "Especialista en Experiencia del Empleado",
            "Analista de Talento y Cultura", "Coordinador de Capacitación y Desarrollo",
            "Coordinadora de Capacitación y Desarrollo", "Analista de Desarrollo Organizacional",
            "Employer Branding Specialist", "Especialista en Marca Empleadora",
            "Referente de Cultura Organizacional", "Consultor en RRHH", "Consultora en RRHH",
        ],
    ),
    RoleTier(
        tier=3,
        label="Operación senior, administración y soporte legal",
        titles=[
            "Analista de RRHH", "Analista de Recursos Humanos", "Analista de Selección de Personal",
            "Generalista de RRHH", "Generalista de Recursos Humanos", "HR Generalist",
            "Coordinador de RRHH", "Coordinadora de RRHH", "Responsable de RRHH",
            "Responsable de Recursos Humanos", "Analista de Clima y Cultura Laboral",
            "Asesor Legal-Laboral", "Asesora Legal-Laboral",
            "Especialista en Compensaciones y Beneficios", "Consultor de Talento Freelance",
            "Consultora de Talento Freelance", "Headhunter", "Asistente Administrativo",
            "Asistente Administrativa", "Auxiliar Administrativo", "Auxiliar Administrativa",
            "Coordinador Administrativo", "Coordinadora Administrativa", "Asistente Legal",
            "Asistente Jurídica", "Asistente Jurídico", "Auxiliar Legal", "Auxiliar Jurídica",
            "Auxiliar Jurídico", "Paralegal",
        ],
    ),
]

HR_TARGET_ROLES = [title for tier in ROMINA_ROLE_TIERS for title in tier.titles]


def build_role_tier_queries(role_tiers: list[RoleTier]) -> list[SearchQuery]:
    return [
        SearchQuery(
            role_tier=tier.tier,
            text=(
                "(" + " OR ".join(f'"{title}"' for title in tier.titles)
                + ") (remoto OR remote OR ((híbrido OR hibrido OR hybrid) Mendoza))"
            ),
            reason=f"Puestos de prioridad Tier {tier.tier} configurados por Romina.",
        )
        for tier in sorted(role_tiers, key=lambda item: item.tier)
        if tier.titles
    ]


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
    version="2026-08-12.1",
    owner_id="romina",
    owner_name="Romina Vanesa Roby",
    candidate_summary=(
        "Profesional de RRHH con más de 8 años de experiencia y más de 4 años "
        "trabajando 100% remoto. Perfil HRBP con base legal-laboral, recruiting IT "
        "y corporativo, experiencia del empleado, onboarding, clima y KPIs de RRHH."
    ),
    description=(
        "Vacantes semi-senior, senior o especialista: 100% remotas desde Argentina o "
        "híbridas únicamente en Mendoza. Se acepta inglés básico o intermedio; "
        "el inglés avanzado o fluido excluyente descalifica la oportunidad."
    ),
    target_roles=HR_TARGET_ROLES,
    role_tiers=ROMINA_ROLE_TIERS,
    location_policy=(
        "La publicación puede originarse en cualquier país, pero debe permitir trabajar "
        "desde Argentina mediante contratación local, LATAM, global o internacional. "
        "También se aceptan posiciones híbridas cuyo lugar presencial sea Mendoza."
    ),
    eligibility_policy=EligibilityPolicy(
        require_fully_remote=False,
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
        allowed_hybrid_locations=[
            "Mendoza", "Gran Mendoza", "Godoy Cruz", "Guaymallén", "Guaymallen",
            "Maipú", "Maipu", "Luján de Cuyo", "Lujan de Cuyo",
        ],
        required_description_language=None,
        require_spanish_application=False,
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
            "sin experiencia",
        ],
        excluded_role_terms=[
            "ventas", "vendedor", "vendedora", "ejecutivo comercial", "ejecutiva comercial",
            "call center", "telemarketer", "customer service", "atención al cliente",
            "atencion al cliente", "analista contable", "auxiliar contable",
            "asistente contable", "administración contable", "administracion contable",
            "administrativo contable", "administrativa contable", "contador", "contadora",
            "impuestos", "impositivo", "impositiva", "tax analyst", "bookkeeper",
        ],
        require_active_posting=True,
        minimum_salary_usd_monthly=1000,
    ),
    required_terms=["remoto", "remote", "híbrido", "hibrido", "hybrid", "Mendoza"],
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
    queries=build_role_tier_queries(ROMINA_ROLE_TIERS),
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
