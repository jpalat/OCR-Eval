# National Archives Catalog Data Retrieval Process

This document describes the process used to retrieve archive images and transcriptions from the National Archives Catalog for NAID 54928953.

## Overview

**Source URL:** https://catalog.archives.gov/id/54928953
**Record Title:** Revolutionary War Pension and Bounty Land Warrant Application File S. 7026, John Hough, Va.
**Items Retrieved:** 14 images with 14 corresponding transcriptions

## Challenge

The National Archives Catalog website is a Single Page Application (SPA) built with React. Traditional HTTP requests to the catalog URLs return only the JavaScript shell, not the actual data. The API (v2) requires authentication via an API key for direct access.

## Solution

A browser automation approach using Puppeteer was implemented to:
1. Render the JavaScript-based page
2. Intercept API calls made by the frontend
3. Extract image URLs and transcription data from the captured responses

## Technical Process

### Step 1: Environment Setup

```bash
npm init -y
npm install puppeteer
```

### Step 2: Browser Automation Script

A Puppeteer script (`scrape_nara.js`) was created to:
- Launch a headless Chrome browser
- Navigate to the catalog page
- Intercept network responses
- Capture API responses containing digital object metadata and contributions

Key API endpoints discovered:
- `https://catalog.archives.gov/proxy/v3/records/search?naId_is=54928953` - Returns record metadata including digital object URLs
- `https://catalog.archives.gov/proxy/contributions/targetNaId/54928953` - Returns user contributions including transcriptions

### Step 3: Data Extraction

The captured API responses revealed:
- **Digital Objects:** Stored in `record.digitalObjects[]` with `objectId` and `objectUrl` fields
- **Transcriptions:** Stored as contributions with `contributionType: "transcription"` and text in the `contribution` field

### Step 4: Download and Organization

A Python script (`extract_and_save.py`) was created to:
1. Parse the captured API responses
2. Download images from S3 URLs to `./images/`
3. Extract transcriptions and save to `./transcriptions/`

## Data Structure

### API Response Structure

**Records Search Response:**
```json
{
  "body": {
    "hits": {
      "hits": [{
        "_source": {
          "record": {
            "digitalObjects": [{
              "objectId": "54928954",
              "objectUrl": "https://s3.amazonaws.com/NARAprodstorage/..."
            }]
          }
        }
      }]
    }
  }
}
```

**Contributions Response:**
```json
[
  {
    "contributionType": "transcription",
    "targetObjectId": "54928954",
    "contribution": "Transcribed text content..."
  }
]
```

### Image URL Pattern

All images are hosted on AWS S3:
```
https://s3.amazonaws.com/NARAprodstorage/opastorage/live/53/9289/54928953/content/23_b/M804-RevolutionaryWarPensionAppFiles_b/M804_1334/images/{image_id}.jpg
```

## Output Files

### Images Directory (`./images/`)
| File | Object ID | Size |
|------|-----------|------|
| item_01_54928954.jpg | 54928954 | 4.7 MB |
| item_02_54928955.jpg | 54928955 | 1.7 MB |
| item_03_54928956.jpg | 54928956 | 2.1 MB |
| item_04_54928957.jpg | 54928957 | 3.4 MB |
| item_05_54928958.jpg | 54928958 | 3.1 MB |
| item_06_54928959.jpg | 54928959 | 3.0 MB |
| item_07_54928960.jpg | 54928960 | 3.3 MB |
| item_08_54928961.jpg | 54928961 | 3.1 MB |
| item_09_54928962.jpg | 54928962 | 3.0 MB |
| item_10_54928963.jpg | 54928963 | 2.9 MB |
| item_11_54928964.jpg | 54928964 | 2.6 MB |
| item_12_54928965.jpg | 54928965 | 1.8 MB |
| item_13_54928966.jpg | 54928966 | 2.1 MB |
| item_14_54928967.jpg | 54928967 | 2.2 MB |

### Transcriptions Directory (`./transcriptions/`)
Each image has a corresponding `.txt` file with the same naming convention containing the community-contributed transcription.

## Scripts

### scrape_nara.js
Puppeteer script that:
- Launches headless Chrome
- Navigates to the NARA catalog page
- Captures API responses via request interception
- Saves responses to `api_responses.json`

### extract_and_save.py
Python script that:
- Parses `api_responses.json`
- Downloads images to `./images/`
- Extracts and saves transcriptions to `./transcriptions/`

## Dependencies

- Node.js v25+
- Puppeteer (npm package)
- Python 3
- Google Chrome browser

## Limitations and Notes

1. The NARA Catalog API v2 requires an API key for direct access
2. This approach relies on intercepting the same API calls the frontend makes
3. Rate limiting may apply for bulk downloads
4. Image URLs are subject to change if NARA reorganizes their storage

## Future Improvements

- Add support for batch processing multiple NAIDs
- Implement retry logic for failed downloads
- Add progress reporting for large collections
- Consider using the official API with a registered key for production use

## References

- [National Archives Catalog](https://catalog.archives.gov/)
- [NARA Catalog API Documentation](https://www.archives.gov/research/catalog/help/api)
- [Puppeteer Documentation](https://pptr.dev/)
