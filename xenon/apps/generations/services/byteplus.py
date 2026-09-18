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
        self.project_name = config('BYTEPLUS_PROJECT_NAME', default='default')
        
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
        for media in generation.reference_media.all():
            media_url = f"asset://{media.byteplus_asset_id}" if getattr(media, 'byteplus_asset_id', None) else f"{base_url}{media.file.url}"
            if media.media_type == 'image':
                content_list.append({
                    "type": "image_url",
                    "image_url": {"url": media_url},
                    "role": "reference_image"
                })
            elif media.media_type == 'video':
                content_list.append({
                    "type": "video_url",
                    "video_url": {"url": media_url},
                    "role": "reference_video"
                })
            elif media.media_type == 'audio':
                content_list.append({
                    "type": "audio_url",
                    "audio_url": {"url": media_url},
                    "role": "reference_audio"
                })

        # Allow user to specify an Endpoint ID (ep-xxx) in .env, otherwise fallback to the raw model string
        model_override = config('BYTEPLUS_MODEL_ID', default=generation.model_id)

        payload = {
            "model": model_override,
            "content": content_list,
            "generate_audio": generation.generate_audio,
            "ratio": generation.ratio,
            "resolution": generation.resolution,
            "duration": generation.duration,
            "watermark": generation.watermark
        }
        
        response = requests.post(
            f"{self.base_url}/contents/generations/tasks", 
            json=payload, 
            headers=self._get_headers(),
            timeout=30.0
        )
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise Exception(f"{str(e)} - API Response: {response.text}")
            
        data = response.json()
        return data.get("id")

    def get_task(self, task_id):
        if self.mock_mode:
            # Simulate processing time (if task_id was created less than 15 seconds ago, it's 'running')
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
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise Exception(f"{str(e)} - API Response: {response.text}")
            
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

    def get_asset_api(self):
        from byteplussdkcore.configuration import Configuration
        from byteplussdkcore.api_client import ApiClient
        from byteplussdkcore.universal import UniversalApi
        
        ak = config('BYTEPLUS_AK', default='')
        sk = config('BYTEPLUS_SK', default='')
        
        if not ak or not sk:
            raise Exception("BYTEPLUS_AK and BYTEPLUS_SK are required in .env")
            
        c = Configuration()
        c.ak = ak
        c.sk = sk
        c.region = 'ap-southeast-1'
        
        client = ApiClient(c)
        return UniversalApi(client)

    def create_asset_group(self, name, description):
        from byteplussdkcore.universal import UniversalInfo
        api = self.get_asset_api()
        info = UniversalInfo(method='POST', service='ark', version='2024-01-01', action='CreateAssetGroup', content_type='application/json')
        body = {'Name': name, 'Description': description, 'ProjectName': self.project_name}
        resp = api.do_call(info, body)
        return resp
        
    def create_asset(self, group_id, file_url, asset_type='Image'):
        from byteplussdkcore.universal import UniversalInfo
        api = self.get_asset_api()
        info = UniversalInfo(method='POST', service='ark', version='2024-01-01', action='CreateAsset', content_type='application/json')
        body = {
            'GroupId': group_id,
            'URL': file_url,
            'AssetType': asset_type,
            'Moderation': {'Strategy': 'Skip'},
            'ProjectName': self.project_name
        }
        resp = api.do_call(info, body)
        return resp
        
    def get_asset(self, asset_id):
        from byteplussdkcore.universal import UniversalInfo
        api = self.get_asset_api()
        info = UniversalInfo(method='POST', service='ark', version='2024-01-01', action='GetAsset', content_type='application/json')
        body = {'Id': asset_id, 'ProjectName': self.project_name}
        resp = api.do_call(info, body)
        return resp
        
    def delete_asset_group(self, group_id):
        from byteplussdkcore.universal import UniversalInfo
        api = self.get_asset_api()
        info = UniversalInfo(method='POST', service='ark', version='2024-01-01', action='DeleteAssetGroup', content_type='application/json')
        body = {'Id': group_id, 'ProjectName': self.project_name}
        resp = api.do_call(info, body)
        return resp