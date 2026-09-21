import requests
import os
import time
import jwt
import base64
from django.conf import settings
from decouple import config

class KlingService:
    def __init__(self):
        self.ak = config('KLING_AK', default='')
        self.sk = config('KLING_SK', default='')
        self.base_url = config('KLING_BASE_URL', default='https://api.klingai.com/v1')
        self.mock_mode = config('MOCK_KLING', default=False, cast=bool)

    def _get_headers(self):
        if not self.ak or not self.sk:
            return {}
        
        headers_jwt = {
            "alg": "HS256",
            "typ": "JWT"
        }
        payload = {
            "iss": self.ak,
            "exp": int(time.time()) + 1800,
            "nbf": int(time.time()) - 5
        }
        token = jwt.encode(payload, self.sk, algorithm="HS256", headers=headers_jwt)
        
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _encode_image(self, file_path):
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def create_task(self, generation, base_url):
        if self.mock_mode:
            return f"mock-kling-task-{int(time.time())}"

        model_name = "kling-v3-omni" if "omni" in generation.model_id.lower() else generation.model_id
        
        has_image = False
        image_b64 = None
        for media in generation.reference_media.all():
            if media.media_type == 'image':
                has_image = True
                image_b64 = self._encode_image(media.file.path)
                break

        endpoint = f"{self.base_url}/videos/image2video" if has_image else f"{self.base_url}/videos/text2video"

        payload = {
            "model_name": model_name,
            "prompt": generation.prompt,
            "duration": generation.duration,
        }
        if has_image and image_b64:
            payload["image"] = image_b64
        
        # Add Kling specific mapping
        # Kling uses 'aspect_ratio' instead of 'ratio' usually
        # Valid aspect ratios for kling: 16:9, 9:16, 1:1
        if generation.ratio in ['16:9', '9:16', '1:1']:
            payload["aspect_ratio"] = generation.ratio

        response = requests.post(
            endpoint, 
            json=payload, 
            headers=self._get_headers(),
            timeout=30.0
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise Exception(f"{str(e)} - API Response: {response.text}")
            
        data = response.json()
        if "data" in data and "task_id" in data["data"]:
            return data["data"]["task_id"]
        return data.get("task_id", data.get("id"))

    def get_task(self, task_id):
        if self.mock_mode:
            try:
                creation_time = int(task_id.split('-')[-1])
                elapsed = time.time() - creation_time
                if elapsed < 15:
                    return {"status": "running", "progress": int((elapsed / 15.0) * 99)}
                else:
                    return {
                        "status": "succeeded", 
                        "progress": 100,
                        "content": {
                            "video_url": "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"
                        }
                    }
            except:
                return {"status": "failed", "error": {"message": "Invalid mock task"}}

        response = requests.get(
            f"{self.base_url}/videos/tasks/{task_id}", 
            headers=self._get_headers(),
            timeout=10.0
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise Exception(f"{str(e)} - API Response: {response.text}")
            
        data = response.json()
        
        # Map Kling response format to our generic format
        kling_data = data.get("data", {})
        kling_status = kling_data.get("task_status", "submitted")
        
        mapped_status = "queued"
        if kling_status in ["submitted", "processing", "running"]:
            mapped_status = "running"
        elif kling_status == "succeed":
            mapped_status = "succeeded"
        elif kling_status in ["failed", "fail"]:
            mapped_status = "failed"
            
        return {
            "status": mapped_status,
            "progress": kling_data.get("task_progress", 0) * 100 if isinstance(kling_data.get("task_progress"), float) else kling_data.get("task_progress", 0),
            "content": {
                "video_url": kling_data.get("task_result", {}).get("videos", [{}])[0].get("url") if kling_data.get("task_result", {}).get("videos") else None
            },
            "error": {
                "message": kling_data.get("task_status_msg", "")
            }
        }

    def download_video(self, url, destination_path):
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        headers = {"User-Agent": "Mozilla/5.0"}
        with requests.get(url, headers=headers, stream=True, timeout=300.0) as response:
            response.raise_for_status()
            with open(destination_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
