import requests
import os
import time
from django.conf import settings
from decouple import config

class BytePlusService:
    def __init__(self):
        self.api_key = config('BYTEPLUS_MODELARK_API_KEY', default='')
        self.base_url = config('BYTEPLUS_MODELARK_BASE_URL', default='https://ark.cn-beijing.volces.com/api/v3')
        self.mock_mode = config('MOCK_BYTEPLUS', default=False, cast=bool)
        
    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def create_task(self, generation, base_url):
        if self.mock_mode:
            # Return a fake task ID immediately
            return f"mock-task-{int(time.time())}"

        content_list = [
            {"type": "text", "text": generation.prompt}
        ]
        
        # Append reference media if provided, turning relative paths into absolute URLs
        if generation.reference_image:
            content_list.append({
                "type": "image_url",
                "image_url": {"url": f"{base_url}{generation.reference_image.url}"},
                "role": "reference_image"
            })
        if generation.reference_video:
            content_list.append({
                "type": "video_url",
                "video_url": {"url": f"{base_url}{generation.reference_video.url}"},
                "role": "reference_video"
            })
        if generation.reference_audio:
            content_list.append({
                "type": "audio_url",
                "audio_url": {"url": f"{base_url}{generation.reference_audio.url}"},
                "role": "reference_audio"
            })

        payload = {
            "model": generation.model_id,
            "content": content_list,
            "generate_audio": generation.generate_audio,
            "ratio": generation.ratio,
            "duration": generation.duration,
            "watermark": generation.watermark
        }
        
        response = requests.post(
            f"{self.base_url}/contents/generations/tasks", 
            json=payload, 
            headers=self._get_headers(),
            timeout=30.0
        )
        response.raise_for_status()
        data = response.json()
        return data.get("id")

    def get_task(self, task_id):
        if self.mock_mode:
            # Simulate processing time (if task_id was created less than 15 seconds ago, it's 'running')
            try:
                creation_time = int(task_id.split('-')[-1])
                if time.time() - creation_time < 15:
                    return {"status": "running"}
                else:
                    return {
                        "status": "succeeded", 
                        "content": {
                            # Using a highly reliable MDN web docs sample video
                            "video_url": "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"
                        }
                    }
            except:
                return {"status": "failed", "error": {"message": "Invalid mock task"}}

        response = requests.get(
            f"{self.base_url}/contents/generations/tasks/{task_id}", 
            headers=self._get_headers(),
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()

    def download_video(self, url, destination_path):
        """Downloads the generated video using an unauthenticated client."""
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        
        # Stream the download (added User-Agent to prevent 403s on some hosts)
        headers = {"User-Agent": "Mozilla/5.0"}
        with requests.get(url, headers=headers, stream=True, timeout=300.0) as response:
            response.raise_for_status()
            with open(destination_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
