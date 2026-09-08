from __future__ import annotations

import os


# This must run before test modules import app.db.session. It prevents a developer's
# local .env (including a Neon URL) from ever becoming the test database.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DATABASE_URL_SSM_PARAMETER"] = ""
os.environ["INITIALIZE_DATABASE"] = "true"

# Optional providers must never consume quota using developer credentials.
os.environ["JOB_SEARCH_EXTERNAL_API_SECRET_NAME"] = ""
os.environ["SERPER_API_KEY"] = ""
os.environ["SERPAPI_API_KEY"] = ""
os.environ["RAPIDAPI_KEY"] = ""
