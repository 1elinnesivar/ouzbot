import os
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import yt_dlp

# .env dosyasını yükle
load_dotenv()

# Bot ayarları
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
        self.current_track = None
        
    async def setup_hook(self):
        try:
            await self.tree.sync()
            print(f'Slash komutları senkronize edildi!')
        except Exception as e:
            print(f'Komut senkronizasyonunda hata: {e}')

bot = MusicBot()

# Müzik kontrol butonları
class MusicControls(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⏸️ Duraklat", style=discord.ButtonStyle.primary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("Müzik duraklatıldı ⏸️", ephemeral=True)
        else:
            await interaction.response.send_message("Şu anda çalan bir müzik yok!", ephemeral=True)

    @discord.ui.button(label="▶️ Devam Et", style=discord.ButtonStyle.primary)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("Müzik devam ediyor ▶️", ephemeral=True)
        else:
            await interaction.response.send_message("Duraklatılmış bir müzik yok!", ephemeral=True)

    @discord.ui.button(label="⏹️ Durdur", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client
        if voice_client and (voice_client.is_playing() or voice_client.is_paused()):
            voice_client.stop()
            await interaction.response.send_message("Müzik durduruldu ⏹️", ephemeral=True)
        else:
            await interaction.response.send_message("Durduralacak müzik yok!", ephemeral=True)

    @discord.ui.button(label="⏭️ Geç", style=discord.ButtonStyle.primary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message("Müzik geçildi ⏭️", ephemeral=True)
        else:
            await interaction.response.send_message("Geçilecek müzik yok!", ephemeral=True)

# YT-DLP ayarları
yt_dlp.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
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
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = ''

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        
        if 'entries' in data:
            data = data['entries'][0]
            
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

@bot.event
async def on_ready():
    print(f'{bot.user} olarak giriş yapıldı!')

@bot.tree.command(
    name="join",
    description="Botu ses kanalına katılmaya davet eder",
    guild=discord.Object(id=int(os.getenv('GUILD_ID')))
)
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message('Bir ses kanalında olmalısınız!', ephemeral=True)
        return
    
    channel = interaction.user.voice.channel
    await channel.connect()
    await interaction.response.send_message(f'{channel.name} kanalına katıldım!', ephemeral=True)

@bot.tree.command(
    name="leave",
    description="Botu ses kanalından çıkarır",
    guild=discord.Object(id=int(os.getenv('GUILD_ID')))
)
async def leave(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client:
        await voice_client.disconnect()
        await interaction.response.send_message('Ses kanalından ayrıldım!', ephemeral=True)
    else:
        await interaction.response.send_message('Bot zaten ses kanalında değil!', ephemeral=True)

@bot.tree.command(
    name="play",
    description="YouTube'dan müzik çalar"
)
async def play(interaction: discord.Interaction, url: str):
    try:
        await interaction.response.defer()
        
        if not interaction.user.voice:
            await interaction.followup.send('Bir ses kanalında olmalısınız!', ephemeral=True)
            return

        voice_client = interaction.guild.voice_client
        if not voice_client:
            channel = interaction.user.voice.channel
            voice_client = await channel.connect()

        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        voice_client.play(player, after=lambda e: print(f'Oynatma hatası: {e}') if e else None)
        bot.current_track = player

        embed = discord.Embed(
            title="🎵 Şimdi Çalınıyor",
            description=f"**{player.title}**",
            color=discord.Color.blue()
        )
        
        view = MusicControls()
        await interaction.followup.send(embed=embed, view=view)
    
    except Exception as e:
        await interaction.followup.send(f'Bir hata oluştu: {str(e)}', ephemeral=True)

# Botu çalıştır
bot.run(os.getenv('DISCORD_TOKEN')) 