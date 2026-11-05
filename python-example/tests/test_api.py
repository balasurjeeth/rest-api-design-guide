from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app, "ARTICLES", list(deepcopy(app.INITIAL_ARTICLES)))
    return TestClient(app.app)


def test_list_articles_filters_sorts_and_paginates(client):
    response = client.get(
        "/v1/articles?status=published&sort=-createdAt&page[size]=1"
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["id"] == "art_102"
    assert response.json()["pagination"] == {
        "page": 1,
        "size": 1,
        "totalPages": 2,
        "hasNext": True,
        "hasPrevious": False,
    }


def test_list_articles_filters_by_author_and_date(client):
    response = client.get(
        "/v1/articles?authorId=u_42&createdAt%5Bgte%5D=2026-02-01"
    )

    assert response.status_code == 200
    assert [article["id"] for article in response.json()["data"]] == ["art_103"]


def test_invalid_page_size_returns_problem_details(client):
    response = client.get("/v1/articles?page[size]=101")

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.headers["x-request-id"] == response.json()["requestId"]
    assert response.json()["errors"][0]["parameter"] == "page[size]"


def test_unsupported_sort_field_returns_problem_details(client):
    response = client.get("/v1/articles?sort=databaseSecret")

    assert response.status_code == 400
    assert response.json()["errors"][0] == {
        "parameter": "sort",
        "code": "unsupported_field",
        "message": "Allowed sort fields: createdAt, status, title.",
    }


def test_create_read_update_and_delete_article(client):
    created = client.post(
        "/v1/articles",
        json={"title": "A useful new article", "authorId": "u_88"},
    )

    assert created.status_code == 201
    assert created.headers["location"].endswith(f"/v1/articles/{created.json()['id']}")
    assert created.json()["status"] == "draft"

    article_id = created.json()["id"]
    updated = client.patch(f"/v1/articles/{article_id}", json={"status": "published"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "published"

    deleted = client.delete(f"/v1/articles/{article_id}")
    assert deleted.status_code == 204
    assert client.get(f"/v1/articles/{article_id}").status_code == 404


def test_invalid_body_and_missing_article_use_problem_details(client):
    invalid = client.post("/v1/articles", json={"title": "x", "authorId": "u_1"})
    missing = client.get("/v1/articles/not_a_real_id")

    assert invalid.status_code == 400
    assert invalid.headers["content-type"].startswith("application/problem+json")
    assert missing.status_code == 404
    assert missing.json()["status"] == 404
    assert missing.json()["type"].endswith("/not-found")
