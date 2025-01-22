import discord
from discord import app_commands
import requests
import os
import asyncio
from account_storage import load_accounts, save_accounts
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Configuración
TOKEN = os.getenv('DISCORD_TOKEN')
RIOT_API_KEY = os.getenv('RIOT_API_KEY')
GUILD_ID = 214856862724521984  # Reemplaza con el ID de tu servidor

# Configurar intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Asegúrate de que el bot tenga permisos para obtener miembros

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Diccionario para almacenar cuentas vinculadas
file_path = 'linked_accounts.json'
player_accounts = load_accounts(file_path)

# Diccionario para asignar valores numéricos a las ligas y divisiones
rank_order = {
    "IRON": 1,
    "BRONZE": 2,
    "SILVER": 3,
    "GOLD": 4,
    "PLATINUM": 5,
    "EMERALD": 6,
    "DIAMOND": 7,
    "MASTER": 8,
    "GRANDMASTER": 9,
    "CHALLENGER": 10
}

division_order = {
    "IV": 1,
    "III": 2,
    "II": 3,
    "I": 4
}

def get_rank_value(tier, division, lp):
    if tier in ["MASTER", "GRANDMASTER", "CHALLENGER"]:
        return rank_order[tier] * 10000 + lp
    return rank_order[tier] * 10000 + division_order[division] * 1000 + lp

async def update_leaderboard_message(message):
    while True:
        leaderboard = []
        for user_id, account_info in player_accounts.items():
            puuid = account_info['puuid']
            summoner_name = account_info['summoner_name']

            # Consultar la API de Riot para obtener el summonerID usando el PUUID
            response = requests.get(
                f"https://la1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}",
                headers={"X-Riot-Token": RIOT_API_KEY}
            )
            if response.status_code == 200:
                summoner_data = response.json()
                summoner_id = summoner_data.get('id')

                # Obtener el usuario de Discord
                member = message.guild.get_member(int(user_id))
                discord_user = member.mention if member else f"<@{user_id}>"

                if summoner_id:
                    # Consultar la API de Riot para obtener los puntos de liga usando el summonerID
                    league_response = requests.get(
                        f"https://la1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}",
                        headers={"X-Riot-Token": RIOT_API_KEY}
                    )
                    if league_response.status_code == 200:
                        league_data = league_response.json()
                        # Filtrar SoloQ
                        soloq_data = next((entry for entry in league_data if entry['queueType'] == 'RANKED_SOLO_5x5'), None)
                        if soloq_data:
                            lp = soloq_data["leaguePoints"]
                            tier = soloq_data["tier"].capitalize()  # Ej: 'GOLD' -> 'Gold'
                            rank = soloq_data["rank"]  # División, ej: 'I', 'II'
                            league_info = f"{tier} {rank} {lp} LP"
                            rank_value = get_rank_value(tier.upper(), rank, lp)
                        else:
                            league_info = "Sin datos de SoloQ"
                            rank_value = 0
                        leaderboard.append((summoner_name, league_info, discord_user, rank_value))
                    else:
                        await message.channel.send(
                            f"Error al obtener datos de liga para {summoner_name}. Código de error: {league_response.status_code}"
                        )
                        return
                else:
                    await message.channel.send(f"No se encontró el `summonerId` para el PUUID: {puuid}.")
                    return
            else:
                await message.channel.send(
                    f"Error al obtener datos del invocador para el PUUID: {puuid}. Código de error: {response.status_code}"
                )
                return

        # Ordenar el leaderboard por rank_value
        leaderboard.sort(key=lambda x: x[3], reverse=True)

        # Crear el embed del leaderboard
        embed = discord.Embed(title="Leaderboard de SoloQ", color=discord.Color.blue())
        for i, (summoner_name, league_info, discord_user, _) in enumerate(leaderboard):
            embed.add_field(name=f"{i+1}. {summoner_name}", value=f"{league_info} ({discord_user})", inline=False)

        # Editar el mensaje con el nuevo embed
        await message.edit(embed=embed)

        # Esperar un tiempo antes de actualizar nuevamente (por ejemplo, cada 10 minutos)
        await asyncio.sleep(600)

# Comando para mostrar el leaderboard
@tree.command(
    name="leaderboard",
    description="Muestra el leaderboard de LP de los miembros vinculados",
    guild=discord.Object(id=GUILD_ID)
)
async def leaderboard(interaction: discord.Interaction):
    # Crear el embed inicial
    embed = discord.Embed(title="Leaderboard de SoloQ", description="Cargando...", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    # Iniciar la tarea de actualización del leaderboard
    asyncio.create_task(update_leaderboard_message(message))

# Comando de ayuda personalizado
@tree.command(
    name="help",
    description="Muestra los comandos disponibles",
    guild=discord.Object(id=GUILD_ID)
)
async def help_command(interaction: discord.Interaction):
    help_message = """
    **Comandos disponibles**:
    `/vincular <game_name> <tag_line>`: Vincula tu cuenta de League of Legends usando Riot ID.
    `/leaderboard`: Muestra el leaderboard de LP de los miembros vinculados.
    """
    await interaction.response.send_message(help_message)

# Comando para vincular cuentas
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
        puuid = account_data['puuid']
        user_id = str(interaction.user.id)
        player_accounts[user_id] = {'puuid': puuid, 'summoner_name': game_name}
        save_accounts(file_path, player_accounts)
        await interaction.response.send_message(f"Cuenta {game_name}#{tag_line} vinculada correctamente.")
    else:
        await interaction.response.send_message(f"Error al vincular la cuenta {game_name}#{tag_line}. Código de error: {response.status_code}")

@client.event
async def on_ready():
    # Sincronizar los comandos con la guild sin eliminarlos
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Bot conectado como {client.user}")

# Iniciar el bot
client.run(TOKEN)
