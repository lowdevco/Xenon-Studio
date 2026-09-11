from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('chat/new/', views.new_chat, name='new_chat'),
    path('chat/<uuid:chat_id>/', views.index, name='chat_session'),
    path('chat/<uuid:chat_id>/rename/', views.rename_chat, name='chat_rename'),
    path('chat/<uuid:chat_id>/delete/', views.delete_chat, name='chat_delete'),
    path('generations/create/', views.create_generation, name='create_generation'),
    path('generations/status/<uuid:generation_id>/', views.get_generation_status, name='get_generation_status'),
    path('generations/<uuid:generation_id>/regenerate/', views.regenerate, name='regenerate'),
]
