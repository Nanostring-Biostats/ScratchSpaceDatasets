import requests
import csv
import os
import sys
from datetime import datetime, timezone

# 1. Pull the secret email
EMAIL = os.environ.get('OPENALEXEMAIL')
if not EMAIL:
    print("Error: OPENALEXEMAIL environment variable not set.")
    sys.exit(1)

# 2. Setup directories and filenames
output_dir = "publication_tracker"
os.makedirs(output_dir, exist_ok=True)
tsv_filename = os.path.join(output_dir, 'spatial_publications.tsv')
manifest_filename = os.path.join(output_dir, 'manifest.csv')

current_year = datetime.now(timezone.utc).year
year_filter = f"publication_year:2008-{current_year}"
base_url = "https://api.openalex.org/works"

# 3. Fetch Data: Loop through platforms individually
platforms = ['CosMx', 'GeoMx', 'AtoMx', 'nCounter']

# Dictionary to store unique publications. Key = OpenAlex ID, Value = Dict of data & flags
master_records = {}

for platform in platforms:
    print(f"Fetching data for: {platform}...")
    
    params = {
        "filter": f"default.search:{platform},{year_filter}",
        "mailto": EMAIL,
        "per-page": 200,
    }
    
    cursor = "*" 
    while cursor:
        params['cursor'] = cursor
        response = requests.get(base_url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            if not results:
                break
                
            for work in results:
                work_id = work.get('id')
                
                # Basic date validation to skip malformed entries
                pub_date = work.get('publication_date')
                if not pub_date:
                    continue
                try:
                    pub_year = int(pub_date[:4])
                    if not (2008 <= pub_year <= current_year):
                        continue
                except (ValueError, TypeError):
                    continue
                
                # If we haven't seen this paper yet, add it to our master dictionary
                if work_id not in master_records:
                    master_records[work_id] = {
                        'data': work,
                        'Has_CosMx': False,
                        'Has_GeoMx': False,
                        'Has_AtoMx': False,
                        'Has_nCounter': False
                    }
                
                # Flip the flag for whichever platform loop we are currently in
                flag_key = f"Has_{platform}"
                master_records[work_id][flag_key] = True
                
            cursor = data.get('meta', {}).get('next_cursor')
        else:
            print(f"Error fetching {platform}: API returned {response.status_code}")
            break

print(f"Found {len(master_records)} unique valid publications.")

# 4. Write the TSV data file
with open(tsv_filename, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t')
    
    headers = [
        'Title', 'Publication Date', 'Authors', 'Institutions', 'Journal', 
        'DOI', 'Cited By', 'Type', 'Open Access', 'Primary Topic', 
        'Has_CosMx', 'Has_GeoMx', 'Has_AtoMx', 'Has_nCounter'
    ]
    writer.writerow(headers)
    
    for work_id, record in master_records.items():
        work = record['data']
        
        # Title
        raw_title = work.get('title') or 'Unknown Title'
        clean_title = str(raw_title).replace('\n', ' ').replace('\t', ' ')
        pub_date = work.get('publication_date') or 'Unknown Date'
        doi = work.get('doi') or ''
        
        authorships = work.get('authorships', [])
        
        # Authors
        author_names = [a.get('author', {}).get('display_name', '') for a in authorships]
        authors_str = ", ".join(filter(None, author_names))
        
        # Institutions
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
        
        # Citation Count, Type, OA, Topic
        cited_by = work.get('cited_by_count', 0)
        pub_type = work.get('type') or 'Unknown'
        open_access_data = work.get('open_access') or {}
        is_oa = open_access_data.get('is_oa', False)
        primary_topic_data = work.get('primary_topic') or {}
        primary_topic = primary_topic_data.get('display_name', 'Unknown')
        
        writer.writerow([
            clean_title, pub_date, authors_str, institutions_str, clean_journal, 
            doi, cited_by, pub_type, is_oa, primary_topic, 
            record['Has_CosMx'], record['Has_GeoMx'], record['Has_AtoMx'], record['Has_nCounter']
        ])

# 5. Write the Manifest file
with open(manifest_filename, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Tracker', 'Last_Updated_UTC', 'Total_Publications'])
    writer.writerow(['Spatial Biology', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), len(master_records)])

print("Update complete!")