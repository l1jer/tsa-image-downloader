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
API_URL = 'https://sales.tasco.net.au/userapi/json/product/v4_tasco.json'
BASE_IMAGE_URL = 'https://sales.tasco.net.au'
INPUT_CSV = 'product-scrape-list.csv'
OUTPUT_DIR = 'tsa-images'
DOWNLOADED_IMAGES_CSV = 'downloaded-images.csv'
API_USERNAME = os.environ.get('API_USERNAME')
API_PASSWORD = os.environ.get('API_PASSWORD')

def create_requests_session():
    """
    Creates a requests session with a robust retry strategy for handling
    common transient server errors.
    """
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504, 522]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def get_auth_headers():
    """Encodes API credentials and returns authorization headers."""
    if not API_USERNAME or not API_PASSWORD:
        raise ValueError("API_USERNAME and API_PASSWORD environment variables must be set.")
    credentials = f"{API_USERNAME}:{API_PASSWORD}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    return {'Authorization': f'Basic {encoded_credentials}'}

def download_images(item_code, headers, session):
    """
    Downloads all images for a given item code, sanitizing the item code to create
    valid directory and file names. It includes a retry mechanism for transient API
    issues where a valid item might temporarily return no data.
    """
    product_url = f"{API_URL}?code={item_code}"
    
    # Retry logic for intermittent API issues where a product might temporarily return no data.
    for attempt in range(3):
        try:
            response = session.get(product_url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            products = data.get('products')

            # If we get a valid product list, process it and exit the function.
            if products:
                # We assume the first product in the list is the one we want.
                images = products[0].get('images')

                if not images:
                    print(f"No images found for {item_code}.")
                    return []

                # Sanitize item_code to make it a valid directory name
                saved_image_paths = []
                sanitized_item_code = item_code.replace('/', '_').replace('\\', '_')
                product_dir_abs = os.path.join(OUTPUT_DIR, sanitized_item_code)
                os.makedirs(product_dir_abs, exist_ok=True)
                
                print(f"Found {len(images)} images for {item_code}. Downloading...")
                for i, img_data in enumerate(images):
                    try:
                        img_url = urljoin(BASE_IMAGE_URL, img_data['url'])
                        img_response = session.get(img_url, headers=headers, timeout=30)
                        img_response.raise_for_status()
                        
                        original_extension = os.path.splitext(img_data['filename'])[1] or '.jpg'
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

            # If 'products' is empty, log, wait, and retry.
            if attempt < 2:  # 2 is the max index for a 3-attempt loop (0, 1, 2)
                print(f"Warning: No product data for {item_code} on attempt {attempt + 1}/3. Retrying in 5s...")
                time.sleep(5)

        except requests.exceptions.RequestException as e:
            print(f"Error fetching product data for {item_code}: {e}")
            return []  # Fail fast on connection errors, as the session already retried.
        except (ValueError, IndexError) as e:
            print(f"Error parsing JSON response for {item_code}: {e}")
            return [] # Fail fast on malformed data.
    
    # If all attempts fail, log the final failure and move on.
    print(f"No product data returned for {item_code} after 3 attempts.")
    return []

def main():
    """
    Main function to initialize, read the product list, and process each item,
    allowing the script to be resumed if interrupted.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # --- Load already processed items to allow for script resumption ---
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
        processed_items = set()

    # --- Read all item codes from the input CSV ---
    try:
        with open(INPUT_CSV, mode='r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            all_rows = [row for row in reader if row.get('Item Code')]
    except FileNotFoundError:
        print(f"FATAL: Input file not found at {INPUT_CSV}")
        return

    items_to_process = [row for row in all_rows if row['Item Code'] not in processed_items]
    if not items_to_process:
        print("All items have already been processed. Nothing to do.")
        return
        
    print(f"Found {len(all_rows)} total items. {len(items_to_process)} items left to process.")
    
    # --- Setup ---
    headers = get_auth_headers()
    session = create_requests_session()
    
    # --- Process items and write results incrementally ---
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
                saved_paths = download_images(item_code, headers, session)
                
                # Log result to CSV, whether images were found or not
                if saved_paths:
                    for path in saved_paths:
                        writer.writerow([item_code, path])
                else:
                    writer.writerow([item_code, ''])
                
                outfile.flush() # Ensure data is written to disk immediately
                
                if i < len(items_to_process) - 1:
                    time.sleep(5) # Rate limit between different item codes
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