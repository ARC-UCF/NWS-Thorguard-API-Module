from services import State, Forecasts, Hurricane, AlertStatistics, Alerts
from utils import Time, identifier, determiner, generate_alert_image, ucf_in_or_near_polygon, webhooks
import config
import asyncio
import discord
from discord import Webhook, SyncWebhook
import os
from io import BytesIO
import datetime
from datetime import time

tManager = Time()
deter = determiner
st = State()
fcast = Forecasts()
hurr = Hurricane()
alertStats = AlertStatistics()
aManager = Alerts()
webs = webhooks

DONOTPOST = False

severity_colors = { # This severity index is based on the severity property in alerts.
    "Extreme": 0xA020F0,   # Purple
    "Severe": 0xFF0000,    # Red
    "Moderate": 0xFFA500,  # Orange
    "Minor": 0xFFFF00,     # Yellow
    "Unknown": 0x808080    # Gray
}

'''
This is the sort of central system basically. This thing manages the services.
I optimized waht I could/wanted to in the moment, further optimization can be expected, well, later.
'''

class Controller():
    def __init__(self):
        self.posted_alerts = {}
        self.establish()
    
    async def run(self):
        while True:
            await self.handle_and_post_alerts()
            self.handle_and_post_forecasts()
            self.save_info()
            await asyncio.sleep(self.timeDelay)
            aManager.check_internal()
            
            newDay = tManager.is_new_day()
            
            if newDay:
                fcast.reset_states()
                hurr.reset_states()
            
            await asyncio.sleep(self.timeDelay)
            
            
    def establish(self):
        data = st.send_to_disseminate()
    
        if data["alerts"]:
            self.posted_alerts = data["alerts"]
            aManager.write_to_alerts(data["alerts"])
        
        if data["forecast"]:
            fcast.write_forecast_states(data["forecast"])
        
        if data["hurricane"]:
            hurr.write_forecast_states(data["hurricane"])
        
        if data["timing"]:
            tManager.write_last_date(data["timing"])
        
        if data["trackId"]:
            identifier.write_to_id(data["trackId"])
        
        if data["stats"]:
           alertStats.write_to_stats(data["stats"])
        
        self.timeDelay = config.checkTime
    
        if self.timeDelay < 20: self.timeDelay = 20
    
        self.timeDelay = self.timeDelay/2
        
    def save_info(self):
        hInfo = hurr.return_forecast_states()
        fInfo = fcast.return_forecast_states()
        sInfo = alertStats.provide_stats()
        tim = tManager.provide()
        tID = identifier.provide_next_id()
        
        st.write_data(fInfo, hInfo, self.posted_alerts, tim, tID, sInfo)
        
    def handle_and_post_forecasts(self):
        post, info = fcast.time_to_post_forecast()
        
        if post:
            
            embed = discord.Embed(
                title="Forecast Information",
                color=0x53eb31,
            )
            
            embed.set_footer(text=config.VERSION)
            
            forecastWeb = webhooks.get_webhook_from_county("forecast")
            
            for day in info:
                fullName = f"{info["timePeriod"]} // {info["startTime"].date()} {info["startTime"].time()} - {info["endTime"].date()} {info["endTime"].time()}"
                
                forecastString = f"Temperature: {info["temp"]}\nWind: {info["windDirection"]} @ {info["windSpeed"]}\nPrecip Chance: {info["precipProbs"]}%\n\n{info["forecast"]}"
                
                embed.add_field(name=fullName, value=forecastString, inline=False)
                
            forecastWeb.send(embed=embed, username=config.AUTHOR)
            
        post, discussion, image = hurr.time_to_post_hurricane()
        
        if post:
            
            discussion = (discussion[:4000] + "...") if len(discussion) > 4000 else discussion
            
            hurricaneWeb = webhooks.get_webhook_from_county("hurricane")
            
            embed = discord.Embed(
                title="Hurricane Discussion",
                description=discussion,
                color=0x1e90ff,
            )
            
            embed.set_footer(text=config.VERSION)
            embed.set_image(url=image)
            
            hurricaneWeb.send(embed=embed, username=config.AUTHOR)    
    
    async def handle_and_post_alerts(self):
        alertList = aManager.cycle() # Handling this cycle is the chunkiest thing in here I swear
        
        if alertList is None: return
        
        for a in alertList:
            alrt = alertList[a]
            Id = alrt["id"]
            
            if Id not in self.posted_alerts:
                
                print(f"Working {Id}")
                
                severity = alrt.get("severity", "Unknown")
                color = severity_colors.get(severity, 0x808080) # Determine color based on severity property.
                
                header = f"(#{alrt["trackId"]}) - {alrt["title"]}"
                
                preambleList = [
                    "WMOidentifier",
                    "AWIPSidentifier",
                    "VTEC",
                    "space",
                    "event",
                    "senderName",
                    "bulletin",
                ]
                
                preamble_lines = []
                
                for field in preambleList:
                    if field == "space":
                        preamble_lines.append("")  # adds a blank line
                    elif field == "bulletin":
                        bulletin = deter.determine(alrt["WEAHandling"], alrt["messageType"], alrt["severity"], alrt["certainty"], alrt["urgency"])
                        if bulletin:
                            preamble_lines.append(bulletin)
                    elif alrt.get(field):
                        preamble_lines.append(alrt[field])
                        
                preambleString = "\n".join(preamble_lines)
                            
                mainList = [
                    "secondary_title",
                    "desc",
                ]
                
                main_lines = []

                for field in mainList:
                    if alrt.get(field):
                        main_lines.append(alrt[field])

                mainString = "\n\n".join(main_lines)
                
                truncated_text = (mainString[:3850-3] + "...") if len(mainString) > 3850 else mainString
                
                if alrt["eventMotionDescription"]:
                    truncated_text = truncated_text + "\n\n" + alrt["eventMotionDescription"]
                    
                total = preambleString + "\n\n" + truncated_text
                
                informationToFetch = {
                    "id": "Alert Id: ",
                    "SAME_code": "SAME: ",
                    "severity": "Severity: ",
                    "urgency": "Urgency: ",
                    "certainty": "Certainty: ",
                    "response": "Response: ",
                    "hailThreat": "Hail Threat: ",
                    "maxHailSize": "Max Hail Size: ",
                    "windThreat": "Wind Threat: ",
                    "maxWindGust": "Max Wind Gust: ",
                    "tornadoDetection": "Tornado Detection: ",
                    "tornadoDamageThreat": "Damage Threat: ",
                    "thunderstormDamageThreat": "Damage Threat: ",
                }
                
                info_lines = []
                
                for key, lead in informationToFetch.items():
                    if alrt.get(key):
                        info_lines.append(lead + alrt.get(key))
                        
                infoMessage = "\n".join(info_lines)
                
                embed = discord.Embed(
                    title=header,
                    description=total,
                    color=color,
                )
                
                if alrt["instruction"]:
                    embed.add_field(name="Precautionary/Prepardness Instructions", value=alrt["instruction"], inline=False)
                    
                embed.add_field(name="Alert Information", value=infoMessage, inline=False)
                embed.set_footer(text=config.VERSION)
                
                buf = generate_alert_image(alrt["coords"], alrt["base"], alrt["SAME_code"], alrt["polyColor"], alrt["trackId"])
                
                embed.set_image(url="attachment://alert_map.png")
                
                print("synced webhooks")
                print(webhooks.SYNCED_WEBHOOKS)
                
                for c in alrt["countiesAffected"]:
                    if DONOTPOST: continue
                    
                    webhook = webhooks.get_webhook_from_county(c)
                    
                    if webhook:
                        print("webhook found")
                        if alrt["SAME_code"] in config.alertCodes:
                            ping = config.pings[c]
                            webhook.send(ping, username=config.AUTHOR)
                        buf.seek(0)
                        file = discord.File(fp=buf, filename="alert_map.png")
                        webhook.send(embed=embed, file=file, username=config.AUTHOR)
                    if c == "orange" and alrt["base"] == "Area" and webhook:
                        webhook = webhooks.get_webhook_from_county("arc")
                        
                        if alrt["SAME_code"] in config.alertCodes:
                            if alrt["SAME_code"] in config.alertCodes:
                                ping = config.pings[c]
                                webhook.send(ping, username=config.AUTHOR)
                        buf.seek(0)
                        file = discord.File(fp=buf, filename="alert_map.png")
                        webhook.send(embed=embed, file=file, username=config.AUTHOR)
                    elif c == "orange" and alrt["base"] == "Polygon" and webhook:
                        ucfAffected = ucf_in_or_near_polygon(alrt["coords"])
                        
                        if ucfAffected:
                            webhook = webhooks.get_webhook_from_county("arc")
                        
                            if alrt["SAME_code"] in config.alertCodes:
                                if alrt["SAME_code"] in config.alertCodes:
                                    ping = config.pings[c]
                                    webhook.send(ping, username=config.AUTHOR)
                            buf.seek(0)
                            file = discord.File(fp=buf, filename="alert_map.png")
                            webhook.send(embed=embed, file=file, username=config.AUTHOR)
                    
                    self.posted_alerts[Id] = alrt
                    print(f"✅🔗 Alert pushed.")
                    print("Sent " + Id)
                    alertStats.add_stat(alrt["countiesAffected"], alrt["SAME_code"])
                    
                await asyncio.sleep(2)
            for ca in self.posted_alerts:
                if ca not in alertList:
                    print("Alert no longer exists per ALERTS. ALERTS takes precedence and deletes.")
                    del self.posted_alerts[ca]
                        
                
                
                
                
                
                
    
    