import time
import uuid
import random
from decouple import config

class GeminiService:
    def __init__(self):
        # Toggle this in your .env file: MOCK_IMAGE_GEN=True or False
        self.mock_mode = config('MOCK_IMAGE_GEN', default=True, cast=bool)

    def generate_image(self, generation, base_url=""):
        if self.mock_mode:
            return f"gemini-mock-{int(time.time())}-{uuid.uuid4()}"
        
        # Real API logic goes here
        # payload = {"prompt": generation.prompt}
        # response = requests.post("https://api.example.com/generate", json=payload)
        raise NotImplementedError("Real Gemini API logic is not yet implemented. Set MOCK_IMAGE_GEN=True in .env")

    def check_status(self, task_id):
        if self.mock_mode:
            parts = task_id.split('-')
            if len(parts) >= 3 and parts[0] == 'gemini' and parts[1] == 'mock':
                start_time = int(parts[2])
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
        raise NotImplementedError("Real Gemini API status check is not yet implemented.")
