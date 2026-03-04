import requests
import csv
import os
import sys
import argparse
from datetime import datetime, timezone

# 1. Setup Command Line Arguments
parser = argparse.ArgumentParser(description="Fetch spatial biology publications from OpenAlex.")
parser.add_argument("--out-dir", default="publication_tracker", help="Directory where TSV/CSV files are stored")
args = parser.parse_args()

# Pull the secret email from GitHub Actions environment
EMAIL = os.environ.get('OPENALEXEMAIL')

if not EMAIL:
    print("Error: OPENALEXEMAIL environment variable not set.")
    sys.exit(1)

# 2. Setup directories and filenames using the argument
output_dir = args.out_dir
os.makedirs(output_dir, exist_ok=True)

tsv_filename = os.path.join(output_dir, 'spatial_publications.tsv')
manifest_filename = os.path.join(output_dir, 'manifest.csv')
filter_filename = os.path.join(output_dir, 'filter.tsv')
added_filename = os.path.join(output_dir, 'added.tsv')

current_year = datetime.now(timezone.utc).year

# 3. Load the Blacklist
blacklist_ids = set()
if os.path.exists(filter_filename):
    with open(filter_filename, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            raw_id = row.get('OpenAlex_ID', '').strip()
            if raw_id:
                # Normalize just in case it's a full URL
                clean_id = raw_id.split('/')[-1]
                blacklist_ids.add(clean_id)
print(f"Loaded {len(blacklist_ids)} IDs to blacklist.")

# 4. Search configuration
# Using exact string matches (with double quotes) to prevent tokenization errors
platforms = {
    'CellScape': '("CellScape")', 
    'CosMx': '"CosMx"',
    'GeoMx': '"GeoMx"',
    'AtoMx': '"AtoMx"',
    'nCounter': '("nCounter" OR "nanostring")'
}

year_filter = f"publication_year:2008-{current_year}"
base_url = "[https://api.openalex.org/works](https://api.openalex.org/works)"

# Dictionary to store unique publications. Key = OpenAlex ID
main_records = {}

# 5. Automated Search Loop
for platform_key, search_query in platforms.items():
    print(f"Fetching automated data for: {platform_key}...")
    
    params = {
        "filter": f"default.search:{search_query},{year_filter}",
        "mailto": EMAIL,
        "per-page": 200,
    }
    
    cursor = "*" 
    page_count = 0
    
    while cursor:
        params['cursor'] = cursor
        response = requests.get(base_url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            
            if not results:
                break
                
            page_count += 1
            if page_count % 10 == 0:
                print(f"  ... fetched ~{page_count * 200} records for {platform_key} ...")
                
            for work in results:
                work_id_full = work.get('id', '')
                work_id = work_id_full.split('/')[-1]
                
                # Apply Blacklist Filter
                if work_id in blacklist_ids:
                    continue
                
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
                
                if work_id not in main_records:
                    main_records[work_id] = {
                        'data': work,
                        'Has_CellScape': False,
                        'Has_CosMx': False,
                        'Has_GeoMx': False,
                        'Has_AtoMx': False,
                        'Has_nCounter': False
                    }
                
                main_records[work_id][f'Has_{platform_key}'] = True
                
            cursor = data.get('meta', {}).get('next_cursor')
        else:
            print(f"Error fetching {platform_key}: API returned {response.status_code}")
            break

# 6. Process the Whitelist (Added.tsv)
if os.path.exists(added_filename):
    print("Processing manual additions from whitelist...")
    with open(added_filename, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            raw_id = row.get('OpenAlex_ID', '').strip()
            if not raw_id:
                continue
            
            work_id = raw_id.split('/')[-1]
            
            # If we don't already have this paper, download its metadata from OpenAlex
            if work_id not in main_records:
                single_url = f"[https://api.openalex.org/works/](https://api.openalex.org/works/){work_id}?mailto={EMAIL}"
                response = requests.get(single_url)
                if response.status_code == 200:
                    work_data = response.json()
                    main_records[work_id] = {
                        'data': work_data,
                        'Has_CellScape': False,
                        'Has_CosMx': False,
                        'Has_GeoMx': False,
                        'Has_AtoMx': False,
                        'Has_nCounter': False
                    }
                else:
                    print(f"  Warning: Could not fetch metadata for whitelisted ID {work_id}")
                    continue
            
            # Force the flags based on what is in the added.tsv
            for p in ['CellScape', 'CosMx', 'GeoMx', 'AtoMx', 'nCounter']:
                flag_val = str(row.get(f'Has_{p}', '')).strip().lower()
                if flag_val in ['true', '1', 'yes']:
                    main_records[work_id][f'Has_{p}'] = True

print(f"Found {len(main_records)} unique valid publications after filtering and adding.")

# 7. Write the TSV data file
print("Writing TSV file...")
with open(tsv_filename, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t')
    
    headers = [
        'OpenAlex_ID', 'Title', 'Publication Date', 'Authors', 'Institutions', 'Journal', 
        'DOI', 'Cited By', 'Type', 'Open Access', 
        'Primary Topic', 'Subfield', 'Field', 'Domain', 'All Topics',
        'Has_CellScape', 'Has_CosMx', 'Has_GeoMx', 'Has_AtoMx', 'Has_nCounter'
    ]
    writer.writerow(headers)
    
    for work_id, record in main_records.items():
        work = record['data']
        
        def clean_text(text):
            return str(text).replace('\n', ' ').replace('\t', ' ') if text else 'Unknown'
        
        clean_title = clean_text(work.get('title'))
        pub_date = work.get('publication_date') or 'Unknown Date'
        doi = work.get('doi') or ''
        cited_by = work.get('cited_by_count', 0)
        pub_type = work.get('type') or 'Unknown'
        is_oa = (work.get('open_access') or {}).get('is_oa', False)
        
        authorships = work.get('authorships', [])
        author_names = [a.get('author', {}).get('display_name', '') for a in authorships]
        authors_str = ", ".join(filter(None, author_names))
        
        institutions = set()
        for a in authorships:
            for inst in a.get('institutions', []):
                inst_name = inst.get('display_name')
                if inst_name:
                    institutions.add(clean_text(inst_name))
        institutions_str = ", ".join(institutions)
        
        primary_location = work.get('primary_location') or {}
        source = primary_location.get('source') or {}
        clean_journal = clean_text(source.get('display_name'))
        
        primary_topic_data = work.get('primary_topic') or {}
        primary_topic = primary_topic_data.get('display_name', 'Unknown')
        subfield = (primary_topic_data.get('subfield') or {}).get('display_name', 'Unknown')
        field = (primary_topic_data.get('field') or {}).get('display_name', 'Unknown')
        domain = (primary_topic_data.get('domain') or {}).get('display_name', 'Unknown')
        
        topics_list = work.get('topics', [])
        topic_names = [t.get('display_name') for t in topics_list if t.get('display_name')]
        all_topics = "; ".join(topic_names) if topic_names else "Unknown"
        
        writer.writerow([
            work_id, clean_title, pub_date, authors_str, institutions_str, clean_journal, 
            doi, cited_by, pub_type, is_oa, 
            primary_topic, subfield, field, domain, all_topics,
            record['Has_CellScape'], record['Has_CosMx'], record['Has_GeoMx'], record['Has_AtoMx'], record['Has_nCounter']
        ])

# 8. Write the Manifest file
print("Writing Manifest file...")
with open(manifest_filename, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Tracker', 'Last_Updated_UTC', 'Total_Publications'])
    writer.writerow(['Spatial Biology', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), len(main_records)])

print("Update complete!")