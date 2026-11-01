from pathlib import Path
from django.conf import settings
from django.http import HttpResponse
from django.views import View
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Incident, Alert
from .serializers import IncidentSerializer, AlertSerializer, SummarySerializer, HealthSerializer, IngestResponseSerializer
from .ingest import ingest_csv

class DashboardView(View):
    """Serve the single-page application dashboard directly."""
    def get(self, request, *args, **kwargs):
        html_path = settings.BASE_DIR / 'backend' / 'static' / 'index.html'
        if html_path.is_file():
            content = html_path.read_text(encoding='utf-8')
            return HttpResponse(content, content_type='text/html')
        return HttpResponse("<h1>GridSignal Mini API is running. Dashboard HTML not found.</h1>", content_type='text/html')

class HealthView(APIView):
    """GET /health - Simple healthy/ready response indicating service status and DB connectivity."""
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
            db_status = "connected"
        except Exception as e:
            db_status = f"unhealthy: {e}"

        data = {
            "status": "ok",
            "service": "GridSignal Mini",
            "database": db_status
        }
        serializer = HealthSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)

class IncidentListView(APIView):
    """
    GET /incidents - Return valid imported incidents, including those with missing coordinates.
    Optional filter: ?utility_type=GAS or ?utility_type=ELECTRIC
    """
    def get(self, request):
        utility_type = request.query_params.get('utility_type')
        queryset = Incident.objects.all()
        if utility_type:
            queryset = queryset.filter(utility_type__iexact=utility_type.strip())
        
        serializer = IncidentSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AlertListView(APIView):
    """
    GET /alerts - Return list of unique GAS/ELECTRIC matched pairs.
    Includes gas_incident_id, electric_incident_id, distance_ft, time_gap_minutes.
    """
    def get(self, request):
        alerts = Alert.objects.select_related('gas_incident', 'electric_incident').all()
        serializer = AlertSerializer(alerts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class SummaryView(APIView):
    """
    GET /summary - Return total_incidents, total_gas, total_electric, total_alerts.
    Loaded dynamically from database state.
    """
    def get(self, request):
        total_incidents = Incident.objects.count()
        total_gas = Incident.objects.filter(utility_type=Incident.UTILITY_GAS).count()
        total_electric = Incident.objects.filter(utility_type=Incident.UTILITY_ELECTRIC).count()
        total_alerts = Alert.objects.count()

        data = {
            "total_incidents": total_incidents,
            "total_gas": total_gas,
            "total_electric": total_electric,
            "total_alerts": total_alerts
        }
        serializer = SummarySerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ImportSeedView(APIView):
    """POST /api/import/seed - Trigger ingestion of seed_incidents.csv."""
    def post(self, request):
        target = settings.SEED_CSV_PATH
        if not target.is_file():
            return Response({"error": "Seed file not found"}, status=status.HTTP_404_NOT_FOUND)
        stats = ingest_csv(target)
        serializer = IngestResponseSerializer(stats)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ImportReplayView(APIView):
    """POST /api/import/replay - Trigger ingestion of replay_batch.csv."""
    def post(self, request):
        target = settings.REPLAY_CSV_PATH
        if not target.is_file():
            return Response({"error": "Replay file not found"}, status=status.HTTP_404_NOT_FOUND)
        stats = ingest_csv(target)
        serializer = IngestResponseSerializer(stats)
        return Response(serializer.data, status=status.HTTP_200_OK)
