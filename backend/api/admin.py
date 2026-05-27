import json

from django.contrib import admin
from django.utils.html import format_html

from .models import TrainingSample

admin.site.site_header = 'Audit AI Admin'
admin.site.site_title = 'Audit AI Dashboard'
admin.site.index_title = 'Machine Learning & Validation'


@admin.register(TrainingSample)
class TrainingSampleAdmin(admin.ModelAdmin):
    list_display = ('id', 'label', 'score', 'created_at', 'feature_count')
    list_filter = ('label', 'created_at')
    search_fields = ('label',)
    readonly_fields = ('document', 'features', 'label', 'score', 'feature_count', 'created_at', 'formatted_features')
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def score(self, obj):
        values = list(obj.features.values() if obj.features else [])
        if not values:
            return '0%'

        ratio = sum(values) / len(values)
        percentage = round(ratio * 100, 1)
        color = '#1b5e20' if ratio > 0.8 else '#b71c1c'
        return format_html(
            '<span style="font-weight:700; color:{}">{}%</span>',
            color,
            percentage,
        )
    score.short_description = 'Score'

    def feature_count(self, obj):
        return len(obj.features or {})
    feature_count.short_description = 'Rule count'

    def get_fields(self, request, obj=None):
        return ('document', 'label', 'formatted_features', 'score', 'feature_count', 'created_at')

    def formatted_features(self, obj):
        formatted = json.dumps(obj.features, indent=2, ensure_ascii=False)
        max_length = 500
        if len(formatted) > max_length:
            return format_html(
                '<pre style="white-space: pre-wrap; overflow: hidden; text-overflow: ellipsis; display: block;">{}</pre>',
                formatted[:max_length].rstrip() + '...',
            )
        return format_html(
            '<pre style="white-space: pre-wrap; display: block;">{}</pre>',
            formatted,
        )
    formatted_features.short_description = 'Features'
