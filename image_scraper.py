import os
import csv
import requests
import time
import base64
import traceback
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import subprocess
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import json

# --- Configuration ---
API_URL_1 = 'https://sales.tasco.net.au/userapi/json/product/v4_tasco.json'
API_URL_2 = 'https://sales.tasco.net.au/api/json/product/v4.json'
BASE_IMAGE_URL = 'https://sales.tasco.net.au'
INPUT_CSV = 'product-scrape-list.csv'
OUTPUT_DIR = 'tsa-images'
DOWNLOADED_IMAGES_CSV = 'downloaded-images.csv'

# Credentials for the primary API
API_USERNAME_1 = os.environ.get('API_USERNAME')
API_PASSWORD_1 = os.environ.get('API_PASSWORD')

# Credentials for the fallback API
API_USERNAME_2 = os.environ.get('API_USERNAME_2')
API_PASSWORD_2 = os.environ.get('API_PASSWORD_2')

# --- Google Drive Configuration ---
GDRIVE_FOLDER_ID = '1sIouYwI5ZaN4mK_CqKkOsXIi__QC_JM6'
GDRIVE_CREDENTIALS_JSON = os.environ.get('GOOGLE_DRIVE_CREDENTIALS')

# Token for committing progress
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')

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

def get_auth_headers(username, password):
    """Encodes API credentials and returns authorization headers."""
    if not username or not password:
        # This will be handled in the main download logic
        return None
    credentials = f"{username}:{password}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    return {'Authorization': f'Basic {encoded_credentials}'}

def fetch_product_data(item_code, api_url, headers, session):
    """
    Attempts to fetch product data from a single API endpoint.
    Returns the list of products if successful, otherwise None.
    """
    if not headers:
        return None # Skip if credentials are not provided

    product_url = f"{api_url}?code={item_code}"
    try:
        # Retry logic for intermittent API issues where a product might temporarily return no data.
        for attempt in range(3):
            response = session.get(product_url, headers=headers, timeout=30)
            time.sleep(0.2) # Throttle to 5 req/s (well within 10 req/s limit)
            response.raise_for_status()
            data = response.json()
            products = data.get('products')
            
            if products:
                return products # Success

            if attempt < 2:
                print(f"  Warning: No product data from {api_url} on attempt {attempt + 1}/3. Retrying...")
                time.sleep(5)
        
        return None # All retries failed for this API
    except requests.exceptions.RequestException as e:
        print(f"  Error connecting to {api_url} for {item_code}: {e}")
        return None
    except (ValueError, IndexError) as e:
        print(f"  Error parsing JSON from {api_url} for {item_code}: {e}")
        return None

def get_gdrive_service():
    """Initializes and returns the Google Drive service object."""
    if not GDRIVE_CREDENTIALS_JSON:
        print("FATAL: GOOGLE_DRIVE_CREDENTIALS secret not set.")
        return None
    try:
        # Save the credentials to a temporary file
        with open("gdrive_creds.json", "w") as creds_file:
            creds_file.write(GDRIVE_CREDENTIALS_JSON)
        
        gauth = GoogleAuth()
        # This line is a workaround for a PyDrive2 bug where the service_config
        # is not initialized in non-interactive environments.
        gauth.settings['service_config'] = {}
        # Authenticate using the service account credentials from the temporary file
        gauth.auth_method = 'service'
        gauth.service_account_filename = 'gdrive_creds.json'
        drive = GoogleDrive(gauth)
        
        # Clean up the temporary credentials file
        os.remove("gdrive_creds.json")
        
        return drive
    except Exception as e:
        print(f"FATAL: Could not authenticate with Google Drive. Error: {e}")
        return None

def set_workflow_output(name, value):
    """Sets an output for the GitHub Actions workflow step."""
    github_output_file = os.getenv('GITHUB_OUTPUT')
    if github_output_file:
        with open(github_output_file, 'a') as f:
            f.write(f"{name}={value}\n")
    else:
        print(f"::set-output name={name}::{value}") # Fallback for local testing

def upload_to_gdrive(drive, local_path, parent_folder_id):
    """Uploads a file to a specific Google Drive folder and returns its ID."""
    try:
        file_name = os.path.basename(local_path)
        file_drive = drive.CreateFile({
            'title': file_name,
            'parents': [{'id': parent_folder_id}]
        })
        file_drive.SetContentFile(local_path)
        file_drive.Upload()
        print(f"  Successfully uploaded {file_name} to Google Drive.")
        return file_drive['id']
    except Exception as e:
        print(f"  Error uploading {local_path} to Google Drive: {e}")
        return None

def get_or_create_gdrive_folder(drive, folder_name, parent_id):
    """Finds a folder by name or creates it if it doesn't exist."""
    query = f"'{parent_id}' in parents and title = '{folder_name}' and trashed = false"
    file_list = drive.ListFile({'q': query}).GetList()
    if file_list:
        return file_list[0]['id']
    else:
        print(f"  Creating Google Drive folder: {folder_name}")
        folder_metadata = {
            'title': folder_name,
            'parents': [{'id': parent_id}],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = drive.CreateFile(folder_metadata)
        folder.Upload()
        return folder['id']

def commit_progress():
    """Commits the downloaded-images.csv file to the repository."""
    try:
        # Stage the file first to ensure we are checking the right changes
        subprocess.run(['git', 'add', DOWNLOADED_IMAGES_CSV], check=True)

        # Check if there are staged changes for the specific file
        status_result = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True)
        if DOWNLOADED_IMAGES_CSV not in status_result.stdout:
            print("No new changes to downloaded-images.csv to commit.")
            return
            
        print("Committing progress...")
        subprocess.run(['git', 'commit', '-m', 'feat: Update image download progress (automated)'], check=True)
        
        # Configure remote URL with token for authentication
        repo_url = f"https://x-access-token:{GITHUB_TOKEN}@github.com/{os.environ['GITHUB_REPOSITORY']}.git"
        subprocess.run(['git', 'remote', 'set-url', 'origin', repo_url], check=True)
        
        subprocess.run(['git', 'push', 'origin', f"HEAD:{os.environ['GITHUB_REF_NAME']}"], check=True)
        print("Progress committed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error during git operation: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during commit_progress: {e}")

def download_images(item_code, session, drive):
    """
    Downloads all images for a given item code and uploads them to Google Drive.
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

    images = products[0].get('images')
    if not images:
        print(f"No images found for {item_code}.")
        return []

    # Get or create the specific subfolder for this item code in Google Drive
    sanitized_item_code = item_code.replace('/', '_').replace('\\', '_')
    gdrive_subfolder_id = get_or_create_gdrive_folder(drive, sanitized_item_code, GDRIVE_FOLDER_ID)
    if not gdrive_subfolder_id:
        print(f"  Could not create or find Google Drive folder for {item_code}. Skipping.")
        return []
    
    saved_image_gdrive_ids = []
    
    print(f"Found {len(images)} images for {item_code}. Downloading and uploading...")
    for i, img_data in enumerate(images):
        try:
            # Use the primary auth headers for image download as they are on the same domain
            img_url = urljoin(BASE_IMAGE_URL, img_data['url'])
            img_response = session.get(img_url, headers=headers_1, timeout=30)
            time.sleep(0.2) # Throttle to 5 req/s (well within 10 req/s limit)
            img_response.raise_for_status()
            
            original_extension = os.path.splitext(img_data['filename'])[1] or '.jpg'
            img_name = f"{sanitized_item_code}_{i+1:03d}{original_extension}"
            
            # Save the image locally to a temporary path
            local_temp_path = os.path.join(OUTPUT_DIR, img_name)
            with open(local_temp_path, 'wb') as f:
                f.write(img_response.content)
            
            # Upload the local file to Google Drive and get its ID
            gdrive_file_id = upload_to_gdrive(drive, local_temp_path, gdrive_subfolder_id)
            if gdrive_file_id:
                saved_image_gdrive_ids.append(gdrive_file_id)

            # Clean up the local file after upload
            os.remove(local_temp_path)

        except requests.exceptions.RequestException as e:
            print(f"  Error downloading image {img_data.get('filename', 'N/A')}: {e}")
        except IOError as e:
            print(f"  Error processing image {img_data.get('filename', 'N/A')}: {e}")
    return saved_image_gdrive_ids

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
        set_workflow_output('work_done', 'true') # Signal to workflow that work is complete
        return
        
    print(f"Found {len(all_rows)} total items. {len(items_to_process)} items left to process.")
    set_workflow_output('work_done', 'false') # Signal to workflow that work is not complete
    
    # --- Setup ---
    session = create_requests_session()
    drive = get_gdrive_service()
    if not drive:
        return # Stop execution if Google Drive is not available

    last_commit_time = time.time()
    
    # --- Process items and write results incrementally ---
    file_exists = os.path.exists(DOWNLOADED_IMAGES_CSV) and os.path.getsize(DOWNLOADED_IMAGES_CSV) > 0
    with open(DOWNLOADED_IMAGES_CSV, mode='a', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        if not file_exists:
            writer.writerow(['Item Code', 'Google Drive File ID'])

        for i, row in enumerate(items_to_process):
            item_code = row.get('Item Code')
            if not item_code:
                print(f"Skipping row {i+1} due to missing 'Item Code'.")
                continue

            print(f"\nProcessing item {i + 1}/{len(items_to_process)}: {item_code}")
            try:
                gdrive_ids = download_images(item_code, session, drive)
                
                # Log result to CSV, whether images were found or not
                if gdrive_ids:
                    for file_id in gdrive_ids:
                        writer.writerow([item_code, file_id])
                else:
                    writer.writerow([item_code, 'NO_IMAGES_FOUND'])
                
                outfile.flush() # Ensure data is written to disk immediately
                
                # --- Commit progress every 30 minutes ---
                current_time = time.time()
                if current_time - last_commit_time > 1800: # 1800 seconds = 30 minutes
                    print("\n--- 30-minute interval reached. Committing progress. ---")
                    commit_progress()
                    last_commit_time = current_time

            except Exception as e:
                print(f"An unexpected error occurred while processing item {item_code}: {e}")
                traceback.print_exc()

    # Final commit at the end of the run
    print("\n--- Process finished. Committing final progress. ---")
    commit_progress()

    print(f"\nProcess complete.")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"A critical error occurred: {e}")
        traceback.print_exc() 
        set_workflow_output('work_done', 'false') # Ensure we signal to continue on critical error 