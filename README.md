# Direct Product Job Radar

## Overview

**Direct Product Job Radar** is an AI-powered job intelligence system for software engineers, AI engineers, and technical professionals who want to identify real direct product opportunities while avoiding recruiter-heavy, outsourced, third-party, or staff augmentation processes.

The app is designed around a simple but important idea:

> Job search should not be optimized only for volume. It should be optimized for opportunity quality.

Many strong candidates receive frequent inbound recruiter messages, but those opportunities often lead to long, inefficient processes involving staffing agencies, hidden clients, vendor interviews, client interviews, unclear salary ranges, and limited ownership of the product being built.

This project helps detect those signals early.

The MVP focuses on analyzing job opportunities, classifying them, scoring them, and producing transparent recommendations.

It does **not** automatically apply to jobs in the first version.

## Problem

The target user is a technical candidate who wants to work directly for companies building their own products.

The current job search experience has several problems:

* Too many recruiter messages with unclear opportunity quality
* Hidden end clients
* Staffing or outsourcing models disguised as product roles
* Multiple technical interviews before meeting the actual hiring company
* Vague job descriptions
* Weak AI engineering roles presented as strong AI opportunities
* Long processes with poor salary and role transparency
* Too much manual effort required to separate good opportunities from noisy ones

The goal of this app is to reduce that noise.

## Product Goal

The product should turn unstructured job opportunities into structured, scored, auditable intelligence.

Each job opportunity should move through this workflow:

**Ingestion → Normalization → Classification → Scoring → Human Review → Recommended Action**

The app should help answer:

* Is this job direct with the company that owns the product?
* Is this role likely connected to staffing, outsourcing, or staff augmentation?
* Is the company building its own product?
* Is the technical stack aligned with the candidate profile?
* Is the role a real AI engineering opportunity?
* How risky or time-consuming does the interview process look?
* Should the candidate discard, review, apply, or investigate further?

## Initial User

The initial user is a single AI Engineer / Full-stack Developer.

However, the app should be designed so it can become multi-user later.

The first version is personal-first, but not personal-only.

Future versions may allow users to:

* Upload a CV
* Define target roles
* Select preferred locations
* Configure deal-breakers
* Define scoring weights
* Receive a ranked list of opportunities
* Export results
* Eventually connect job sources and email inboxes

## MVP Scope

The MVP is backend-only.

No frontend is required for the first version.

The MVP should support:

* Candidate profile creation
* CV text ingestion
* CV-to-structured-profile extraction using LLM structured outputs
* Manual job post submission
* Job post normalization
* Job facts extraction
* Intermediary and staffing signal detection
* Product ownership scoring
* Directness scoring
* Technical fit scoring
* AI depth scoring
* Process risk scoring
* Overall recommendation generation
* Human review and decision tracking
* Persistence in PostgreSQL
* API-first interaction

## Non-Goals for MVP

The MVP should **not** include:

* Automatic job applications
* Automatic LinkedIn messaging
* Automatic outreach to hiring managers
* Full frontend
* Chrome extension
* Browser automation as a core dependency
* Heavy scraping-first architecture
* Multi-user SaaS billing
* Resume tailoring
* Cover letter generation

These can be considered later.

## Core Workflow

The core workflow is a repeatable, auditable, scoring-based process.

Initial graph:

**NewJobLead**
→ **NormalizeJobText**
→ **ExtractStructuredJobFacts**
→ **ResolveCompanyType**
→ **DetectIntermediarySignals**
→ **ScoreAgainstCandidateProfile**
→ **ScoreProcessRisk**
→ **ScoreProductOwnership**
→ **GenerateRecommendation**
→ **HumanReview**
→ **PersistDecision**

Each node should have a clear responsibility and should produce traceable output.

## Why LangGraph

LangGraph is the right fit for this app because the product is not a single prompt or a simple chatbot.

It is a stateful workflow where each opportunity passes through multiple explicit stages.

The app needs:

* Stateful processing
* Explicit graph nodes
* Human-in-the-loop review
* Auditable intermediate outputs
* Long-term extensibility
* Hybrid deterministic and LLM-based logic
* Future support for recurring workflows and background agents

The graph should not be overcomplicated, but the architecture should make it easy to add new nodes later.

## Technical Stack

Initial stack:

* Python
* LangGraph
* LangChain where useful
* FastAPI
* PostgreSQL-compatible database
* SQLAlchemy or SQLModel
* Alembic
* Pydantic
* Docker Compose

The database should be compatible with Neon PostgreSQL.

The app should be designed so it can eventually be exported or deployed to AWS.

Possible future AWS services:

* ECS Fargate or App Runner
* RDS PostgreSQL
* S3
* EventBridge Scheduler
* Secrets Manager
* CloudWatch
* Bedrock

## Local and Cloud LLM Strategy

The first version may use cloud LLMs for structured extraction and reasoning.

The app should be designed so local inference can be added later.

Possible future local inference stack:

* Ollama
* Hugging Face Transformers
* Quantized local models
* Local embeddings
* Batch classification using a local GPU

Local inference is a future optimization, not a requirement for MVP.

## Scoring Philosophy

The scoring system must be transparent.

The app should not return a mysterious “AI says this is good” result.

Every opportunity should include a score breakdown that can eventually be exported to a spreadsheet.

The scoring system should combine:

* Deterministic rules
* Configurable weights
* LLM-based structured extraction
* Human review

The LLM should help interpret messy text, but it should not secretly control the entire decision.

## Scoring Layers

### 1. Directness Score

Measures whether the candidate would be hired directly by the company that owns the product.

Positive signals:

* Company-owned careers page
* Direct application link
* Internal product team
* Full-time employee
* Clear company identity
* Clear reporting line
* Hiring manager involved early

Negative signals:

* Client
* End client
* Confidential client
* Staff augmentation
* Outsourcing
* Vendor
* Consulting
* Implementation partner
* Nearshore
* Allocated to projects
* Multiple clients
* Client interview after vendor interview

### 2. Product Ownership Score

Measures whether the job involves building a product owned by the company.

Positive signals:

* Own platform
* SaaS product
* Product team
* Product roadmap
* Customer-facing product
* Internal AI product
* Product engineering culture

Negative signals:

* Client projects
* Delivery team
* Consulting engagement
* Services-only delivery
* Rotating client assignments

### 3. Technical Fit Score

Measures alignment with the candidate’s target profile.

Example signals:

* Python
* TypeScript
* Next.js
* React
* Node.js
* PostgreSQL
* LangChain
* LangGraph
* LlamaIndex
* RAG
* Agents
* Tool calling
* Function calling
* AI SDK
* Vector databases
* LLM evaluation
* Ollama
* Hugging Face
* Local inference

This list must be configurable through the candidate profile.

### 4. AI Depth Score

Measures whether the opportunity involves real AI engineering work.

Positive signals:

* RAG
* Agents
* Tool calling
* Function calling
* Evals
* Model routing
* Observability
* Embeddings
* Retrieval
* Fine-tuning
* LLMOps
* Inference optimization
* AI product features

Negative signals:

* Prompt engineering only
* Basic chatbot only
* No-code automation only
* Vague AI transformation language
* No clear engineering ownership

### 5. Process Risk Score

Measures how likely the process is to waste time.

High-risk signals:

* Recruiter screen
* Vendor technical interview
* Client technical interview
* Client final interview
* Long take-home project
* No salary range
* Confidential client
* More than four stages
* Details only disclosed in a call

Low-risk signals:

* Direct hiring manager conversation
* Clear salary range
* Clear company
* Clear role scope
* Two to three interview stages
* Technical discussion with the product team

## Candidate Profile

The app should support configurable candidate profiles.

A candidate profile should include:

* Target roles
* Preferred locations
* Time zone preferences
* Work modality preferences
* Seniority
* Technical skills
* AI skills
* Languages
* Compensation preferences
* Deal-breakers
* Scoring weights
* Preferred company types
* Negative company types

Example target roles:

* AI Engineer
* Full-stack AI Engineer
* Applied AI Engineer
* LLM Engineer
* AI Product Engineer
* Backend AI Engineer
* RAG Engineer
* Agentic AI Engineer

The system should not hardcode a single candidate’s preferences into the scoring logic.

## Deal-Breakers

Deal-breakers should be configurable.

Examples:

* Staffing
* Staff augmentation
* Outsourcing
* Hidden client
* Third-party vendor
* More than N interview stages
* No company name disclosed
* No salary range
* Contractor-only
* Time zone mismatch
* No hands-on coding
* No meaningful AI engineering work

A job that triggers a deal-breaker should still be analyzed, but clearly marked.

## Data Model

Initial entities:

* User
* CandidateProfile
* CandidateCV
* JobLead
* Company
* JobSource
* JobAnalysis
* ScoreBreakdown
* DetectedSignal
* HumanDecision
* AppConfig

The MVP can run with one user, but the database design should not block future multi-user support.

## Initial API

Suggested API capabilities:

* Create candidate profile
* List candidate profiles
* Upload or paste CV text
* Extract structured profile from CV text
* Submit job post manually
* Analyze job post
* List analyzed job posts
* Get job analysis details
* Save human decision
* Get scoring configuration

The API should return structured, inspectable data.

## Initial Ingestion Strategy

The first ingestion mode is manual job post submission.

Later ingestion sources may include:

* Recruiter emails
* LinkedIn job alerts received by email
* Public career pages
* Greenhouse
* Lever
* Ashby
* Wellfound
* YC Work at a Startup
* Remote job boards
* Controlled scraping sources

LinkedIn integration should be treated carefully. The MVP should not depend on direct LinkedIn automation. The system should be able to analyze LinkedIn job text when provided manually or through acceptable channels.

## Human Review

The app should keep a human in the loop.

Possible human decisions:

* Discard
* Save for later
* Investigate company
* Apply directly
* Contact hiring manager
* Needs more information
* Blocked by deal-breaker

The app should store both the system recommendation and the human decision.

## Recommended Actions

Possible app-generated recommendations:

* Strong fit: apply directly
* Strong fit: investigate company first
* Good technical fit but unclear directness
* Likely staffing: discard
* Product company but weak technical fit
* High process risk: proceed only if compensation is strong
* Missing data: request more information

## Nice to Have / Future Features

Future features may include:

* Next.js frontend
* User authentication
* Multi-user SaaS mode
* CSV / Excel export
* Email ingestion
* Gmail integration
* Scheduled job source monitoring
* Career page crawlers
* Greenhouse / Lever / Ashby connectors
* Company enrichment
* Hiring manager discovery
* Outreach generation
* Resume tailoring
* Cover letter generation
* LinkedIn alert parsing
* Browser extension
* Local LLM inference
* GPU-accelerated batch scoring
* Embeddings and semantic matching
* PostgreSQL pgvector support
* LangSmith tracing and evals
* AWS deployment
* Background workers
* Notification system
* Opportunity lifecycle tracking
* Interview process tracker
* Personal CRM for job search
* Team mode for career coaches or recruiters
* Benchmark dataset for job classification
* Model evaluation suite

## Guiding Principles

* Analyze before acting
* Prefer direct product opportunities
* Avoid wasting candidate time
* Keep scoring transparent
* Make preferences configurable
* Keep humans in control
* Separate extraction from scoring
* Use LLMs where they help, not everywhere
* Build a product, not just a script
* Start simple, but design for extensibility

## MVP Success Criteria

The first successful milestone is:

A user can paste CV text, define target roles and deal-breakers, paste a job description, run the LangGraph workflow, and receive a persisted transparent score breakdown with a recommended action.

## ToDos

* Define initial repository structure
* Set up Python project configuration
* Add FastAPI application skeleton
* Add PostgreSQL database configuration
* Add SQLAlchemy or SQLModel models
* Add Alembic migrations
* Define Pydantic schemas
* Define CandidateProfile schema
* Define CandidateCV schema
* Define JobLead schema
* Define JobAnalysis schema
* Define ScoreBreakdown schema
* Define DetectedSignal schema
* Define HumanDecision schema
* Create first LangGraph workflow skeleton
* Implement manual job post ingestion
* Implement CV text ingestion
* Implement CV-to-structured-profile extraction
* Implement job post structured extraction
* Implement deterministic intermediary signal detection
* Implement directness scoring
* Implement product ownership scoring
* Implement technical fit scoring
* Implement AI depth scoring
* Implement process risk scoring
* Implement overall recommendation generation
* Persist analysis results
* Persist human decisions
* Add API endpoint for candidate profile creation
* Add API endpoint for CV ingestion
* Add API endpoint for job submission
* Add API endpoint for job analysis
* Add API endpoint for listing analyzed jobs
* Add API endpoint for reading job analysis details
* Add API endpoint for saving human decision
* Add basic tests for scoring rules
* Add basic tests for graph workflow
* Add sample candidate profile
* Add sample job posts for testing
* Add documentation for local setup
* Add documentation for scoring logic
* Add documentation for future ingestion sources
