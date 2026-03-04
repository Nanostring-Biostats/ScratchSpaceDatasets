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

tsv_filename = os.path.join(output_dir, 'spatial_publications.tsv')
manifest_filename = os.path.join(output_dir, 'manifest.csv')

current_year = datetime.now(timezone.utc).year

# 3. Search configuration
# Dictionary maps the specific platform flag to the exact query sent to OpenAlex
platforms = {
    'CellScape': 'Cellscape',
    'CosMx': 'CosMx',
    'GeoMx': 'GeoMx',
    'AtoMx': 'AtoMx',
    'nCounter': '(nCounter OR nanostring)' # historically, some papers referred to nCounter simply as "NanoString"
}

year_filter = f"publication_year:2008-{current_year}"
base_url = "https://api.openalex.org/works"

# Dictionary to store unique publications. Key = OpenAlex ID
main_records = {}

for platform_key, search_query in platforms.items():
    print(f"Fetching data for: {platform_key}...")
    
    # 'default.search' tells OpenAlex to search the title, abstract, AND full text
    params = {
        "filter": f"default.search:{search_query},{year_filter}",
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
                
                # Initialize the record if it's the first time seeing this paper
                if work_id not in main_records:
                    main_records[work_id] = {
                        'data': work,
                        'Has_CellScape':  False,
                        'Has_CosMx': False,
                        'Has_GeoMx': False,
                        'Has_AtoMx': False,
                        'Has_nCounter': False
                    }
                
                # Flip the flag using the dictionary key
                main_records[work_id][f'Has_{platform_key}'] = True
                
            cursor = data.get('meta', {}).get('next_cursor')
        else:
            print(f"Error fetching {platform_key}: API returned {response.status_code}")
            print("Response details:", response.text)
            break

print(f"Found {len(main_records)} unique valid publications.")

# 4. Write the TSV data file
print("Writing TSV file...")
with open(tsv_filename, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t')
    
    headers = [
        'Title', 'Publication Date', 'Authors', 'Institutions', 'Journal', 
        'DOI', 'Cited By', 'Type', 'Open Access', 
        'Primary Topic', 'Subfield', 'Field', 'Domain', 'All Topics', 'Has_CellScape',
        'Has_CosMx', 'Has_GeoMx', 'Has_AtoMx', 'Has_nCounter'
    ]
    writer.writerow(headers)
    
    for work_id, record in main_records.items():
        work = record['data']
        
        # Text cleaning helper to prevent TSV formatting errors
        def clean_text(text):
            return str(text).replace('\n', ' ').replace('\t', ' ') if text else 'Unknown'
        
        # Title & Basic Metadata
        clean_title = clean_text(work.get('title'))
        pub_date = work.get('publication_date') or 'Unknown Date'
        doi = work.get('doi') or ''
        cited_by = work.get('cited_by_count', 0)
        pub_type = work.get('type') or 'Unknown'
        is_oa = (work.get('open_access') or {}).get('is_oa', False)
        
        # Authors & Institutions
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
        
        # Journal
        primary_location = work.get('primary_location') or {}
        source = primary_location.get('source') or {}
        clean_journal = clean_text(source.get('display_name'))
        
        # Topics & Hierarchy
        primary_topic_data = work.get('primary_topic') or {}
        primary_topic = primary_topic_data.get('display_name', 'Unknown')
        subfield = (primary_topic_data.get('subfield') or {}).get('display_name', 'Unknown')
        field = (primary_topic_data.get('field') or {}).get('display_name', 'Unknown')
        domain = (primary_topic_data.get('domain') or {}).get('display_name', 'Unknown')
        
        topics_list = work.get('topics', [])
        topic_names = [t.get('display_name') for t in topics_list if t.get('display_name')]
        all_topics = "; ".join(topic_names) if topic_names else "Unknown"
        
        writer.writerow([
            clean_title, pub_date, authors_str, institutions_str, clean_journal, 
            doi, cited_by, pub_type, is_oa, 
            primary_topic, subfield, field, domain, all_topics, record['Has_CellScape'],
            record['Has_CosMx'], record['Has_GeoMx'], record['Has_AtoMx'], record['Has_nCounter']
        ])

# 5. Write the Manifest file
print("Writing Manifest file...")
with open(manifest_filename, mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Tracker', 'Last_Updated_UTC', 'Total_Publications'])
    writer.writerow(['Spatial Biology', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), len(main_records)])

print("Update complete!")