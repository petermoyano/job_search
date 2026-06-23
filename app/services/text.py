import re


def normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.split("\n")]
    return "\n".join(line for line in lines if line)


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def evidence_for(text: str, term: str, window: int = 80) -> str | None:
    match = re.search(re.escape(term), text, flags=re.IGNORECASE)
    if not match:
        return None
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    return compact_text(text[start:end])
