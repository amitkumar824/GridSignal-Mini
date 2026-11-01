import pytest
from app.config import SEED_CSV_PATH
from app.ingest import ingest_csv

def test_api_health(test_client):
    """GET /health: A simple healthy/ready response."""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "GridSignal Mini"
    assert data["database"] == "connected"

def test_api_summary_and_incidents_empty(test_client):
    """Verify clean response when database is freshly initialized."""
    summary_res = test_client.get("/summary")
    assert summary_res.status_code == 200
    assert summary_res.json() == {
        "total_incidents": 0,
        "total_gas": 0,
        "total_electric": 0,
        "total_alerts": 0
    }

    incidents_res = test_client.get("/incidents")
    assert incidents_res.status_code == 200
    assert incidents_res.json() == []

    alerts_res = test_client.get("/alerts")
    assert alerts_res.status_code == 200
    assert alerts_res.json() == []

def test_api_endpoints_with_seed_data(test_client, temp_db):
    """
    Test GET /incidents, GET /alerts, and GET /summary after seed import.
    """
    # Trigger seed import via API endpoint
    import_res = test_client.post("/api/import/seed")
    assert import_res.status_code == 200
    import_data = import_res.json()
    assert import_data["inserted_new"] == 11
    assert import_data["alerts_count"] == 6

    # 1. Test GET /summary
    summary_res = test_client.get("/summary")
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_incidents"] == 11
    assert summary["total_gas"] == 4
    assert summary["total_electric"] == 7
    assert summary["total_alerts"] == 6

    # 2. Test GET /incidents (all)
    incidents_res = test_client.get("/incidents")
    assert incidents_res.status_code == 200
    incidents = incidents_res.json()
    assert len(incidents) == 11

    # Verify incident missing coordinates is included (e.g. E-X5)
    e_x5 = next((inc for inc in incidents if inc["incident_id"] == "E-X5"), None)
    assert e_x5 is not None
    assert e_x5["x_ft"] is None
    assert e_x5["y_ft"] is None

    # 3. Test GET /incidents with utility_type filter
    gas_res = test_client.get("/incidents?utility_type=GAS")
    assert gas_res.status_code == 200
    gas_incidents = gas_res.json()
    assert len(gas_incidents) == 4
    assert all(inc["utility_type"] == "GAS" for inc in gas_incidents)

    elec_res = test_client.get("/incidents?utility_type=ELECTRIC")
    assert elec_res.status_code == 200
    elec_incidents = elec_res.json()
    assert len(elec_incidents) == 7
    assert all(inc["utility_type"] == "ELECTRIC" for inc in elec_incidents)

    # 4. Test GET /alerts
    alerts_res = test_client.get("/alerts")
    assert alerts_res.status_code == 200
    alerts = alerts_res.json()
    assert len(alerts) == 6

    # Verify required alert fields exist in every alert item
    for a in alerts:
        assert "gas_incident_id" in a
        assert "electric_incident_id" in a
        assert "distance_ft" in a
        assert "time_gap_minutes" in a
        assert a["distance_ft"] <= 200.0
        assert a["time_gap_minutes"] <= 360.0

    # Specifically check the boundary pair G-X1 and E-X1
    boundary_alert = next(
        (a for a in alerts if a["gas_incident_id"] == "G-X1" and a["electric_incident_id"] == "E-X1"),
        None
    )
    assert boundary_alert is not None
    assert boundary_alert["distance_ft"] == 200.0
    assert boundary_alert["time_gap_minutes"] == 360.0

