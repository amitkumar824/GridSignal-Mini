from django.db import models

class Incident(models.Model):
    UTILITY_GAS = 'GAS'
    UTILITY_ELECTRIC = 'ELECTRIC'
    UTILITY_CHOICES = [
        (UTILITY_GAS, 'Gas'),
        (UTILITY_ELECTRIC, 'Electric'),
    ]

    incident_id = models.CharField(max_length=64, primary_key=True, help_text="Unique incident identifier")
    utility_type = models.CharField(max_length=16, choices=UTILITY_CHOICES, db_index=True)
    reported_at = models.DateTimeField(db_index=True, help_text="UTC timestamp of incident report")
    x_ft = models.FloatField(null=True, blank=True, help_text="Planar X coordinate in feet (optional)")
    y_ft = models.FloatField(null=True, blank=True, help_text="Planar Y coordinate in feet (optional)")
    severity = models.CharField(max_length=32, default='MEDIUM')
    status = models.CharField(max_length=32, default='OPEN')
    area = models.CharField(max_length=128, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['reported_at']
        indexes = [
            models.Index(fields=['utility_type', 'x_ft', 'y_ft'], name='idx_inc_util_coords'),
        ]

    def __str__(self):
        return f"{self.incident_id} [{self.utility_type}] - {self.status}"

    @property
    def has_coordinates(self) -> bool:
        return self.x_ft is not None and self.y_ft is not None


class Alert(models.Model):
    gas_incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name='gas_alerts'
    )
    electric_incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name='electric_alerts'
    )
    distance_ft = models.FloatField(help_text="Planar distance in feet between incidents")
    time_gap_minutes = models.FloatField(help_text="Absolute reporting time difference in minutes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['distance_ft', 'time_gap_minutes']
        constraints = [
            models.UniqueConstraint(
                fields=['gas_incident', 'electric_incident'],
                name='unique_gas_electric_pair'
            )
        ]

    def __str__(self):
        return f"Alert: {self.gas_incident_id} + {self.electric_incident_id} ({self.distance_ft:.1f} ft, {self.time_gap_minutes:.1f} min)"
