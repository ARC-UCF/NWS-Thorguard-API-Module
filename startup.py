import os 
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord import SyncWebhook
import asyncio
import warnings
from controller import Controller
import config
load_dotenv('sensitive.env')

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # Sync slash commands to your server
        guild = discord.Object(id=os.environ.get('GUILD_ID'))
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        
client = MyClient()

@client.event
async def on_ready():
    print("Successful login!")
    print(f'✅ Logged in as user {client.user})')
    channel = client.get_channel(1402335502215942310)
    
    await channel.send(f"✅ Bot has successfully connected to Discord and is online! Operating on {config.VERSION}")
    
    await Controller().run()
    
@client.event
async def on_disconnect():
    print("❌ Discord client has disconnected.")
    
def login():
    max_tries = 5 # Max login attempts
    tries = 0 # Current number of attempts to login
    successful = False
    print("🔑 Attempting to log into Discord...")
    if not client.is_closed():
        while not successful and tries < max_tries:
            try:
                client.run(os.environ.get('API-TOKEN'))
            except Exception as e:
                if client.is_closed():
                    print("❌ Discord client is closed. Exiting login attempts.")
                    break
                if tries < max_tries:
                    print(f"⚠️⚠️ 🔄Error logging into discord: {e}!! Retrying...")
                    print(f"Tries {tries} of {max_tries}")
                    tries += 1
                elif tries == max_tries:
                    warnings.warn(f"🔐🚫 Login attempt failed after {max_tries} tries.")
            if not Exception:
                successful = True
                print("✅ Successfully logged into Discord!")
                break
    
login()
    

    


