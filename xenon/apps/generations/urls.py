from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('generations/create/', views.create_generation, name='create_generation'),
    path('generations/status/<uuid:generation_id>/', views.get_generation_status, name='get_generation_status'),
]
