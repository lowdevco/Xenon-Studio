# Xenon Studio - Local Development Guide

To run the Xenon Seedance application locally and test the advanced reference media uploads (which require BytePlus to download files from your machine), you need to run **three separate terminal windows**.

Ensure you have your Python virtual environment activated in the first two terminals:
```bash
# On Windows, activate your virtual environment (if not already activated)
.\env\Scripts\activate
```

---

### Terminal 1: The Django Web Server
This runs the main web application and the frontend UI.

1. Navigate to the `xenon` directory:
   ```bash
   cd xenon
   ```
2. Start the Django server:
   ```bash
   python manage.py runserver
   ```
*Leave this terminal running in the background.*

---

### Terminal 2: The Celery Background Worker
This runs the background tasks that communicate with the BytePlus API, poll for status, and download the finished videos. (Requires Redis to be running on your machine).

1. Navigate to the `xenon` directory:
   ```bash
   cd xenon
   ```
2. Start the Celery worker:
   ```bash
   celery -A config worker -l info --pool=solo
   ```
*Leave this terminal running in the background.*

---

### Terminal 3: Ngrok (For Public File URLs)
Because the BytePlus API requires a public URL to download any reference images/videos you upload, we use Ngrok to temporarily expose your local Django server to the internet.

1. Open a new terminal (virtual environment not required).
2. Start the ngrok tunnel on port 8000:
   ```bash
   ngrok http 8000
   ```
3. Look for the **Forwarding** URL in the ngrok output (it will look something like `https://a1b2c3d4.ngrok-free.app`).

### Accessing the App
**Important:** Do not open `127.0.0.1:8000` in your browser. 
Instead, copy the **Forwarding URL** provided by Ngrok and paste it into your browser. 

By accessing the app through the Ngrok URL, Django will automatically detect the public domain and securely send public file links to the BytePlus servers!
