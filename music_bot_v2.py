import asyncio
from collections import deque

import discord
import yt_dlp as youtube_dl

from discord.ext import commands, tasks

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ""


ffmpeg_options = {
    "options": "-vn",
}

ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get("title")
        self.url = data.get("url")

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if "entries" in data:
            # take first item from a playlist
            data = data["entries"][0]

        filename = data["url"] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    valid_urls = [
        "youtube",
        "youtu.be",
    ]

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.play_music = False
        self.paused = False
        self.looping = False
        self.song = None
        self.ctx: commands.Context = None
        self.play_queue = deque()

        self.music_player.start()

    @property
    def is_playing(self):
        if self.ctx is None:
            return False
        elif self.ctx.voice_client is None:
            return False
        else:
            return self.ctx.voice_client.is_playing()

    @tasks.loop(seconds=1)
    async def music_player(self):
        print(
            f"starting loop, {self.play_music=}, {self.is_playing=}, {self.paused=}, {self.play_queue=}, {self.looping=}"
        )

        if self.play_music:
            await self.ensure_voice(self.ctx)
            if len(self.ctx.voice_client.channel.members) < 2:
                print("All alone, stopping")
                await self.stop(self.ctx)

            if self.is_playing is False and self.paused is False:
                if self.play_queue:
                    print(f"\t{self.song=}, {self.looping=}")
                    if self.song is not None and self.looping is True:
                        self.song = self.song
                    elif self.play_queue:
                        self.song = self.play_queue.pop()
                    else:
                        print("\t\tQueue is empty, no new song to play")
                        await self.stop(self.ctx)
                        return
                    self.ctx.voice_client.play(self.song, after=lambda e: print(f"Player error: {e}") if e else None)
                    print(f"\t\t\t now playing {self.song.title}")
                    await self.ctx.send(f"Now playing: {self.song.title}")

    @classmethod
    def validate_link(cls, url) -> bool:
        return any(x in url for x in cls.valid_urls)

    @commands.command()
    async def play(self, ctx):
        """Joins the voice channel  you're in and starts playing from the queue"""
        self.ctx = ctx
        self.play_music = True

    @commands.command()
    async def add(self, ctx, *, url: str):
        """Add a youtube song to the play queue"""
        if self.validate_link(url):
            song = await YTDLSource.from_url(url, stream=True)
            self.play_queue.append(song)
            await ctx.send(f"Song added to queue 👍")
        else:
            await ctx.send(f"🚨Not a valid Youtube URL🚨")

    @commands.command()
    async def queue(self, ctx):
        """Show the current play queue"""
        print("Showing the queue")
        newline = "\n"
        songs = [song.title for song in self.play_queue]
        # msg = f"""Current queue:{newline}{f'{newline}'.join(songs)} """
        msg = """Current queue:\n""" f"""{f'{newline}'.join(songs)}"""
        await ctx.send(msg)

    # @commands.command()
    # async def pause(self, ctx):
    #     """Pauses the currently playing song"""
    #     self.paused = True
    #     await ctx.voice_client.pause()

    # @commands.command()
    # async def resume(self, ctx):
    #     """Resumes the paused song"""
    #     print("in resume command")
    #     if self.paused is True:
    #         print("unpausing")
    #         await ctx.voice_client.resume()
    #         self.paused = False
    #         print("all done unpausing")

    @commands.command()
    async def next(self, ctx):
        """Skips to the next song"""
        await ctx.voice_client.stop()

    @commands.command()
    async def clearqueue(self, ctx):
        """Clears all songs from the queue"""
        self.play_queue.clear()

    @commands.command()
    async def stop(self, ctx):
        """Stops and disconnects the bot from voice"""
        self.play_music = False
        await ctx.voice_client.disconnect()

    @commands.command()
    async def loop(self, ctx):
        """Toggles looping the current song"""
        self.looping = not self.looping

    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")

    @add.before_invoke
    async def acknowledge_cmd(self, ctx):
        await ctx.message.add_reaction("👍")


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("!"),
    description="Relatively simple music bot example",
    intents=intents,
)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")


async def main():
    import dotenv
    import os

    dotenv.load_dotenv()

    async with bot:
        await bot.add_cog(Music(bot))
        await bot.start(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    asyncio.run(main())
