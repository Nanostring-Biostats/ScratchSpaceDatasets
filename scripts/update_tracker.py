import requests
import csv
import os
import sys
from datetime import datetime, timezone

# 1. Pull the secret email from GitHub Actions environment
EMAIL = os.environ.get('OPENALEXEMAIL')

if not EMAIL:
    print("Error: OPENALEXEMAIL environment variable not set.")
    sys.exit(1)

# 2. Setup directories and filenames
output_dir = "publication_tracker"
os.makedirs(output_dir, exist_ok=True) # Creates the folder if it doesn't exist

tsv_filename = os.path.join(output_dir, 'cosmx_smi_publications.tsv')
manifest_filename = os.path.join(output_dir, 'manifest.csv')

# 3. Fetch Data
base_url = f"https://api.openalex.org/works?filter=title_and_abstract.search:CosMx&mailto={EMAIL}&per-page=200"
all_results = []
cursor = "*" 

print("Fetching data from OpenAlex...")
while cursor:
    url = f"{base_url}&cursor={cursor}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        current_page_results = data.get('results', [])
        
        if not current_page_results:
            break
            
        all_results.extend(current_page_results)
        cursor = data.get('meta', {}).get('next_cursor')
    else:
        print(f"Error: API returned status code {response.status_code}")
        break

print(f"Found {len(all_results)} publications.")

# 4. Write the TSV data file
with open(tsv_filename, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t')
    writer.writerow(['Title', 'Publication Date', 'Authors', 'Journal', 'DOI', 'Cited By'])
    
    for work in all_results:
        raw_title = work.get('title') or 'Unknown Title'
        clean_title = str(raw_title).replace('\n', ' ').replace('\t', ' ')
        pub_date = work.get('publication_date') or 'Unknown Date'
        doi = work.get('doi') or ''
        
        authorships = work.get('authorships', [])
        author_names = [a.get('author', {}).get('display_name', '') for a in authorships]
        authors_str = ", ".join(filter(None, author_names))
        
        primary_location = work.get('primary_location') or {}
        source = primary_location.get('source') or {}
        raw_journal = source.get('display_name') or 'Unknown Journal'
        clean_journal = str(raw_journal).replace('\n', ' ').replace('\t', ' ')
        
        cited_by = work.get('cited_by_count', 0)
        
        writer.writerow([clean_title, pub_date, authors_str, clean_journal, doi, cited_by])

# 5. Write the Manifest file
# We use UTC time so it is standardized for your dashboard
with open(manifest_filename, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Tracker', 'Last_Updated_UTC', 'Total_Publications'])
    writer.writerow(['CosMx', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), len(all_results)])

print("Update complete!")