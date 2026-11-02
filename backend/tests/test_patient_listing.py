"""Listado paginado de pacientes con búsqueda y filtros en el servidor (ODON-126 / ODON-129)."""
import pytest

from app.models import Patient
from tests.conftest import create_clinic_with_doctor, auth_headers

pytestmark = [pytest.mark.patients]


@pytest.fixture
def clinic(db, client):
    clinic, _, ana = create_clinic_with_doctor(db, "Clinica Lista", "ana@lista-clinica.com")
    _, _, luis = create_clinic_with_doctor(db, "Clinica Lista Dos", "luis@lista-clinica.com")
    # Luis es de otra clínica: se usa para probar filtros entre clínicas.
    other_clinic, _, foreign = create_clinic_with_doctor(db, "Clinica Ajena", "doc@ajena-clinica.com")

    people = [
        ("José", "Pérez", ana.id),
        ("María", "López", None),
        ("Carlos", "Ruiz", ana.id),
        ("Ángela", "Álvarez", None),
        ("Iván", "Zapata", ana.id),
        ("jose", "perezoso", None),
    ]
    ids = {}
    for first, last, doctor_id in people:
        patient = Patient(first_name=first, last_name=last, clinic_id=clinic.id, doctor_id=doctor_id)
        db.add(patient)
        db.flush()
        ids[f"{first} {last}"] = patient.id
    db.add(Patient(first_name="José", last_name="Pérez Ajeno", clinic_id=other_clinic.id, doctor_id=foreign.id))
    db.commit()

    return {
        "clinic": clinic.id, "ana": ana.id, "foreign": foreign.id, "ids": ids,
        "headers": auth_headers(client, "ana@lista-clinica.com"),
        "other_headers": auth_headers(client, "doc@ajena-clinica.com"),
    }


def get_page(client, clinic, headers=None, **params):
    response = client.get("/patients/", params=params, headers=headers or clinic["headers"])
    assert response.status_code == 200, response.text
    return response.json()


def names(body):
    return [f"{p['first_name']} {p['last_name']}" for p in body["items"]]


# --- Paginación (ODON-127) -----------------------------------------------------------

def test_response_is_a_page_with_defaults(client, clinic):
    body = get_page(client, clinic)

    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 6
    assert body["page"] == 1
    assert body["page_size"] == 20


def test_sorted_by_last_name_ignoring_accents_and_case(client, clinic):
    assert names(get_page(client, clinic)) == [
        "Ángela Álvarez", "María López", "José Pérez", "jose perezoso", "Carlos Ruiz", "Iván Zapata",
    ]


def test_pages_split_results_without_overlap(client, clinic, db):
    db.add_all([Patient(first_name=f"Lote{i:02d}", last_name="Masivo", clinic_id=clinic["clinic"]) for i in range(25)])
    db.commit()

    first = get_page(client, clinic, page=1, page_size=20)
    second = get_page(client, clinic, page=2, page_size=20)
    beyond = get_page(client, clinic, page=3, page_size=20)

    assert first["total"] == second["total"] == beyond["total"] == 31
    assert len(first["items"]) == 20
    assert len(second["items"]) == 11
    assert beyond["items"] == []
    ids_first = {p["id"] for p in first["items"]}
    ids_second = {p["id"] for p in second["items"]}
    assert not ids_first & ids_second
    assert len(ids_first | ids_second) == 31


def test_page_size_is_respected(client, clinic):
    body = get_page(client, clinic, page_size=2, page=2)

    assert names(body) == ["José Pérez", "jose perezoso"]
    assert body["page_size"] == 2


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"page": 0}, "Debe ser mayor o igual a 1."),
        ({"page_size": 0}, "Debe ser mayor o igual a 1."),
        ({"page_size": 101}, "Debe ser menor o igual a 100."),
        ({"page": "dos"}, "Debe ser un número entero."),
        ({"archived": "quizas"}, "Debe ser verdadero o falso."),
        ({"q": "x" * 101}, "Debe tener como máximo 100 caracteres."),
    ],
)
def test_invalid_parameters_are_422_in_spanish(client, clinic, params, message):
    response = client.get("/patients/", params=params, headers=clinic["headers"])

    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == message


# --- Búsqueda (ODON-129) -------------------------------------------------------------

@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("jose perez", ["José Pérez", "jose perezoso"]),
        ("PÉREZ JOSÉ", ["José Pérez"]),
        ("  perez   jose  ", ["José Pérez"]),
        ("angela", ["Ángela Álvarez"]),
        ("ALVAREZ", ["Ángela Álvarez"]),
        ("ruiz", ["Carlos Ruiz"]),
        ("van", ["Iván Zapata"]),
        ("zzz", []),
    ],
)
def test_search_ignores_accents_case_order_and_spaces(client, clinic, term, expected):
    body = get_page(client, clinic, q=term)

    assert names(body) == expected
    assert body["total"] == len(expected)


@pytest.mark.parametrize("term", ["%", "_", "\\"])
def test_like_wildcards_are_literal(client, clinic, term):
    assert get_page(client, clinic, q=term)["items"] == []


def test_blank_search_returns_everything(client, clinic):
    assert get_page(client, clinic, q="   ")["total"] == 6


# --- Filtros combinados (ODON-129) ---------------------------------------------------

def test_filter_by_doctor(client, clinic):
    body = get_page(client, clinic, doctor_id=clinic["ana"])

    assert names(body) == ["José Pérez", "Carlos Ruiz", "Iván Zapata"]
    assert body["total"] == 3


def test_doctor_filter_combines_with_search(client, clinic):
    assert names(get_page(client, clinic, doctor_id=clinic["ana"], q="jose")) == ["José Pérez"]


def test_search_combines_with_archived(client, clinic):
    client.post(f"/patients/{clinic['ids']['José Pérez']}/archive", headers=clinic["headers"])

    assert names(get_page(client, clinic, q="jose")) == ["jose perezoso"]
    assert names(get_page(client, clinic, q="jose", archived="true")) == ["José Pérez"]
    assert get_page(client, clinic, archived="true", doctor_id=clinic["ana"])["total"] == 1


@pytest.mark.isolation
def test_doctor_of_other_clinic_matches_nothing(client, clinic):
    body = get_page(client, clinic, doctor_id=clinic["foreign"])

    assert body["items"] == []
    assert body["total"] == 0


@pytest.mark.isolation
def test_search_and_total_never_include_other_clinic(client, clinic):
    mine = get_page(client, clinic, q="perez")
    theirs = get_page(client, clinic, headers=clinic["other_headers"], q="perez")

    assert "José Pérez Ajeno" not in names(mine)
    assert mine["total"] == 2
    assert names(theirs) == ["José Pérez Ajeno"]
    assert theirs["total"] == 1
