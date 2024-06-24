import discord
from discord.ext import commands
from discord import app_commands
from discord.ext import commands, tasks
import yt_dlp as youtube_dl
import asyncio
import logging
import random
from datetime import datetime
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import pymongo
from dotenv import load_dotenv
import openai

logging.basicConfig(level=logging.DEBUG)

intents = discord.Intents.default()
intents.message_content = True 

# Loading The Environment Variables From auth_token.env File.
dotenv_path = r"C:\Users\Jacob\Desktop\It's Canon\bot-env\auth_token.env"
load_dotenv(dotenv_path)

# Verify if dotenv_path is correct and pulling as it should
print(f"Loading environment variables from: {dotenv_path}")

#Trying to hide API Keys and Client Secrets
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
MONGODB_CONNECTION_STRING = os.getenv('MONGODB_CONNECTION_STRING')
SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
#TWITCH_OAUTH_TOKEN = os.getenv('TWITCH_OAUTH_TOKEN')
#TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Debugging As To Why It Is Saying "Incorrect, fuck me man"
#print(f"DISCORD_BOT_TOKEN: {DISCORD_BOT_TOKEN}")
#print(f"MONGODB_CONNECTION_STRING: {MONGODB_CONNECTION_STRING}")
#print(f"SPOTIFY_CLIENT_ID: {SPOTIFY_CLIENT_ID}")
#print(f"SPOTIFY_CLIENT_SECRET: {SPOTIFY_CLIENT_SECRET}")

# If any of these variables are None, End Script
if not all([DISCORD_BOT_TOKEN, MONGODB_CONNECTION_STRING, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET]):
    raise ValueError("Environment variables are missing.")

youtube_dl.utils.bug_reports_message = lambda: ''

bot = commands.Bot(command_prefix='?', intents=intents)

#OpenAI Setup
openai.api_key = OPENAI_API_KEY

#MongoDB Steup
mongo_client = pymongo.MongoClient(MONGODB_CONNECTION_STRING)
db = mongo_client["B-Day"]
birthdays = db["birthdays"]

# Spotify API setup
#SPOTIFY_CLIENT_ID = SPOTIFY_CLIENT_ID
#SPOTIFY_CLIENT_SECRET = SPOTIFY_CLIENT_SECRET

client_credentials_manager = SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

#Song Queue, Doesn't Stay on Reboot.
queue = []

#Netherim Quotes
quotes = [
    "I'd conjure up motes of happiness and infuse your heart with it if I could. Best I can do is a kiss. But you'd get horny from that.",
    "You really hit me with the. That's a premium feature! Purchase the DLC now for exclusive content. (I am kidding & not projecting).",
    "The thing about dangerous games my love. Is that I win every single time ;)",
    "I'm enthralled. Not just by you and your personality. But by how fucking gorgeous and attractive you are ❤️",
    "I go nini. But I snatch you for wow when I wake up ;3. Check snap for surprise c:",
    "Wanna milk me? ;3. Could give you control this time and let you have fun. Spoiling you a lil.",
    "The thought of making love to you is enough to send shivers down my body and get me incredibly hard. I crave you, deeply.",
    "I want to breed you raw. Only raw. Every morning and night. While kissing you everywhere.",
    "Woke up incredibly horny. Thinking about marking you, laying you down and fucking your sensitive little pussy in a way you'd never be able to stop thinking about. Forcing you to cum all over my cock inside you and counting you down.",
    "Your future husband must sleep now.",
    "I wanna drown in your eyes. I'll drown you in cum. :thumbsup: Too Sticky."
]

#Prints When Ready and Logged In, Starts Birthday Check and Syncs / Commands
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    check_birthdays.start() #Checking For Updates.
    try:
        synced = await bot.tree.sync() #Syncing / Commands
        print(f'Synced {len(synced)} Slash Commands')
    except Exception as e:
        print(f'Failed to sync commands: {e}')
    bot.loop.create_task(disconnect_after_inactivity())

async def disconnect_after_inactivity():
    while True:
        await asyncio.sleep(300)  # Increased to 5 Minutes, To Avoid Auto Disconnects.
        for vc in bot.voice_clients:
            if not vc.is_playing() and not vc.is_paused():
                await vc.disconnect()
                await vc.channel.send("Disconnected due to inactivity.")

@bot.command(aliases=['r'])
async def roll(ctx, *, dice: str):
    try:
        if 'd' not in dice:
            raise ValueError
        # Removes Spaces Around '+' or '-' For Simplicity.
        dice = dice.replace(' ', '')

        # Split the dice string to handle modifiers
        parts = dice.split('d') #After the "D", Rand 1 - <num>. I.E D<seperate> 20, makes randint(1, 20).
        if '+' in parts[1]:
            limit, modifier = parts[1].split('+')
            modifier = int(modifier)
        elif '-' in parts[1]:
            limit, modifier = parts[1].split('-')
            modifier = -int(modifier)
        else:
            limit = parts[1]
            modifier = 0

        rolls = int(parts[0]) if parts[0] else 1
        limit = int(limit) #This is the number after D or d.

        results = [random.randint(1, limit) for _ in range(rolls)]
        total = sum(results) + modifier
        result_str = ', '.join(str(result) for result in results)
        await ctx.send(f'Rolled {dice}: {result_str} (Total: {total})')
    except Exception:
        await ctx.send('Format has to be in Number, Die, Number. I.E "1d20 +3" "4d6 -2"')

@bot.command()
async def netherim(ctx):
    quote = random.choice(quotes)
    await ctx.send(quote)

@bot.tree.command(name="setbirthday", description="Set your birthday")
async def set_birthday(interaction: discord.Interaction, month: int, day: int):
    existing_birthday = birthdays.find_one({"user_id": interaction.user.id})
    if existing_birthday:
        await interaction.response.send_message(f"You have already set your birthday as {existing_birthday['month']}/{existing_birthday['day']}. Please use /removebirthday if incorrect.")
        return
    
    if 1 <= month <= 12 and 1 <= day <= 31:  # Basic validation of month and day.
        birthdays.update_one(
            {"user_id": interaction.user.id},
            {"$set": {"username": interaction.user.name, "month": month, "day": day}},
            upsert=True
        )
        await interaction.response.send_message(f"Birthday set for {interaction.user.name}: {month}/{day}") 
    else:
        await interaction.response.send_message("Invalid date. Please enter a valid month (1-12) and day (1-31).")

@bot.tree.command(name="getbirthday", description="Get a user's birthday")
@app_commands.describe(username="Username to get the birthday of")
async def get_birthday(interaction: discord.Interaction, username: str):
    user_birthday = birthdays.find_one({"username": username}) #Searches MongoDB for user's B-Day, and returns it.
    if user_birthday:
        await interaction.response.send_message(f"{username}'s birthday is on {user_birthday['month']}/{user_birthday['day']}.")
    else:
        await interaction.response.send_message(f"No birthday found for {username}.")

@bot.tree.command(name="removebirthday", description="Remove your birthday")
async def remove_birthday(interaction: discord.Interaction):
    result = birthdays.delete_one({"user_id": interaction.user.id})
    if result.deleted_count:
        await interaction.response.send_message("Your birthday has been removed.")
    else:
        await interaction.response.send_message("You don't have a birthday set.")

@tasks.loop(hours=24)
async def check_birthdays():
    now = datetime.now() #Uses date_time to get current date.
    current_month = now.month
    current_day = now.day
    channel = bot.get_channel(931343657515253770) #Uberzones Annoucement Channel.

    today_birthdays = birthdays.find({"month": current_month, "day": current_day}) #Searching MongoDB for current B-Day
    for user_birthday in today_birthdays:
        user = bot.get_user(user_birthday["user_id"])
        if user:
            await channel.send(f"Happy Birthday, {user.mention}! 🎉🎂")

@check_birthdays.before_loop
async def before_check_birthdays():
    await bot.wait_until_ready()

@bot.tree.command(name="askgpt", description="Ask a Bratty Teenage Girl a question.")
@app_commands.describe(question="Your question to GPT")
async def ask_gpt(interaction: discord.Interaction, question: str):
    """Command to ask GPT a question"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Answer All Questions Like a Ryan Reynold's Deadpool."},
                {"role": "user", "content": question}
            ],
            max_tokens=150
        )
        answer = response.choices[0].message['content'].strip()
        await interaction.response.send_message(f"**Question:** {question}\n**Answer:** {answer}")
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}")

@bot.command()
async def join(ctx):
    if ctx.voice_client is not None: #Easier to make it "not None" since there are other join codes.
        return await ctx.send("Joined the Voice Channel. Enjoy!")

    if not ctx.message.author.voice:
        return await ctx.send("You are not connected to a voice channel.")

    channel = ctx.message.author.voice.channel
    await channel.connect()

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.guild.voice_client.disconnect()
        await ctx.send("Disconnected from the VC.")
    else:
        await ctx.send("I Wasn't In VC.")

@bot.command()
async def skip(ctx):
    if ctx.voice_client is not None and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped the current song.")
    else:
        await ctx.send("No song is currently playing. (Check Que, and if broken MSG me :))")

@bot.command()
async def play(ctx, *, query):
    if "spotify.com" in query: #Checks the Spotify API for songs if it has Spotify.com in Title, and play off of their servers.
        results = sp.track(query)
        track_name = results['name']
        track_artists = ', '.join(artist['name'] for artist in results['artists'])
        youtube_query = f"{track_name} {track_artists}"
        info = await YTDLSource.from_url(f"ytsearch:{youtube_query}", loop=bot.loop, stream=True)
    else:
        info = await YTDLSource.from_url(query, loop=bot.loop, stream=True)

    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        ctx.voice_client.stop()
    queue.insert(0, info)
    await play_next(ctx)

@bot.command()
async def add(ctx, *, query):
    if "spotify.com" in query:
        results = sp.track(query)
        track_name = results['name']
        track_artists = ', '.join(artist['name'] for artist in results['artists'])
        youtube_query = f"{track_name} {track_artists}"
        info = await YTDLSource.from_url(f"ytsearch:{youtube_query}", loop=bot.loop, stream=True)
    else:
        info = await YTDLSource.from_url(query, loop=bot.loop, stream=True)

    queue.append(info)
    await ctx.send(f'Added to queue: {info.title}')

async def play_next(interaction):
    if not interaction.guild.voice_client:
        return
    if queue:
        info = queue.pop(0)
        try:
            player = await YTDLSource.from_url(info.url, loop=bot.loop, stream=True)
            interaction.guild.voice_client.play(player, after=lambda e: bot.loop.create_task(check_queue(interaction, e)))
            await interaction.channel.send(f'Now playing: {info.title}')
        except Exception as e:
            await interaction.channel.send(f'An error occurred: {str(e)}')
            if queue:
                await play_next(interaction)
    else:
        await interaction.channel.send("Queue is now empty.")

async def check_queue(interaction, error):
    if error:
        print(f'Player error: {error}')
    if queue:
        await play_next(interaction)

@bot.command()
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Paused the current song.")
    else:
        await ctx.send("No song is currently playing.")

@bot.command()
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Resumed the current song.")
    else:
        await ctx.send("The song is not paused.")

@bot.command()
async def stop(ctx):
    ctx.voice_client.stop()
    await ctx.send("Stopped the current song.")

#Would like to adjust this, making it keep changes while in VC, not per song.
@bot.command()
async def volume(ctx, volume: int):
    if ctx.voice_client is None:
        return await ctx.send("Not connected to a voice channel.")

    ctx.voice_client.source.volume = volume / 100
    await ctx.send(f"Changed volume to {volume}%")

@bot.command()
async def showqueue(ctx):
    if not queue:
        await ctx.send("The queue is empty. Add some songs using /add!")
    else:
        queue_titles = [info.title for info in queue]
        await ctx.send("Current queue:\n" + "\n".join(queue_titles))

@bot.tree.command(name="join", description="Used To Have Canon Join Chat")
async def slash_join(interaction: discord.Interaction):
    if interaction.user.voice is None:
        await interaction.response.send_message("You are not connected to a voice channel.")
        return

    channel = interaction.user.voice.channel
    if interaction.guild.voice_client is not None: #Once again, easier to use not None.
        await interaction.guild.voice_client.move_to(channel)
    else:
        await channel.connect()
    await interaction.response.send_message("Joined the Voice Channel. Enjoy!")

@bot.tree.command(name="leave", description="Use To Have Canon Leave Chat")
async def slash_leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Disconnected from the VC.")
    else:
        await interaction.response.send_message("I am not in a VC")

@bot.tree.command(name="play", description="Used To Give Either Spotify Link or Youtube Link")
async def slash_play(interaction: discord.Interaction, query: str):
    await interaction.response.send_message("Processing... (I can take a moment.)", ephemeral=True)
    
    if "spotify.com" in query:
        results = sp.track(query)
        track_name = results['name']
        track_artists = ', '.join(artist['name'] for artist in results['artists'])
        youtube_query = f"{track_name} {track_artists}"
        info = await YTDLSource.from_url(f"ytsearch:{youtube_query}", loop=bot.loop, stream=True)
    else:
        info = await YTDLSource.from_url(query, loop=bot.loop, stream=True)

    voice_client = interaction.guild.voice_client
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
    queue.insert(0, info)
    await play_next(interaction)
    await interaction.edit_original_response(content=f'Now playing: {info.title}')

@bot.tree.command(name="add", description="Add A Song To The Queue")
async def slash_add(interaction: discord.Interaction, query: str):
    await interaction.response.send_message("Processing... (I can take a moment.)", ephemeral=True)
    
    if "spotify.com" in query:
        results = sp.track(query)
        track_name = results['name']
        track_artists = ', '.join(artist['name'] for artist in results['artists'])
        youtube_query = f"{track_name} {track_artists}"
        info = await YTDLSource.from_url(f"ytsearch:{youtube_query}", loop=bot.loop, stream=True)
    else:
        info = await YTDLSource.from_url(query, loop=bot.loop, stream=True)

    queue.append(info)
    await interaction.edit_original_response(content=f'Added to queue: {info.title}')

@bot.tree.command(name="skip", description="Ask GPT a question")
async def slash_skip(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client is not None and voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("Skipped the current song.")
    else:
        await interaction.response.send_message("No song is currently playing.")

@bot.tree.command(name="pause", description="Used To Pause A Song")
async def slash_pause(interaction: discord.Interaction):
    if interaction.guild.voice_client.is_playing():
        interaction.guild.voice_client.pause()
        await interaction.response.send_message("Paused the current song.")
    else:
        await interaction.response.send_message("No song is currently playing.")

@bot.tree.command(name="resume", description="Used To Resume A Song")
async def slash_resume(interaction: discord.Interaction):
    if interaction.guild.voice_client.is_paused():
        interaction.guild.voice_client.resume()
        await interaction.response.send_message("Resumed the current song.")
    else:
        await interaction.response.send_message("The song is not paused.")

@bot.tree.command(name="stop", description="Used To Stop A Song From Playing")
async def slash_stop(interaction: discord.Interaction):
    interaction.guild.voice_client.stop()
    await interaction.response.send_message("Stopped the current song.")

@bot.tree.command(name="volume", description="Used To Adjust Volume Of a Song")
async def slash_volume(interaction: discord.Interaction, volume: int):
    if interaction.guild.voice_client is None:
        await interaction.response.send_message("Not connected to a voice channel.")
    else:
        interaction.guild.voice_client.source.volume = volume / 100
        await interaction.response.send_message(f"Changed volume to {volume}%")

@bot.tree.command(name="showqueue", description="Used To Show The Current Queue")

async def slash_showqueue(interaction: discord.Interaction):
    if not queue:
        await interaction.response.send_message("The queue is empty.")
    else:
        queue_titles = [info.title for info in queue]
        await interaction.response.send_message("Current queue:\n" + "\n".join(queue_titles))

@bot.tree.command(name="randomstats", description="Used To Roll Random Array Of Stats For DND")
async def slash_randomstats(interaction: discord.Interaction):
    all_results = []
    for i in range(6):
        rolls = sorted([random.randint(1, 6) for _ in range(4)], reverse=True) #Always going to be a D6
        total = sum(rolls[:-1])  # Drop the lowest roll
        all_results.append((rolls, total))
    results_str = '\n'.join([f'Roll {i+1}: {rolls} -> Total: {total}' for i, (rolls, total) in enumerate(all_results)])
    overall_total = sum(total for _, total in all_results)
    await interaction.response.send_message(f'Random Stats:\n{results_str}\nOverall Total: {overall_total}')

@bot.tree.command(name="roll", description="Used To Roll A D2, D4, D6, D8, D12, D20, D100, ETC.")
async def slash_roll(interaction: discord.Interaction, dice: str):
    try:
        if 'd' not in dice:
            raise ValueError

        # Remove spaces around '+' or '-'
        dice = dice.replace(' ', '')

        # Split the dice string to handle modifiers
        parts = dice.split('d')
        if '+' in parts[1]:
            limit, modifier = parts[1].split('+')
            modifier = int(modifier)
        elif '-' in parts[1]:
            limit, modifier = parts[1].split('-')
            modifier = -int(modifier)
        else:
            limit = parts[1]
            modifier = 0

        rolls = int(parts[0]) if parts[0] else 1
        limit = int(limit)

        results = [random.randint(1, limit) for _ in range(rolls)]
        total = sum(results) + modifier
        result_str = ', '.join(str(result) for result in results)
        await interaction.response.send_message(f'Rolled {dice}: {result_str} (Total: {total})')
    except Exception:
        await interaction.response.send_message('Format has to be in Number, Die, Number. I.E "1d20 +3" "4d6 -2"')

@bot.tree.command(name="r", description="Used To Roll A D2, D4, D6, D8, D12, D20, D100, ETC.")
async def slash_r(interaction: discord.Interaction, dice: str):
    await slash_roll(interaction, dice)

@play.before_invoke
@join.before_invoke
async def ensure_voice(ctx):
    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You are not connected to a VC!")
            raise commands.CommandError("You are not connected to a VC!")
    elif ctx.voice_client.is_playing():
        ctx.voice_client.stop()

bot.run(DISCORD_BOT_TOKEN)