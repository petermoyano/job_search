from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class PdfTextExtractionError(Exception):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message


@dataclass(frozen=True)
class ExtractedPdfText:
    text: str
    total_characters: int
    input_characters: int
    page_count: int
    truncated: bool


class PdfTextExtractor:
    def __init__(self, *, minimum_characters: int, maximum_characters: int) -> None:
        self.minimum_characters = minimum_characters
        self.maximum_characters = maximum_characters

    def extract(self, content: bytes) -> ExtractedPdfText:
        try:
            reader = PdfReader(BytesIO(content), strict=False)
            pages = [
                self._normalize_page(page.extract_text() or "") for page in reader.pages
            ]
        except (PdfReadError, OSError, ValueError, KeyError) as exc:
            raise PdfTextExtractionError(
                code="PDF_TEXT_EXTRACTION_FAILED",
                message="PDF text could not be parsed",
            ) from exc

        useful_characters = sum(len(re.sub(r"\s+", "", page)) for page in pages)
        if useful_characters < self.minimum_characters:
            raise PdfTextExtractionError(
                code="PDF_TEXT_NOT_EXTRACTABLE",
                message="PDF does not contain enough extractable text",
            )

        page_sections = [
            f"--- Page {page_number} ---\n{page}"
            for page_number, page in enumerate(pages, start=1)
            if page
        ]
        full_text = "\n\n".join(page_sections)
        total_characters = len(full_text)
        truncated = total_characters > self.maximum_characters
        model_text = full_text[: self.maximum_characters]
        return ExtractedPdfText(
            text=model_text,
            total_characters=total_characters,
            input_characters=len(model_text),
            page_count=len(pages),
            truncated=truncated,
        )

    @staticmethod
    def _normalize_page(text: str) -> str:
        normalized_lines: list[str] = []
        previous_blank = False
        for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = re.sub(r"[\t \f\v]+", " ", raw_line).strip()
            if line:
                normalized_lines.append(line)
                previous_blank = False
            elif normalized_lines and not previous_blank:
                normalized_lines.append("")
                previous_blank = True
        while normalized_lines and not normalized_lines[-1]:
            normalized_lines.pop()
        return "\n".join(normalized_lines)
