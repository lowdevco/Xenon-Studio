import os
from celery import shared_task
from celery.exceptions import Retry
from django.conf import settings
from .models import Generation
from .services.byteplus import BytePlusService
from .services.kling import KlingService

@shared_task(bind=True, max_retries=300)
def generate_video_task(self, generation_id, base_url=""):
    try:
        generation = Generation.objects.get(id=generation_id)
    except Generation.DoesNotExist:
        return

    if generation.model_id.lower().startswith('kling'):
        service = KlingService()
    else:
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
        progress = task_data.get('progress', 0)
        
        # If the API doesn't return progress directly, we can safely just use what we get (default 0)
        # Byteplus might return it under different keys. If not provided, it stays 0 or previous.
        if progress:
            generation.progress = progress
            generation.save(update_fields=['progress'])

        if status in ['queued', 'running']:
            # Still working, check again in 5 seconds
            raise self.retry(countdown=5)
            
        elif status == 'succeeded':
            generation.progress = 100
            generation.save(update_fields=['progress'])
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


@shared_task(bind=True, max_retries=10)
def generate_image_task(self, generation_id, base_url=""):
    try:
        generation = Generation.objects.get(id=generation_id)
    except Generation.DoesNotExist:
        return

    from .services.gemini import GeminiService
    service = GeminiService()

    try:
        if not generation.provider_task_id:
            generation.status = Generation.Status.PROCESSING
            generation.provider_task_id = service.generate_image(generation, base_url)
            generation.save(update_fields=['status', 'provider_task_id'])
            raise self.retry(countdown=3)

        # Polling
        task_data = service.check_status(generation.provider_task_id)
        status = task_data.get('status')
        
        if status in ['running', 'queued', 'pending']:
            progress = task_data.get('progress', generation.progress + 20)
            generation.progress = min(progress, 99)
            generation.save(update_fields=['progress'])
            raise self.retry(countdown=3)
        elif status == 'succeeded':
            generation.progress = 100
            
            image_url = task_data.get('image_url')
            if image_url:
                import requests
                import os
                from django.conf import settings
                
                filename = f"generated_img_{generation.id}.jpg"
                relative_path = os.path.join('images', filename)
                absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)
                os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
                
                headers = {"User-Agent": "Mozilla/5.0"}
                with requests.get(image_url, headers=headers, stream=True, timeout=30.0) as response:
                    response.raise_for_status()
                    with open(absolute_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                
                generation.image_file.name = relative_path
                generation.status = Generation.Status.COMPLETED
                generation.save(update_fields=['progress', 'image_file', 'status'])
            else:
                generation.status = Generation.Status.FAILED
                generation.error_message = "No image URL returned"
                generation.save(update_fields=['status', 'error_message'])
                
    except Retry:
        raise
    except Exception as e:
        generation.status = Generation.Status.FAILED
        generation.error_message = str(e)
        generation.save(update_fields=['status', 'error_message'])

