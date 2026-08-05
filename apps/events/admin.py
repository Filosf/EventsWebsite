from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from apps.accounts.admin_i18n import admin_text
from apps.accounts.admin_mixins import RoleBasedAdminMixin
from apps.accounts.permissions import can_export, can_publish, is_administrator
from apps.audit.services import log_action, snapshot

from .admin_forms import LANGUAGE_CHOICES, EventAdminForm, translation_field_names
from .models import Event, EventTheme, EventTranslation
from .validators import sanitize_image_upload


def _event_content_snapshot(event: Event) -> dict:
    translations = list(
        EventTranslation.objects.filter(event=event)
        .order_by("language")
        .values(
            "language",
            "banner_image",
            "title",
            "subtitle",
            "description",
            "location_name",
            "location_address",
            "location_description",
            "success_message",
            "decline_message",
            "registration_closed_message",
            "additional_information",
        )
    )
    try:
        theme = snapshot(EventTheme.objects.get(event=event))
    except EventTheme.DoesNotExist:
        theme = {}
    return {"translations": translations, "theme": theme}


class EventThemeAdminForm(forms.ModelForm):
    class Meta:
        model = EventTheme
        fields = "__all__"
        widgets = {
            "primary_color": forms.TextInput(attrs={"type": "color"}),
            "secondary_color": forms.TextInput(attrs={"type": "color"}),
            "background_color": forms.TextInput(attrs={"type": "color"}),
            "text_color": forms.TextInput(attrs={"type": "color"}),
            "button_color": forms.TextInput(attrs={"type": "color"}),
            "button_text_color": forms.TextInput(attrs={"type": "color"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "background_image": admin_text("Фоновое изображение", "Background image"),
            "logo_image": admin_text("Логотип", "Logo"),
            "primary_color": admin_text("Основной цвет", "Primary color"),
            "secondary_color": admin_text("Дополнительный цвет", "Secondary color"),
            "background_color": admin_text("Цвет фона", "Background color"),
            "text_color": admin_text("Цвет текста", "Text color"),
            "button_color": admin_text("Цвет кнопки", "Button color"),
            "button_text_color": admin_text("Текст кнопки", "Button text"),
            "border_radius": admin_text("Скругление", "Corner radius"),
            "theme_mode": admin_text("Тема", "Theme"),
        }
        for name, label in labels.items():
            self.fields[name].label = label

    def clean(self):
        cleaned = super().clean()
        for field_name in ("background_image", "logo_image"):
            uploaded = cleaned.get(field_name)
            if uploaded and uploaded is not False:
                cleaned[field_name] = sanitize_image_upload(uploaded)
        return cleaned


class EventThemeInline(RoleBasedAdminMixin, admin.StackedInline):
    model = EventTheme
    form = EventThemeAdminForm
    extra = 1
    max_num = 1
    verbose_name = admin_text("Оформление", "Appearance")
    verbose_name_plural = admin_text("Оформление", "Appearance")


@admin.register(Event)
class EventAdmin(RoleBasedAdminMixin, admin.ModelAdmin):
    form = EventAdminForm
    change_form_template = "admin/events/event/change_form.html"
    list_display = [
        "event_name",
        "status_label",
        "event_date",
        "language_badges",
        "registration_count",
        "event_pages",
        "stats_link",
        "export_link",
    ]
    list_display_links = ["event_name"]
    list_filter = ["status", "default_language"]
    search_fields = ["internal_name", "slug", "translations__title"]
    prepopulated_fields = {"slug": ("internal_name",)}
    inlines = [EventThemeInline]
    actions = ["publish_events", "close_registrations", "archive_events"]
    save_on_top = True

    class Media:
        css = {"all": ("admin/css/event_editor.css",)}
        js = ("admin/js/event_editor.js",)

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            (admin_text("Событие", "Event"), {"fields": ["internal_name", "slug", "status", "creator"]}),
            (admin_text("Дата и место", "Date and venue"), {"fields": ["starts_at", "ends_at", "registration_starts_at", "registration_ends_at", "timezone"]}),
            (admin_text("Языки", "Languages"), {"fields": ["enabled_languages", "default_language"], "classes": ["language-settings"]}),
            (admin_text("Регистрация", "Registration"), {"fields": ["max_guests", "allow_public_registration", "require_email", "require_phone"]}),
            (admin_text("Публикация", "Publishing"), {"fields": ["is_search_engine_visible", "published_time"]}),
        ]
        for language, label in LANGUAGE_CHOICES:
            fieldsets.append(
                (
                    label,
                    {
                        "fields": translation_field_names(language),
                        "classes": ["language-panel", f"language-{language}"],
                    },
                )
            )
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        fields = ["creator", "published_time"]
        if not can_publish(request.user):
            fields.append("status")
        return fields

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("translations").annotate(registrations_total=Count("registrations", distinct=True))

    def get_list_display(self, request):
        fields = list(super().get_list_display(request))
        if not can_export(request.user):
            fields.remove("export_link")
        return fields

    def change_view(self, request, object_id, form_url="", extra_context=None):
        event = self.get_object(request, object_id)
        context = dict(extra_context or {})
        if event:
            labels = dict(LANGUAGE_CHOICES)
            preview_languages = [
                {
                    "code": language,
                    "label": labels[language],
                    "short_label": language.upper(),
                    "url": reverse("events:event_page_language", kwargs={"language": language, "slug": event.slug}),
                }
                for language in event.supported_languages
                if language in labels
            ]
            context["preview_languages"] = preview_languages
            context["preview_url"] = next(
                (item["url"] for item in preview_languages if item["code"] == event.default_language),
                preview_languages[0]["url"] if preview_languages else "",
            )
        return super().change_view(request, object_id, form_url, context)

    def save_model(self, request, obj, form, change):
        previous_obj = Event.objects.get(pk=obj.pk) if change else None
        previous = snapshot(previous_obj) if previous_obj else {}
        if previous_obj and previous_obj.status != obj.status and not can_publish(request.user):
            raise PermissionDenied
        if not change:
            obj.created_by = request.user
        if obj.status == Event.Status.PUBLISHED and (not previous_obj or previous_obj.status != Event.Status.PUBLISHED):
            obj.published_at = timezone.now()
        super().save_model(request, obj, form, change)
        action = "event_created" if not change else "event_updated"
        if previous_obj and previous_obj.status != obj.status:
            action = {
                Event.Status.PUBLISHED: "event_published",
                Event.Status.REGISTRATION_CLOSED: "registration_closed",
                Event.Status.ARCHIVED: "event_archived",
            }.get(obj.status, action)
        log_action(request=request, action=action, instance=obj, previous_data=previous)

    def save_related(self, request, form, formsets, change):
        previous_content = _event_content_snapshot(form.instance) if change else {}
        content_changed = form.translation_changed or any(formset.has_changed() for formset in formsets)
        super().save_related(request, form, formsets, change)
        EventTheme.objects.get_or_create(event=form.instance)
        form.save_translations()
        if content_changed:
            log_action(
                request=request,
                action="event_content_updated",
                instance=form.instance,
                previous_data=previous_content,
                new_data=_event_content_snapshot(form.instance),
            )

    def has_delete_permission(self, request, obj=None):
        return is_administrator(request.user)

    def _change_status(self, request, queryset, status, action):
        if not can_publish(request.user):
            raise PermissionDenied
        for event in queryset:
            previous = snapshot(event)
            event.status = status
            if status == Event.Status.PUBLISHED:
                event.published_at = timezone.now()
            event.save()
            log_action(request=request, action=action, instance=event, previous_data=previous)

    @admin.action(description=admin_text("Опубликовать выбранные события", "Publish selected events"))
    def publish_events(self, request, queryset):
        self._change_status(request, queryset, Event.Status.PUBLISHED, "event_published")

    @admin.action(description=admin_text("Закрыть регистрацию", "Close registration"))
    def close_registrations(self, request, queryset):
        self._change_status(request, queryset, Event.Status.REGISTRATION_CLOSED, "registration_closed")

    @admin.action(description=admin_text("Архивировать выбранные события", "Archive selected events"))
    def archive_events(self, request, queryset):
        self._change_status(request, queryset, Event.Status.ARCHIVED, "event_archived")

    @admin.display(description=admin_text("Языки", "Languages"))
    def language_badges(self, obj):
        labels = dict(LANGUAGE_CHOICES)
        return format_html_join(
            " ",
            '<span class="event-language-badge">{}</span>',
            ((labels.get(language, language.upper()),) for language in obj.supported_languages),
        )

    @admin.display(description=admin_text("Ответы", "Responses"), ordering="registrations_total")
    def registration_count(self, obj):
        return obj.registrations_total

    @admin.display(description=admin_text("Название", "Name"), ordering="internal_name")
    def event_name(self, obj):
        return obj.internal_name

    @admin.display(description=admin_text("Статус", "Status"), ordering="status")
    def status_label(self, obj):
        return obj.get_status_display()

    @admin.display(description=admin_text("Дата", "Date"), ordering="starts_at")
    def event_date(self, obj):
        return obj.starts_at

    @admin.display(description=admin_text("Создал", "Created by"))
    def creator(self, obj):
        return obj.created_by if obj and obj.created_by_id else "-"

    @admin.display(description=admin_text("Опубликован", "Published at"))
    def published_time(self, obj):
        return obj.published_at or "-"

    @admin.display(description=admin_text("Страницы ивента", "Event pages"))
    def event_pages(self, obj):
        copy_label = admin_text("Скопировать ссылку", "Copy link")
        copied_label = admin_text("Скопировано", "Copied")
        links = []
        for language in obj.supported_languages:
            url = reverse("events:event_page_language", kwargs={"language": language, "slug": obj.slug})
            short_label = language.upper()
            aria_label = f"{copy_label} {short_label}"
            links.append((url, short_label, url, copy_label, copied_label, copy_label, aria_label))
        return format_html(
            '<div class="event-public-links">{}</div>',
            format_html_join(
                "",
                '<span class="event-public-link"><a href="{}" target="_blank" rel="noopener">{}</a><button type="button" class="copy-link-button" data-copy-url="{}" data-copy-label="{}" data-copied-label="{}" title="{}" aria-label="{}"></button></span>',
                links,
            ),
        )

    @admin.display(description=admin_text("Статистика", "Statistics"))
    def stats_link(self, obj):
        url = reverse("event_admin:statistics", kwargs={"event_id": obj.id})
        return format_html('<a href="{}">{}</a>', url, admin_text("Смотреть", "View"))

    @admin.display(description=admin_text("Экспорт", "Export"))
    def export_link(self, obj):
        url = reverse("event_admin:registrations_export", kwargs={"event_id": obj.id})
        return format_html('<a href="{}">CSV</a>', url)

    def delete_model(self, request, obj):
        log_action(request=request, action="event_deleted", instance=obj, previous_data=snapshot(obj), new_data={})
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)
