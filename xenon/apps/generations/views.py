from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse
from django.db import models
from django.views.decorators.csrf import ensure_csrf_cookie
from django_ratelimit.decorators import ratelimit
from .models import Generation, ReferenceMedia
from .tasks import generate_video_task

def landing_page(request):
    return render(request, 'pages/landing.html')

@ensure_csrf_cookie
def video_studio(request):
    # Fetch all generations for the user (or session based for now)
    # Since we dropped user auth, we'll just show all generations for now, 
    # or rely on the session if we want to restrict it.
    if not request.session.session_key:
        request.session.create()
    
    # We can link generations to session_key
    generations = Generation.objects.all().order_by('-created_at')[:20]
    return render(request, 'pages/video_studio.html', {'generations': generations})

def assets(request):
    # Fetch all successful video generations
    generations = Generation.objects.filter(status='COMPLETED').order_by('-created_at')
    return render(request, 'pages/assets.html', {'generations': generations})

@ratelimit(key='ip', rate='5/m', block=False)
def create_generation(request):
    if getattr(request, 'limited', False):
        return JsonResponse({'error': 'Rate limit exceeded. Please try again in a minute.'}, status=429)
        
    if request.method == 'POST':
        prompt = request.POST.get('prompt')
        if not prompt:
            return JsonResponse({'error': 'Prompt is required'}, status=400)
            
        generation = Generation.objects.create(
            prompt=prompt,
            model_id=request.POST.get('model', 'dreamina-seedance-2-5-260628'),
            generate_audio=request.POST.get('generate_audio') == 'true',
            ratio=request.POST.get('ratio', '16:9'),
            resolution=request.POST.get('resolution', '480p'),
            duration=int(request.POST.get('duration', 5)),
            watermark=request.POST.get('watermark') == 'true'
        )
        
        # Handle reference media placeholders (if any files were uploaded)
        for f in request.FILES.getlist('files'):
            ReferenceMedia.objects.create(generation=generation, file=f)
            
        # Dispatch Celery Task
        generate_video_task.delay(generation.id, request.build_absolute_uri('/'))
        
        return JsonResponse({
            'status': 'success',
            'generation_id': generation.id,
            'status_url': reverse('get_generation_status', args=[generation.id])
        })
    return JsonResponse({'error': 'Invalid request'}, status=400)

def get_generation_status(request, generation_id):
    try:
        generation = Generation.objects.get(id=generation_id)
        response_data = {
            'id': generation.id,
            'status': generation.status,
            'error_message': generation.error_message,
        }
        
        if generation.status == 'COMPLETED' and generation.video_file:
            response_data['video_url'] = generation.video_file.url
            
        return JsonResponse(response_data)
    except Generation.DoesNotExist:
        return JsonResponse({'error': 'Generation not found'}, status=404)

@ratelimit(key='ip', rate='5/m', block=False)
def regenerate(request, generation_id):
    if getattr(request, 'limited', False):
        return JsonResponse({'error': 'Rate limit exceeded. Please try again in a minute.'}, status=429)
        
    try:
        old_gen = Generation.objects.get(id=generation_id)
        
        new_gen = Generation.objects.create(
            prompt=old_gen.prompt,
            model_id=old_gen.model_id,
            generate_audio=old_gen.generate_audio,
            ratio=old_gen.ratio,
            resolution=old_gen.resolution,
            duration=old_gen.duration,
            watermark=old_gen.watermark
        )
        
        for media in old_gen.references.all():
            ReferenceMedia.objects.create(generation=new_gen, file=media.file)
            
        # Dispatch Celery Task
        generate_video_task.delay(new_gen.id, request.build_absolute_uri('/'))
        
        return JsonResponse({
            'status': 'success',
            'generation_id': new_gen.id,
            'status_url': reverse('get_generation_status', args=[new_gen.id])
        })
    except Generation.DoesNotExist:
        return JsonResponse({'error': 'Original generation not found'}, status=404)

from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt

import os

@csrf_exempt
def delete_generation(request, generation_id):
    print(f"DELETE API HIT FOR {generation_id}")
    if request.method == 'DELETE':
        try:
            generation = Generation.objects.get(id=generation_id)
            
            # Delete physical video file
            if generation.video_file and hasattr(generation.video_file, 'path'):
                file_path = generation.video_file.path
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"Deleted physical file: {file_path}")
                    except Exception as e:
                        print(f"Failed to delete physical file {file_path}: {e}")

            generation.delete()
            print(f"Successfully deleted DB row for {generation_id}")
            return JsonResponse({'status': 'success'})
        except Generation.DoesNotExist:
            print(f"Generation {generation_id} not found!")
            return JsonResponse({'error': 'Generation not found'}, status=404)
        except Exception as e:
            print(f"Error in delete_generation: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    
    print(f"Invalid method {request.method} for delete API")
    return JsonResponse({'error': 'Method not allowed'}, status=405)
