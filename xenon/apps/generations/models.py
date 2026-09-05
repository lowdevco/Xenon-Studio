import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Generation(models.Model):
    class Status(models.TextChoices):
        QUEUED = 'QUEUED', 'Queued'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    prompt = models.TextField()
    model_id = models.CharField(max_length=100, default='dreamina-seedance-2-5-260628')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    provider_task_id = models.CharField(max_length=100, null=True, blank=True)
    
    # After download, the file will be saved here
    video_file = models.FileField(upload_to='videos/', null=True, blank=True)
    
    error_message = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Advanced API Configuration
    reference_image = models.FileField(upload_to='references/images/', null=True, blank=True)
    reference_video = models.FileField(upload_to='references/videos/', null=True, blank=True)
    reference_audio = models.FileField(upload_to='references/audio/', null=True, blank=True)
    
    generate_audio = models.BooleanField(default=True)
    ratio = models.CharField(max_length=10, default='16:9')
    duration = models.IntegerField(default=5)
    watermark = models.BooleanField(default=False)

    def __str__(self):
        return f"Generation {self.id} ({self.status})"
