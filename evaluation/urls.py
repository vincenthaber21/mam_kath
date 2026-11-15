from django.urls import path

from . import views

urlpatterns = [
    path("", views.evaluation_page, name="evaluation"),
    path("<int:pk>/status.json", views.evaluation_status, name="evaluation_status"),
    path("<int:pk>/report.csv", views.evaluation_csv, name="evaluation_csv"),
]
