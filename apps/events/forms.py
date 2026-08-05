import time

from django import forms
from django.conf import settings
from django.core import signing

from apps.registrations.models import Registration

from .i18n import interface_text, party_size_choices


class RegistrationForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput(attrs={"autocomplete": "off", "tabindex": "-1"}))
    form_token = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Registration
        fields = ["full_name", "email", "phone", "attendance_status", "guest_count", "comment"]
        widgets = {
            "comment": forms.Textarea(attrs={"rows": 3}),
            "attendance_status": forms.RadioSelect(attrs={"class": "attendance-options"}),
        }

    def __init__(self, *args, event=None, language="ru", **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.ui = interface_text(language)
        self.fields["full_name"].label = self.ui["full_name"]
        self.fields["email"].label = self.ui["email"]
        self.fields["phone"].label = self.ui["phone"]
        self.fields["attendance_status"].label = self.ui["attendance"]
        self.fields["attendance_status"].choices = [
            (Registration.Attendance.ATTENDING, self.ui["attending"]),
            (Registration.Attendance.DECLINED, self.ui["declined"]),
        ]
        self.fields["guest_count"].label = self.ui["guest_count"]
        self.fields["comment"].label = self.ui["comment"]
        self.fields["email"].required = bool(event and event.require_email)
        self.fields["phone"].required = bool(event and event.require_phone)
        max_guests = event.max_guests if event else 10
        self.fields["guest_count"].widget = forms.Select(
            choices=party_size_choices(language, max_guests),
        )
        if not self.is_bound and event:
            self.fields["form_token"].initial = signing.dumps(
                {"event_id": event.pk, "issued_at": time.time()},
                salt="registration-form",
                compress=True,
            )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if not phone:
            return ""
        prefix = "+" if phone.startswith("+") else ""
        return prefix + "".join(character for character in phone if character.isdigit())

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("website"):
            raise forms.ValidationError(self.ui["submission_rejected"])

        minimum_seconds = settings.REGISTRATION_MIN_FORM_SECONDS
        if minimum_seconds <= 0:
            return cleaned
        try:
            payload = signing.loads(
                cleaned.get("form_token", ""),
                salt="registration-form",
                max_age=settings.REGISTRATION_FORM_TOKEN_MAX_AGE,
            )
            valid_event = payload.get("event_id") == getattr(self.event, "pk", None)
            old_enough = time.time() - float(payload.get("issued_at", 0)) >= minimum_seconds
        except (signing.BadSignature, TypeError, ValueError):
            valid_event = old_enough = False
        if not valid_event or not old_enough:
            raise forms.ValidationError(self.ui["submission_too_fast"])
        return cleaned

    def clean_guest_count(self):
        count = self.cleaned_data["guest_count"]
        status = self.cleaned_data.get("attendance_status")
        if status == Registration.Attendance.DECLINED:
            return 0
        if self.event and count > self.event.max_guests:
            raise forms.ValidationError(self.ui["max_guests"].format(count=self.event.max_guests + 1))
        return count
