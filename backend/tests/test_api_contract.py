"""Contrato de la API: OpenAPI, health y formato único de errores (ODON-22)."""
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import PASSWORD, create_clinic_with_doctor

pytestmark = [pytest.mark.api]


def test_openapi_and_docs_respond(client):
    assert client.get("/docs").status_code == 200

    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["title"] == "OdontoNet API"


def test_every_success_response_is_typed(client):
    spec = client.get("/openapi.json").json()
    untyped = []
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            success = next((r for code, r in operation["responses"].items() if code.startswith("2")), {})
            content = success.get("content", {})
            # Archivos (imágenes, PDF, CSV): contenido binario declarado en lugar de JSON.
            binary = content and all(
                media.get("schema") == {"type": "string", "format": "binary"} for media in content.values()
            )
            if not content.get("application/json", {}).get("schema") and not binary:
                untyped.append(f"{method.upper()} {path}")
    assert untyped == []


def test_health_checks_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.auth
def test_login_returns_typed_token(client, db):
    create_clinic_with_doctor(db, "Clinica Token", "token@clinica.com")
    response = client.post("/auth/login", json={"email": "token@clinica.com", "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type", "expires_in", "user_id"}
    assert body["token_type"] == "bearer"


@pytest.mark.auth
def test_missing_token_is_401_with_bearer_challenge(client):
    response = client.get("/patients/")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json() == {"detail": "No autenticado."}


def test_unknown_route_has_spanish_detail(client):
    response = client.get("/no-existe")
    assert response.status_code == 404
    assert response.json() == {"detail": "Recurso no encontrado."}


def test_method_not_allowed_has_spanish_detail(client):
    response = client.delete("/patients/")
    assert response.status_code == 405
    assert response.json() == {"detail": "Método no permitido."}


def test_validation_errors_have_unified_format(client, two_clinics):
    response = client.post(
        "/patients/",
        json={"first_name": "", "last_name": "X", "email": "malo", "birth_date": "2999-01-01"},
        headers=two_clinics["a"]["headers"],
    )

    assert response.status_code == 422
    body = response.json()
    assert isinstance(body["detail"], str)
    assert body["detail"].startswith("Revisa los campos:")
    messages = {error["field"]: error["message"] for error in body["errors"]}
    assert messages == {
        "first_name": "Campo obligatorio.",
        "email": "Correo electrónico inválido.",
        "birth_date": "La fecha de nacimiento no puede ser futura",
    }


def test_invalid_json_body_is_422(client, two_clinics):
    response = client.post(
        "/patients/",
        content="{no es json",
        headers={**two_clinics["a"]["headers"], "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert response.json()["errors"] == [{"field": "body", "message": "El cuerpo de la petición no es JSON válido."}]


def test_unhandled_errors_do_not_leak_internals():
    router = APIRouter()

    @router.get("/__test_boom")
    def boom():
        raise RuntimeError("detalle interno secreto")

    app.include_router(router)
    try:
        response = TestClient(app, raise_server_exceptions=False).get("/__test_boom")
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/__test_boom"]

    assert response.status_code == 500
    assert response.json() == {"detail": "Error interno del servidor."}
    assert "secreto" not in response.text


# --- Contrato que fija la migración a Pydantic v2 (ODON-264) -------------------

def test_invalid_date_has_spanish_message(client, two_clinics):
    response = client.post("/patients/", json={"first_name": "A", "last_name": "B", "birth_date": "2020-13-01"},
                           headers=two_clinics["a"]["headers"])
    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "birth_date", "message": "Fecha inválida."}]


@pytest.mark.records
def test_model_validator_errors_keep_root_field(client, two_clinics):
    patient = client.post("/patients/", json={"first_name": "A", "last_name": "B"},
                          headers=two_clinics["a"]["headers"]).json()
    response = client.post(f"/patients/{patient['id']}/medical-history",
                          json={"base_version": None, "smoking_status": "former", "cigarettes_per_day": 5},
                          headers=two_clinics["a"]["headers"])
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "__root__"


@pytest.mark.periodontal
def test_nested_model_validator_errors_keep_their_path(client, two_clinics):
    patient = client.post("/patients/", json={"first_name": "A", "last_name": "B"},
                          headers=two_clinics["a"]["headers"]).json()
    response = client.post(f"/patients/{patient['id']}/periodontal-exams",
                           json={"exam_date": "2026-01-10", "teeth": [{"tooth": 11, "missing": True, "implant": True}]},
                           headers=two_clinics["a"]["headers"])
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "teeth.0.__root__"


@pytest.mark.appointments
def test_datetimes_are_returned_with_utc_offset(client, two_clinics):
    headers = two_clinics["a"]["headers"]
    patient = client.post("/patients/", json={"first_name": "A", "last_name": "B"}, headers=headers).json()
    response = client.post("/appointments/", headers=headers, json={
        "patient_id": patient["id"], "doctor_id": two_clinics["a"]["doctor"],
        "starts_at": "2030-01-15T15:00:00Z", "duration_minutes": 30, "allow_outside_schedule": True})
    assert response.status_code == 201, response.text
    assert response.json()["starts_at"] == "2030-01-15T15:00:00+00:00"


def test_openapi_keeps_datetime_format_in_responses(client):
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert schemas["AppointmentResponse"]["properties"]["starts_at"] == {"type": "string", "format": "date-time", "title": "Starts At"}
