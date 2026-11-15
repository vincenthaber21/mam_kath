from django.urls import path

from . import views

urlpatterns = [
    path("", views.front_page, name="home"),
    path("classify/", views.classify_page, name="classify"),
    path("result/<int:pk>/", views.result_page, name="result"),
    path("history/", views.history_page, name="history"),
    path("history/export.csv", views.history_export, name="history_export"),
]
