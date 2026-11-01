from rest_framework import serializers
from .models import Incident, Alert

class IncidentSerializer(serializers.ModelSerializer):
    reported_at = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%SZ")

    class Meta:
        model = Incident
        fields = [
            'incident_id',
            'utility_type',
            'reported_at',
            'x_ft',
            'y_ft',
            'severity',
            'status',
            'area'
        ]

class AlertSerializer(serializers.ModelSerializer):
    gas_incident_id = serializers.CharField(source='gas_incident.incident_id', read_only=True)
    electric_incident_id = serializers.CharField(source='electric_incident.incident_id', read_only=True)
    
    # Extra joined fields for rich UI presentation
    gas_severity = serializers.CharField(source='gas_incident.severity', read_only=True)
    gas_status = serializers.CharField(source='gas_incident.status', read_only=True)
    gas_reported_at = serializers.DateTimeField(source='gas_incident.reported_at', format="%Y-%m-%dT%H:%M:%SZ", read_only=True)
    electric_severity = serializers.CharField(source='electric_incident.severity', read_only=True)
    electric_status = serializers.CharField(source='electric_incident.status', read_only=True)
    electric_reported_at = serializers.DateTimeField(source='electric_incident.reported_at', format="%Y-%m-%dT%H:%M:%SZ", read_only=True)

    class Meta:
        model = Alert
        fields = [
            'gas_incident_id',
            'electric_incident_id',
            'distance_ft',
            'time_gap_minutes',
            'gas_severity',
            'gas_status',
            'gas_reported_at',
            'electric_severity',
            'electric_status',
            'electric_reported_at',
        ]

class SummarySerializer(serializers.Serializer):
    total_incidents = serializers.IntegerField()
    total_gas = serializers.IntegerField()
    total_electric = serializers.IntegerField()
    total_alerts = serializers.IntegerField()

class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()
    database = serializers.CharField()

class IngestResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    file_processed = serializers.CharField()
    total_rows = serializers.IntegerField()
    inserted_new = serializers.IntegerField()
    updated_conflicting = serializers.IntegerField()
    skipped_identical = serializers.IntegerField()
    skipped_malformed = serializers.IntegerField()
    alerts_count = serializers.IntegerField()
