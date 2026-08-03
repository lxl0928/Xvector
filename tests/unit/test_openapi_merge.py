from __future__ import annotations

import logging

from xvector.gateway.openapi_merge import infer_resource, merge_schemas, tag_for_path


def test_infer_resource_mapping():
    assert infer_resource("/v2/vectordb/collections/list") == "Collection"
    assert infer_resource("/v2/vectordb/entities/search") == "Vector"
    assert infer_resource("/v2/vectordb/databases/list") == "Database"
    assert infer_resource("/v2/vectordb/jobs/import/create") == "Import"
    assert infer_resource("/v2/vectordb/import/create") == "Import"
    assert infer_resource("/v2/vectordb/aliases/list") == "Alias"


def test_gateway_special_tags():
    assert tag_for_path("/healthz", "Gateway") == "Gateway / System"
    assert tag_for_path("/openapi/refresh", "Gateway") == "Gateway / Admin"
    assert tag_for_path("/v2/vectordb/auth", "Gateway") == "Gateway / System"


def test_merge_hides_internal_and_full_path_and_sets_security():
    gateway = {
        "openapi": "3.1.0",
        "info": {"title": "gw", "version": "0.1.0"},
        "paths": {
            "/healthz": {"get": {"responses": {"200": {"description": "ok"}}}},
            "/v2/vectordb/auth": {"post": {"responses": {"200": {"description": "ok"}}}},
            "/openapi/refresh": {"post": {"responses": {"200": {"description": "ok"}}}},
            "/v2/vectordb/{full_path:path}": {
                "post": {"responses": {"200": {"description": "proxy"}}}
            },
        },
    }
    writer = {
        "openapi": "3.1.0",
        "info": {"title": "w", "version": "0.1.0"},
        "paths": {
            "/v2/vectordb/collections/list": {
                "post": {"responses": {"200": {"description": "ok"}}, "tags": ["Collection"]}
            },
            "/internal/auth/verify": {
                "post": {"responses": {"200": {"description": "ok"}}}
            },
        },
    }
    reader = {
        "openapi": "3.1.0",
        "info": {"title": "r", "version": "0.1.0"},
        "paths": {
            "/v2/vectordb/entities/search": {
                "post": {"responses": {"200": {"description": "ok"}}}
            },
        },
    }
    merged = merge_schemas(gateway, writer, reader, include_internal=False)
    paths = merged["paths"]
    assert "/v2/vectordb/{full_path:path}" not in paths
    assert "/internal/auth/verify" not in paths
    assert paths["/v2/vectordb/collections/list"]["post"]["tags"] == ["Writer / Collection"]
    assert paths["/v2/vectordb/entities/search"]["post"]["tags"] == ["Reader / Vector"]
    assert paths["/v2/vectordb/auth"]["post"]["security"] == [{"BearerAuth": []}]
    assert "security" not in paths["/healthz"]["get"]
    assert "security" not in paths["/openapi/refresh"]["post"]
    assert "BearerAuth" in merged["components"]["securitySchemes"]
    assert merged["info"]["title"] == "Xvector API"
    assert "Base URL" in merged["info"]["description"]
    tag_names = [t["name"] for t in merged["tags"]]
    assert tag_names[0] == "Gateway / System"
    assert "Gateway / Admin" in tag_names
    assert "Writer / Collection" in tag_names
    assert "Reader / Vector" in tag_names


def test_writer_wins_over_reader_on_conflict():
    gateway = {"openapi": "3.1.0", "info": {}, "paths": {}}
    writer = {
        "paths": {
            "/v2/vectordb/collections/list": {
                "post": {"summary": "from-writer", "responses": {"200": {"description": "ok"}}}
            }
        }
    }
    reader = {
        "paths": {
            "/v2/vectordb/collections/list": {
                "post": {"summary": "from-reader", "responses": {"200": {"description": "ok"}}}
            }
        }
    }
    merged = merge_schemas(gateway, writer, reader)
    assert merged["paths"]["/v2/vectordb/collections/list"]["post"]["summary"] == "from-writer"
    assert merged["paths"]["/v2/vectordb/collections/list"]["post"]["tags"] == ["Writer / Collection"]


def test_gateway_wins_over_writer_on_same_path(caplog):
    gateway = {
        "openapi": "3.1.0",
        "info": {},
        "paths": {
            "/healthz": {"get": {"summary": "gw-health", "responses": {"200": {"description": "ok"}}}},
            "/readyz": {"get": {"summary": "gw-ready", "responses": {"200": {"description": "ok"}}}},
            "/v2/vectordb/heartbeat": {
                "get": {"summary": "gw-hb", "responses": {"200": {"description": "ok"}}}
            },
        },
    }
    writer = {
        "paths": {
            "/healthz": {"get": {"summary": "w-health", "responses": {"200": {"description": "ok"}}}},
            "/readyz": {"get": {"summary": "w-ready", "responses": {"200": {"description": "ok"}}}},
            "/v2/vectordb/heartbeat": {
                "get": {"summary": "w-hb", "responses": {"200": {"description": "ok"}}}
            },
        }
    }
    with caplog.at_level(logging.WARNING, logger="xvector.gateway.openapi_merge"):
        merged = merge_schemas(gateway, writer, None)
    assert merged["paths"]["/healthz"]["get"]["summary"] == "gw-health"
    assert merged["paths"]["/healthz"]["get"]["tags"] == ["Gateway / System"]
    assert not any("path conflict" in r.message for r in caplog.records)


def test_unexpected_path_conflict_still_warns(caplog):
    gateway = {
        "openapi": "3.1.0",
        "info": {},
        "paths": {
            "/v2/vectordb/collections/list": {
                "post": {"summary": "gw", "responses": {"200": {"description": "ok"}}}
            },
        },
    }
    writer = {
        "paths": {
            "/v2/vectordb/collections/list": {
                "post": {"summary": "w", "responses": {"200": {"description": "ok"}}}
            },
        }
    }
    with caplog.at_level(logging.WARNING, logger="xvector.gateway.openapi_merge"):
        merged = merge_schemas(gateway, writer, None)
    assert merged["paths"]["/v2/vectordb/collections/list"]["post"]["summary"] == "gw"
    assert any(
        "openapi path conflict, keeping Gateway/existing" in r.message for r in caplog.records
    )
