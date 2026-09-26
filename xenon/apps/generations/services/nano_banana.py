import time
import uuid
import random
from decouple import config

class NanoBananaService:
    def __init__(self):
        # Allow testing mode using MOCK_NANO_BANANA in .env
        self.mock_mode = config('MOCK_NANO_BANANA', default=True, cast=bool)

    def _get_api_url(self, model_id):
        # Route to different URLs based on the model variation
        if model_id == 'nano_banana_pro':
            return "https://api.nanobanana.com/v1/pro/generate"
        else:
            return "https://api.nanobanana.com/v1/v2/generate"

    def generate_image(self, generation, base_url=""):
        api_url = self._get_api_url(generation.model_id)
        
        if self.mock_mode:
            return f"nano-mock-{generation.model_id}-{int(time.time())}-{uuid.uuid4()}"
        
        # Real API logic goes here
        # payload = {"prompt": generation.prompt, "model": generation.model_id}
        # response = requests.post(api_url, json=payload, headers={"Authorization": f"Bearer {config('NANO_API_KEY')}"})
        # return response.json().get('task_id')
        raise NotImplementedError(f"Real API for {api_url} not yet implemented. Set MOCK_NANO_BANANA=True in .env")

    def check_status(self, task_id):
        if self.mock_mode:
            parts = task_id.split('-')
            if len(parts) >= 4 and parts[0] == 'nano' and parts[1] == 'mock':
                # parts[2] might be 'nano_banana_2' but split by '-' breaks it because of underscores, so it's fine
                # Let's just find the timestamp which is the second to last part
                start_time = int(parts[-2])
                elapsed = time.time() - start_time
                if elapsed < 8:
                    return {'status': 'running', 'progress': int((elapsed/8.0)*99)}
                else:
                    images = [
                        'https://images.unsplash.com/photo-1579546929518-9e396f3cc809?w=1200&h=800&fit=crop',
                        'https://images.unsplash.com/photo-1550684848-fac1c5b4e853?w=1200&h=800&fit=crop',
                        'https://images.unsplash.com/photo-1549490349-8643362247b5?w=1200&h=800&fit=crop',
                        'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=1200&h=800&fit=crop',
                        'https://images.unsplash.com/photo-1574169208507-84376144848b?w=1200&h=800&fit=crop'
                    ]
                    return {
                        'status': 'succeeded',
                        'progress': 100,
                        'image_url': random.choice(images)
                    }
            return {'status': 'failed', 'error': 'Invalid mock ID'}
        
        # Real API check logic goes here
        raise NotImplementedError("Real NanoBanana API status check is not yet implemented.")
