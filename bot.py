import discord
from discord import app_commands
import requests
import os
import asyncio
import datetime
from account_storage import load_accounts, save_accounts
from urllib.parse import quote_plus
from dotenv import load_dotenv, set_key

# Cargar variables de entorno
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
RIOT_API_KEY = os.getenv('RIOT_API_KEY')
GUILD_ID = 214856862724521984

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

file_path = 'linked_accounts.json'
player_accounts = load_accounts(file_path)

rank_order = {"IRON": 1, "BRONZE": 2, "SILVER": 3, "GOLD": 4, "PLATINUM": 5, "EMERALD": 6, "DIAMOND": 7, "MASTER": 8, "GRANDMASTER": 9, "CHALLENGER": 10}
division_order = {"IV": 1, "III": 2, "II": 3, "I": 4}

channel_id = None  # Canal donde se enviarán los mensajes automáticos

def get_rank_value(tier, division, lp):
    if tier in ["MASTER", "GRANDMASTER", "CHALLENGER"]:
        return rank_order[tier] * 10000 + lp
    return rank_order[tier] * 10000 + division_order[division] * 1000 + lp

async def send_leaderboard():
    global channel_id
    if channel_id is None:
        print("No se ha definido un canal para los mensajes automáticos.")
        return
    
    guild = client.get_guild(GUILD_ID)
    channel = guild.get_channel(channel_id)
    if not channel:
        print("El canal definido no es válido.")
        return
    
    leaderboard = []
    for user_id, account_info in player_accounts.items():
        puuid = account_info['puuid']
        summoner_name = account_info['summoner_name']

        response = requests.get(
            f"https://la1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}",
            headers={"X-Riot-Token": RIOT_API_KEY}
        )
        if response.status_code == 200:
            summoner_data = response.json()
            summoner_id = summoner_data.get('id')
            member = guild.get_member(int(user_id))
            discord_user = member.mention if member else f"<@{user_id}>"

            if summoner_id:
                league_response = requests.get(
                    f"https://la1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}",
                    headers={"X-Riot-Token": RIOT_API_KEY}
                )
                if league_response.status_code == 200:
                    league_data = league_response.json()
                    soloq_data = next((entry for entry in league_data if entry['queueType'] == 'RANKED_SOLO_5x5'), None)
                    if soloq_data:
                        lp = soloq_data["leaguePoints"]
                        tier = soloq_data["tier"].capitalize()
                        rank = soloq_data["rank"]
                        league_info = f"{tier} {rank} {lp} LP"
                        rank_value = get_rank_value(tier.upper(), rank, lp)
                    else:
                        league_info = "Sin datos de SoloQ"
                        rank_value = 0
                    leaderboard.append((summoner_name, league_info, discord_user, rank_value))
                else:
                    print(f"Error en Riot API (Liga) para {summoner_name}: {league_response.status_code}")
            else:
                print(f"Error: No se encontró summonerID para {summoner_name}.")
        else:
            print(f"Error en Riot API (Summoner) para {summoner_name}: {response.status_code}")

    if not leaderboard:
        print("El leaderboard está vacío.")
        await channel.send("No hay datos de SoloQ disponibles.")
        return

    leaderboard.sort(key=lambda x: x[3], reverse=True)
    embed = discord.Embed(title="Leaderboard de SoloQ", color=discord.Color.blue())

    for i, (summoner_name, league_info, discord_user, _) in enumerate(leaderboard):
        embed.add_field(name=f"{i+1}. {summoner_name}", value=f"{league_info} ({discord_user})", inline=False)

    await channel.send(embed=embed)

async def leaderboard_task():
    while True:
        now = datetime.datetime.now()
        target_time = datetime.datetime(now.year, now.month, now.day, 19, 0)  # 7 PM CDMX
        if now > target_time:
            target_time += datetime.timedelta(days=1)
        wait_time = (target_time - now).total_seconds()
        await asyncio.sleep(wait_time)
        await send_leaderboard()

@tree.command(name="leaderboard", description="Muestra el leaderboard de LP de los miembros vinculados", guild=discord.Object(id=GUILD_ID))
async def leaderboard(interaction: discord.Interaction):
    embed = discord.Embed(title="Leaderboard de SoloQ", description="Cargando...", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)
    await send_leaderboard()

@tree.command(name="cambiar_api_key", description="Modifica la API Key de Riot en el .env", guild=discord.Object(id=GUILD_ID))
async def cambiar_api_key(interaction: discord.Interaction, nueva_key: str):
    global RIOT_API_KEY
    RIOT_API_KEY = nueva_key
    set_key('.env', 'RIOT_API_KEY', nueva_key)
    await interaction.response.send_message("API Key actualizada correctamente.")

@tree.command(name="definir_canal", description="Define el canal para los mensajes automáticos", guild=discord.Object(id=GUILD_ID))
async def definir_canal(interaction: discord.Interaction, canal: discord.TextChannel):
    global channel_id
    channel_id = canal.id
    await interaction.response.send_message(f"Canal de mensajes automáticos definido en {canal.mention}")

@tree.command(name="help", description="Muestra los comandos disponibles", guild=discord.Object(id=GUILD_ID))
async def help_command(interaction: discord.Interaction):
    help_message = """
    **Comandos disponibles**:
    `/vincular <game_name> <tag_line>` - Vincula tu cuenta de League of Legends.
    `/leaderboard` - Muestra el leaderboard de LP.
    `/cambiar_api_key <nueva_key>` - Cambia la API Key de Riot.
    `/definir_canal <canal>` - Define el canal para mensajes automáticos.
    """
    await interaction.response.send_message(help_message)

@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Bot conectado como {client.user}")
    asyncio.create_task(leaderboard_task())

client.run(TOKEN)
