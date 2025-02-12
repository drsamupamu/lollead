import discord
from discord import app_commands
import requests
import os
import asyncio
import datetime
from account_storage import load_accounts, save_accounts
from urllib.parse import quote_plus
from dotenv import load_dotenv, set_key
import time
import json

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
notification_channel_id = None  # Inicializa la variable correctamente
TEMPLATES_FILE = "embed_templates.json"

def load_embed_templates():
    try:
        with open(TEMPLATES_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        print("⚠️ No se encontró el archivo de templates o tiene errores. Usando valores predeterminados.")
        return {}  # Devuelve un diccionario vacío si hay un error

embed_templates = load_embed_templates()


def get_rank_value(tier, division, lp):
    if tier in ["MASTER", "GRANDMASTER", "CHALLENGER"]:
        return rank_order[tier] * 10000 + lp
    return rank_order[tier] * 10000 + division_order[division] * 1000 + lp

async def send_leaderboard(interaction=None):
    global notification_channel_id

    if notification_channel_id is None:
        print("⚠️ No se ha definido un canal para los mensajes automáticos.")
        if interaction:
            await interaction.response.send_message("⚠️ No se ha definido un canal para los mensajes automáticos.", ephemeral=True)
        return
    
    guild = client.get_guild(GUILD_ID)
    channel = guild.get_channel(notification_channel_id)

    if not channel:
        print("⚠️ El canal definido no es válido.")
        if interaction:
            await interaction.response.send_message("⚠️ El canal definido no es válido.", ephemeral=True)
        return

    # 🛠️ Filtrar jugadores válidos
    valid_players = {
        str(user_id): info for user_id, info in player_accounts.items()
        if isinstance(info, dict) and "lp" in info and "tier" in info and "rank" in info
    }

    if not valid_players:
        await channel.send("⚠️ No hay datos de SoloQ disponibles.")
        return

    # 📊 Ordenar primero por rango y luego por LP
    sorted_players = sorted(valid_players.items(), key=lambda x: (
        rank_order.get(x[1]["tier"].upper(), 0),
        division_order.get(x[1]["rank"], 0),
        x[1]["lp"]
    ), reverse=True)

    embeds = []

    for i, (user_id, account_info) in enumerate(sorted_players):
        try:
            member = guild.get_member(int(user_id))
            if member is None:
                await asyncio.sleep(1)  # Evitar rate limits
                member = await guild.fetch_member(int(user_id))  
            
            discord_user = f"**{member.mention}**" if member else "**@Jugador Desconocido**"
            avatar_url = member.display_avatar.url if member else None
        except Exception as e:
            print(f"⚠️ Error obteniendo miembro {user_id}: {e}")
            discord_user = "**@Jugador Desconocido**"
            avatar_url = None

        tier = account_info.get("tier", "UNRANKED")
        rank = account_info.get("rank", "")
        lp = account_info.get("lp", 0)
        summoner_name = account_info.get("summoner_name", "Desconocido")

        # 🔹 Crear embed por jugador
        embed = discord.Embed(
            title=f"🏆 #{i+1}",
            description=f"{discord_user}\n\n**{tier} {rank}** - {lp} LP\n🎮 **Nick:** {summoner_name}",
            color=discord.Color.blue()
        )

        if avatar_url:
            embed.set_thumbnail(url=avatar_url)  # 📷 Foto de perfil del usuario

        embeds.append(embed)

    # 🚀 Enviar todos los embeds en un solo mensaje (máximo 10 por mensaje)
    for i in range(0, len(embeds), 10):
        if interaction:
            await interaction.response.defer()
            await interaction.followup.send(embeds=embeds[i:i+10])  
        else:
            await channel.send(embeds=embeds[i:i+10])

    print("✅ Leaderboard enviado con éxito.")

async def leaderboard_task():
    while True:
        now = datetime.datetime.now()
        target_time = datetime.datetime(now.year, now.month, now.day, 19, 0)  # 7 PM CDMX
        if now > target_time:
            target_time += datetime.timedelta(days=1)
        
        wait_time = (target_time - now).total_seconds()
        print(f"⏳ Esperando {wait_time} segundos para enviar el leaderboard automático.")  # 👈 Depuración
        
        await asyncio.sleep(wait_time)
        print("🚀 Enviando leaderboard automático...")  # 👈 Mensaje cuando se ejecuta
        await send_leaderboard()

async def rank_update_task():
    global notification_channel_id
    await client.wait_until_ready()

    while not client.is_closed():
        guild = client.get_guild(GUILD_ID)
        channel = guild.get_channel(notification_channel_id) if notification_channel_id else None

        if not channel:
            print("⚠️ No se ha definido un canal para notificaciones de rango.")
            await asyncio.sleep(60)
            continue

        for user_id, account_info in list(player_accounts.items()):
            if not isinstance(account_info, dict):
                continue

            puuid = account_info.get("puuid")
            summoner_name = account_info.get("summoner_name")

            try:
                response = requests.get(
                    f"https://la1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}",
                    headers={"X-Riot-Token": RIOT_API_KEY},
                    timeout=5
                )
                if response.status_code != 200:
                    continue

                summoner_data = response.json()
                summoner_id = summoner_data.get("id")

                league_response = requests.get(
                    f"https://la1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}",
                    headers={"X-Riot-Token": RIOT_API_KEY},
                    timeout=5
                )
                if league_response.status_code != 200:
                    continue

                league_data = league_response.json()
                soloq_data = next((entry for entry in league_data if entry["queueType"] == "RANKED_SOLO_5x5"), None)

                if soloq_data:
                    new_tier = soloq_data["tier"]
                    new_rank = soloq_data["rank"]
                    new_lp = soloq_data["leaguePoints"]
                    old_tier = account_info.get("tier", "UNRANKED")
                    old_rank = account_info.get("rank", "")
                    old_lp = account_info.get("lp", 0)

                    discord_user = f"<@{user_id}>"

                    if new_tier != old_tier or new_rank != old_rank:
                        embed = discord.Embed(
                            title=embed_templates["rank_up"]["title"],
                            color=getattr(discord.Color, embed_templates["rank_up"]["color"])(),
                            description=embed_templates["rank_up"]["description"].format(
                                discord_user=discord_user, new_tier=new_tier, new_rank=new_rank, new_lp=new_lp
                            )
                        )
                        await channel.send(embed=embed)

                    elif new_lp < old_lp:
                        embed = discord.Embed(
                            title=embed_templates["rank_down"]["title"],
                            color=getattr(discord.Color, embed_templates["rank_down"]["color"])(),
                            description=embed_templates["rank_down"]["description"].format(
                                discord_user=discord_user, new_tier=new_tier, new_rank=new_rank, new_lp=new_lp
                            )
                        )
                        await channel.send(embed=embed)

                    player_accounts[user_id]["tier"] = new_tier
                    player_accounts[user_id]["rank"] = new_rank
                    player_accounts[user_id]["lp"] = new_lp

            except requests.exceptions.RequestException:
                await asyncio.sleep(10)

        save_accounts(file_path, player_accounts)
        await asyncio.sleep(60)

@tree.command(name="test_embed", description="Prueba enviar un embed", guild=discord.Object(id=GUILD_ID))
async def test_embed(interaction: discord.Interaction):
    embed = discord.Embed(title="Embed de prueba", description="Esto es un mensaje de prueba.", color=discord.Color.green())
    embed.add_field(name="Jugador", value="Ejemplo", inline=False)
    await interaction.response.send_message(embed=embed)


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

@tree.command(
    name="definir_canal_notificaciones",
    description="Define el canal donde se enviarán las notificaciones de cambios de rango",
    guild=discord.Object(id=GUILD_ID)
)
async def definir_canal_notificaciones(interaction: discord.Interaction, canal: discord.TextChannel):
    await interaction.response.defer()

    global notification_channel_id
    notification_channel_id = canal.id  # 👈 Guardamos en la variable global

    # Guardamos en el JSON correctamente
    player_accounts["notification_channel_id"] = notification_channel_id
    save_accounts(file_path, player_accounts)

    await interaction.followup.send(f"✅ Canal de notificaciones definido en {canal.mention}")

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
    global notification_channel_id

    # Cargar el canal de notificaciones desde JSON si existe
    notification_channel_id = player_accounts.get("notification_channel_id", None)

    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Bot conectado como {client.user}")
    asyncio.create_task(leaderboard_task())
    asyncio.create_task(rank_update_task())


@tree.command(
    name="vincular",
    description="Vincula tu cuenta de League of Legends usando Riot ID",
    guild=discord.Object(id=GUILD_ID)
)
async def vincular(interaction: discord.Interaction, game_name: str, tag_line: str):
    # Codificar el nombre del juego y la línea de etiqueta
    encoded_game_name = quote_plus(game_name)
    encoded_tag_line = quote_plus(tag_line)

    # Consultar la API de Riot para obtener el PUUID usando el nombre y tag
    response = requests.get(
        f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{encoded_game_name}/{encoded_tag_line}",
        headers={"X-Riot-Token": RIOT_API_KEY}
    )
    if response.status_code == 200:
        account_data = response.json()
        puuid = account_data.get('puuid')
        summoner_name = account_data.get('gameName')

        # Guardar la cuenta vinculada en el diccionario
        player_accounts[interaction.user.id] = {
            'puuid': puuid,
            'summoner_name': summoner_name
        }
        save_accounts(file_path, player_accounts)

        await interaction.response.send_message(f"Cuenta vinculada correctamente: {summoner_name}")
    else:
        await interaction.response.send_message("Error al vincular la cuenta. Por favor, verifica tu Riot ID y vuelve a intentarlo.")
client.run(TOKEN)