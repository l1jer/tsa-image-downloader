Modify `main.py` to achieve the following:

1. Read a list of Item Codes from `product-scrape-list.csv`. Each Item Code represents a product to process.
2. For each Item Code:
   - Download all associated product images.
   - Save the images in a folder named after the Item Code (e.g., `ABC123/`).
   - If no images are found for a product, record the Item Code in a CSV file listing products with no images.
   - If only one image is found, save it as `ItemCode_1.<original_extension>` (e.g., `ABC123_1.jpg`).
   - If multiple images are found, save them as `ItemCode_1.<ext>`, `ItemCode_2.<ext>`, etc., preserving the original file extensions.
   - Ensure all images for a product are stored within its respective Item Code folder.

Follow best practices for error handling and logging throughout the process.

For initial testing, process only the first 10 Item Codes.
Note: The API enforces a 5-second rate limit between requests. Ensure your code waits at least 5 seconds after each API call to avoid being rate-limited or blocked.
Download and store all folder and images under tsa-image folder.

Here are url and credentials:
define('WCAP_API_URL', 'https://sales.tasco.net.au/userapi/json/product/v4_tasco.json');
define('WCAP_API_USERNAME', 'Cc999186-3a84-4eb0-8972-2fafb2501e80');
define('WCAP_API_PASSWORD', '7302b53a685a2b56bd5d8f454c2f56');

e.g. item code is 312-1219
url is https://sales.tasco.net.au/api/json/product/v4.json?code=312-1219
credential using basic64

The endpoint returns:
{
    "products": [
        {
            "code": "312-1219",
            "description": "3M STD. EAR PLUGS UNCORDED 200 PAIRS PER BOX, 26dB EARPLUGS",
            "abc_class": "",
            "description1": "3M STD. EAR PLUGS UNCORDED",
            "description2": "200 PAIRS PER BOX, 26dB",
            "description3": "EARPLUGS",
            "apn": "080529120137",
            "group_code": "3M",
            "brand": "3M",
            "condition_code": "",
            "default_conversion_factor": 1,
            "issue_ctrl": "",
            "stk_licences_rebate_flag": "",
            "pack_weight": "0.0",
            "title": null,
            "stock_status": "S",
            "sales_type": "",
            "user_only_alpha20_1": "",
            "user_only_alpha20_2": "",
            "user_only_alpha4_1": "",
            "user_only_alpha4_2": "",
            "user_only_alpha4_3": "",
            "user_only_alpha4_4": "",
            "user_only_date1": null,
            "user_only_date2": null,
            "user_only_num1": "0.0",
            "user_only_num2": "0.0",
            "user_only_num3": "0.0",
            "user_only_num4": "0.0",
            "pronto_user_group": "",
            "pronto_user_group_1": "",
            "saleability": true,
            "visibility": true,
            "uom": "EA",
            "pack_size": "1.0",
            "updated_at": "03:10 23-Jul-2025",
            "created_at": "08:02 25-Mar-2020",
            "prices": [
                {
                    "debtor": "ALD002",
                    "breaks": [
                        {
                            "price_rule": "06",
                            "currency_code": "",
                            "inc_tax": "44.2497",
                            "ex_tax": "40.227",
                            "min_qty": 1,
                            "max_qty": null
                        }
                    ],
                    "base_price": {
                        "currency_code": "",
                        "inc_tax": "44.2497",
                        "ex_tax": "40.227"
                    }
                }
            ],
            "images": [
                {
                    "filename": "312-1219.jpg",
                    "content_type": "image/jpeg",
                    "updated_at": "21:39 15-Mar-2021",
                    "url": "/ts1615804769/attachments/Product/15481/312-1219.jpg"
                }
            ],
            "notes": [],
            "alternative_products": [],
            "companion_products": [],
            "inventory_quantities": [
                {
                    "warehouse": "1",
                    "quantity": "-3.0"
                }
            ],
            "uoms": [
                {
                    "code": "CTN",
                    "conv": "1.0",
                    "gtin": "",
                    "weight": "0.0",
                    "height": "0.0",
                    "width": "0.0",
                    "depth": "0.0"
                },
                {
                    "code": "EA",
                    "conv": "1.0",
                    "gtin": "",
                    "weight": "0.0",
                    "height": "0.0",
                    "width": "0.0",
                    "depth": "0.0"
                },
                {
                    "code": "PLT",
                    "conv": "999999.0",
                    "gtin": "",
                    "weight": "0.0",
                    "height": "0.0",
                    "width": "0.0",
                    "depth": "0.0"
                }
            ],
            "categories": [
                {
                    "slug": "earmuffs",
                    "url": "/earmuffs",
                    "search_url": "/_accessories/earmuffs"
                },
                {
                    "slug": "100_0",
                    "url": "/100_0",
                    "search_url": "/_price_range_search/100_0"
                },
                {
                    "slug": "3M",
                    "url": "/earmuffs/3M",
                    "search_url": "/_accessories/earmuffs/3M"
                },
                {
                    "slug": "3M",
                    "url": "/3M/3M",
                    "search_url": "/_pronto/3M/3M"
                },
                {
                    "slug": "3M",
                    "url": "/3M/3M",
                    "search_url": "/3M/3M"
                },
                {
                    "slug": "sm",
                    "url": "/sm",
                    "search_url": "/_defence/sm"
                },
                {
                    "slug": "3M",
                    "url": "/3M",
                    "search_url": "/_pronto_brand/3M"
                }
            ]
        }
    ],
    "count": 1,
    "pages": 1
}


Then in:
            "images": [
                {
                    "filename": "312-1219.jpg",
                    "content_type": "image/jpeg",
                    "updated_at": "21:39 15-Mar-2021",
                    "url": "/ts1615804769/attachments/Product/15481/312-1219.jpg"
                }
            ],

To download a product image, use the full URL provided in the "url" field of the "images" object. For example, if the image object contains:
"url": "/ts1615804769/attachments/Product/15481/312-1219.jpg"

The complete image URL to download will be:
https://sales.tasco.net.au/ts1615804769/attachments/Product/15481/312-1219.jpg

Use this URL to fetch and save the image file.
