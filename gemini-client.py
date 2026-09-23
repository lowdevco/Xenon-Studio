import os
from google import genai

print("Starting...")

client = genai.Client(
    api_key="AQ.Ab8RN6JFJd5feLKEmKDVPyFjuwad3T9XM4WkPW4Pw6wA"
)

print("Client created.")

print("Sending request...")

response = client.models.generate_content(
    model="gemini-3.1-flash-image",
    contents="Generate a simple image of a red apple on a white table."
)

print("Response received!")
print(response)