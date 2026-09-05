import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import Generation, ReferenceMedia
from .tasks import generate_video_task

@ensure_csrf_cookie
def index(request):
    generations = Generation.objects.all().order_by('created_at')
    return render(request, 'pages/home.html', {'generations': generations})

def create_generation(request):
    if request.method == 'POST':
        try:
            prompt = request.POST.get('prompt')
            if not prompt:
                return JsonResponse({'error': 'Prompt is required'}, status=400)
                
            images = request.FILES.getlist('reference_image')
            videos = request.FILES.getlist('reference_video')
            audios = request.FILES.getlist('reference_audio')
            
            if len(images) > 30: return JsonResponse({'error': 'Maximum 30 images allowed'}, status=400)
            if len(videos) > 10: return JsonResponse({'error': 'Maximum 10 videos allowed'}, status=400)
            if len(audios) > 10: return JsonResponse({'error': 'Maximum 10 audios allowed'}, status=400)
            
            # Create the database record
            generation = Generation.objects.create(
                prompt=prompt, 
                status=Generation.Status.QUEUED,
                generate_audio=request.POST.get('generate_audio') == 'true',
                ratio=request.POST.get('ratio', '16:9'),
                resolution=request.POST.get('resolution', '720p'),
                duration=int(request.POST.get('duration', 5)),
                watermark=request.POST.get('watermark') == 'true',
            )

            for img in images:
                ReferenceMedia.objects.create(generation=generation, media_type=ReferenceMedia.MediaType.IMAGE, file=img)
            for vid in videos:
                ReferenceMedia.objects.create(generation=generation, media_type=ReferenceMedia.MediaType.VIDEO, file=vid)
            for aud in audios:
                ReferenceMedia.objects.create(generation=generation, media_type=ReferenceMedia.MediaType.AUDIO, file=aud)
            
            # Get the base URL from the current request domain (e.g. localhost or ngrok domain)
            base_url = request.build_absolute_uri('/')[:-1]
            
            # Dispatch Celery task
            generate_video_task.delay(str(generation.id), base_url)
            
            return JsonResponse({'generation_id': str(generation.id)})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

def get_generation_status(request, generation_id):
    try:
        generation = Generation.objects.get(id=generation_id)
        return JsonResponse({
            'status': generation.status,
            'video_url': generation.video_file.url if generation.video_file else None,
            'error_message': generation.error_message
        })
    except Generation.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
