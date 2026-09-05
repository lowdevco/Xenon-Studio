import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import Generation
from .tasks import generate_video_task

@ensure_csrf_cookie
def index(request):
    return render(request, 'generations/index.html')

def create_generation(request):
    if request.method == 'POST':
        try:
            # When files are uploaded, data comes in request.POST and request.FILES
            prompt = request.POST.get('prompt')
            if not prompt:
                return JsonResponse({'error': 'Prompt is required'}, status=400)
            
            # Create the database record
            generation = Generation(
                prompt=prompt, 
                status=Generation.Status.QUEUED,
                generate_audio=request.POST.get('generate_audio') == 'true',
                ratio=request.POST.get('ratio', '16:9'),
                duration=int(request.POST.get('duration', 5)),
                watermark=request.POST.get('watermark') == 'true',
            )

            if 'reference_image' in request.FILES:
                generation.reference_image = request.FILES['reference_image']
            if 'reference_video' in request.FILES:
                generation.reference_video = request.FILES['reference_video']
            if 'reference_audio' in request.FILES:
                generation.reference_audio = request.FILES['reference_audio']
                
            generation.save()
            
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
