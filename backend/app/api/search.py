from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.sources.schemas import BookCandidate, Language

router = APIRouter(prefix="/api")


class SearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=300)
    language: Language


class SearchResponse(BaseModel):
    books: list[BookCandidate]


@router.post("/search")
async def search(request: SearchRequest) -> SearchResponse:
    # Step 2: a fixed fake answer. Step 3 will call the real APIs.
    fake_book = BookCandidate(
        isbn13="9780307474728",
        title=f"Fake result for: {request.query}",
        authors=["Lumen"],
        language=request.language,
        source="fake",
    )
    return SearchResponse(books=[fake_book])
