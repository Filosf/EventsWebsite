import csv
import io
import os
import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.analytics.services import statistics_for_event
from apps.audit.models import AuditLog
from apps.events.admin import EventAdmin
from apps.events.admin_forms import TRANSLATION_FIELDS, EventAdminForm
from apps.events.models import Event, EventTheme, EventTranslation
from apps.events.services import create_event, unique_event_slug
from apps.events.validators import (
    MAX_IMAGE_SIZE,
    sanitize_image_upload,
    validate_image_upload,
)
from apps.registrations.admin import RegistrationAdmin
from apps.registrations.models import Registration
from apps.registrations.services import export_registrations_csv, iter_registrations_csv


@override_settings(REGISTRATION_MIN_FORM_SECONDS=0)
class EventMvpTests(TestCase):
    def setUp(self):
        cache.clear()
        users = get_user_model()
        self.administrator = users.objects.create_superuser(username="admin@example.com", email="admin@example.com", password="pass")
        self.manager = users.objects.create_user(username="staff@example.com", email="staff@example.com", password="pass", is_staff=True)
        self.viewer = users.objects.create_user(username="visitor@example.com", email="visitor@example.com", password="pass")
        self.event = create_event(
            created_by=self.administrator,
            internal_name="Wedding",
            starts_at=timezone.now(),
            supported_languages=["ru", "en", "he"],
        )
        self.event.status = Event.Status.PUBLISHED
        self.event.save()
        EventTranslation.objects.create(event=self.event, language="en", title="Wedding")
        EventTranslation.objects.create(event=self.event, language="he", title="חתונה")

    def test_create_event_creates_slug_theme_and_default_translation(self):
        self.assertEqual(self.event.slug, "wedding")
        self.assertTrue(EventTheme.objects.filter(event=self.event).exists())
        self.assertEqual(self.event.translations.get(language="ru").title, "Wedding")

    def test_unique_slug_adds_suffix(self):
        self.assertEqual(unique_event_slug("Wedding"), "wedding-2")

    def test_public_registration_records_rsvp_and_statistics(self):
        response = self.client.post(
            reverse("events:event_page_language", kwargs={"language": "ru", "slug": self.event.slug}),
            {
                "full_name": "Test Guest",
                "email": "guest@example.com",
                "phone": "+972500000000",
                "attendance_status": Registration.Attendance.ATTENDING,
                "guest_count": "2",
                "comment": "See you",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.event.registrations.count(), 1)
        stats = statistics_for_event(self.event)
        self.assertEqual(stats["attending_total"], 1)
        self.assertEqual(stats["expected_guests"], 3)

    def test_duplicate_registration_is_blocked_with_organizer_message(self):
        url = reverse("events:event_page_language", kwargs={"language": "ru", "slug": self.event.slug})
        data = {
            "full_name": "Test Guest",
            "email": "guest@example.com",
            "phone": "+972500000000",
            "attendance_status": Registration.Attendance.ATTENDING,
            "guest_count": "0",
            "comment": "",
        }
        self.assertEqual(self.client.post(url, data).status_code, 302)
        duplicate = self.client.post(url, data)
        self.assertEqual(duplicate.status_code, 200)
        self.assertContains(duplicate, "Ответ от этого гостя уже получен")
        self.assertEqual(self.event.registrations.count(), 1)

    def test_same_name_without_contacts_is_only_duplicate_for_same_browser(self):
        url = reverse("events:event_page_language", kwargs={"language": "ru", "slug": self.event.slug})
        data = {
            "full_name": "Same Name",
            "attendance_status": Registration.Attendance.DECLINED,
            "guest_count": "0",
        }
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertContains(self.client.post(url, data), "Ответ от этого гостя уже получен")

        another_browser = Client()
        self.assertEqual(another_browser.post(url, data).status_code, 302)
        self.assertEqual(self.event.registrations.filter(full_name="Same Name").count(), 2)

    def test_honeypot_rejects_bot_submission(self):
        url = reverse("events:event_page_language", kwargs={"language": "ru", "slug": self.event.slug})
        response = self.client.post(
            url,
            {
                "full_name": "Bot",
                "attendance_status": Registration.Attendance.DECLINED,
                "guest_count": "0",
                "website": "https://spam.example",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.event.registrations.count(), 0)

    @override_settings(REGISTRATION_MIN_FORM_SECONDS=3)
    def test_submission_without_timing_token_is_rejected(self):
        url = reverse("events:event_page_language", kwargs={"language": "ru", "slug": self.event.slug})
        response = self.client.post(
            url,
            {
                "full_name": "Too Fast",
                "attendance_status": Registration.Attendance.DECLINED,
                "guest_count": "0",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Пожалуйста, заполните форму")
        self.assertEqual(self.event.registrations.count(), 0)

    def test_image_upload_limit_is_five_megabytes(self):
        with self.assertRaises(ValidationError):
            validate_image_upload(SimpleNamespace(size=MAX_IMAGE_SIZE + 1, width=100, height=100))

    def test_image_sanitizer_removes_exif(self):
        source = io.BytesIO()
        image = Image.new("RGB", (20, 20), "white")
        exif = Image.Exif()
        exif[0x010F] = "Test camera"
        image.save(source, format="JPEG", exif=exif)
        upload = SimpleUploadedFile("photo.jpg", source.getvalue(), content_type="image/jpeg")

        sanitized = sanitize_image_upload(upload)
        with Image.open(sanitized) as result:
            self.assertFalse(result.getexif())

    def test_replaced_event_image_is_removed_from_storage(self):
        translation = self.event.translations.get(language="ru")
        image_bytes = io.BytesIO()
        Image.new("RGB", (10, 10), "white").save(image_bytes, format="PNG")
        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            translation.banner_image.save("old.png", ContentFile(image_bytes.getvalue()), save=True)
            old_path = translation.banner_image.path
            self.assertTrue(os.path.exists(old_path))
            with self.captureOnCommitCallbacks(execute=True):
                translation.banner_image.save("new.png", ContentFile(image_bytes.getvalue()), save=True)
            self.assertFalse(os.path.exists(old_path))

    @override_settings(REGISTRATION_RATE_LIMIT_COUNT=2, REGISTRATION_DAILY_LIMIT_COUNT=100)
    def test_registration_rate_limit_returns_429(self):
        url = reverse("events:event_page_language", kwargs={"language": "ru", "slug": self.event.slug})
        for number in range(2):
            response = self.client.post(
                url,
                {
                    "full_name": f"Guest {number}",
                    "email": f"guest{number}@example.com",
                    "attendance_status": Registration.Attendance.DECLINED,
                    "guest_count": "0",
                },
            )
            self.assertEqual(response.status_code, 302)
        limited = self.client.post(
            url,
            {
                "full_name": "Guest 3",
                "email": "guest3@example.com",
                "attendance_status": Registration.Attendance.DECLINED,
                "guest_count": "0",
            },
        )
        self.assertEqual(limited.status_code, 429)
        self.assertContains(limited, "Слишком много попыток", status_code=429)

    def test_interface_is_localized_and_has_no_empty_attendance_choice(self):
        ru = self.client.get(reverse("events:event_page_language", kwargs={"language": "ru", "slug": self.event.slug}))
        self.assertContains(ru, '<select name="guest_count"')
        ru_party_sizes = list(ru.context["form"].fields["guest_count"].widget.choices)
        self.assertEqual(len(ru_party_sizes), self.event.max_guests + 1)
        self.assertEqual(ru_party_sizes[0], (0, "Буду один"))
        self.assertEqual(ru_party_sizes[1], (1, "Будем вдвоём"))
        self.assertEqual(ru_party_sizes[4], (4, "Нас будет пятеро"))
        self.assertEqual(ru_party_sizes[-1], (self.event.max_guests, "Нас будет 11"))

        en = self.client.get(reverse("events:event_page_language", kwargs={"language": "en", "slug": self.event.slug}))
        self.assertContains(en, "Will you attend?")
        self.assertContains(en, "How many people will attend?")
        en_party_sizes = list(en.context["form"].fields["guest_count"].widget.choices)
        self.assertEqual(en_party_sizes[1], (1, "There will be two of us"))
        self.assertContains(en, "Submit response")
        self.assertContains(en, 'class="attendance-options"')
        self.assertNotContains(en, "---------")
        he = self.client.get(reverse("events:event_page_language", kwargs={"language": "he", "slug": self.event.slug}))
        self.assertContains(he, 'dir="rtl"')
        self.assertContains(he, "האם תגיעו?")
        he_party_sizes = list(he.context["form"].fields["guest_count"].widget.choices)
        self.assertEqual(he_party_sizes[0], (0, "אגיע לבד"))

    def test_unique_visitor_uses_stable_cookie(self):
        url = reverse("events:event_page_language", kwargs={"language": "ru", "slug": self.event.slug})
        first = self.client.get(url)
        self.assertIn("event_visitor", first.cookies)
        self.client.get(url)
        stats = statistics_for_event(self.event)
        self.assertEqual(stats["page_views"], 1)
        self.assertEqual(stats["unique_visitors"], 1)

    def test_staff_preview_does_not_increment_page_views(self):
        self.client.force_login(self.manager)
        url = reverse("events:event_page_language", kwargs={"language": "ru", "slug": self.event.slug})
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(statistics_for_event(self.event)["page_views"], 0)

    def test_archived_event_is_not_public(self):
        self.event.status = Event.Status.ARCHIVED
        self.event.save()
        response = self.client.get(reverse("events:event_page_language", kwargs={"language": "ru", "slug": self.event.slug}))
        self.assertEqual(response.status_code, 404)

    def test_thanks_page_requires_real_registration_token(self):
        url = reverse(
            "events:registration_thanks",
            kwargs={"language": "ru", "slug": self.event.slug, "token": uuid.uuid4()},
        )
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_csv_export_neutralizes_formulas_and_has_bom(self):
        Registration.objects.create(
            event=self.event,
            full_name="=HYPERLINK(\"https://example.test\")",
            attendance_status=Registration.Attendance.DECLINED,
            guest_count=0,
        )
        content = export_registrations_csv(self.event)
        self.assertTrue(content.startswith("\ufeff"))
        self.assertIn("'=HYPERLINK", content)

    def test_statistics_and_streaming_export_handle_large_guest_list(self):
        registrations = [
            Registration(
                event=self.event,
                full_name=f"Load Guest {number:04d}",
                email=f"load{number:04d}@example.com",
                attendance_status=Registration.Attendance.ATTENDING,
                guest_count=2,
            )
            for number in range(2000)
        ]
        Registration.objects.bulk_create(registrations, batch_size=500)
        stats = statistics_for_event(self.event)
        self.assertEqual(stats["registrations_total"], 2000)
        self.assertEqual(stats["expected_guests"], 6000)
        self.assertEqual(sum(1 for _ in iter_registrations_csv(self.event)), 2002)

    def test_non_staff_cannot_open_admin_and_staff_cannot_manage_users(self):
        self.client.force_login(self.viewer)
        event_change = reverse("admin:events_event_change", args=[self.event.pk])
        self.assertEqual(self.client.post(event_change, {}).status_code, 302)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(reverse("admin:auth_user_changelist")).status_code, 403)

    def test_staff_can_change_events_and_administrator_has_full_access(self):
        event_admin = EventAdmin(Event, admin.site)
        manager_request = RequestFactory().get("/")
        manager_request.user = self.manager
        admin_request = RequestFactory().get("/")
        admin_request.user = self.administrator
        self.assertTrue(event_admin.has_change_permission(manager_request, self.event))
        self.assertFalse(event_admin.has_delete_permission(manager_request, self.event))
        self.assertTrue(event_admin.has_delete_permission(admin_request, self.event))

        delete_url = reverse("admin:events_event_delete", args=[self.event.pk])
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(delete_url).status_code, 403)
        self.client.force_login(self.administrator)
        self.assertEqual(self.client.get(delete_url).status_code, 200)

    def test_export_permission_and_audit(self):
        export_url = reverse("event_admin:registrations_export", kwargs={"event_id": self.event.pk})
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(export_url).status_code, 302)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get(export_url).status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action="registrations_exported", user=self.manager).exists())

    def test_event_status_change_is_audited(self):
        request = RequestFactory().post("/")
        request.user = self.administrator
        self.event.status = Event.Status.REGISTRATION_CLOSED
        EventAdmin(Event, admin.site).save_model(request, self.event, form=None, change=True)
        log = AuditLog.objects.get(action="registration_closed", event=self.event)
        self.assertEqual(log.previous_data["status"], Event.Status.PUBLISHED)
        self.assertEqual(log.new_data["status"], Event.Status.REGISTRATION_CLOSED)

    def test_translation_content_audit_contains_before_and_after_values(self):
        event_admin = EventAdmin(Event, admin.site)
        request = RequestFactory().post("/")
        request.user = self.administrator

        class ContentForm:
            instance = self.event
            translation_changed = True

            def save_m2m(inner_self):
                return None

            def save_translations(inner_self):
                translation = self.event.translations.get(language="ru")
                translation.title = "Changed wedding"
                translation.save(update_fields=["title"])

        event_admin.save_related(request, ContentForm(), [], change=True)
        log = AuditLog.objects.get(action="event_content_updated", event=self.event)
        previous = {item["language"]: item for item in log.previous_data["translations"]}
        current = {item["language"]: item for item in log.new_data["translations"]}
        self.assertEqual(previous["ru"]["title"], "Wedding")
        self.assertEqual(current["ru"]["title"], "Changed wedding")

    def test_registration_change_is_audited(self):
        registration = Registration.objects.create(
            event=self.event,
            full_name="Guest",
            attendance_status=Registration.Attendance.ATTENDING,
            guest_count=1,
        )
        request = RequestFactory().post("/")
        request.user = self.manager
        registration.guest_count = 2
        RegistrationAdmin(Registration, admin.site).save_model(request, registration, form=None, change=True)
        log = AuditLog.objects.get(action="registration_updated", entity_id=str(registration.pk))
        self.assertEqual(log.previous_data["guest_count"], 1)
        self.assertEqual(log.new_data["guest_count"], 2)

    def test_statistics_is_bilingual_and_lists_responses(self):
        registration = Registration.objects.create(
            event=self.event,
            full_name="Guest With Typo",
            email="typo@example.com",
            attendance_status=Registration.Attendance.ATTENDING,
            guest_count=2,
        )
        self.client.force_login(self.administrator)
        url = reverse("event_admin:statistics", args=[self.event.pk])

        russian = self.client.get(url)
        self.assertContains(russian, "Статистика")
        self.assertContains(russian, "Ответы гостей")
        self.assertContains(russian, registration.full_name)

        self.client.post(reverse("set_language"), {"language": "en", "next": url})
        english = self.client.get(url)
        self.assertContains(english, "Statistics")
        self.assertContains(english, "Guest responses")
        self.assertContains(english, "Attending")

    def test_response_sorting_filtering_and_export_use_the_visible_list(self):
        registrations = [
            Registration.objects.create(
                event=self.event,
                full_name="Alpha Guest",
                email="alpha@example.com",
                attendance_status=Registration.Attendance.ATTENDING,
                guest_count=2,
            ),
            Registration.objects.create(
                event=self.event,
                full_name="Beta Guest",
                email="beta@example.com",
                attendance_status=Registration.Attendance.DECLINED,
                guest_count=0,
            ),
            Registration.objects.create(
                event=self.event,
                full_name="Charlie Guest",
                email="charlie@example.com",
                attendance_status=Registration.Attendance.ATTENDING,
                guest_count=0,
            ),
        ]
        self.client.force_login(self.administrator)
        statistics_url = reverse("event_admin:statistics", args=[self.event.pk])

        by_name = self.client.get(statistics_url, {"status": "all", "sort": "name"})
        content = by_name.content.decode()
        self.assertLess(content.index("Alpha Guest"), content.index("Beta Guest"))
        self.assertLess(content.index("Beta Guest"), content.index("Charlie Guest"))

        attending_desc = self.client.get(statistics_url, {"status": "attending", "sort": "guests_desc"})
        self.assertContains(attending_desc, registrations[0].full_name)
        self.assertContains(attending_desc, registrations[2].full_name)
        self.assertNotContains(attending_desc, registrations[1].full_name)
        attending_content = attending_desc.content.decode()
        self.assertLess(attending_content.index("Alpha Guest"), attending_content.index("Charlie Guest"))

        export_url = reverse("event_admin:registrations_export", args=[self.event.pk])
        exported = self.client.get(export_url, {"status": "attending", "sort": "guests_asc"})
        exported_content = b"".join(exported.streaming_content).decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(exported_content)))
        self.assertEqual([row["full_name"] for row in rows], ["Charlie Guest", "Alpha Guest"])
        self.assertEqual([row["additional_guests"] for row in rows], ["0", "2"])

        stats = statistics_for_event(self.event)
        self.assertEqual(stats["expected_guests"], 4)

    def test_only_administrator_can_edit_or_delete_response(self):
        registration = Registration.objects.create(
            event=self.event,
            full_name="Guset Name",
            email="guest@example.com",
            attendance_status=Registration.Attendance.ATTENDING,
            guest_count=2,
        )
        statistics_url = reverse("event_admin:statistics", args=[self.event.pk])
        edit_url = reverse("event_admin:registration_edit", args=[self.event.pk, registration.pk])
        delete_url = reverse("event_admin:registration_delete", args=[self.event.pk, registration.pk])

        self.client.force_login(self.manager)
        staff_statistics = self.client.get(statistics_url)
        self.assertEqual(staff_statistics.status_code, 200)
        self.assertNotContains(staff_statistics, edit_url)
        self.assertEqual(self.client.get(edit_url).status_code, 403)
        self.assertEqual(self.client.get(delete_url).status_code, 403)

        self.client.force_login(self.administrator)
        edited = self.client.post(
            edit_url,
            {
                "full_name": "Guest Name",
                "email": registration.email,
                "phone": "+972500000000",
                "attendance_status": Registration.Attendance.ATTENDING,
                "guest_count": 3,
                "comment": "Corrected",
            },
        )
        self.assertEqual(edited.status_code, 302)
        registration.refresh_from_db()
        self.assertEqual(registration.full_name, "Guest Name")
        self.assertEqual(registration.guest_count, 3)
        edit_log = AuditLog.objects.get(action="registration_updated", entity_id=str(registration.pk))
        self.assertEqual(edit_log.previous_data["full_name"], "Guset Name")
        self.assertEqual(edit_log.new_data["full_name"], "Guest Name")

        confirmation = self.client.get(delete_url)
        self.assertContains(confirmation, "Вы уверены, что хотите удалить этот ответ?")
        deleted = self.client.post(delete_url)
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(Registration.objects.filter(pk=registration.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action="registration_deleted", entity_id=str(registration.pk)).exists())

    def test_admin_requires_authentication(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("admin:events_event_changelist"))
        protected = self.client.get(reverse("admin:events_event_changelist"))
        self.assertEqual(protected.status_code, 302)
        self.assertIn(reverse("admin:login"), protected.url)

    def test_healthcheck_verifies_database_and_cache(self):
        response = self.client.get(reverse("healthcheck"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_event_is_single_admin_object_with_language_editor(self):
        self.client.force_login(self.administrator)
        app_index_url = reverse("admin:app_list", kwargs={"app_label": "events"})
        app_index = self.client.get(app_index_url)
        self.assertRedirects(
            app_index,
            reverse("admin:events_event_changelist"),
            fetch_redirect_response=False,
        )

        event_list = self.client.get(reverse("admin:events_event_changelist"))
        self.assertEqual(event_list.status_code, 200)
        self.assertEqual(event_list.context["cl"].result_count, 1)
        self.assertNotContains(event_list, f'href="{app_index_url}"')
        self.assertContains(event_list, "Ивенты")
        self.assertContains(event_list, "admin/css/event_changelist.css")
        self.assertContains(event_list, "admin/js/event_changelist.js")
        self.assertContains(event_list, 'class="copy-link-button"', count=3)
        for language in ("ru", "en", "he"):
            self.assertContains(event_list, reverse("events:event_page_language", kwargs={"language": language, "slug": self.event.slug}))
        self.assertNotIn(EventTranslation, admin.site._registry)
        self.assertNotIn(EventTheme, admin.site._registry)

        editor = self.client.get(reverse("admin:events_event_change", args=[self.event.pk]))
        self.assertContains(editor, 'class="event-page-toolbar"')
        self.assertContains(editor, 'class="copy-link-button"', count=3)
        self.assertContains(editor, 'id="id_ru_banner_image"')
        self.assertContains(editor, 'id="id_en_banner_image"')
        self.assertContains(editor, 'id="id_he_banner_image"')
        self.assertContains(editor, '<textarea name="ru_subtitle"')
        self.assertContains(editor, '<textarea name="en_subtitle"')
        self.assertContains(editor, '<textarea name="he_subtitle"')
        self.assertContains(editor, 'id="event-preview-viewport"')
        self.assertContains(editor, 'id="event-preview-frame"')
        self.assertContains(editor, "language-panel language-ru")
        self.assertContains(editor, "language-panel language-en")
        self.assertContains(editor, "language-panel language-he")
        self.assertEqual(editor.context["preview_languages"][0]["code"], "ru")
        self.assertEqual(self.client.get(reverse("admin:events_event_add")).status_code, 200)

    def test_admin_navigation_is_bilingual_and_has_no_analytics_or_audit_tabs(self):
        self.client.force_login(self.administrator)
        event_list_url = reverse("admin:events_event_changelist")

        russian = self.client.get(event_list_url)
        self.assertContains(russian, "Язык админки")
        self.assertContains(russian, "Ивенты")
        self.assertNotContains(russian, ">Регистрации<")
        self.assertNotContains(russian, ">Аналитика<")
        self.assertNotContains(russian, ">Журнал<")

        switched = self.client.post(reverse("set_language"), {"language": "en", "next": event_list_url})
        self.assertEqual(switched.status_code, 302)
        english = self.client.get(event_list_url)
        self.assertContains(english, "Admin language")
        self.assertContains(english, "Events")
        self.assertContains(english, "Event pages")
        self.assertNotContains(english, ">Registrations<")
        self.assertNotContains(english, ">Analytics<")
        self.assertNotContains(english, ">Audit log<")

    def test_user_admin_uses_email_and_has_only_staff_or_administrator_access(self):
        self.client.force_login(self.administrator)
        add_url = reverse("admin:auth_user_add")
        add_page = self.client.get(add_url)
        self.assertEqual(add_page.status_code, 200)
        self.assertContains(add_page, 'name="email"')
        self.assertContains(add_page, 'name="password1"')
        self.assertContains(add_page, 'name="password2"')
        self.assertContains(add_page, "Администратор")
        self.assertNotContains(add_page, 'name="username"')
        self.assertNotContains(add_page, 'name="groups"')
        self.assertNotContains(add_page, 'name="is_staff"')
        self.assertNotIn(Group, admin.site._registry)

        user_admin = admin.site._registry[get_user_model()]
        request = RequestFactory().get("/")
        request.user = self.administrator
        self.assertEqual(set(user_admin.get_readonly_fields(request, self.administrator)), {"is_active", "is_superuser"})
        self.assertNotIn("delete_selected", user_admin.get_actions(request))
        with self.assertRaises(PermissionDenied):
            user_admin.delete_queryset(request, get_user_model().objects.filter(pk=self.administrator.pk))

        own_change_page = self.client.get(reverse("admin:auth_user_change", args=[self.administrator.pk]))
        self.assertEqual(own_change_page.status_code, 200)
        self.assertNotContains(own_change_page, 'name="is_active"')
        self.assertNotContains(own_change_page, 'name="is_superuser"')

        response = self.client.post(
            add_url,
            {
                "email": "new.staff@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
                "first_name": "New",
                "last_name": "Staff",
            },
        )
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(email="new.staff@example.com")
        self.assertEqual(user.username, user.email)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    @override_settings(DEBUG=False)
    def test_demo_seed_is_blocked_outside_debug(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo")

    def test_bootstrap_admin_uses_environment_and_does_not_reset_password(self):
        environment = {
            "ADMIN_EMAIL": "release.admin@example.com",
            "ADMIN_PASSWORD": "Release-Only-Strong-Password-937!",
        }
        with patch.dict(os.environ, environment, clear=False):
            call_command("bootstrap_admin")
            administrator = get_user_model().objects.get(email=environment["ADMIN_EMAIL"])
            self.assertTrue(administrator.is_superuser)
            self.assertTrue(administrator.check_password(environment["ADMIN_PASSWORD"]))
            call_command("bootstrap_admin")
            administrator.refresh_from_db()
            self.assertTrue(administrator.check_password(environment["ADMIN_PASSWORD"]))

    @override_settings(
        DEBUG=False,
        SECRET_KEY="release-preflight-secret-key-93725184062731584062517395184062",
        ALLOWED_HOSTS=["events.example.com", "localhost", "web"],
        CSRF_TRUSTED_ORIGINS=["https://events.example.com"],
        SECURE_SSL_REDIRECT=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
    )
    def test_release_preflight_passes_with_secure_runtime(self):
        with patch.dict(os.environ, {"SITE_ADDRESS": "events.example.com"}, clear=False):
            call_command("release_preflight")

    def test_each_language_uses_its_own_banner(self):
        russian = self.event.translations.get(language="ru")
        english = self.event.translations.get(language="en")
        russian.banner_image = "events/banners/russian.jpg"
        english.banner_image = "events/banners/english.jpg"
        russian.save(update_fields=["banner_image"])
        english.save(update_fields=["banner_image"])

        russian_page = self.client.get(reverse("events:event_page_language", kwargs={"language": "ru", "slug": self.event.slug}))
        english_page = self.client.get(reverse("events:event_page_language", kwargs={"language": "en", "slug": self.event.slug}))
        self.assertContains(russian_page, "/media/events/banners/russian.jpg")
        self.assertNotContains(russian_page, "/media/events/banners/english.jpg")
        self.assertContains(english_page, "/media/events/banners/english.jpg")

    def test_language_can_be_disabled_without_losing_translation(self):
        data = {
            "internal_name": self.event.internal_name,
            "slug": self.event.slug,
            "status": self.event.status,
            "starts_at": self.event.starts_at.strftime("%Y-%m-%d %H:%M:%S"),
            "ends_at": "",
            "registration_starts_at": "",
            "registration_ends_at": "",
            "timezone": self.event.timezone,
            "default_language": "ru",
            "enabled_languages": ["ru", "en"],
            "max_guests": self.event.max_guests,
            "allow_public_registration": "on",
            "is_search_engine_visible": "",
            "published_at": self.event.published_at.strftime("%Y-%m-%d %H:%M:%S") if self.event.published_at else "",
            "created_by": self.administrator.pk,
        }
        translations = {item.language: item for item in self.event.translations.all()}
        for language in ("ru", "en", "he"):
            translation = translations[language]
            for name, _, _ in TRANSLATION_FIELDS:
                data[f"{language}_{name}"] = getattr(translation, name)

        form = EventAdminForm(data=data, instance=self.event)
        self.assertTrue(form.is_valid(), form.errors)
        event = form.save()
        form.save_translations()
        self.assertEqual(event.supported_languages, ["ru", "en"])
        self.assertEqual(event.translations.get(language="he").title, "חתונה")
