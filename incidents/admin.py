from django.contrib import admin
from .models import Incident, Alert

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('incident_id', 'utility_type', 'reported_at', 'x_ft', 'y_ft', 'severity', 'status', 'area')
    list_filter = ('utility_type', 'severity', 'status')
    search_fields = ('incident_id', 'area')
    ordering = ('reported_at',)

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('id', 'gas_incident', 'electric_incident', 'distance_ft', 'time_gap_minutes', 'created_at')
    readonly_fields = ('gas_incident', 'electric_incident', 'distance_ft', 'time_gap_minutes', 'created_at')
    ordering = ('distance_ft', 'time_gap_minutes')
