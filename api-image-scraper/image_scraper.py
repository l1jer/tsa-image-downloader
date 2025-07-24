import os
import csv
import requests
import time
import base64
import traceback
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- Configuration ---
# TODO: Replace these placeholder URLs with your actual API endpoints.
API_URL_1 = 'https://api.example.com/v1/products'  # Primary API
API_URL_2 = 'https://api.example.com/v2/products'  # Fallback API
BASE_IMAGE_URL = 'https://images.example.com'      # Base URL for image resources

# --- File Paths ---
INPUT_CSV = 'product-scrape-list.csv'
OUTPUT_DIR = 'product-images'
DOWNLOADED_IMAGES_CSV = 'downloaded-images.csv'

# --- Credentials (Set these as GitHub Secrets in your repository) ---
# See README.md for setup instructions.
API_USERNAME_1 = os.environ.get('API_USERNAME_1')
API_PASSWORD_1 = os.environ.get('API_PASSWORD_1')
API_USERNAME_2 = os.environ.get('API_USERNAME_2')
API_PASSWORD_2 = os.environ.get('API_PASSWORD_2')


def create_requests_session():
    """
    Creates a requests session with a robust retry strategy for handling
    common transient server errors.
    """
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504] # Standard server errors
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def get_auth_headers(username, password):
    """Encodes API credentials and returns authorization headers."""
    if not username or not password:
        return None
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    return {'Authorization': f'Basic {encoded_credentials}'}

def fetch_product_data(item_code, api_url, headers, session):
    """
    Attempts to fetch product data from a single API endpoint.
    Includes a retry mechanism for transient issues.
    """
    if not headers:
        print(f"  Skipping API call for {api_url} because credentials are not set.")
        return None

    product_url = f"{api_url}?code={item_code}"
    for attempt in range(3):
        try:
            response = session.get(product_url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            products = data.get('products')
            
            if products:
                print(f"  Successfully fetched data for {item_code} from {api_url}")
                return products

            if attempt < 2:
                print(f"  Warning: No product data from {api_url} on attempt {attempt + 1}/3. Retrying...")
                time.sleep(5)
        
        except requests.exceptions.RequestException as e:
            print(f"  Error connecting to {api_url} for {item_code}: {e}")
            return None # Fail fast on connection errors, session already retried.
        except (ValueError, IndexError) as e:
            print(f"  Error parsing JSON from {api_url} for {item_code}: {e}")
            return None # Fail fast on malformed data.
    
    print(f"  All retries failed for {item_code} at {api_url}.")
    return None

def download_images(item_code, session):
    """
    Downloads all images for an item, trying the primary API first,
    then the fallback API.
    """
    # --- Try Primary API ---
    print(f"  Attempting to fetch from primary API...")
    headers_1 = get_auth_headers(API_USERNAME_1, API_PASSWORD_1)
    products = fetch_product_data(item_code, API_URL_1, headers_1, session)

    # --- Try Fallback API if Primary Fails ---
    if not products:
        print(f"  Primary API failed for {item_code}. Trying fallback API...")
        headers_2 = get_auth_headers(API_USERNAME_2, API_PASSWORD_2)
        products = fetch_product_data(item_code, API_URL_2, headers_2, session)

    # --- Process Results ---
    if not products:
        print(f"No product data returned for {item_code} from any API.")
        return []

    # We assume the first product in the list is the one we want.
    images = products[0].get('images', [])
    if not images:
        print(f"No images found for {item_code}.")
        return []

    saved_image_paths = []
    sanitized_item_code = item_code.replace('/', '_').replace('\\', '_')
    product_dir_abs = os.path.join(OUTPUT_DIR, sanitized_item_code)
    os.makedirs(product_dir_abs, exist_ok=True)
    
    print(f"Found {len(images)} images for {item_code}. Downloading...")
    for i, img_data in enumerate(images):
        try:
            # Assumes images are hosted at the same base URL.
            # The primary credentials are used for the download.
            img_url = urljoin(BASE_IMAGE_URL, img_data.get('url', ''))
            img_response = session.get(img_url, headers=headers_1, timeout=30)
            img_response.raise_for_status()
            
            original_extension = os.path.splitext(img_data.get('filename', ''))[1] or '.jpg'
            img_name = f"{sanitized_item_code}_{i+1:03d}{original_extension}"
            
            saved_file_path_abs = os.path.join(product_dir_abs, img_name)
            saved_file_path_rel = os.path.join(f"/{sanitized_item_code}", img_name).replace('\\', '/')

            with open(saved_file_path_abs, 'wb') as f:
                f.write(img_response.content)
            print(f"  Downloaded {img_name}")
            saved_image_paths.append(saved_file_path_rel)
        except requests.exceptions.RequestException as e:
            print(f"  Error downloading image {img_data.get('filename', 'N/A')}: {e}")
        except IOError as e:
            print(f"  Error saving image {img_data.get('filename', 'N/A')}: {e}")
    return saved_image_paths

def main():
    """
    Main function to initialize, read the product list, and process each item,
    allowing the script to be resumed if interrupted.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    processed_items = set()
    try:
        if os.path.exists(DOWNLOADED_IMAGES_CSV):
            with open(DOWNLOADED_IMAGES_CSV, mode='r', encoding='utf-8', newline='') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    if 'Item Code' in row:
                        processed_items.add(row['Item Code'])
            if processed_items:
                print(f"Resuming download. Found {len(processed_items)} already processed items.")
    except (IOError, csv.Error) as e:
        print(f"Warning: Could not read {DOWNLOADED_IMAGES_CSV}. Starting fresh. Error: {e}")

    try:
        with open(INPUT_CSV, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            all_rows = [row for row in reader if row.get('Item Code')]
    except FileNotFoundError:
        print(f"FATAL: Input file '{INPUT_CSV}' not found.")
        return

    items_to_process = [row for row in all_rows if row['Item Code'] not in processed_items]
    if not items_to_process:
        print("All items have already been processed. Nothing to do.")
        return
        
    print(f"Found {len(all_rows)} total items. {len(items_to_process)} items left to process.")
    
    session = create_requests_session()
    
    file_exists = os.path.exists(DOWNLOADED_IMAGES_CSV) and os.path.getsize(DOWNLOADED_IMAGES_CSV) > 0
    with open(DOWNLOADED_IMAGES_CSV, mode='a', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        if not file_exists:
            writer.writerow(['Item Code', 'Saved Image Path'])

        for i, row in enumerate(items_to_process):
            item_code = row.get('Item Code')
            if not item_code:
                print(f"Skipping row {i+1} due to missing 'Item Code'.")
                continue

            print(f"\nProcessing item {i + 1}/{len(items_to_process)}: {item_code}")
            try:
                saved_paths = download_images(item_code, session)
                
                if saved_paths:
                    for path in saved_paths:
                        writer.writerow([item_code, path])
                else:
                    writer.writerow([item_code, ''])
                
                outfile.flush()
                
                if i < len(items_to_process) - 1:
                    # Rate limit to avoid overwhelming the API server.
                    time.sleep(1) 
            except Exception as e:
                print(f"An unexpected error occurred while processing item {item_code}: {e}")
                traceback.print_exc()

    print(f"\nProcess complete.")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"A critical error occurred: {e}")
        traceback.print_exc() 