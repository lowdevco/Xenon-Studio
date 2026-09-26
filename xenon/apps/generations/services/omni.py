import os
import shutil
import base64
import time
from decouple import config
from django.conf import settings
from google import genai

class OmniService:
    def __init__(self):
        self.api_key = config('GEMINI_API_KEY', default='')
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None

    def create_task(self, generation, base_url):
        if not self.client:
            raise ValueError("GEMINI_API_KEY is not configured in .env")

        # 1. Structure the input array
        inputs = []
        
        # Add the text prompt
        inputs.append({
            "type": "text", 
            "text": generation.prompt
        })
        
        # Add the reference media (Ingredients / Frames)
        # We upload each local file to the GenAI API and append it to the inputs list
        for media in generation.reference_media.all():
            if os.path.exists(media.file.path):
                # We can use the GenAI file upload utility for images/videos
                uploaded_file = self.client.files.upload(file=media.file.path)
                inputs.append(uploaded_file)

        # 2. Map the Aspect Ratio to exactly what the API expects
        ratio_map = {
            "16:9": "16:9",
            "9:16": "9:16",
            "1:1": "16:9" # 1:1 might not be natively supported yet by Omni Video, fallback to 16:9
        }
        aspect_ratio = ratio_map.get(generation.ratio, "16:9")
        
        # Determine resolution (user choice: 360p or 720p)
        resolution = generation.resolution if generation.resolution in ["360p", "720p", "1080p", "4k"] else "720p"

        # 3. Call the Interactions API as specified by the official SDK
        interaction = self.client.interactions.create(
            model="gemini-omni-1.1-flash",
            input=inputs,
            response_format={
                "resolution": resolution,
                "aspect_ratio": aspect_ratio
            }
        )

        # 4. Extract and save the output video locally
        video_part = interaction.output_video
        
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_omni')
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_path = os.path.join(temp_dir, f'omni_gen_{generation.id}.mp4')
        
        with open(temp_path, "wb") as f:
            f.write(video_part.data)
            
        # 5. Return a sync-task ID so Celery get_task knows it's already done
        return f"omni-sync-{generation.id}-" + temp_path

    def get_task(self, task_id):
        # Because we generated it synchronously in create_task, we immediately return success!
        if task_id.startswith("omni-sync-"):
            temp_path = task_id.split("-", 3)[-1] # Extract the path
            return {
                "status": "succeeded",
                "progress": 100,
                "content": {
                    "video_url": temp_path  # We pass the local path instead of a URL
                }
            }
        return {"status": "failed", "error": {"message": "Invalid Omni task"}}

    def download_video(self, url, destination_path):
        # The 'url' here is actually our local temp_path from get_task!
        if os.path.exists(url):
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            shutil.copy2(url, destination_path)
            # Clean up the temp file
            try:
                os.remove(url)
            except Exception:
                pass
        else:
            raise FileNotFoundError(f"Omni generated video not found at {url}")
