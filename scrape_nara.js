const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

// Create directories for output
const imagesDir = './images';
const transcriptionsDir = './transcriptions';

if (!fs.existsSync(imagesDir)) fs.mkdirSync(imagesDir);
if (!fs.existsSync(transcriptionsDir)) fs.mkdirSync(transcriptionsDir);

async function downloadFile(url, filepath) {
  return new Promise((resolve, reject) => {
    const protocol = url.startsWith('https') ? https : http;
    const file = fs.createWriteStream(filepath);
    protocol.get(url, (response) => {
      response.pipe(file);
      file.on('finish', () => {
        file.close();
        resolve();
      });
    }).on('error', (err) => {
      fs.unlink(filepath, () => {});
      reject(err);
    });
  });
}

async function scrapeNARA() {
  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  // Enable request interception to capture API calls
  await page.setRequestInterception(true);

  const apiResponses = [];

  page.on('request', request => {
    request.continue();
  });

  page.on('response', async response => {
    const url = response.url();
    if (url.includes('/records/') || url.includes('/transcription') || url.includes('/contributions')) {
      try {
        const data = await response.json();
        apiResponses.push({ url, data });
      } catch (e) {
        // Not JSON response
      }
    }
  });

  console.log('Navigating to National Archives catalog page...');
  await page.goto('https://catalog.archives.gov/id/54928953', {
    waitUntil: 'networkidle2',
    timeout: 60000
  });

  console.log('Waiting for content to load...');
  await new Promise(resolve => setTimeout(resolve, 8000));

  // Get all digital object info
  const itemData = await page.evaluate(async () => {
    const items = [];
    const thumbs = document.querySelectorAll('[class*="thumbnail"]');
    const pageNumbers = document.querySelectorAll('[class*="page-number"], [aria-label*="page"]');

    // Try to get image data from page
    const downloadLink = document.querySelector('a[href*="s3.amazonaws.com"]');

    return {
      downloadLink: downloadLink ? downloadLink.href : null,
      pageCount: 14,
      thumbCount: thumbs.length
    };
  });

  console.log('Item data:', itemData);

  // The images follow a pattern based on the first one we found
  // https://s3.amazonaws.com/NARAprodstorage/opastorage/live/53/9289/54928953/content/23_b/M804-RevolutionaryWarPensionAppFiles_b/M804_1334/images/4159576_00490.jpg

  // Let's navigate through each page and get images and transcriptions
  const results = [];

  for (let i = 1; i <= 14; i++) {
    console.log(`\nProcessing page ${i} of 14...`);

    // Click on page thumbnail or navigate to it
    try {
      // Wait for thumbnails to be visible
      await page.waitForSelector('button, [role="button"]', { timeout: 5000 });

      // Find and click the thumbnail for this page
      const clicked = await page.evaluate((pageNum) => {
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
          if (btn.textContent.trim() === String(pageNum) || btn.getAttribute('aria-label')?.includes(`page ${pageNum}`)) {
            btn.click();
            return true;
          }
        }
        // Try thumbnails
        const thumbs = document.querySelectorAll('[class*="thumbnail"]');
        if (thumbs.length >= pageNum) {
          thumbs[pageNum - 1].click();
          return true;
        }
        return false;
      }, i);

      await new Promise(resolve => setTimeout(resolve, 2000));

      // Get current image URL
      const imageUrl = await page.evaluate(() => {
        const downloadLink = document.querySelector('a[href*="s3.amazonaws.com"], a[download], a[href*=".jpg"], a[href*=".png"]');
        if (downloadLink) return downloadLink.href;

        const img = document.querySelector('img[src*="s3.amazonaws.com"], img[src*="NARAprodstorage"]');
        if (img) return img.src;

        return null;
      });

      // Get transcription by clicking on transcription tab if available
      let transcription = '';
      try {
        const hasTranscriptionTab = await page.evaluate(() => {
          const tabs = document.querySelectorAll('button, [role="tab"]');
          for (const tab of tabs) {
            if (tab.textContent.toLowerCase().includes('transcription')) {
              tab.click();
              return true;
            }
          }
          return false;
        });

        if (hasTranscriptionTab) {
          await new Promise(resolve => setTimeout(resolve, 1500));
          transcription = await page.evaluate(() => {
            const transcriptionEl = document.querySelector('[class*="transcription"], [data-transcription], pre, .prose, [class*="contribution-text"]');
            return transcriptionEl ? transcriptionEl.innerText : '';
          });
        }
      } catch (e) {
        console.log(`Could not get transcription for page ${i}`);
      }

      results.push({
        page: i,
        imageUrl,
        transcription
      });

      console.log(`Page ${i}: Image URL: ${imageUrl ? 'Found' : 'Not found'}`);
      console.log(`Page ${i}: Transcription: ${transcription ? transcription.substring(0, 100) + '...' : 'Not found'}`);

    } catch (e) {
      console.log(`Error processing page ${i}:`, e.message);
    }
  }

  console.log('\n--- API Responses captured ---');
  console.log(`Captured ${apiResponses.length} API responses`);

  // Save API responses for analysis
  fs.writeFileSync('api_responses.json', JSON.stringify(apiResponses, null, 2));

  // Save results
  fs.writeFileSync('scrape_results.json', JSON.stringify(results, null, 2));

  await browser.close();
  console.log('\nBrowser closed. Results saved to scrape_results.json');
}

scrapeNARA().catch(console.error);
