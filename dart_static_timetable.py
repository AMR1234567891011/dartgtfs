import os
import requests
import zipfile
import shutil
from datetime import datetime

class GTFSUpdater:
    def __init__(self, endpoint: str = None, directory: str = "gtfs_timetable"):
        self.directory = directory
        self.endpoint = endpoint
        self.zip_path = "./static/eph_tt.zip"
        
    def update_timetable(self) -> bool:
        try:
            response = requests.get(self.endpoint, stream=True)
            response.raise_for_status()
            
            with open(self.zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self._cleanup_old_files()
            
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                zip_ref.extractall(f"./static/{self.directory}")
            
            os.remove(self.zip_path)
            
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error getting tt: {e}")
            return False
        except Exception as e:
            print(f"Error using tt: {e}")
            return False
    
    def _cleanup_old_files(self):
        target_dir = f"./static/{self.directory}"
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)