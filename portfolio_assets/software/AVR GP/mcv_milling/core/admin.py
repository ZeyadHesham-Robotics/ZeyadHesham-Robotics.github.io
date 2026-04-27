from django.contrib import admin
from .models import SystemSettings, KRLProgram, CalibrationRecord, JobCycle

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    pass

@admin.register(KRLProgram)
class KRLProgramAdmin(admin.ModelAdmin):
    list_display = ['name', 'point_count', 'is_active', 'uploaded_at']

@admin.register(CalibrationRecord)
class CalibrationRecordAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'status', 'correction_x', 'correction_y', 'correction_z']

@admin.register(JobCycle)
class JobCycleAdmin(admin.ModelAdmin):
    list_display = ['cycle_number', 'status', 'started_at', 'completed_at']
