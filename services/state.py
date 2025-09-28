import json
import warnings

fileLocation = "json_data.json"

class State():
    def __init__(self):
        self.data = {
            "forecast": {},
            "hurricane": {},
            "alerts": {},
            "timing": {},
            "trackId": {},
            "stats": {},
        }
        self.open_data()
        
    def open_data(self):
        try:
            with open(fileLocation) as f:
                data = json.load(f)
                print("File found and read.")
                print("Loaded data: ", data)
                if data:
                    self.data = data
        except (FileNotFoundError, Exception):
            warnings.warn("JSON FILE DOES NOT EXIST OR ISSUE OCCURRED WHILE READING")
            
    def write_data(self, forecast: dict | None, hurricane: dict | None, alerts: dict | None, timing: str | None, trackId: str | None, stats: dict | None):
        tempData = {
            "forecast": forecast,
            "hurricane": hurricane,
            "alerts": alerts,
            "timing": timing,
            "trackId": trackId,
            "stats": stats,
        }
        
        for d, v in tempData.items():
            if v is not None:
                self.data[d] = v
                
        try:
            with open(fileLocation, "w") as f:
                json.dump(self.data, f)
        except Exception as E:
            warnings.warn(f"ISSUE WHEN WRITING TO FILE: {E}")
                
    def send_to_disseminate(self):
        return self.data