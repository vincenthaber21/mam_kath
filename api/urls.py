from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="api_index"),
    path("health/", views.health, name="api_health"),
    path("auth/login/", views.login, name="api_login"),
    path("auth/register/", views.register, name="api_register"),
    path("auth/logout/", views.logout, name="api_logout"),
    path("auth/me/", views.me, name="api_me"),
    path("meta/", views.meta, name="api_meta"),
    path("classify/", views.classify, name="api_classify"),
    path("classifications/", views.classification_list, name="api_classifications"),
    path("classifications/<int:pk>/", views.classification_detail, name="api_classification_detail"),
    path("classifications/<int:pk>/verify/", views.classification_verify, name="api_classification_verify"),
]
