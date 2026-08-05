from django import forms

from apps.accounts.admin_i18n import admin_text

from .models import SUPPORTED_LANGUAGE_CODES, Event, EventTranslation
from .validators import IMAGE_VALIDATORS, sanitize_image_upload

LANGUAGE_CHOICES = [
    ("ru", admin_text("Русский", "Russian")),
    ("en", "English"),
    ("he", "עברית"),
]

TRANSLATION_FIELDS = [
    ("title", admin_text("Заголовок", "Title"), forms.TextInput),
    ("subtitle", admin_text("Подзаголовок", "Subtitle"), forms.TextInput),
    ("description", admin_text("Описание", "Description"), forms.Textarea),
    ("location_name", admin_text("Название места", "Venue name"), forms.TextInput),
    ("location_address", admin_text("Адрес", "Address"), forms.TextInput),
    ("location_description", admin_text("Описание места", "Venue description"), forms.Textarea),
    ("success_message", admin_text("Сообщение после подтверждения", "Confirmation message"), forms.Textarea),
    ("decline_message", admin_text("Сообщение после отказа", "Decline message"), forms.Textarea),
    ("registration_closed_message", admin_text("Сообщение о закрытой регистрации", "Registration closed message"), forms.Textarea),
    ("additional_information", admin_text("Дополнительная информация", "Additional information"), forms.Textarea),
]


def _translation_form_field(label, widget_class):
    widget = widget_class(attrs={"rows": 4}) if widget_class is forms.Textarea else widget_class()
    return forms.CharField(label=label, required=False, widget=widget)


class BannerImageWidget(forms.ClearableFileInput):
    template_name = "admin/widgets/banner_image.html"


class EventAdminForm(forms.ModelForm):
    enabled_languages = forms.MultipleChoiceField(
        label=admin_text("Языки события", "Event languages"),
        choices=LANGUAGE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
    )
    default_language = forms.ChoiceField(label=admin_text("Язык по умолчанию", "Default language"), choices=LANGUAGE_CHOICES)

    for _language in SUPPORTED_LANGUAGE_CODES:
        locals()[f"{_language}_banner_image"] = forms.ImageField(
            label=admin_text("Баннер", "Banner"),
            required=False,
            widget=BannerImageWidget,
            validators=IMAGE_VALIDATORS,
        )
        for _name, _label, _widget_class in TRANSLATION_FIELDS:
            locals()[f"{_language}_{_name}"] = _translation_form_field(_label, _widget_class)
    del _language, _name, _label, _widget_class

    class Meta:
        model = Event
        exclude = ["supported_languages"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "internal_name": admin_text("Название в админке", "Admin name"),
            "slug": admin_text("Адрес страницы", "Page address"),
            "status": admin_text("Статус", "Status"),
            "starts_at": admin_text("Начало", "Starts at"),
            "ends_at": admin_text("Окончание", "Ends at"),
            "registration_starts_at": admin_text("Начало регистрации", "Registration starts"),
            "registration_ends_at": admin_text("Окончание регистрации", "Registration ends"),
            "timezone": admin_text("Часовой пояс", "Time zone"),
            "max_guests": admin_text("Максимум дополнительных гостей в одном ответе", "Maximum additional guests per response"),
            "allow_public_registration": admin_text("Открытая регистрация", "Public registration"),
            "require_email": admin_text("Требовать email", "Require email"),
            "require_phone": admin_text("Требовать телефон", "Require phone"),
            "is_search_engine_visible": admin_text("Разрешить индексацию", "Allow search indexing"),
            "published_at": admin_text("Опубликован", "Published at"),
            "created_by": admin_text("Создал", "Created by"),
        }
        for name, label in labels.items():
            if name in self.fields:
                self.fields[name].label = label
        enabled = self.instance.supported_languages if self.instance.pk else ["ru"]
        self.fields["enabled_languages"].initial = enabled
        translations = {
            translation.language: translation
            for translation in self.instance.translations.all()
        } if self.instance.pk else {}

        for language in SUPPORTED_LANGUAGE_CODES:
            translation = translations.get(language)
            if translation:
                self.fields[f"{language}_banner_image"].initial = translation.banner_image
            for name, _, _ in TRANSLATION_FIELDS:
                if translation:
                    self.fields[f"{language}_{name}"].initial = getattr(translation, name)

    def clean(self):
        cleaned = super().clean()
        for language in SUPPORTED_LANGUAGE_CODES:
            field_name = f"{language}_banner_image"
            uploaded = cleaned.get(field_name)
            if uploaded and uploaded is not False:
                cleaned[field_name] = sanitize_image_upload(uploaded)
        enabled = cleaned.get("enabled_languages") or []
        default_language = cleaned.get("default_language")
        if not enabled:
            self.add_error("enabled_languages", admin_text("Включите хотя бы один язык.", "Enable at least one language."))
        if default_language and default_language not in enabled:
            self.add_error("default_language", admin_text("Язык по умолчанию должен быть включён.", "The default language must be enabled."))
        for language in enabled:
            if not cleaned.get(f"{language}_title", "").strip():
                self.add_error(f"{language}_title", admin_text("Укажите заголовок для включённого языка.", "Enter a title for each enabled language."))
        self.instance.supported_languages = list(enabled)
        return cleaned

    @property
    def translation_changed(self) -> bool:
        text_changed = any(
            f"{language}_{name}" in self.changed_data
            for language in SUPPORTED_LANGUAGE_CODES
            for name, _, _ in TRANSLATION_FIELDS
        )
        banner_changed = any(f"{language}_banner_image" in self.changed_data for language in SUPPORTED_LANGUAGE_CODES)
        return text_changed or banner_changed

    def save_translations(self):
        enabled = self.cleaned_data["enabled_languages"]
        for language in enabled:
            values = {
                name: self.cleaned_data.get(f"{language}_{name}", "")
                for name, _, _ in TRANSLATION_FIELDS
            }
            translation, _ = EventTranslation.objects.update_or_create(
                event=self.instance,
                language=language,
                defaults=values,
            )
            banner = self.cleaned_data.get(f"{language}_banner_image")
            if banner is False:
                translation.banner_image = ""
                translation.save(update_fields=["banner_image"])
            elif banner:
                translation.banner_image = banner
                translation.save(update_fields=["banner_image"])


def translation_field_names(language: str) -> list[str]:
    return [f"{language}_banner_image", *[f"{language}_{name}" for name, _, _ in TRANSLATION_FIELDS]]
