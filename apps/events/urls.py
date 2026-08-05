from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("e/<slug:slug>/", views.event_page, name="event_page"),
    path("<str:language>/e/<slug:slug>/", views.event_page, name="event_page_language"),
    path("<str:language>/e/<slug:slug>/thanks/<uuid:token>/", views.registration_thanks, name="registration_thanks"),
    path("e/<slug:slug>/language/<str:language>/", views.switch_language, name="switch_language"),
]
