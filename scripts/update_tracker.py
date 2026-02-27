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
os.makedirs(output_dir, exist_ok=True)

# Updated filename to reflect the broader scope
tsv_filename = os.path.join(output_dir, 'spatial_publications.tsv')
manifest_filename = os.path.join(output_dir, 'manifest.csv')

# Get the current year dynamically to prevent future-dated typos
current_year = datetime.now(timezone.utc).year

# 3. Fetch Data using OR logic (|) and apply year bounds directly in the OpenAlex API query
# Added nCounter to the search and restricted publication_year to 2008 - current_year
search_query = "CosMx|GeoMx|AtoMx|nCounter"
year_filter = f"publication_year:2008-{current_year}"
base_url = f"https://api.openalex.org/works?filter=title_and_abstract.search:{search_query},{year_filter}&mailto={EMAIL}&per-page=200"

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

# Python-side validation to double-check dates and remove any malformed entries
valid_results = []
for work in all_results:
    pub_date = work.get('publication_date')
    if not pub_date:
        continue
    try:
        pub_year = int(pub_date[:4])
        if 2008 <= pub_year <= current_year:
            valid_results.append(work)
    except (ValueError, TypeError):
        continue

print(f"Found {len(valid_results)} valid publications (filtered from {len(all_results)} raw hits).")

# 4. Write the TSV data file
with open(tsv_filename, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t')
    
    # Expanded headers to include Has_nCounter
    headers = [
        'Title', 'Publication Date', 'Authors', 'Institutions', 'Journal', 
        'DOI', 'Cited By', 'Type', 'Open Access', 'Primary Topic', 
        'Has_CosMx', 'Has_GeoMx', 'Has_AtoMx', 'Has_nCounter'
    ]
    writer.writerow(headers)
    
    for work in valid_results:
        # Title
        raw_title = work.get('title') or 'Unknown Title'
        clean_title = str(raw_title).replace('\n', ' ').replace('\t', ' ')
        pub_date = work.get('publication_date') or 'Unknown Date'
        doi = work.get('doi') or ''
        
        authorships = work.get('authorships', [])
        
        # Authors
        author_names = [a.get('author', {}).get('display_name', '') for a in authorships]
        authors_str = ", ".join(filter(None, author_names))
        
        # Institutions (Gathering unique institutions across all authors)
        institutions = set()
        for a in authorships:
            for inst in a.get('institutions', []):
                inst_name = inst.get('display_name')
                if inst_name:
                    institutions.add(inst_name.replace('\n', ' ').replace('\t', ' '))
        institutions_str = ", ".join(institutions)
        
        # Journal
        primary_location = work.get('primary_location') or {}
        source = primary_location.get('source') or {}
        raw_journal = source.get('display_name') or 'Unknown Journal'
        clean_journal = str(raw_journal).replace('\n', ' ').replace('\t', ' ')
        
        # Citation Count
        cited_by = work.get('cited_by_count', 0)
        
        # New Metadata: Type, Open Access, Primary Topic
        pub_type = work.get('type') or 'Unknown'
        open_access_data = work.get('open_access') or {}
        is_oa = open_access_data.get('is_oa', False)
        primary_topic_data = work.get('primary_topic') or {}
        primary_topic = primary_topic_data.get('display_name', 'Unknown')
        
        # Boolean Logic for Product Hits
        title_lower = clean_title.lower()
        abstract_keys = [k.lower() for k in (work.get('abstract_inverted_index') or {}).keys()]
        
        has_cosmx = 'cosmx' in title_lower or 'cosmx' in abstract_keys
        has_geomx = 'geomx' in title_lower or 'geomx' in abstract_keys
        has_atomx = 'atomx' in title_lower or 'atomx' in abstract_keys
        has_ncounter = 'ncounter' in title_lower or 'ncounter' in abstract_keys
        
        writer.writerow([
            clean_title, pub_date, authors_str, institutions_str, clean_journal, 
            doi, cited_by, pub_type, is_oa, primary_topic, 
            has_cosmx, has_geomx, has_atomx, has_ncounter
        ])

# 5. Write the Manifest file
with open(manifest_filename, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Tracker', 'Last_Updated_UTC', 'Total_Publications'])
    # Updated to count valid_results rather than all_results
    writer.writerow(['Spatial Biology', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), len(valid_results)])

print("Update complete!")