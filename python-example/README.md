# Runnable Python REST API example

This FastAPI example complements the HTML guide in [`../site/`](../site/). It keeps its sample articles in memory, so changes reset when the server restarts.

## Run it

From this directory, create and activate a virtual environment, then install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app:app --reload
```

Requires Python 3.10 or later. On macOS or Linux, use `python3 -m venv .venv` and `source .venv/bin/activate` in place of the first two commands. Open <http://127.0.0.1:8000/docs> for interactive API documentation.

## Endpoints

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/v1/articles` | List articles with filters, sorting, and bounded pagination |
| `POST` | `/v1/articles` | Create an article; returns `201` and a `Location` header |
| `GET` | `/v1/articles/{articleId}` | Read one article or return `404` |
| `PATCH` | `/v1/articles/{articleId}` | Partially update an article |
| `DELETE` | `/v1/articles/{articleId}` | Delete an article; returns `204` |

Collection queries support `status` (`draft` or `published`), `authorId`, `createdAt[gte]` (ISO date), and `sort` (`title`, `status`, or `createdAt`; prefix a field with `-` for descending). Pagination uses one-based `page[number]`, defaults to 20 items, and caps `page[size]` at 100. Sorting is stable, with article ID as a tie-breaker.

For example:

```http
GET /v1/articles?status=published&authorId=u_42&createdAt%5Bgte%5D=2026-01-01&sort=-createdAt&page%5Bsize%5D=10&page%5Bnumber%5D=1
```

```json
{
  "data": [
    {
      "id": "art_101",
      "title": "Designing reliable APIs",
      "status": "published",
      "authorId": "u_42",
      "createdAt": "2026-01-15"
    }
  ],
  "pagination": {
    "page": 1,
    "size": 10,
    "totalPages": 1,
    "hasNext": false,
    "hasPrevious": false
  }
}
```

Create an article with:

```http
POST /v1/articles
Content-Type: application/json

{"title":"A predictable API","authorId":"u_42","status":"draft"}
```

The response is `201 Created`, includes the new article representation, and sets `Location` to its resource URL. Invalid input and unsupported query values return `400` with `Content-Type: application/problem+json`; the response follows RFC 9457 Problem Details and adds a request ID and field errors. For example, requesting `page[size]=101` reports the invalid parameter instead of silently clamping it.

## Run tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```
