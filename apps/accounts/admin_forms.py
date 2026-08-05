from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .admin_i18n import admin_text

User = get_user_model()


class StaffUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(
        label=admin_text("Пароль", "Password"),
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label=admin_text("Подтверждение пароля", "Password confirmation"),
        strip=False,
        widget=forms.PasswordInput,
    )

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "is_active", "is_superuser"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Email"
        self.fields["email"].required = True
        self.fields["is_superuser"].label = admin_text("Администратор", "Administrator")
        self.fields["is_superuser"].help_text = admin_text(
            "Разрешает управлять другими пользователями.",
            "Allows this user to manage other users.",
        )

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise ValidationError(admin_text("Пользователь с таким email уже существует.", "A user with this email already exists."))
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password1")
        if password and password != cleaned.get("password2"):
            self.add_error("password2", admin_text("Пароли не совпадают.", "The passwords do not match."))
        elif password:
            try:
                validate_password(password, self.instance)
            except ValidationError as error:
                self.add_error("password2", error)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = user.email
        user.is_staff = True
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class StaffUserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(label=admin_text("Пароль", "Password"))

    class Meta:
        model = User
        fields = ["email", "password", "first_name", "last_name", "is_active", "is_superuser"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Email"
        self.fields["email"].required = True
        self.fields["is_superuser"].label = admin_text("Администратор", "Administrator")
        self.fields["is_superuser"].help_text = admin_text(
            "Разрешает управлять другими пользователями.",
            "Allows this user to manage other users.",
        )

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).lower()
        email_exists = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists()
        username_exists = User.objects.filter(username__iexact=email).exclude(pk=self.instance.pk).exists()
        if email_exists or username_exists:
            raise ValidationError(admin_text("Пользователь с таким email уже существует.", "A user with this email already exists."))
        return email

    def clean_password(self):
        return self.initial.get("password")

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk or not self.instance.is_superuser or not self.instance.is_active:
            return cleaned
        remains_administrator = cleaned.get("is_superuser", self.instance.is_superuser)
        remains_active = cleaned.get("is_active", self.instance.is_active)
        another_administrator = User.objects.filter(is_superuser=True, is_active=True).exclude(pk=self.instance.pk).exists()
        if (not remains_administrator or not remains_active) and not another_administrator:
            raise ValidationError(
                admin_text(
                    "Нельзя отключить или разжаловать последнего активного администратора.",
                    "The last active administrator cannot be disabled or demoted.",
                )
            )
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = user.email
        user.is_staff = True
        if commit:
            user.save()
        return user


class EmailAdminAuthenticationForm(AdminAuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True}))
