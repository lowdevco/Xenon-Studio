import os
import base64


from google import genai

client = genai.Client(
    api_key="AQ.Ab8RN6JFJd5feLKEmKDVPyFjuwad3T9XM4WkPW4Pw6wA"
)

interaction = client.interactions.create(
    model="gemini-3.1-flash-image",
    input=(
        "Create a highly photorealistic cinematic image of a modern "
        "Indian film studio set, with dramatic professional lighting, "
        "realistic materials, detailed production equipment, and a "
        "premium cinematic atmosphere."
    ),
)

if interaction.output_image:
    image_data = base64.b64decode(
        interaction.output_image.data
    )

    with open("gemini_test.png", "wb") as f:
        f.write(image_data)

    print("Image generated successfully.")
    print("Saved to gemini_test.png")
else:
    print("No image was returned.")
    print(interaction)