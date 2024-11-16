import json
import os
from typing import List, Dict

def read_storage_data() -> List[Dict]:
    """
    Read all JSON files from storage directory
    
    Args:
        storage_dir: Path to storage directory
        
    Returns:
        List of dictionaries containing crawled data
    """
    data = []
    
    # Get absolute path
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_path, 'storage', 'datasets', 'default')
    
    # Create directory if it doesn't exist
    os.makedirs(full_path, exist_ok=True)
    
    print(f"Reading files from: {full_path}")
    
    # Read all JSON files
    for filename in os.listdir(full_path):
        if filename.endswith('.json'):
            file_path = os.path.join(full_path, filename)
            print(f"\nReading file: {filename}")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                    print(f"Content: {json_data}")
                    data.append(json_data)
            except Exception as e:
                print(f"Error reading {filename}: {str(e)}")
                
    return data