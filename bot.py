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

# Función que actualizará el leaderboard y verificará cambios de división
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

                # Consultar la API de Riot para obtener los puntos de liga usando el summonerID
                league_response = requests.get(
                    f"https://la1.api.riotgames.com/lol/league/v4/entries/by-summoner/{summoner_id}",
                    headers={"X-Riot-Token": RIOT_API_KEY}
                )
                if league_response.status_code == 200:
                    league_data = league_response.json()
                    soloq_data = next((entry for entry in league_data if entry['queueType'] == 'RANKED_SOLO_5x5'), None)
                    if soloq_data:
                        leaderboard.append({
                            'summoner_name': summoner_name,
                            'tier': soloq_data['tier'],
                            'rank': soloq_data['rank'],
                            'league_points': soloq_data['leaguePoints']
                        })
                    else:
                        print(f"No se encontraron datos de SoloQ para {summoner_name}.")
                else:
                    print(f"Error al obtener datos de liga para {summoner_name}. Código de error: {league_response.status_code}")
            else:
                print(f"Error al obtener datos del invocador para el PUUID: {puuid}. Código de error: {response.status_code}")

        # Ordenar el leaderboard por puntos de liga
        leaderboard.sort(key=lambda x: x['league_points'], reverse=True)

        # Crear el embed del leaderboard
        embed = discord.Embed(title="Leaderboard de SoloQ", color=discord.Color.blue())
        for entry in leaderboard:
            embed.add_field(name=entry['summoner_name'], value=f"{entry['tier']} {entry['rank']} - {entry['league_points']} LP", inline=False)

        # Editar el mensaje original con el nuevo embed
        try:
            await message.edit(embed=embed)
            print("Embed actualizado correctamente.")
        except discord.errors.NotFound:
            print("No se encontró el mensaje. Deteniendo la actualización del leaderboard.")
            break
        except Exception as e:
            print(f"Error al actualizar el mensaje: {e}")
            break

        # Esperar un tiempo antes de actualizar nuevamente
        await asyncio.sleep(600)  # Actualizar cada 10 minutos

# Comando para mostrar el leaderboard
@tree.command(
    name="leaderboard",
    description="Muestra el leaderboard de LP de los miembros vinculados",
    guild=discord.Object(id=GUILD_ID)
)
async def leaderboard(interaction: discord.Interaction):
    # Crear el embed inicial
    embed = discord.Embed(title="Leaderboard de SoloQ", description="Cargando...", color=discord.Color.blue())
    message = None
    try:
        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
    except discord.errors.NotFound:
        await interaction.followup.send("La interacción ha expirado. Por favor, intenta de nuevo.")
        return
    except Exception as e:
        print(f"Error al enviar el mensaje: {e}")
        return

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
    `/set_channel <canal>`: Configura el canal donde se enviarán las actualizaciones de subida y bajada de división.
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

# Iniciar el bot
client.run(TOKEN)
