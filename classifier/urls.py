from django.urls import path

from . import views

urlpatterns = [
    path("", views.front_page, name="home"),
    path("dashboard/", views.dashboard_page, name="dashboard"),
    path("classify/", views.classify_page, name="classify"),
    path("result/<int:pk>/", views.result_page, name="result"),
    path("result/<int:pk>/respond/", views.incident_respond, name="incident_respond"),
    path("incidents/", views.history_page, name="history"),
    path("incidents/map/", views.incident_map_page, name="incident_map"),
    path("incidents/export.csv", views.history_export, name="history_export"),
    path("agencies/", views.agency_list, name="agency_list"),
    path("agencies/new/", views.agency_create, name="agency_create"),
    path("agencies/<int:pk>/edit/", views.agency_edit, name="agency_edit"),
    # Old paths kept so bookmarks and older links still work.
    path("history/", views.history_page),
    path("history/export.csv", views.history_export),
]
