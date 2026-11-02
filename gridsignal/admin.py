from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Incident, Alert

# Customize Admin Site Branding
admin.site.site_header = "GridSignal Mini Administration"
admin.site.site_title = "GridSignal Admin Portal"
admin.site.index_title = "Utility Incident Intelligence & Hazard Alert Management"

@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        'incident_id',
        'utility_type_badge',
        'reported_at',
        'coordinates_display',
        'severity_badge',
        'status_badge',
        'area',
    )
    list_filter = ('utility_type', 'severity', 'status')
    search_fields = ('incident_id', 'area')
    ordering = ('-reported_at',)
    date_hierarchy = 'reported_at'
    list_per_page = 25

    @admin.display(description="Utility Type", ordering="utility_type")
    def utility_type_badge(self, obj):
        if obj.utility_type == Incident.UTILITY_GAS:
            color, bg = "#c2410c", "#ffedd5"  # Orange
        else:
            color, bg = "#1d4ed8", "#dbeafe"  # Blue
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 2px 8px; border-radius: 9999px; font-weight: bold; font-size: 11px;">{}</span>',
            bg, color, str(obj.utility_type)
        )

    @admin.display(description="Planar Coords (x, y)")
    def coordinates_display(self, obj):
        if obj.x_ft is not None and obj.y_ft is not None:
            return f"({obj.x_ft:.1f}, {obj.y_ft:.1f}) ft"
        return mark_safe('<span style="color: #9ca3af; font-style: italic;">NULL (Missing)</span>')

    @admin.display(description="Severity", ordering="severity")
    def severity_badge(self, obj):
        sev_colors = {
            'CRITICAL': ('#991b1b', '#fee2e2'),
            'HIGH': ('#b45309', '#fef3c7'),
            'MEDIUM': ('#4338ca', '#e0e7ff'),
            'LOW': ('#374151', '#f3f4f6'),
        }
        color, bg = sev_colors.get(str(obj.severity).upper(), ('#374151', '#f3f4f6'))
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 11px;">{}</span>',
            bg, color, str(obj.severity)
        )

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        stat_colors = {
            'OPEN': ('#047857', '#d1fae5'),
            'INVESTIGATING': ('#854d0e', '#fef9c3'),
            'RESOLVED': ('#4b5563', '#e5e7eb'),
            'CLOSED': ('#6b7280', '#f3f4f6'),
        }
        color, bg = stat_colors.get(str(obj.status).upper(), ('#4b5563', '#e5e7eb'))
        return format_html(
            '<span style="background-color: {}; color: {}; padding: 2px 8px; border-radius: 9999px; font-weight: 600; font-size: 11px;">{}</span>',
            bg, color, str(obj.status)
        )

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'gas_incident_link',
        'electric_incident_link',
        'distance_display',
        'time_gap_display',
        'created_at',
    )
    list_filter = ('created_at',)
    search_fields = ('gas_incident__incident_id', 'electric_incident__incident_id')
    readonly_fields = ('gas_incident', 'electric_incident', 'distance_ft', 'time_gap_minutes', 'created_at')
    ordering = ('distance_ft', 'time_gap_minutes')
    list_per_page = 25

    @admin.display(description="Gas Incident")
    def gas_incident_link(self, obj):
        return format_html(
            '<strong style="color: #c2410c;">🔥 {}</strong>',
            str(obj.gas_incident.incident_id)
        )

    @admin.display(description="Electric Incident")
    def electric_incident_link(self, obj):
        return format_html(
            '<strong style="color: #1d4ed8;">⚡ {}</strong>',
            str(obj.electric_incident.incident_id)
        )

    @admin.display(description="Planar Distance", ordering="distance_ft")
    def distance_display(self, obj):
        formatted_distance = f"{obj.distance_ft:.2f} ft"
        return format_html(
            '<span style="font-family: monospace; font-weight: bold; color: #b91c1c;">{}</span>',
            formatted_distance
        )

    @admin.display(description="Time Gap", ordering="time_gap_minutes")
    def time_gap_display(self, obj):
        hours = obj.time_gap_minutes / 60.0
        formatted_gap = f"{obj.time_gap_minutes:.1f} min ({hours:.1f} hr)"
        return format_html(
            '<span style="font-family: monospace; color: #4338ca;">{}</span>',
            formatted_gap
        )
