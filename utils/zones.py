import requests
import os
from dotenv import load_dotenv
load_dotenv('../sensitive.env')
from config import countiesToMonitor as counties
    
'''
Yes, I use a lot of print statements.
Yes, they have a purpose.
Delete them in your code if they want, they stay on the repo.
'''
    
class Zones():
    
    def __init__(self):
        self.ZONE_MAP = {} # ZoneIDs we need to look for.
        self.ZONE_TO_COUNTY_DESIGNATIONS = {} # Maps ZoneID to county name for easier reference.
        self.StateAppendixs = {} # Useful for comparing different possible counties and zones. Better if ref diff states.
        self.ZONE_GEOMETRY = {}
        self.requestHeader = {'User-Agent': os.environ.get('HEADER')} # Creating header for requests to NWS API.
        print("Initializing...")
        self.determine_state_appendix() # Determine state appendixs for counties we monitor.
        self.load_zones_and_filter() # Load zones and filter them for later use.
        self.compile_zone_geometry()
        
    def determine_state_appendix(self):
        for c in counties: 
            parts = c.lower().strip().split(",")
            state_appendix = parts[1].strip()
            if state_appendix not in self.StateAppendixs:
                self.StateAppendixs[state_appendix] = state_appendix
            else: 
                print("Appendix already included.")
        
        
    def load_zones_and_filter(self): # Load zones from NWS API and compile them. Then filter to figure out which ones we need.
        self.discretionaryZoneMap = {} # Discretionary zones are zones we will filter. We will place ones we care about in ZONE_MAP.
        self.countyNormalized = {}
        
        '''
        The following code fetches zone data from the NWS API. 
        It will find forecast and county zones. Using zones is the MOST reliable method for determining if an alert does or does not affect a county.
        Yes, we need both. Flood alerts and storm-based alerts use different zone types. Flood alerts may use county, storm-based alerts often use forecast zones.
        Hurricane alerts may also use county zones, not forecast.
        Referencing the "state" and "name" properties of the zones, we will set them up similar to how we have them defined in countiesToMonitor.
        This code will flag a county so long as the base name matches, even if it's labeled like "Northern Lake" or "Southern Lake", or as "Mainland Northern Brevard" etc.
        This is the most reliable method for finding these alerts. Though "areaDesc" exists, it is not always reliable, and it not always correct. Could also bring false alerts into our map if the API
        is ever expanded to include different states. Zones are specific to each geographical area. 
        
        Should either request fail, the bot must stop running, as alerts cannot be filtered without this data. 
        Instead of comparing alert "areaDesc" properties, we will filter by zone IDs. 
        Zone IDs also carry with them a link. Filtering out ones we care about, we can gather geodata for the alert and plot the entire county for alert imagery.
        Effectively; "areaDesc" is stupid and is unreliable. Zones are precise and don't screw up. 
        DON'T USE AREADESC. I will drill this into your head.
        '''
        
        url = "https://api.weather.gov/zones?type=forecast&area=FL" # FLZ area, for most storm-based alerts.
        resp = requests.get(url, headers=self.requestHeader)

        try:
            r = resp.json()
        except Exception as e:
            raise RuntimeError(f"Failed to parse JSON from NWS: {e}")

        if "features" not in r:
            raise RuntimeError(f"NWS API error: {r}")
        
        for feature in r["features"]: # Collecting areas.
            zoneId = feature["id"]
            name = feature["properties"]["name"]
            state = feature["properties"]["state"] 
            self.discretionaryZoneMap[zoneId] = f"{name}, {state}"
        
        url = "https://api.weather.gov/zones?type=county&area=FL" # FLC type. Used for flood alerts.
        resp = requests.get(url, headers=self.requestHeader)
        
        try:
            r = resp.json()
        except Exception as e:
            raise RuntimeError(f"Failed to parse County Area JSON from NWS: {e}")
        
        if "features" not in r:
            raise RuntimeError(f"NWS API error: {r}")
        
        for feature in r["features"]: # Collecting areas.
            zoneId = feature["id"]
            name = feature["properties"]["name"]
            state = feature["properties"]["state"] 
            self.discretionaryZoneMap[zoneId] = f"{name}, {state}"
            
        for c in counties: # Normalize county names for easier comparison and to avoid missing a zone with the correct county name.
            parts = c.lower().replace(",", "").strip().split()
            county_name = parts[0].lower().strip()
            county_state = parts[1].lower().strip() 
            self.countyNormalized[county_name] = f"{county_name}, {county_state}"
            
        for zone in self.discretionaryZoneMap: # Begin filtering out which zones we care about.
            parts = self.discretionaryZoneMap[zone].lower().replace(",", " ").strip().split() # Split by spaces and commas to handle different variations of County Names. Ie., Mainland Northern Brevard.
            
            formattedZoneName = None # Reset for each zone.
            
            for part in parts:
                part = str.lower(part)
                if part in self.countyNormalized: # If part of the zone name matches a county, use that and format the initial county.
                    formattedZoneName = f"{part}" # Found a match. Begin format.
                if part in self.StateAppendixs: # Find state appendix.
                    formattedZoneName = f"{formattedZoneName}, {part}" # Return string formatted for our list.
                    
            if formattedZoneName and formattedZoneName in self.countyNormalized.values(): # Compare.
                print(f"✅ Match found: {self.discretionaryZoneMap[zone]} matches monitored county {formattedZoneName}")
                print(f"This matches with {zone}, which corresponds to {self.discretionaryZoneMap[zone]}")
                print(f"Therefore, adding {zone} to ZONE_MAP.")
                self.ZONE_MAP[zone] = zone
                parts = formattedZoneName.split(",")
                self.ZONE_TO_COUNTY_DESIGNATIONS[zone] = parts[0]
                print(f"ZONE_TO_COUNTY_DESIGNATIONS updated: {zone} → {parts[0]}")
                    
        print(f"ZONE_MAP compiled. Contains {len(self.ZONE_MAP)} entries after filtering.") 
        print(f"Contains following zones: {self.ZONE_MAP}")
        print(f"ZONE_TO_COUNTY_DESIGNATIONS: {self.ZONE_TO_COUNTY_DESIGNATIONS}")
    
    def compile_zone_geometry(self): # We compile Zone geometry via calling each individual zone through the NOAA api.
        # Notably, this process takes a few seconds for the code to handle. Minor delay.
        for z in self.ZONE_MAP:
            url = self.ZONE_MAP[z] # Fetch url based on zone id. Zone id is url API call.
            
            resp = requests.get(url, headers=self.requestHeader)
            
            try:
                r = resp.json()
            except Exception as e:
                print(f"Failed to load data from {z}") # Don't need to raise a major error here, just note this zone id did not return data.
                print(e)
            
            if r["geometry"]: # Filter.
                geo = r["geometry"]
                type = geo.get("type", "")
                coords = geo.get("coordinates", [])
                
                if coords and type: # We have coords?
                    if type == "Polygon":
                        self.ZONE_GEOMETRY[z] = [coords] # Coords go into our ZONE_GEOMETRY dictionary.
                    elif type == "MultiPolygon":
                        self.ZONE_GEOMETRY[z] = coords
                else:
                    print(f"{z} failed to get zone geometry.") 
        
        print(f"Completed compiling of zone geometry. {len(self.ZONE_GEOMETRY)} members.")
            
    def check_areas_impacted(self, zones: list) -> tuple[bool, list]: # Alerts contain zone information. Parsing the list of zones from that alert into here can return the areas which are affected. Returns zones in ZONE_MAP.
        impacted = [z for z in zones if z in self.ZONE_MAP]
                    
        if len(impacted) > 0: # If impacted is not 0, return.
            return True, impacted
        return False, None # Return false and none otherwise. We have no zones to provide. Also can use for determining if an alert is in a specified area.
    
    def name_from_zone(self, zone_id: str) -> str: # Retrieve a county name from a ZoneID.
        if zone_id in self.ZONE_TO_COUNTY_DESIGNATIONS: # If Zone_Id exists...
            return self.ZONE_TO_COUNTY_DESIGNATIONS[zone_id] # ...return the county name.
        return None # Or return none if no zone is found in this list.
    
    def get_zone_geo(self, zone_id: str) -> list:
        if zone_id in self.ZONE_GEOMETRY:
            return self.ZONE_GEOMETRY[zone_id]
        return None