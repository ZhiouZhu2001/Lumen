from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request

from app.channels.schemas import BookDetails
from app.repository import StorageUnavailable
from app.sources.isbn import to_isbn13

router = APIRouter(prefix="/api")


@router.get("/books/{isbn13}", response_model=BookDetails)
async def book_details(
    isbn13: Annotated[str, Path(pattern=r"^[0-9]{13}$")], request: Request
):
    if to_isbn13(isbn13) != isbn13:
        raise HTTPException(status_code=422, detail="A valid ISBN-13 is required")
    try:
        book = await request.app.state.repository.get_book(isbn13)
    except StorageUnavailable:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "upstream_unavailable",
                "message": "Book details are temporarily unavailable.",
            },
        ) from None
    if book is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_found",
                "message": "This book has not been saved yet.",
            },
        )
    refresher = getattr(request.app.state, "book_refresh", None)
    if refresher is not None:
        book = await refresher.refresh(book)
    return book
