from functools import lru_cache
import os

from dotenv import load_dotenv

load_dotenv()


def s(*codes):
    return bytes(codes).decode()


class Settings:
    app_env: str = os.getenv(s(65,80,80,95,69,78,86), s(108,111,99,97,108))
    database_url: str = os.getenv(s(68,65,84,65,66,65,83,69,95,85,82,76), s(115,113,108,105,116,101,58,47,47,47,46,47,106,111,98,95,114,97,100,97,114,46,100,98))
    openai_api_key: str = os.getenv(s(79,80,69,78,65,73,95,65,80,73,95,75,69,89), s())
    tavily_api_key: str = os.getenv(s(84,65,86,73,76,89,95,65,80,73,95,75,69,89), s())
    llm_model: str = os.getenv(s(76,76,77,95,77,79,68,69,76), s(103,112,116,45,52,46,49,45,109,105,110,105))


@lru_cache
def get_settings() -> Settings:
    return Settings()
