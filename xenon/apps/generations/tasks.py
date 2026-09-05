import os
from celery import shared_task
from celery.exceptions import Retry
from django.conf import settings
from .models import Generation
from .services.byteplus import BytePlusService

@shared_task(bind=True, max_retries=100)
def generate_video_task(self, generation_id, base_url=""):
    try:
        generation = Generation.objects.get(id=generation_id)
    except Generation.DoesNotExist:
        return

    service = BytePlusService()

    try:
        # 1. Submission
        if not generation.provider_task_id:
            generation.status = Generation.Status.PROCESSING
            generation.save(update_fields=['status'])
            
            provider_task_id = service.create_task(
                generation=generation, 
                base_url=base_url
            )
            generation.provider_task_id = provider_task_id
            generation.save(update_fields=['provider_task_id'])
            
            # Re-queue to check status after 10 seconds
            raise self.retry(countdown=10)

        # 2. Polling
        task_data = service.get_task(generation.provider_task_id)
        status = task_data.get('status')

        if status in ['queued', 'running']:
            # Still working, check again in 5 seconds
            raise self.retry(countdown=5)
            
        elif status == 'succeeded':
            content = task_data.get('content', {})
            video_url = content.get('video_url')
            
            if video_url:
                # Download to local media storage
                filename = f"generated_{generation.id}.mp4"
                relative_path = os.path.join('videos', filename)
                absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                
                service.download_video(video_url, absolute_path)
                
                # Update record
                generation.video_file.name = relative_path
                generation.status = Generation.Status.COMPLETED
                generation.save(update_fields=['video_file', 'status'])
            else:
                generation.status = Generation.Status.FAILED
                generation.error_message = "Task succeeded but no video URL found."
                generation.save(update_fields=['status', 'error_message'])
                
        elif status in ['failed', 'cancelled', 'expired']:
            error_details = task_data.get('error', {})
            error_message = error_details.get('message', f"Task ended with status: {status}")
            
            generation.status = Generation.Status.FAILED
            generation.error_message = error_message
            generation.save(update_fields=['status', 'error_message'])

    except Retry:
        raise
    except Exception as e:
        generation.status = Generation.Status.FAILED
        generation.error_message = str(e)
        generation.save(update_fields=['status', 'error_message'])
