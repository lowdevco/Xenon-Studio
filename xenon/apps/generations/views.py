from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse
from django.db import models
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit
from .models import Generation, ReferenceMedia
from .tasks import generate_video_task

def landing_page(request):
    return render(request, 'pages/landing.html')

@ensure_csrf_cookie
def video_studio(request, model='seedance_2_5'):
    # Fetch all generations for the user (or session based for now)
    # Since we dropped user auth, we'll just show all generations for now, 
    # or rely on the session if we want to restrict it.
    if not request.session.session_key:
        request.session.create()
    
    # We can link generations to session_key
    generations = Generation.objects.all().order_by('-created_at')[:20]
    
    # Read model from URL path parameter
    active_model = model
    
    return render(request, 'pages/video_studio.html', {
        'generations': generations,
        'active_model': active_model
    })

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
        
        # Handle reference_ids
        reference_ids = request.POST.get('reference_ids', '')
        if reference_ids:
            from .models import Upload, ReferenceMedia
            for ref_id in reference_ids.split(','):
                try:
                    upload = Upload.objects.get(id=ref_id)
                    media_type = 'video' if upload.file.name.lower().endswith('.mp4') else 'image'
                    # We copy the file reference to ReferenceMedia
                    ReferenceMedia.objects.create(
                        generation=generation,
                        media_type=media_type,
                        file=upload.file,
                        byteplus_asset_id=upload.byteplus_asset_id
                    )
                except Upload.DoesNotExist:
                    pass
            
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
            'progress': generation.progress,
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

from .models import Upload

@require_http_methods(['GET'])
@require_http_methods(['GET'])
def list_uploads(request):
    uploads = Upload.objects.order_by('-created_at')
    data = []
    for up in uploads:
        data.append({
            'id': str(up.id),
            'name': up.name,
            'category': 'Upload',
            'media_url': up.file.url if up.file else '',
            'status': up.byteplus_status
        })
    return JsonResponse({'uploads': data})

@require_http_methods(['POST'])
def create_upload(request):
    media_file = request.FILES.get('media_file')
    if not media_file:
        return JsonResponse({'error': 'Media file is required'}, status=400)
        
    upload = Upload.objects.create(
        name=media_file.name,
        file=media_file,
        byteplus_status='Unverified'
    )
    
    return JsonResponse({
        'id': str(upload.id),
        'name': upload.name,
        'category': 'Upload',
        'media_url': upload.file.url,
        'status': upload.byteplus_status
    })

@require_http_methods(['POST'])
def verify_upload(request, upload_id):
    try:
        upload = Upload.objects.get(id=upload_id)
        model = request.GET.get('model', '')
        
        # If the active model is Kling, we don't need BytePlus verification.
        # Kling uses base64 local file encoding at generation time.
        if model.startswith('kling'):
            # Kling image2video only supports images, not videos. We could enforce it here, 
            # but for now, we'll just bypass BytePlus and mark it verified.
            upload.byteplus_status = 'Verified'
            upload.save()
            return JsonResponse({
                'id': str(upload.id),
                'status': upload.byteplus_status
            })
            
        from apps.generations.services.byteplus import BytePlusService
        bps = BytePlusService()
        
        public_url = request.build_absolute_uri(upload.file.url)
        group_resp = bps.create_asset_group(f"upload_group_{upload.id}", "Xenon Upload Group")
        group_id = group_resp.get("Id")
        
        asset_type = 'Video' if upload.file.name.lower().endswith('.mp4') else 'Image'
        asset_resp = bps.create_asset(group_id, public_url, asset_type)
        asset_id = asset_resp.get("Id")
        
        # We rely on BytePlus API at generation time to catch privacy issues
        # to avoid burning generation credits during verification.
        
        upload.byteplus_group_id = group_id
        upload.byteplus_asset_id = asset_id
        upload.byteplus_status = 'Verified' 
        upload.save()
        
        return JsonResponse({
            'id': str(upload.id),
            'status': upload.byteplus_status
        })
    except Upload.DoesNotExist:
        return JsonResponse({'error': 'Upload not found'}, status=404)
    except Exception as e:
        print(f"Verify Error: {e}")
        upload.byteplus_status = 'Failed'
        upload.save()
        return JsonResponse({'error': str(e)}, status=500)

@require_http_methods(['DELETE'])
def delete_upload(request, upload_id):
    try:
        upload = Upload.objects.get(id=upload_id)
        
        if upload.byteplus_group_id:
            from apps.generations.services.byteplus import BytePlusService
            try:
                bps = BytePlusService()
                bps.delete_asset_group(upload.byteplus_group_id)
            except Exception as e:
                print(f"Failed to delete BytePlus asset group: {e}")

        upload.file.delete(save=False)
        upload.delete()
        return JsonResponse({'status': 'success'})
    except Upload.DoesNotExist:
        return JsonResponse({'error': 'Upload not found'}, status=404)
