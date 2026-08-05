from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.events.models import Event, EventTheme, EventTranslation
from apps.registrations.models import Registration


class Command(BaseCommand):
    help = "Create the local administrator and multilingual demo wedding."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo is available only when DEBUG=True.")
        users = get_user_model()
        email = "admin@example.com"
        user = users.objects.filter(email__iexact=email).first() or users.objects.filter(username__iexact="Admin").first()
        if user is None:
            user = users(username=email, email=email)
        user.username = email
        user.email = "admin@example.com"
        user.is_staff = True
        user.is_superuser = True
        user.set_password("admin1")
        user.save()

        event, _ = Event.objects.update_or_create(
            slug="anna-david-wedding-2026",
            defaults={
                "created_by": user,
                "internal_name": "Свадьба Анны и Давида",
                "status": Event.Status.PUBLISHED,
                "starts_at": timezone.now() + timedelta(days=30),
                "timezone": "Asia/Jerusalem",
                "default_language": "ru",
                "supported_languages": ["ru", "en", "he"],
                "max_guests": 6,
                "allow_public_registration": True,
                "published_at": timezone.now(),
            },
        )
        EventTheme.objects.update_or_create(
            event=event,
            defaults={
                "primary_color": "#31572c",
                "secondary_color": "#b08968",
                "background_color": "#f8f7f3",
                "text_color": "#1f2933",
                "button_color": "#31572c",
                "button_text_color": "#ffffff",
            },
        )
        translations = {
            "ru": {
                "title": "Свадьба Анны и Давида",
                "subtitle": "Будем рады разделить с вами наш день",
                "description": "Дорогие друзья и родные! Приглашаем вас отпраздновать нашу свадьбу.",
                "location_name": "Сад торжеств Carmel View",
                "location_address": "Хайфа, Израиль",
                "additional_information": "Дресс-код: элегантный вечерний. Начало церемонии в 18:00.",
                "success_message": "Спасибо! Ваш ответ сохранён.",
                "registration_closed_message": "Регистрация на свадьбу закрыта.",
            },
            "en": {
                "title": "Anna and David Wedding",
                "subtitle": "We would love to share our special day with you",
                "description": "Dear family and friends, please join us to celebrate our wedding.",
                "location_name": "Carmel View Events Garden",
                "location_address": "Haifa, Israel",
                "additional_information": "Dress code: elegant evening. The ceremony begins at 18:00.",
                "success_message": "Thank you! Your response has been saved.",
                "registration_closed_message": "Wedding registration is closed.",
            },
            "he": {
                "title": "החתונה של אנה ודוד",
                "subtitle": "נשמח לחגוג איתכם את היום שלנו",
                "description": "משפחה וחברים יקרים, אנו מזמינים אתכם לחגוג איתנו את חתונתנו.",
                "location_name": "גן האירועים Carmel View",
                "location_address": "חיפה, ישראל",
                "additional_information": "קוד לבוש: ערב אלגנטי. תחילת הטקס בשעה 18:00.",
                "success_message": "תודה! תשובתכם נשמרה.",
                "registration_closed_message": "ההרשמה לחתונה נסגרה.",
            },
        }
        for language, values in translations.items():
            EventTranslation.objects.update_or_create(event=event, language=language, defaults=values)

        for number in range(1, 51):
            attending = number <= 38
            Registration.objects.update_or_create(
                event=event,
                email=f"demo.guest{number:02d}@example.com",
                defaults={
                    "full_name": f"Тестовый гость {number:02d}",
                    "phone": f"+97250000{number:03d}",
                    "attendance_status": Registration.Attendance.ATTENDING if attending else Registration.Attendance.DECLINED,
                    "guest_count": number % 4 if attending else 0,
                    "comment": "Буду рад прийти!" if attending and number % 5 == 0 else "",
                },
            )

        self.stdout.write(self.style.SUCCESS("Demo administrator, wedding, and 50 responses are ready."))
