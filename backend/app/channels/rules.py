from pathlib import Path
from string import Formatter
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.channels.matching import normalize, safe_url
from app.channels.schemas import BookFormat, BookLink
from app.sources.isbn import to_isbn13
from app.sources.schemas import BookCandidate, Language

DEFAULT_RULES = Path(__file__).resolve().parent.parent / "stores.yaml"


class StoreRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    label: str
    host: str = Field(pattern=r"^[a-z0-9.-]+$")
    languages: list[Language] = Field(min_length=1)
    genres: list[str] = []
    formats: list[BookFormat] = Field(min_length=1)
    mode: Literal["search", "lookup"]
    provider: Literal["apple_books", "gutenberg"] | None = None
    url_template: str | None = None

    @model_validator(mode="after")
    def check_method(self):
        if self.mode == "lookup":
            if self.provider is None or self.url_template is not None:
                raise ValueError("Lookup rules need a provider and no URL template")
            hosts = {"apple_books": "books.apple.com", "gutenberg": "gutenberg.org"}
            if self.host != hosts[self.provider]:
                raise ValueError("Lookup host must match its provider")
        else:
            if not self.url_template or self.provider is not None:
                raise ValueError("Search rules need a URL template and no provider")
            fields = [
                (name, spec, conversion)
                for _, name, spec, conversion in Formatter().parse(self.url_template)
                if name is not None
            ]
            if fields != [("isbn13", "", None)]:
                raise ValueError(
                    "Templates must contain one plain {isbn13} placeholder"
                )
            if not safe_url(
                self.url_template.format(isbn13="9780141439518"), self.host
            ):
                raise ValueError("Template host must match its HTTPS store host")
        return self


class StoreRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stores: list[StoreRule]

    @model_validator(mode="after")
    def unique_ids(self):
        if len({rule.id for rule in self.stores}) != len(self.stores):
            raise ValueError("Store IDs must be unique")
        return self


def load_rules(path: Path = DEFAULT_RULES) -> list[StoreRule]:
    return StoreRules.model_validate(yaml.safe_load(path.read_text("utf-8"))).stores


def applies(rule: StoreRule, book: BookCandidate) -> bool:
    genres = " " + normalize(" ".join(book.genres)) + " "
    return book.language in rule.languages and (
        not rule.genres
        or any(" " + normalize(genre) + " " in genres for genre in rule.genres)
    )


def search_links(book: BookCandidate, rules: list[StoreRule]) -> list[BookLink]:
    if to_isbn13(book.isbn13) != book.isbn13:
        raise ValueError("Book cards require a valid retrieved ISBN-13")
    return [
        BookLink(
            store=rule.id,
            label=rule.label,
            url=rule.url_template.format(isbn13=book.isbn13),
            formats=rule.formats,
            match="isbn_search",
        )
        for rule in rules
        if rule.mode == "search" and applies(rule, book)
    ]
