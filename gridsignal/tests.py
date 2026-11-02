import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from django.test import TestCase, Client
from django.conf import settings

from gridsignal.models import Incident, Alert
from gridsignal.correlate import is_correlated, run_correlation
from gridsignal.ingest import ingest_csv

class BoundaryAndCorrelationTests(TestCase):
    """
    Acceptance Check:
    Demonstrate that exactly 200 feet and exactly 6 hours do match,
    while values just outside either limit do not.
    """
    def test_exact_boundary_conditions(self):
        t_base = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
        t_6hr = datetime(2026, 10, 20, 6, 0, 0, tzinfo=timezone.utc)  # exactly 360.0 minutes

        # Exactly 200.0 ft, exactly 360.0 min -> MATCH (both boundaries inclusive)
        matches, dist, gap = is_correlated(
            gas_x=0.0, gas_y=0.0, gas_dt=t_base,
            elec_x=200.0, elec_y=0.0, elec_dt=t_6hr
        )
        self.assertTrue(matches)
        self.assertEqual(dist, 200.0)
        self.assertEqual(gap, 360.0)

    def test_boundary_distance_just_outside(self):
        t_base = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
        t_1hr = datetime(2026, 10, 20, 1, 0, 0, tzinfo=timezone.utc)

        # 200.01 ft (0.01 ft beyond limit) -> NO MATCH
        matches, dist, gap = is_correlated(
            gas_x=1000.0, gas_y=1000.0, gas_dt=t_base,
            elec_x=1200.01, elec_y=1000.0, elec_dt=t_1hr
        )
        self.assertFalse(matches)
        self.assertEqual(dist, 200.01)

    def test_boundary_time_just_outside(self):
        t_base = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)
        t_over = datetime(2026, 10, 20, 6, 0, 1, tzinfo=timezone.utc)  # 360 min and 1 sec

        # > 360.0 min -> NO MATCH
        matches, dist, gap = is_correlated(
            gas_x=0.0, gas_y=0.0, gas_dt=t_base,
            elec_x=0.0, elec_y=0.0, elec_dt=t_over
        )
        self.assertFalse(matches)
        self.assertGreater(gap, 360.0)

    def test_missing_coordinates_never_matches(self):
        t_base = datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc)

        # Missing coordinates for electric incident
        matches, _, _ = is_correlated(
            gas_x=100.0, gas_y=100.0, gas_dt=t_base,
            elec_x=None, elec_y=None, elec_dt=t_base
        )
        self.assertFalse(matches)

        # Missing coordinates for gas incident
        matches2, _, _ = is_correlated(
            gas_x=None, gas_y=None, gas_dt=t_base,
            elec_x=100.0, elec_y=100.0, elec_dt=t_base
        )
        self.assertFalse(matches2)

    def test_time_ordering_reversibility(self):
        t_early = datetime(2026, 10, 20, 2, 0, 0, tzinfo=timezone.utc)
        t_late = datetime(2026, 10, 20, 4, 30, 0, tzinfo=timezone.utc)

        # Gas earlier than Electric
        m1, _, gap1 = is_correlated(0, 0, t_early, 50, 0, t_late)
        self.assertTrue(m1)
        self.assertEqual(gap1, 150.0)

        # Electric earlier than Gas (absolute time difference)
        m2, _, gap2 = is_correlated(0, 0, t_late, 50, 0, t_early)
        self.assertTrue(m2)
        self.assertEqual(gap2, 150.0)

    def test_correlation_ignores_severity_status_area(self):
        g = Incident.objects.create(
            incident_id="G-CLOSED",
            utility_type="GAS",
            reported_at=datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc),
            x_ft=10, y_ft=10, severity="LOW", status="CLOSED", area="Area-1"
        )
        e = Incident.objects.create(
            incident_id="E-OPEN",
            utility_type="ELECTRIC",
            reported_at=datetime(2026, 10, 20, 1, 0, 0, tzinfo=timezone.utc),
            x_ft=20, y_ft=20, severity="CRITICAL", status="OPEN", area="Area-2"
        )
        count = run_correlation()
        self.assertEqual(count, 1)
        alert = Alert.objects.first()
        self.assertEqual(alert.gas_incident, g)
        self.assertEqual(alert.electric_incident, e)
        self.assertAlmostEqual(alert.distance_ft, 14.14, places=2)
        self.assertEqual(alert.time_gap_minutes, 60.0)

    def test_one_to_many_matches(self):
        g = Incident.objects.create(
            incident_id="G-HUB",
            utility_type="GAS",
            reported_at=datetime(2026, 10, 20, 0, 0, 0, tzinfo=timezone.utc),
            x_ft=100, y_ft=100
        )
        e1 = Incident.objects.create(
            incident_id="E-L1",
            utility_type="ELECTRIC",
            reported_at=datetime(2026, 10, 20, 1, 0, 0, tzinfo=timezone.utc),
            x_ft=120, y_ft=100
        )
        e2 = Incident.objects.create(
            incident_id="E-L2",
            utility_type="ELECTRIC",
            reported_at=datetime(2026, 10, 20, 2, 0, 0, tzinfo=timezone.utc),
            x_ft=100, y_ft=150
        )
        count = run_correlation()
        self.assertEqual(count, 2)


class IngestionAndDeduplicationTests(TestCase):
    """
    Acceptance Check:
    1. Re-importing must not duplicate incident IDs.
    2. Ignore identical duplicates.
    3. Choose and document policy for conflicting duplicates (Last-Write-Wins).
    4. Skip malformed timestamps with a logged warning without crashing.
    """
    def test_idempotent_ingestion(self):
        stats1 = ingest_csv(settings.SEED_CSV_PATH)
        self.assertEqual(stats1["total_rows"], 11)
        self.assertEqual(stats1["inserted_new"], 11)
        self.assertEqual(stats1["alerts_count"], 6)
        self.assertEqual(Incident.objects.count(), 11)
        self.assertEqual(Alert.objects.count(), 6)

        # Run the same import again
        stats2 = ingest_csv(settings.SEED_CSV_PATH)
        self.assertEqual(stats2["total_rows"], 11)
        self.assertEqual(stats2["inserted_new"], 0)
        self.assertEqual(stats2["skipped_identical"], 11)
        self.assertEqual(stats2["alerts_count"], 6)

        # Total counts and pairs must remain strictly unchanged
        self.assertEqual(Incident.objects.count(), 11)
        self.assertEqual(Alert.objects.count(), 6)

    def test_conflicting_duplicates_last_write_wins(self):
        with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False) as f:
            f.write("incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area\n")
            f.write("G-100,GAS,2026-10-20T00:00:00Z,0,0,MEDIUM,OPEN,Sector-1\n")
            p1 = Path(f.name)

        ingest_csv(p1)
        inc = Incident.objects.get(incident_id="G-100")
        self.assertEqual(inc.severity, "MEDIUM")
        self.assertEqual(inc.status, "OPEN")

        # Second batch with conflicting attributes
        with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False) as f:
            f.write("incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area\n")
            f.write("G-100,GAS,2026-10-20T00:00:00Z,0,0,CRITICAL,RESOLVED,Sector-1-Updated\n")
            p2 = Path(f.name)

        stats2 = ingest_csv(p2)
        self.assertEqual(stats2["inserted_new"], 0)
        self.assertEqual(stats2["updated_conflicting"], 1)

        # Still exactly 1 record, updated in place
        self.assertEqual(Incident.objects.count(), 1)
        inc_updated = Incident.objects.get(incident_id="G-100")
        self.assertEqual(inc_updated.severity, "CRITICAL")
        self.assertEqual(inc_updated.status, "RESOLVED")
        self.assertEqual(inc_updated.area, "Sector-1-Updated")

    def test_malformed_timestamp_gracefully_skipped(self):
        with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False) as f:
            f.write("incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area\n")
            f.write("G-V1,GAS,2026-10-20T00:00:00Z,0,0,HIGH,OPEN,Demo\n")
            f.write("E-BAD1,ELECTRIC,invalid-date-string,200,0,MEDIUM,OPEN,Demo\n")
            f.write("E-BAD2,ELECTRIC,2026/13/45,200,0,LOW,OPEN,Demo\n")
            f.write("E-V2,ELECTRIC,2026-10-20T02:00:00Z,50,0,LOW,OPEN,Demo\n")
            p = Path(f.name)

        stats = ingest_csv(p)
        self.assertEqual(stats["total_rows"], 4)
        self.assertEqual(stats["inserted_new"], 2)
        self.assertEqual(stats["skipped_malformed"], 2)
        self.assertEqual(Incident.objects.count(), 2)
        # Valid pair G-V1 + E-V2 matches
        self.assertEqual(stats["alerts_count"], 1)

    def test_missing_coordinates_stored_as_null(self):
        with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False) as f:
            f.write("incident_id,utility_type,reported_at,x_ft,y_ft,severity,status,area\n")
            f.write("G-NULL,GAS,2026-10-20T00:00:00Z,,,HIGH,OPEN,Demo\n")
            p = Path(f.name)

        ingest_csv(p)
        inc = Incident.objects.get(incident_id="G-NULL")
        self.assertIsNone(inc.x_ft)
        self.assertIsNone(inc.y_ft)
        self.assertFalse(inc.has_coordinates)
        self.assertEqual(Alert.objects.count(), 0)

    def test_replay_batch_integration(self):
        ingest_csv(settings.SEED_CSV_PATH)
        stats = ingest_csv(settings.REPLAY_CSV_PATH)

        self.assertGreaterEqual(stats["skipped_identical"], 2)
        self.assertGreaterEqual(stats["updated_conflicting"], 1)
        self.assertGreaterEqual(stats["skipped_malformed"], 2)
        self.assertGreaterEqual(stats["inserted_new"], 3)
        self.assertEqual(Incident.objects.count(), 11 + stats["inserted_new"])


class ApiEndpointTests(TestCase):
    """
    Acceptance Check:
    API response expectations for GET /health, GET /incidents, GET /alerts, and GET /summary.
    """
    def setUp(self):
        ingest_csv(settings.SEED_CSV_PATH)
        self.client = Client()

    def test_get_health(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "GridSignal Mini")
        self.assertEqual(data["database"], "connected")

    def test_get_summary(self):
        response = self.client.get('/summary')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data, {
            "total_incidents": 11,
            "total_gas": 4,
            "total_electric": 7,
            "total_alerts": 6
        })

    def test_get_incidents_all(self):
        response = self.client.get('/incidents')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 11)

        # Verify missing coordinates item (E-X5) is included with nulls
        e_x5 = next(i for i in data if i["incident_id"] == "E-X5")
        self.assertIsNone(e_x5["x_ft"])
        self.assertIsNone(e_x5["y_ft"])

    def test_get_incidents_filtered(self):
        # Filter GAS
        res_gas = self.client.get('/incidents?utility_type=GAS')
        self.assertEqual(res_gas.status_code, 200)
        data_gas = json.loads(res_gas.content)
        self.assertEqual(len(data_gas), 4)
        self.assertTrue(all(i["utility_type"] == "GAS" for i in data_gas))

        # Filter ELECTRIC
        res_elec = self.client.get('/incidents?utility_type=ELECTRIC')
        self.assertEqual(res_elec.status_code, 200)
        data_elec = json.loads(res_elec.content)
        self.assertEqual(len(data_elec), 7)
        self.assertTrue(all(i["utility_type"] == "ELECTRIC" for i in data_elec))

    def test_get_alerts(self):
        response = self.client.get('/alerts')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data), 6)

        # Validate required fields
        for a in data:
            self.assertIn("gas_incident_id", a)
            self.assertIn("electric_incident_id", a)
            self.assertIn("distance_ft", a)
            self.assertIn("time_gap_minutes", a)
            self.assertLessEqual(a["distance_ft"], 200.0)
            self.assertLessEqual(a["time_gap_minutes"], 360.0)

        # Check boundary match G-X1 + E-X1
        boundary_pair = next(
            (a for a in data if a["gas_incident_id"] == "G-X1" and a["electric_incident_id"] == "E-X1"),
            None
        )
        self.assertIsNotNone(boundary_pair)
        self.assertEqual(boundary_pair["distance_ft"], 200.0)
        self.assertEqual(boundary_pair["time_gap_minutes"], 360.0)
