from django.urls import path

from . import views

urlpatterns = [
    path("models/", views.models_page, name="models"),
    path("models/upload/", views.upload_model, name="model_upload"),
    path("models/<int:pk>/activate/", views.activate_model, name="model_activate"),
    path("dataset/", views.dataset_page, name="dataset"),
]
