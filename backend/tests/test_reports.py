"""Reportes de citas y pacientes: agrupación, filtros, aislamiento, roles y CSV (ODON-206)."""
import logging
from datetime import date

import pytest

from app.models.patient import Patient
from tests.test_dashboard import MARCH, add_appointment, local, setup  # noqa: F401 (fixture)

pytestmark = [pytest.mark.dashboard]


def get(client, s, path, role="admin", **params):
    return client.get(f"/reports/{path}", params=params, headers=s["headers"][role])


# --- Acceso -------------------------------------------------------------------

@pytest.mark.rbac
@pytest.mark.parametrize("role", ["doctor", "admin", "receptionist"])
@pytest.mark.parametrize("path", ["appointments", "patients"])
def test_all_roles_see_reports(client, setup, role, path):  # noqa: F811
    assert get(client, setup, path, role, **MARCH).status_code == 200


@pytest.mark.rbac
@pytest.mark.parametrize("role,expected", [("admin", 200), ("doctor", 403), ("receptionist", 403)])
@pytest.mark.parametrize("path", ["appointments.csv", "patients.csv"])
def test_only_admin_exports_csv(client, setup, role, expected, path):  # noqa: F811
    assert get(client, setup, path, role, **MARCH).status_code == expected


@pytest.mark.rbac
@pytest.mark.parametrize("path", ["appointments", "patients", "appointments.csv"])
def test_reports_require_authentication(client, setup, path):  # noqa: F811
    assert client.get(f"/reports/{path}").status_code == 401


@pytest.mark.isolation
def test_reports_are_scoped_to_clinic(client, setup):  # noqa: F811
    add_appointment(setup, local(date(2026, 3, 10), 9), "completed",
                    doctor=setup["other_doctor"], patient=setup["other_patient"], clinic=setup["other_clinic"])
    report = get(client, setup, "appointments", **MARCH).json()
    assert report["totals"]["total"] == 0
    assert report["by_doctor"] == []
    other = get(client, setup, "appointments", "other", **MARCH).json()
    assert other["totals"]["total"] == 1
    csv_text = get(client, setup, "appointments.csv", **MARCH).content.decode("utf-8-sig")
    assert "Clinica Ajena" not in csv_text


@pytest.mark.isolation
@pytest.mark.parametrize("path", ["appointments", "patients", "appointments.csv"])
def test_doctor_from_other_clinic_is_404(client, setup, path):  # noqa: F811
    assert get(client, setup, path, doctor_id=setup["other_doctor"].id, **MARCH).status_code == 404


# --- Citas --------------------------------------------------------------------

def test_appointments_by_day_status_and_doctor(client, setup):  # noqa: F811
    add_appointment(setup, local(date(2026, 3, 2), 9), "completed")
    add_appointment(setup, local(date(2026, 3, 2), 10), "no_show")
    add_appointment(setup, local(date(2026, 3, 4), 9), "cancelled")
    add_appointment(setup, local(date(2026, 3, 4), 9), "completed", doctor=setup["colleague"],
                    patient=setup["second_patient"])
    report = get(client, setup, "appointments", **MARCH).json()

    assert report["group"] == "day"
    assert len(report["series"]) == 31  # también los días sin citas
    march2 = report["series"][1]
    assert march2["period_start"] == "2026-03-02"
    assert (march2["completed"], march2["no_show"], march2["total"]) == (1, 1, 2)
    assert march2["attendance_rate"] == 50.0
    assert report["series"][0]["total"] == 0 and report["series"][0]["attendance_rate"] is None

    by_doctor = {row["doctor"]["id"]: row for row in report["by_doctor"]}
    mine = by_doctor[setup["doctor"].id]
    assert (mine["total"], mine["no_show"], mine["cancelled"], mine["no_show_rate"]) == (3, 1, 1, 50.0)
    assert mine["doctor"]["name"] == "Dr. Clinica Panel"
    assert by_doctor[setup["colleague"].id]["attendance_rate"] == 100.0
    # Ordenado de más a menos citas.
    assert report["by_doctor"][0]["doctor"]["id"] == setup["doctor"].id
    assert report["totals"]["total"] == 4


def test_grouping_by_week_and_month_in_clinic_timezone(client, setup):  # noqa: F811
    # Domingo 8-mar 23:00 en Guatemala = lunes 9-mar 05:00 UTC: es de la semana del 2-mar.
    add_appointment(setup, local(date(2026, 3, 8), 23), "completed")
    add_appointment(setup, local(date(2026, 3, 9), 9), "completed")
    weekly = get(client, setup, "appointments", group="week", **MARCH).json()
    # Las semanas del borde se recortan al periodo y se marcan parciales.
    spans = [(row["period_start"], row["period_end"], row["partial"]) for row in weekly["series"]]
    assert spans == [
        ("2026-03-01", "2026-03-01", True), ("2026-03-02", "2026-03-08", False),
        ("2026-03-09", "2026-03-15", False), ("2026-03-16", "2026-03-22", False),
        ("2026-03-23", "2026-03-29", False), ("2026-03-30", "2026-03-31", True),
    ]
    totals = {row["period_start"]: row["total"] for row in weekly["series"]}
    assert totals["2026-03-02"] == 1 and totals["2026-03-09"] == 1

    monthly = get(client, setup, "appointments", group="month", **{"from": "2026-01-15", "to": "2026-03-31"}).json()
    assert [row["period_start"] for row in monthly["series"]] == ["2026-01-15", "2026-02-01", "2026-03-01"]
    assert [row["partial"] for row in monthly["series"]] == [True, False, False]
    assert [row["total"] for row in monthly["series"]] == [0, 0, 2]


def test_doctor_filter(client, setup):  # noqa: F811
    add_appointment(setup, local(date(2026, 3, 2), 9), "completed")
    add_appointment(setup, local(date(2026, 3, 2), 9), "no_show", doctor=setup["colleague"],
                    patient=setup["second_patient"])
    report = get(client, setup, "appointments", doctor_id=setup["colleague"].id, **MARCH).json()
    assert report["doctor_id"] == setup["colleague"].id
    assert report["totals"]["total"] == 1 and report["totals"]["no_show"] == 1
    assert [row["doctor"]["id"] for row in report["by_doctor"]] == [setup["colleague"].id]


@pytest.mark.parametrize("params", [
    {"from": "2026-03-10", "to": "2026-03-01"},
    {"from": "2025-01-01", "to": "2026-03-01"},
    {**MARCH, "group": "year"},
])
def test_invalid_parameters_are_422(client, setup, params):  # noqa: F811
    assert get(client, setup, "appointments", **params).status_code == 422


# --- Pacientes ----------------------------------------------------------------

def test_new_patients_by_month(client, setup):  # noqa: F811
    db = setup["db"]
    db.query(Patient).filter(Patient.clinic_id == setup["clinic"].id).update({"created_at": None})
    db.add_all([
        Patient(first_name="Nuevo", last_name="Uno", clinic_id=setup["clinic"].id,
                created_at=local(date(2026, 2, 3), 10)),
        Patient(first_name="Nuevo", last_name="Dos", clinic_id=setup["clinic"].id,
                created_at=local(date(2026, 3, 3), 10), doctor_id=setup["doctor"].id),
        # 31-mar 22:00 local = 1-abr UTC: cuenta en marzo.
        Patient(first_name="Nuevo", last_name="Tres", clinic_id=setup["clinic"].id,
                created_at=local(date(2026, 3, 31), 22)),
    ])
    db.commit()
    report = get(client, setup, "patients", group="month", **{"from": "2026-02-01", "to": "2026-03-31"}).json()
    assert report["series"] == [
        {"period_start": "2026-02-01", "period_end": "2026-02-28", "partial": False, "new_patients": 1},
        {"period_start": "2026-03-01", "period_end": "2026-03-31", "partial": False, "new_patients": 2},
    ]
    assert report["total_new"] == 3
    assert report["without_registration_date"] == 2

    mine = get(client, setup, "patients", group="month", doctor_id=setup["doctor"].id,
               **{"from": "2026-02-01", "to": "2026-03-31"}).json()
    assert mine["total_new"] == 1
    # El paciente de la fixture está asignado al doctor y no tiene fecha de alta.
    assert mine["without_registration_date"] == 1


# --- CSV ----------------------------------------------------------------------

def test_appointments_csv(client, setup, caplog):  # noqa: F811
    add_appointment(setup, local(date(2026, 3, 2), 9), "completed")
    add_appointment(setup, local(date(2026, 3, 2), 10), "no_show")
    with caplog.at_level(logging.INFO, logger="odontonet.audit"):
        response = get(client, setup, "appointments.csv", group="month", **MARCH)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["cache-control"] == "private, no-store"
    assert 'filename="reporte-citas-2026-03-01-2026-03-31.csv"' in response.headers["content-disposition"]
    assert response.content.startswith("﻿".encode("utf-8"))
    lines = response.content.decode("utf-8-sig").splitlines()
    assert lines[0] == ("Tipo,Grupo,Hasta,Programada,Confirmada,Atendida,Cancelada,No asistió,Total,"
                        "Asistencia %,Inasistencia %")
    assert lines[1] == "Mes,2026-03-01,2026-03-31,0,0,1,0,1,2,50.0,50.0"
    assert lines[2] == "Doctor,Dr. Clinica Panel,,0,0,1,0,1,2,50.0,50.0"
    assert lines[3].startswith("Total,2026-03-01,2026-03-31,")
    # Solo datos agregados: ningún nombre de paciente.
    assert "Ana" not in response.text and "Ríos" not in response.text
    audit = [r.getMessage() for r in caplog.records if r.name == "odontonet.audit"]
    assert any("report.exported kind=appointments" in message for message in audit)
    assert not any("Ana" in message for message in audit)


def test_patients_csv(client, setup):  # noqa: F811
    response = get(client, setup, "patients.csv", group="month", **MARCH)
    lines = response.content.decode("utf-8-sig").splitlines()
    assert lines[0] == "Mes,Hasta,Parcial,Pacientes nuevos"
    assert lines[1] == "2026-03-01,2026-03-31,no,0"
    assert lines[-2] == "Total,2026-03-31,,0"
    assert lines[-1].startswith("Sin fecha de alta")


def test_today_patients_count_in_current_month(client, setup):  # noqa: F811
    report = get(client, setup, "patients").json()
    assert report["total_new"] == 2  # los dos pacientes de la fixture se crearon hoy


def test_csv_neutralizes_formulas_in_text(client, setup):  # noqa: F811
    from app.models.user import User
    setup["db"].query(User).filter(User.id == setup["doctor_user"].id).update({"name": "=HYPERLINK(1)"})
    setup["db"].commit()
    add_appointment(setup, local(date(2026, 3, 2), 9), "completed")
    lines = get(client, setup, "appointments.csv", group="month", **MARCH).content.decode("utf-8-sig").splitlines()
    assert lines[2].startswith("Doctor,'=HYPERLINK(1),")
