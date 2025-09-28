from utils import Zones, identifier
import requests
import os
from dotenv import load_dotenv
import datetime
from datetime import datetime, timezone, timedelta, time
import warnings
from config import polygon_colors_SAME
load_dotenv('../sensitive.env')

zones = Zones()

class Alerts():
    
    def __init__(self): # Initalize
        self.requestHeader = {"User-Agent": os.environ.get('HEADER')}
        self.initialized = True
        self.ActiveAlerts = {}
        print("Alerts SERIVCE initialized.")
        
    def cycle(self) -> dict: # Public function called for the function to cycle.
        print("Cycling")
        self._clean_up() # Clean up
        
        aList = self._retrieve_alerts_and_organize() # Fetch alerts
        
        if aList:
            for alert in aList: # Begin checking alerts.
                polyColor = '#6e6e6e'
                
                if alert["SAME_code"] == "NWS": alert["SAME_code"] = alert["NWS_code"]
                
                if alert["SAME_code"] in polygon_colors_SAME:
                    polyColor = polygon_colors_SAME[alert["SAME_code"]]
                    
                alert["polyColor"] = polyColor
                
                if alert["id"] not in self.ActiveAlerts: # If we don't have the alert, add it.
                    replacement, ref = self._check_for_replacement(alert)
                    
                    if replacement and ref in self.ActiveAlerts:
                        alert["trackId"] = self.ActiveAlerts[ref]["trackId"]
                        alert["polyColor"] = self.ActiveAlerts[ref]["polyColor"]
                        alert["Replacement"] = True
                    else:
                        alert["trackId"] = identifier.issue_identifier()
                        
                    self.ActiveAlerts[alert["id"]] = alert
                    
        print("Complete: returning activealerts")
        return self.ActiveAlerts
    
    def _check_for_replacement(self, alert: dict) -> tuple[bool, str]:
        print("checking replacements")
        references = alert.get("references", None)
        
        if not references: print(f"{alert["id"]} has no references."); return False, None
        
        for ref in references:
            refId = ref["@id"]
            
            if refId and refId in self.ActiveAlerts:
                compareAlert = self.ActiveAlerts[refId]
                
                replacedBy = compareAlert.get("replacedBy", "")
                
                if replacedBy is not None:
                    if replacedBy == alert["id"]:
                        print("Alert Id matches replacement id for another alert.")
                        return True, refId
            
            info = self._poll_internal_alerts(refId)
            
            if info and info["properties"]:
                props = info["properties"]
                
                replacedBy = props.get("replacedBy", "")
                replacedAt = props.get("replacedAt", "")
                
                if replacedBy:
                    if refId and refId in self.ActiveAlerts:
                        self.ActiveAlerts[refId]["replacedBy"] = replacedBy
                        self.ActiveAlerts[refId]["replacedAt"] = replacedAt
                    
                    if replacedBy == alert["id"] and replacedBy in self.ActiveAlerts:
                        print("Alert Id matches replacement id for another alert.")
                        return True, refId
        
        print("Referenced alerts are not recorded.")
        
        return False, None
                        
        
        
        
    def _clean_up(self): # Clean up our alerts; remove expired alerts or alerts which are expireless.
        print("Cleaning")
        now = datetime.now(timezone.utc)
        for aid, data in list(self.ActiveAlerts.items()):
            expires = data.get("expires")
            if not expires or datetime.fromisoformat(expires) < now:
                del self.ActiveAlerts[aid]
        
    def _retrieve_alerts_and_organize(self) -> list:
        print("Retrieving alerts.")
        compiled_alerts = []
        def first_or_empty(lst): # Helper function for condensing code. Returns important information.
            return lst[0] if lst else ""
        
        if not self.initialized: 
            raise RuntimeError("System not initialized!") # Why haven't you initialized???
        alerts = self._poll_active_alerts() # Poll active alerts from API.
        
        if not alerts: print ("No alerts found."); return None # Gate; return if no alerts exist.
        
        if not alerts["features"]: return None # If "features" is null.
        
        for feature in alerts["features"]: # Define basic parameters.
            props = feature.get("properties")
            geometry = feature.get("geometry", {})
            parameters = props.get("parameters", {})
            
            param_keys = [ # Parameter keys.
                "hailThreat",
                "windThreat",
                "maxWindGust",
                "maxHailSize",
                "tornadoDamageThreat",
                "thunderstormDamageThreat",
                "WEAHandling",
                "tornadoDetection",
                "BLOCKCHANNEL",
                "VTEC",
                "AWIPSidentifier",
                "WMOidentifier",
                "eventMotionDescription",
                "expiredReferences",
            ]
            param_values = {k: first_or_empty(parameters.get(k, [])) for k in param_keys} # Get values for keys. Point of this is to condense code.
            
            nws_headline = first_or_empty(parameters.get("NWSheadline", [])) or props.get("headline", "No title") # Apply helper function to headline.
            
            aZones = props.get("affectedZones", [])
            eventCode = props.get("eventCode", {})
            SAME_LIST = eventCode.get("SAME", [])
            NWS_LIST = eventCode.get("NationalWeatherService", [])
            
            impacted, areas = zones.check_areas_impacted(aZones) # Check if any areas listed in the alert data are impacted by this alert.
            
            if impacted: # If an area or multiple areas are impacted, continue to append information to the alert.
                counties = []
                
                for a in areas:
                    countyName = zones.name_from_zone(a)
                    
                    print(countyName)
                    
                    if countyName and countyName not in counties:
                        counties.append(countyName)
                    
                
                coordinates = None
                coordBase = None # Used as a discriminator for geometry script.
                
                if geometry and geometry["coordinates"]: 
                    coordinates = geometry.get("coordinates")
                    coordBase = "Polygon" # Use polygon for storm-based alerts.
                else:
                    coordinates = [zones.get_zone_geo(a) for a in areas] # Check area to zone geodata.
                    coordBase = "Area" # Area for county-based or region-based alerts.
                    
                compiled_alerts.append({ # Compile each individual alert that we have.
                    "id": feature["id"],
                    "sent": props.get("sent", ""),
                    "expires": props.get("expires", ""),
                    "title": nws_headline,
                    "secondary_title": props.get("headline", "No secondary title"),
                    "areaDesc": props.get("areaDesc", ""),
                    "desc": props.get("description", ""),
                    "instruction": props.get("instruction", ""),
                    "messageType": props.get("messageType", ""),
                    "SAME_code": SAME_LIST[0],
                    "NWS_code": NWS_LIST[0],
                    "status": props.get("status", ""),
                    "certainty": props.get("certainty", ""),
                    "severity": props.get("severity", ""),
                    "urgency": props.get("urgency", ""),
                    "senderName": props.get("senderName", ""),
                    "response": props.get("response", ""),
                    "event": props.get("event", "UNSPECIFIED"),
                    "coords": coordinates,
                    "base": coordBase,
                    "countiesAffected": counties,
                    "references": props.get("references", ""),
                    "replacedBy": props.get("replacedBy", ""),
                    "replacedAt": props.get("replacedAt", ""),
                    **param_values,
                })
        
        return compiled_alerts # Return list of compiled alerts.
    
    def check_internal(self): # Internally check alerts: add specific information if it's been added.
        if self.ActiveAlerts == None: 
            print(f"❌ No alerts to filter. {len(self.ActiveAlerts)} are active.")
            return
        
        totalChecked = 0
        failed = 0
        completed = 0
        updated = 0
        
        for alert, info in self.ActiveAlerts.items():
            totalChecked += 1
            newInfo = self._poll_internal_alerts(alert)
            
            if newInfo and newInfo["properties"]:
                props = newInfo["properties"]
                
                replacedBy = props.get("replacedBy", "")
                replacedAt = props.get("replacedAt", "")
                
                if replacedBy: 
                    self.ActiveAlerts[alert]["replacedBy"] = replacedBy
                    self.ActiveAlerts[alert]["replacedAt"] = replacedAt 
                    updated += 1
                else:
                    print(f"{alert} was not updated.")
                    
                completed += 1
            else:
                warnings.warn(f"{alert} failed to update.")
                failed += 1
        
        print(f"Completed internal checks. {totalChecked} alerts checked, {failed} alerts failed to be checked, {completed} were successfully checked, and {updated} alerts were updated.")
        
    def _poll_active_alerts(self) -> dict:
        url = "https://api.weather.gov/alerts/active?area=FL"

        try:
            r = requests.get(url, headers=self.requestHeader)  # keep as Response object
            if r.status_code != 200:
                print(f"⚠️ API returned status {r.status_code}: {r.text[:200]}")
                return []

            try:
                return r.json()
            except requests.exceptions.JSONDecodeError:
                print("⚠️ Response was not valid JSON!")
                print(f"Response text: {r.text[:200]}")  # Log first 200 chars
                return []
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Request failed: {e}")
            return []
        
    def _poll_internal_alerts(self, url: str):
        try:
            r = requests.get(url, headers=self.requestHeader)  # keep as Response object
            if r.status_code != 200:
                print(f"⚠️ API returned status {r.status_code}: {r.text[:200]}")
                return []

            try:
                return r.json()
            except requests.exceptions.JSONDecodeError:
                print("⚠️ Response was not valid JSON!")
                print(f"Response text: {r.text[:200]}")  # Log first 200 chars
                return []
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Request failed: {e}")
            return []
        
    def provide_alerts(self):
        return self.ActiveAlerts
    
    def write_to_alerts(self, data: dict):
        self.ActiveAlerts = data