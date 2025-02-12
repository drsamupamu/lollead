import json

notification_channel_id = None  # 👈 Variable global

def load_accounts(file_path):
    global notification_channel_id
    try:
        with open(file_path, 'r') as file:
            accounts = json.load(file)

        # Si hay un canal de notificaciones, cargarlo en la variable global y eliminarlo del diccionario
        notification_channel_id = accounts.pop("notification_channel_id", None)

        return accounts
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_accounts(file_path, accounts):
    global notification_channel_id
    # Guardar el canal de notificaciones por separado
    data_to_save = accounts.copy()
    if notification_channel_id:
        data_to_save["notification_channel_id"] = notification_channel_id

    with open(file_path, 'w') as file:
        json.dump(data_to_save, file, indent=4)

def load_accounts(file_path):
    try:
        with open(file_path, 'r') as file:
            accounts = json.load(file)

        # Cargar el canal de notificaciones si existe
        global notification_channel_id
        notification_channel_id = accounts.get("notification_channel_id", None)

        # Asegurar que cada cuenta tenga los datos necesarios sin sobrescribir los existentes
        for user_id, account in accounts.items():
            if user_id == "notification_channel_id":  # No tocar la configuración del canal
                continue
            account.setdefault("tier", "UNRANKED")
            account.setdefault("rank", "")
            account.setdefault("lp", 0)

        return accounts
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# Uso de ejemplo
file_path = 'linked_accounts.json'
player_accounts = load_accounts(file_path)

# Guardar cuentas cuando sea necesario
save_accounts(file_path, player_accounts)
