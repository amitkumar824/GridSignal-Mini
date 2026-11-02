from pathlib import Path
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import Incident, Alert
from .ingest import ingest_csv

class DashboardView(View):
    """Serve the single-page application dashboard directly."""
    def get(self, request, *args, **kwargs):
        html_path = settings.BASE_DIR / 'static' / 'index.html'
        if html_path.is_file():
            content = html_path.read_text(encoding='utf-8')
            return HttpResponse(content, content_type='text/html')
        return HttpResponse("<h1>GridSignal Mini API is running. Dashboard HTML not found.</h1>", content_type='text/html')

class HealthView(View):
    """GET /health - Simple healthy/ready response indicating service status and DB connectivity."""
    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
            db_status = "connected"
        except Exception as e:
            db_status = f"unhealthy: {e}"

        return JsonResponse({
            "status": "ok",
            "service": "GridSignal Mini",
            "database": db_status
        })

class IncidentListView(View):
    """
    GET /incidents - Return valid imported incidents, including those with missing coordinates.
    Optional filter: ?utility_type=GAS or ?utility_type=ELECTRIC
    """
    def get(self, request):
        utility_type = request.GET.get('utility_type')
        queryset = Incident.objects.all()
        if utility_type:
            queryset = queryset.filter(utility_type__iexact=utility_type.strip())
        
        data = [inc.to_dict() for inc in queryset]
        return JsonResponse(data, safe=False)

class AlertListView(View):
    """
    GET /alerts - Return list of unique GAS/ELECTRIC matched pairs.
    Includes gas_incident_id, electric_incident_id, distance_ft, time_gap_minutes.
    """
    def get(self, request):
        alerts = Alert.objects.select_related('gas_incident', 'electric_incident').all()
        data = [alert.to_dict() for alert in alerts]
        return JsonResponse(data, safe=False)

class SummaryView(View):
    """
    GET /summary - Return total_incidents, total_gas, total_electric, total_alerts.
    Loaded dynamically from database state.
    """
    def get(self, request):
        total_incidents = Incident.objects.count()
        total_gas = Incident.objects.filter(utility_type=Incident.UTILITY_GAS).count()
        total_electric = Incident.objects.filter(utility_type=Incident.UTILITY_ELECTRIC).count()
        total_alerts = Alert.objects.count()

        return JsonResponse({
            "total_incidents": total_incidents,
            "total_gas": total_gas,
            "total_electric": total_electric,
            "total_alerts": total_alerts
        })

@method_decorator(csrf_exempt, name='dispatch')
class ImportSeedView(View):
    """POST /api/import/seed - Trigger ingestion of seed_incidents.csv."""
    def post(self, request):
        target = settings.SEED_CSV_PATH
        if not target.is_file():
            return JsonResponse({"error": "Seed file not found"}, status=404)
        stats = ingest_csv(target)
        return JsonResponse(stats)

@method_decorator(csrf_exempt, name='dispatch')
class ImportReplayView(View):
    """POST /api/import/replay - Trigger ingestion of replay_batch.csv."""
    def post(self, request):
        target = settings.REPLAY_CSV_PATH
        if not target.is_file():
            return JsonResponse({"error": "Replay file not found"}, status=404)
        stats = ingest_csv(target)
        return JsonResponse(stats)
