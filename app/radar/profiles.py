from __future__ import annotations

from app.radar.models import ScoringGroup, SearchProfile, SearchQuery


ROMINA_SOURCE_REFERENCES = [
    "https://www.zonajobs.com.ar",
    "https://www.infojobs.net",
    "https://www.computrabajo.com.ar",
    "https://www.trabajando.com",
    "https://www.bumeran.com.ar",
    "https://www.jobleads.com",
    "https://ar.jooble.org",
    "https://remolatam.com",
    "https://www.remlist.com",
    "https://ar.indeed.com",
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

HR_TARGET_ROLES = [
    "HR Business Partner",
    "Recursos Humanos",
    "Analista de Recursos Humanos",
    "Analista de Capital Humano",
    "Talent Acquisition",
    "Recruiter IT",
    "Reclutamiento y Selecci?n",
    "People Operations",
    "Onboarding",
    "Employee Experience",
    "Responsable de Recursos Humanos",
    "Especialista en Recursos Humanos",
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
            "reclutamiento y selecci?n",
            "seleccion de personal",
            "selecci?n de personal",
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
            "evaluacion de desempe?o",
            "evaluaci?n de desempe?o",
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
            "inducci?n",
            "capacitacion",
            "capacitaci?n",
            "gestion integral",
            "gesti?n integral",
        ],
    ),
]

ENGLISH_REQUIRED_GROUP = ScoringGroup(
    label="required English",
    points=70,
    terms=[
        "ingles avanzado",
        "ingl?s avanzado",
        "ingles excluyente",
        "ingl?s excluyente",
        "advanced english",
        "english required",
        "bilingual",
        "bilingue",
        "biling?e",
        "nivel avanzado de ingles",
        "nivel avanzado de ingl?s",
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
    name="Romina - Remote Spanish HR",
    owner_id="romina",
    owner_name="Romina Roby",
    description=(
        "Find remote Spanish-language HR, recruiting, HRBP, and people operations "
        "roles for an Argentina/LATAM-based candidate who does not speak English."
    ),
    target_roles=HR_TARGET_ROLES,
    location_policy=(
        "Prefer remote roles open to Argentina or LATAM. Spanish-language roles are "
        "strongly preferred; roles requiring English should be rejected."
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
        "seleccion",
        "selecci?n",
        "hr business partner",
        "recruiter it",
        "onboarding",
    ],
    reject_terms=ENGLISH_REQUIRED_GROUP.terms,
    positive_scoring_groups=[
        ScoringGroup(
            label="remote Spanish/LATAM fit",
            points=22,
            terms=[
                "remoto",
                "trabajo remoto",
                "modalidad remota",
                "latam",
                "argentina",
                "america latina",
                "am?rica latina",
            ],
        ),
        *HR_POSITIVE_GROUPS,
        ScoringGroup(
            label="Spanish-friendly signal",
            points=12,
            terms=[
                "espa?ol",
                "sin ingles",
                "sin ingl?s",
                "no requiere ingles",
                "no requiere ingl?s",
            ],
        ),
    ],
    negative_scoring_groups=[ENGLISH_REQUIRED_GROUP],
    source_references=ROMINA_SOURCE_REFERENCES,
    queries=[
        SearchQuery(
            text='"Recursos Humanos" "remoto" "Argentina" empleo',
            reason="Spanish-language HR roles open to remote Argentina candidates.",
        ),
        SearchQuery(
            text='"HR Business Partner" "remoto" "LATAM" "sin ingl?s"',
            reason="Remote HRBP roles that may explicitly avoid English requirements.",
        ),
        SearchQuery(
            text='"Recruiter IT" "remoto" "Argentina"',
            reason="Remote IT recruiting roles in Argentina.",
        ),
        SearchQuery(
            text='"Analista de Recursos Humanos" "trabajo remoto" "Argentina"',
            reason="Remote HR analyst roles in Argentina.",
        ),
        SearchQuery(
            text='"Talent Acquisition" "remoto" "Argentina" "Recursos Humanos"',
            reason="Talent acquisition roles with Spanish HR context.",
        ),
    ],
    max_results_per_query=8,
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
        "maip?",
        "godoy cruz",
        "guaymallen",
        "guaymall?n",
        "lujan de cuyo",
        "luj?n de cuyo",
    ],
    preferred_terms=[
        "mendoza",
        "gran mendoza",
        "presencial",
        "hibrido",
        "h?brido",
        "maipu",
        "maip?",
        "godoy cruz",
        "guaymallen",
        "guaymall?n",
        "lujan de cuyo",
        "luj?n de cuyo",
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
        "reubicaci?n",
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
                "maip?",
                "godoy cruz",
                "guaymallen",
                "guaymall?n",
                "lujan de cuyo",
                "luj?n de cuyo",
            ],
        ),
        ScoringGroup(
            label="onsite or hybrid modality",
            points=15,
            terms=["presencial", "hibrido", "h?brido", "modalidad presencial"],
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
                "c?rdoba",
                "rosario",
                "relocation required",
                "reubicacion",
                "reubicaci?n",
            ],
        ),
        ScoringGroup(
            label="payroll/admin-only role",
            points=20,
            terms=[
                "liquidacion de sueldos exclusivamente",
                "liquidaci?n de sueldos exclusivamente",
                "solo payroll",
                "payroll only",
                "administrativo exclusivamente",
            ],
        ),
    ],
    source_references=ROMINA_SOURCE_REFERENCES,
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
            text='"Analista de Recursos Humanos" "Mendoza" "h?brido"',
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
        raise ValueError(f"Unknown radar profile '{profile_id}'. Supported: {supported}") from exc
