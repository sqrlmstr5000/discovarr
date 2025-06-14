import requests
import json
from datetime import datetime, timezone
import csv
import argparse
import sys
import time # Import the time module

# Global variable for the endpoint, to be formatted with base_url
WATCH_HISTORY_ENDPOINT_PATH = "/api/watch-history/import"

def add_watch_history_item(data: dict, base_url: str):
    """
    Sends a POST request to add a new watch history item.
    """
    try:
        print(f"Sending POST request to: {base_url}{WATCH_HISTORY_ENDPOINT_PATH}")
        # Ensure last_played_date is in ISO format if present
        if data.get("last_played_date") and isinstance(data["last_played_date"], datetime):
            data["last_played_date"] = data["last_played_date"].isoformat()
        
        print(f"Payload: {json.dumps(data, indent=2)}")

        response = requests.post(f"{base_url}{WATCH_HISTORY_ENDPOINT_PATH}", json=data)

        print(f"\nResponse Status Code: {response.status_code}")

        # Try to parse JSON response, otherwise print text
        try:
            response_json = response.json()
            print("Response JSON:")
            print(json.dumps(response_json, indent=2))
        except json.JSONDecodeError:
            print("Response Text (not JSON):")
            print(response.text)

        if response.ok: # Checks for 2xx status codes
            print("\nWatch history item added/updated successfully!")
        else:
            print(f"\nFailed to add/update watch history item. Server responded with error.")

    except requests.exceptions.ConnectionError as e:
        print(f"\nConnection Error: Could not connect to the server at {base_url}.")
        print(f"Please ensure the Discovarr server is running and accessible.")
        print(f"Details: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

def process_csv(csv_filepath: str, base_url: str):
    """
    Reads a CSV file and sends a POST request for each row.
    Required columns: title, watched_by, media_type
    Optional columns: media_id, last_played_date (ISO format), source, poster_url_source
    """
    try:
        with open(csv_filepath, mode='r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            if not all(col in reader.fieldnames for col in ['title', 'watched_by', 'media_type']):
                print("Error: CSV file must contain 'title', 'watched_by', and 'media_type' columns.")
                sys.exit(1)

            for i, row in enumerate(reader):
                print(f"\n--- Processing row {i+1} ---")
                item_data = {
                    "title": row.get('title'),
                    "watched_by": row.get('watched_by'),
                    "media_type": row.get('media_type', '').lower(), # Ensure lowercase for 'tv'/'movie'
                    # Optional fields from CSV
                    "media_id": row.get('media_id') if row.get('media_id') else None,
                    # If last_played_date is not in CSV, server will default to now()
                    "last_played_date": row.get('last_played_date') if row.get('last_played_date') else None,
                    "source": row.get('source', 'csv_import'), # Default source if not in CSV
                    "poster_url_source": row.get('poster_url_source') if row.get('poster_url_source') else None
                }

                # Basic validation for required fields from CSV
                if not item_data["title"] or not item_data["watched_by"] or not item_data["media_type"]:
                    print(f"Skipping row {i+1} due to missing required fields (title, watched_by, media_type): {row}")
                    continue
                
                if item_data["media_type"] not in ["movie", "tv"]:
                    print(f"Skipping row {i+1} due to invalid media_type '{item_data['media_type']}'. Must be 'movie' or 'tv'.")
                    continue

                add_watch_history_item(item_data, base_url)
                print("Waiting for 2 seconds before next request...")
                time.sleep(2) # Add a 2-second delay to avoid hitting the rate limit on the TMDB API

    except FileNotFoundError:
        print(f"Error: CSV file not found at {csv_filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred while processing the CSV file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import watch history from a CSV file.")
    parser.add_argument("csv_file", help="Path to the CSV file to import.")
    parser.add_argument("--base_url", default="http://localhost:8000", help="Base URL of the Discovarr API (e.g., http://localhost:8000)")
    args = parser.parse_args()

    process_csv(args.csv_file, args.base_url)

    # To run this script:
    # python import_watch_history.py /path/to/your/watch_history.csv 
    # python import_watch_history.py /path/to/your/watch_history.csv --base_url http://your_discovarr_host:port
    #
    # Example CSV with all supported fields:
    # title,media_id,media_type,watched_by,last_played_date,source,poster_url_source
    # "The Matrix",tt0133093,movie,user1,2023-01-15T10:00:00Z,my_csv_import,https://image.tmdb.org/t/p/w500/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg
    # "Breaking Bad",,tv,user2,,, # media_id, last_played_date, poster_url_source are optional
    # "Another Movie",,movie,user1,2023-02-20T12:30:00+02:00,,

    # Example CSV with minimal required fields:
    #title,watched_by,media_type
    #"The Grand Budapest Hotel",test,movie
    #"Pulp Fiction",test,movie
    #"Interstellar",test,movie
