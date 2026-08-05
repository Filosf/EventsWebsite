from django.urls import path

from . import views

app_name = "event_admin"

urlpatterns = [
    path("<int:event_id>/statistics/", views.event_statistics, name="statistics"),
    path("<int:event_id>/responses/<int:registration_id>/edit/", views.registration_edit, name="registration_edit"),
    path("<int:event_id>/responses/<int:registration_id>/delete/", views.registration_delete, name="registration_delete"),
    path("<int:event_id>/registrations.csv", views.registrations_export, name="registrations_export"),
]
