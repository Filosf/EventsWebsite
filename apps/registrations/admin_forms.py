from django import forms

from apps.accounts.admin_i18n import admin_text

from .models import Registration


class RegistrationAdminEditForm(forms.ModelForm):
    class Meta:
        model = Registration
        fields = ["full_name", "email", "phone", "attendance_status", "guest_count", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            "full_name": admin_text("Имя гостя", "Guest name"),
            "email": "Email",
            "phone": admin_text("Телефон", "Phone"),
            "attendance_status": admin_text("Ответ", "Response"),
            "guest_count": admin_text("Дополнительные гости", "Additional guests"),
            "comment": admin_text("Комментарий", "Comment"),
        }
        for name, label in labels.items():
            self.fields[name].label = label
        self.fields["attendance_status"].choices = [
            (Registration.Attendance.ATTENDING, admin_text("Придёт", "Attending")),
            (Registration.Attendance.DECLINED, admin_text("Не придёт", "Declined")),
        ]
        self.fields["guest_count"].widget.attrs["max"] = self.instance.event.max_guests

    def clean_guest_count(self):
        count = self.cleaned_data["guest_count"]
        status = self.cleaned_data.get("attendance_status")
        if status == Registration.Attendance.DECLINED:
            return 0
        if count > self.instance.event.max_guests:
            raise forms.ValidationError(
                admin_text(
                    f"Максимум дополнительных гостей в одном ответе: {self.instance.event.max_guests}.",
                    f"Maximum additional guests per response: {self.instance.event.max_guests}.",
                )
            )
        return count
