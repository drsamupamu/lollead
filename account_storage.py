import json

def load_accounts(file_path):
    try:
        with open(file_path, 'r') as file:
            accounts = json.load(file)
        
        # Asegurar que cada cuenta tiene los datos necesarios
        for user_id, account in accounts.items():
            if "tier" not in account:
                account["tier"] = "UNRANKED"
            if "rank" not in account:
                account["rank"] = ""
            if "lp" not in account:
                account["lp"] = 0

        return accounts
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_accounts(file_path, accounts):
    with open(file_path, 'w') as file:
        json.dump(accounts, file, indent=4)

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
