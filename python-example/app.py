from __future__ import annotations

import logging
from datetime import date
from enum import Enum
from math import ceil
from typing import Annotated
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

app = FastAPI(title="REST API Design Guide example", version="1.0.0")


class ArticleStatus(str, Enum):
    draft = "draft"
    published = "published"


class Article(BaseModel):
    id: str
    title: str
    status: ArticleStatus
    author_id: str = Field(alias="authorId")
    created_at: date = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


ArticleTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)
]
AuthorId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)
]


class ArticleCreate(BaseModel):
    title: ArticleTitle
    author_id: AuthorId = Field(alias="authorId")
    status: ArticleStatus = ArticleStatus.draft

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ArticleUpdate(BaseModel):
    title: ArticleTitle | None = None
    status: ArticleStatus | None = None

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @model_validator(mode="after")
    def require_a_change(self) -> ArticleUpdate:
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Update fields cannot be null.")
        return self


class Pagination(BaseModel):
    page: int
    size: int
    totalPages: int
    hasNext: bool
    hasPrevious: bool


class ArticleList(BaseModel):
    data: list[Article]
    pagination: Pagination


INITIAL_ARTICLES = (
    Article(
        id="art_101",
        title="Designing reliable APIs",
        status=ArticleStatus.published,
        authorId="u_42",
        createdAt=date(2026, 1, 15),
    ),
    Article(
        id="art_102",
        title="Pagination that scales",
        status=ArticleStatus.published,
        authorId="u_17",
        createdAt=date(2026, 2, 2),
    ),
    Article(
        id="art_103",
        title="A draft about HTTP errors",
        status=ArticleStatus.draft,
        authorId="u_42",
        createdAt=date(2026, 3, 10),
    ),
)

# 2026-11-05: in-memory data keeps this sample focused on HTTP behavior, not persistence.
ARTICLES = list(INITIAL_ARTICLES)


def problem_response(
    request: Request,
    status: int,
    title: str,
    detail: str,
    problem_type: str,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "type": f"https://api.example.com/problems/{problem_type}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "requestId": request.state.request_id,
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(
        status_code=status,
        content=body,
        media_type="application/problem+json",
    )


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = f"req_{uuid4().hex[:12]}"
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    field_errors = [
        {
            "parameter": ".".join(str(part) for part in error["loc"][1:]) or "request",
            "code": "invalid_value",
            "message": "Value is invalid or outside the allowed range.",
        }
        for error in exc.errors()
    ]
    return problem_response(
        request,
        400,
        "Invalid request",
        "One or more request values are invalid.",
        "invalid-request",
        field_errors,
    )


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    if exc.status_code == 404:
        title, problem_type = "Resource not found", "not-found"
    else:
        title, problem_type = "Request failed", "http-error"
    detail = (
        exc.detail
        if isinstance(exc.detail, str)
        else "The request could not be completed."
    )
    return problem_response(request, exc.status_code, title, detail, problem_type)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled API error", exc_info=(type(exc), exc, exc.__traceback__)
    )
    return problem_response(
        request,
        500,
        "Internal server error",
        "An unexpected error occurred.",
        "internal-error",
    )


class InvalidSortParameter(Exception):
    pass


def parse_sort(sort: str | None) -> list[tuple[str, bool]]:
    allowed_fields = {"title", "createdAt", "status"}
    if sort is None:
        return [("createdAt", True)]

    terms: list[tuple[str, bool]] = []
    seen: set[str] = set()
    for raw_term in sort.split(","):
        descending = raw_term.startswith("-")
        field = raw_term[1:] if descending else raw_term
        if field not in allowed_fields or field in seen:
            raise InvalidSortParameter()
        seen.add(field)
        terms.append((field, descending))
    return terms


@app.exception_handler(InvalidSortParameter)
async def invalid_sort_handler(
    request: Request, exc: InvalidSortParameter
) -> JSONResponse:
    return problem_response(
        request,
        400,
        "Invalid query parameter",
        "The requested sort field is not supported.",
        "invalid-query",
        [
            {
                "parameter": "sort",
                "code": "unsupported_field",
                "message": "Allowed sort fields: createdAt, status, title.",
            }
        ],
    )


@app.get("/v1/articles", response_model=ArticleList)
def list_articles(
    status: ArticleStatus | None = None,
    author_id: str | None = Query(
        default=None, alias="authorId", min_length=1, max_length=80
    ),
    created_at_gte: date | None = Query(default=None, alias="createdAt[gte]"),
    sort: str | None = Query(default=None, max_length=100),
    page_size: int = Query(default=20, alias="page[size]", ge=1, le=100),
    page_number: int = Query(default=1, alias="page[number]", ge=1),
) -> ArticleList:
    matches = [
        article
        for article in ARTICLES
        if (status is None or article.status == status)
        and (author_id is None or article.author_id == author_id)
        and (created_at_gte is None or article.created_at >= created_at_gte)
    ]

    sort_terms = parse_sort(sort)
    # Stable sorts applied from least- to most-significant field preserve multi-field order.
    matches.sort(key=lambda article: article.id)
    for field, descending in reversed(sort_terms):
        key = {
            "title": lambda article: article.title.casefold(),
            "createdAt": lambda article: article.created_at,
            "status": lambda article: article.status.value,
        }[field]
        matches.sort(key=key, reverse=descending)

    total = len(matches)
    start = (page_number - 1) * page_size
    page = matches[start : start + page_size]
    return ArticleList(
        data=page,
        pagination=Pagination(
            page=page_number,
            size=page_size,
            totalPages=ceil(total / page_size),
            hasNext=start + page_size < total,
            hasPrevious=page_number > 1 and start < total,
        ),
    )


@app.get("/v1/articles/{article_id}", name="get_article", response_model=Article)
def get_article(article_id: str) -> Article:
    for article in ARTICLES:
        if article.id == article_id:
            return article
    raise StarletteHTTPException(
        status_code=404, detail="No article was found with that ID."
    )


@app.post("/v1/articles", status_code=201, response_model=Article)
def create_article(
    payload: ArticleCreate, response: Response, request: Request
) -> Article:
    article = Article(
        id=f"art_{uuid4().hex[:12]}",
        title=payload.title,
        status=payload.status,
        authorId=payload.author_id,
        createdAt=date.today(),
    )
    ARTICLES.append(article)
    response.headers["Location"] = str(
        request.url_for("get_article", article_id=article.id)
    )
    return article


@app.patch("/v1/articles/{article_id}", response_model=Article)
def update_article(article_id: str, payload: ArticleUpdate) -> Article:
    for index, article in enumerate(ARTICLES):
        if article.id == article_id:
            updated = article.model_copy(update=payload.model_dump(exclude_unset=True))
            ARTICLES[index] = updated
            return updated
    raise StarletteHTTPException(
        status_code=404, detail="No article was found with that ID."
    )


@app.delete("/v1/articles/{article_id}", status_code=204)
def delete_article(article_id: str) -> None:
    for index, article in enumerate(ARTICLES):
        if article.id == article_id:
            ARTICLES.pop(index)
            return
    raise StarletteHTTPException(
        status_code=404, detail="No article was found with that ID."
    )


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
