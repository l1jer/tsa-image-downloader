# Product Image Scraper – Developer Guide

## Why This Exists

We built this tool to help move a mountain of product images from an old, cranky product system into a shiny new CRM. The goal: grab every image (no matter how many or how weird the product codes), and make sure nothing gets lost along the way. The whole thing runs on GitHub Actions, so you can kick it off manually or let it run on a schedule—set and forget.

---

## What Makes It Tick

- **Smart API Fallback:** If the main API endpoint doesn’t have what we need, the script automatically tries a backup API (with its own credentials). This is a lifesaver for legacy systems where data is scattered or sometimes just… missing.

- **Handles Errors Like a Pro:**
    - **Resumable Runs:** Progress is logged to `downloaded-images.csv`. If the job gets interrupted (network blip, API outage, GitHub runner timeout), just rerun it—already-processed items are skipped, so you don’t waste time or bandwidth.
    - **Retries Built-In:** Uses `requests` and `urllib3` to retry on flaky HTTP errors (like 5xx) and those annoying “empty response” moments. It’s persistent.

- **Fully Automated with GitHub Actions:**
    - The workflow is set up for both scheduled (cron) and manual runs.
    - Progress is always saved: the CSV log is committed back to the repo, and all images are zipped and uploaded as an artifact—even if something fails.
    - API credentials are handled securely via GitHub Secrets. No secrets in code, ever.

- **Safe File Handling:** Product codes sometimes have slashes or other odd characters. The script sanitises these so your file system doesn’t freak out.

---

## Getting Set Up

1. **Configure Your Environment:**
    - Open up `image_scraper.py`.
    - In the config section, swap out the placeholder URLs for your real API endpoints:
      ```python
      # API and Image Host Configuration
      API_URL_1 = 'https://your-primary-api.com/products'
      API_URL_2 = 'https://your-fallback-api.com/products'
      BASE_IMAGE_URL = 'https://your-image-host.com'
      ```

2. **Set Up GitHub Secrets:**
    - In your repo, go to `Settings` > `Secrets and variables` > `Actions`.
    - Add these four secrets (used for API authentication):
        - `API_USERNAME_1`
        - `API_PASSWORD_1`
        - `API_USERNAME_2`
        - `API_PASSWORD_2`

---

## How to Run & What You Get

- **Running the Scraper:** Go to the `Actions` tab in GitHub and run the “Automated Image Scraper” workflow. Or just let it run on its schedule—your call.

- **What You’ll Get:**
    1. `downloaded-images.csv` – a log of every product processed and where its images are saved.
    2. A zipped archive (as a GitHub Actions artifact) with all the images, neatly sorted by product code, plus the CSV log.

---

## Tech Stack

- **Python**
- **GitHub Actions** (for automation and CI/CD)
- **Libraries:** `requests`, `urllib3`
- **Tools:** `Git`, `Bash` (for scripting in the workflow)

---