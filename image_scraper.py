import os
import csv
import requests
import time
import base64
from urllib.parse import urljoin

# API credentials and base URL
API_URL = 'https://sales.tasco.net.au/userapi/json/product/v4_tasco.json'
API_USERNAME = os.environ.get('API_USERNAME')
API_PASSWORD = os.environ.get('API_PASSWORD')
BASE_IMAGE_URL = 'https://sales.tasco.net.au'

# File paths
INPUT_CSV = 'zt-image-fetch/product-scrape-list.csv'
OUTPUT_DIR = 'zt-image-fetch/tsa-images'
DOWNLOADED_IMAGES_CSV = 'zt-image-fetch/downloaded-images.csv'

def get_auth_headers():
    """Encodes credentials and returns authorization headers."""
    if not API_USERNAME or not API_PASSWORD:
        raise ValueError("API_USERNAME and API_PASSWORD environment variables must be set.")
    credentials = f"{API_USERNAME}:{API_PASSWORD}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    return {
        'Authorization': f'Basic {encoded_credentials}'
    }

def download_images(item_code, headers):
    """Downloads images for a given item code and returns their paths."""
    product_url = f"https://sales.tasco.net.au/userapi/json/product/v4_tasco.json?code={item_code}"
    saved_image_paths = []
    try:
        response = requests.get(product_url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data.get('count', 0) > 0 and 'images' in data['products'][0] and data['products'][0]['images']:
            product_dir_abs = os.path.join(OUTPUT_DIR, item_code)
            product_dir_rel = f"/{item_code}"
            os.makedirs(product_dir_abs, exist_ok=True)
            
            images = data['products'][0]['images']
            print(f"Found {len(images)} images for {item_code}. Downloading...")

            for i, img_data in enumerate(images):
                img_url = urljoin(BASE_IMAGE_URL, img_data['url'])
                img_response = requests.get(img_url, headers=headers)
                img_response.raise_for_status()
                
                original_extension = os.path.splitext(img_data['filename'])[1]
                img_name = f"{item_code}_{i+1:03d}{original_extension}"
                
                saved_file_path_abs = os.path.join(product_dir_abs, img_name)
                saved_file_path_rel = os.path.join(product_dir_rel, img_name).replace('\\', '/')

                with open(saved_file_path_abs, 'wb') as f:
                    f.write(img_response.content)
                print(f"  Downloaded {img_name}")
                saved_image_paths.append(saved_file_path_rel)
            return saved_image_paths
        else:
            print(f"No images found for {item_code}.")
            return []

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {item_code}: {e}")
        return []

def main():
    """Main function to process the CSV and download images."""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    headers = get_auth_headers()
    downloaded_images_list = []

    with open(INPUT_CSV, mode='r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        for i, row in enumerate(reader):
            item_code = row['Item Code']
            print(f"\nProcessing Item Code: {item_code}")
            
            saved_paths = download_images(item_code, headers)
            if saved_paths:
                for path in saved_paths:
                    downloaded_images_list.append([item_code, path])
            else:
                downloaded_images_list.append([item_code, ''])
            
            time.sleep(5)

    if downloaded_images_list:
        with open(DOWNLOADED_IMAGES_CSV, mode='w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            writer.writerow(['Item Code', 'Saved Image Path'])
            writer.writerows(downloaded_images_list)
        print(f"Logged {len(downloaded_images_list)} downloaded image paths to {DOWNLOADED_IMAGES_CSV}")

if __name__ == '__main__':
    main() 