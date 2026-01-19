#!/usr/bin/env python3
import json
import os
import urllib.request
import ssl

# Create directories
images_dir = './images'
transcriptions_dir = './transcriptions'

os.makedirs(images_dir, exist_ok=True)
os.makedirs(transcriptions_dir, exist_ok=True)

# Load the API responses
with open('api_responses.json', 'r') as f:
    data = json.load(f)

# Extract digital objects (images) and their info
digital_objects = []
for response in data:
    url = response['url']
    resp_data = response.get('data', {})

    if 'records/search' in url and isinstance(resp_data, dict):
        body = resp_data.get('body', {})
        hits = body.get('hits', {}).get('hits', [])
        for hit in hits:
            source = hit.get('_source', {})
            record = source.get('record', {})
            objs = record.get('digitalObjects', [])
            if objs:
                digital_objects = objs
                break

print(f"Found {len(digital_objects)} digital objects")

# Extract transcriptions - the text is in 'contribution' field
transcriptions = {}
for response in data:
    url = response['url']
    resp_data = response.get('data', {})

    if 'contributions' in url and isinstance(resp_data, list):
        for item in resp_data:
            if item.get('contributionType') == 'transcription':
                obj_id = str(item.get('targetObjectId'))
                text = item.get('contribution', '')  # Text is in 'contribution' field
                if obj_id and text and obj_id not in transcriptions:
                    transcriptions[obj_id] = text

print(f"Found {len(transcriptions)} transcriptions")

# Create SSL context to handle certificates
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Download images and save transcriptions
for i, obj in enumerate(digital_objects, 1):
    obj_id = str(obj.get('objectId', ''))
    image_url = obj.get('objectUrl', '')

    if image_url:
        # Download image
        filename = f"item_{i:02d}_{obj_id}.jpg"
        filepath = os.path.join(images_dir, filename)

        if not os.path.exists(filepath):
            print(f"Downloading image {i}: {filename}")
            try:
                request = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(request, context=ssl_context, timeout=60) as response:
                    with open(filepath, 'wb') as out_file:
                        out_file.write(response.read())
                print(f"  Saved to {filepath}")
            except Exception as e:
                print(f"  Error downloading: {e}")
        else:
            print(f"Image {i} already exists: {filename}")

    # Save transcription
    transcription = transcriptions.get(obj_id, '')
    if transcription:
        trans_filename = f"item_{i:02d}_{obj_id}.txt"
        trans_filepath = os.path.join(transcriptions_dir, trans_filename)

        print(f"Saving transcription {i}: {trans_filename}")
        with open(trans_filepath, 'w', encoding='utf-8') as f:
            f.write(transcription)
        print(f"  Saved to {trans_filepath}")
        print(f"  Preview: {transcription[:100]}...")
    else:
        print(f"  No transcription found for object {obj_id}")

print("\nDone!")
print(f"Images saved to: {images_dir}")
print(f"Transcriptions saved to: {transcriptions_dir}")

# List contents
print(f"\nImages folder contents:")
for f in sorted(os.listdir(images_dir)):
    size = os.path.getsize(os.path.join(images_dir, f))
    print(f"  {f} ({size:,} bytes)")

print(f"\nTranscriptions folder contents:")
for f in sorted(os.listdir(transcriptions_dir)):
    size = os.path.getsize(os.path.join(transcriptions_dir, f))
    print(f"  {f} ({size:,} bytes)")
