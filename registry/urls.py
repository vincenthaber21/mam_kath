from django.urls import path

from . import views

urlpatterns = [
    path("models/", views.models_page, name="models"),
    path("models/upload/", views.upload_model, name="model_upload"),
    path("models/<int:pk>/activate/", views.activate_model, name="model_activate"),
    path("models/selection/", views.set_selection_mode, name="model_selection"),
    path("models/train/", views.start_training, name="model_train"),
    path("models/train/<int:pk>/status/", views.training_status, name="model_train_status"),
    path("dataset/", views.dataset_page, name="dataset"),
]
