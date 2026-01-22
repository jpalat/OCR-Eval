import base64
import os
from mistralai import Mistral

api_key = os.environ["MISTRAL_API_KEY"]

client = Mistral(api_key=api_key)

def encode_file(file_path):
    with open(file_path, "rb") as pdf_file:
        return base64.b64encode(file_path.read()).decode('utf-8')

file_path = "path/to/4159576_00495.jpg"
base64_file = encode_file(file_path)

ocr_response = client.ocr.process(
    model="mistral-ocr-latest",
    document={
      "type": image_url,
      "image_url": f"data:image/jpeg;base64,{base64_file}" 
    },
    include_image_base64=True
