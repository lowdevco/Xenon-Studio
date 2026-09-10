from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse
from django.db import models
from django.views.decorators.csrf import ensure_csrf_cookie
import mimetypes
from .models import Generation, ReferenceMedia, ChatSession
from .tasks import generate_video_task

def get_session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key

@ensure_csrf_cookie
def index(request, chat_id=None):
    session_key = get_session_key(request)
    # Include chats tied to this session or legacy chats with no session key
    chat_sessions = ChatSession.objects.filter(
        models.Q(session_key=session_key) | models.Q(session_key__isnull=True)
    ).order_by('-created_at')
    
    # If no chat_id provided, redirect to the most recent one or create one
    if not chat_id:
        latest_chat = chat_sessions.first()
        if latest_chat:
            return redirect('chat_session', chat_id=latest_chat.id)
        else:
            new_session = ChatSession.objects.create(title="New Chat", session_key=session_key)
            return redirect('chat_session', chat_id=new_session.id)
            
    # We have a specific chat_id
    try:
        active_chat = chat_sessions.get(id=chat_id)
    except ChatSession.DoesNotExist:
        return redirect('index')
        
    generations = active_chat.generations.all().order_by('created_at')
    
    return render(request, 'pages/home.html', {
        'generations': generations,
        'chat_sessions': chat_sessions,
        'active_chat': active_chat
    })

def new_chat(request):
    session_key = get_session_key(request)
    # Determine chat title based on current count
    count = ChatSession.objects.filter(session_key=session_key).count()
    new_session = ChatSession.objects.create(title=f"Chat {count + 1}", session_key=session_key)
    return redirect('chat_session', chat_id=new_session.id)

def rename_chat(request, chat_id):
    if request.method == 'POST':
        new_title = request.POST.get('title', '').strip()
        if new_title:
            try:
                session_key = get_session_key(request)
                chat = ChatSession.objects.get(
                    models.Q(session_key=session_key) | models.Q(session_key__isnull=True), 
                    id=chat_id
                )
                chat.title = new_title
                # Automatically claim legacy null sessions
                if not chat.session_key:
                    chat.session_key = session_key
                chat.save()
            except ChatSession.DoesNotExist:
                pass
    return redirect('chat_session', chat_id=chat_id)

def delete_chat(request, chat_id):
    if request.method == 'POST':
        try:
            session_key = get_session_key(request)
            chat = ChatSession.objects.get(
                models.Q(session_key=session_key) | models.Q(session_key__isnull=True), 
                id=chat_id
            )
            chat.delete()
        except ChatSession.DoesNotExist:
            pass
    return redirect('index')

def create_generation(request):
    if request.method == 'POST':
        try:
            prompt = request.POST.get('prompt')
            chat_id = request.POST.get('chat_id')
            
            if not prompt:
                return JsonResponse({'error': 'Prompt is required'}, status=400)
            if not chat_id:
                return JsonResponse({'error': 'Chat Session is required'}, status=400)
                
            try:
                session_key = get_session_key(request)
                active_chat = ChatSession.objects.get(
                    models.Q(session_key=session_key) | models.Q(session_key__isnull=True), 
                    id=chat_id
                )
            except ChatSession.DoesNotExist:
                return JsonResponse({'error': 'Invalid chat session'}, status=400)
                
            images = request.FILES.getlist('reference_image')
            videos = request.FILES.getlist('reference_video')
            audios = request.FILES.getlist('reference_audio')
            
            if len(images) > 30: return JsonResponse({'error': 'Maximum 30 images allowed'}, status=400)
            if len(videos) > 10: return JsonResponse({'error': 'Maximum 10 videos allowed'}, status=400)
            if len(audios) > 10: return JsonResponse({'error': 'Maximum 10 audios allowed'}, status=400)
            
            # File validation
            def validate_files(files, max_mb, allowed_prefix):
                max_bytes = max_mb * 1024 * 1024
                for f in files:
                    if f.size > max_bytes:
                        return f"File {f.name} exceeds {max_mb}MB limit."
                    mime_type, _ = mimetypes.guess_type(f.name)
                    if not mime_type or not mime_type.startswith(allowed_prefix):
                        return f"File {f.name} has invalid type. Allowed: {allowed_prefix}"
                return None

            err = validate_files(images, 30, 'image')
            if err: return JsonResponse({'error': err}, status=400)
            
            err = validate_files(videos, 200, 'video')
            if err: return JsonResponse({'error': err}, status=400)
            
            err = validate_files(audios, 15, 'audio')
            if err: return JsonResponse({'error': err}, status=400)
            
            # Create the database record
            generation = Generation.objects.create(
                chat_session=active_chat,
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
        session_key = get_session_key(request)
        generation = Generation.objects.get(
            models.Q(chat_session__session_key=session_key) | models.Q(chat_session__session_key__isnull=True),
            id=generation_id
        )
        return JsonResponse({
            'status': generation.status,
            'video_url': generation.video_file.url if generation.video_file else None,
            'error_message': generation.error_message
        })
    except Generation.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
