from django.contrib import admin
from django.urls import path
from .views import (
    DashboardView,
    HealthView,
    IncidentListView,
    AlertListView,
    SummaryView,
    ImportSeedView,
    ImportReplayView
)

urlpatterns = [
    # Admin Interface
    path('admin/', admin.site.urls),

    # Dashboard UI (serving the React SPA directly)
    path('', DashboardView.as_view(), name='dashboard'),

    # Core Required Take-Home API Endpoints
    path('health', HealthView.as_view(), name='api-health'),
    path('health/', HealthView.as_view(), name='api-health-slash'),
    path('incidents', IncidentListView.as_view(), name='api-incidents'),
    path('incidents/', IncidentListView.as_view(), name='api-incidents-slash'),
    path('alerts', AlertListView.as_view(), name='api-alerts'),
    path('alerts/', AlertListView.as_view(), name='api-alerts-slash'),
    path('summary', SummaryView.as_view(), name='api-summary'),
    path('summary/', SummaryView.as_view(), name='api-summary-slash'),

    # Data Ingestion Trigger Endpoints
    path('api/import/seed', ImportSeedView.as_view(), name='api-import-seed'),
    path('api/import/replay', ImportReplayView.as_view(), name='api-import-replay'),
]
