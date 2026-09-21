from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('video/<str:model>/', views.video_studio, name='video_studio'),
    path('assets/', views.assets, name='assets'),
    
    # API endpoints
    path('generations/create/', views.create_generation, name='create_generation'),
    path('generations/status/<uuid:generation_id>/', views.get_generation_status, name='get_generation_status'),
    path('generations/<uuid:generation_id>/delete/', views.delete_generation, name='delete_generation'),
    path('generations/<uuid:generation_id>/regenerate/', views.regenerate, name='regenerate'),
    
    # Uploads API
    path('uploads/', views.list_uploads, name='list_uploads'),
    path('uploads/create/', views.create_upload, name='create_upload'),
    path('uploads/<uuid:upload_id>/verify/', views.verify_upload, name='verify_upload'),
    path('uploads/<uuid:upload_id>/delete/', views.delete_upload, name='delete_upload'),
]