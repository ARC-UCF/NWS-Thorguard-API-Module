import os 
import json
from dotenv import load_dotenv
load_dotenv("sensitive.env")

from discord import SyncWebhook

class Webhooks():
    
    def __init__(self):
        self.SYNCED_WEBHOOKS = {}
        print("initalizing WEBHOOKS")
        self.sync_webhooks()
        
    def sync_webhooks(self): # Probably a better way to handle this, but we'll work about that later.
        URLS = os.environ.get("WEBHOOKS")
        
        print(URLS)
        
        if not URLS:
            raise RuntimeError("Webhooks failed to load.") # Failure to load webhooks is critical. This is the service we provide, not having it means we're broken.
        
        parsed = {}
        lines = URLS.strip().split(",")
        
        for line in lines:
            line.strip()
            parts = line.strip().split("=")
            if parts[0] and parts[1]:
                parsed[parts[0].strip()] = parts[1].strip()
                
        if parsed:
            for key, url in parsed.items():
                key = key.replace('"', '')
                
                self.SYNCED_WEBHOOKS[key] = SyncWebhook.from_url(url)
                print(f"SYNCED {self.SYNCED_WEBHOOKS[key]}")
                
    def get_webhook_from_county(self, county: str):
        if county in self.SYNCED_WEBHOOKS:
            return self.SYNCED_WEBHOOKS[county]
        
webhooks = Webhooks()