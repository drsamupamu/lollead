import json

def load_accounts(file_path):
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def save_accounts(file_path, accounts):
    with open(file_path, 'w') as file:
        json.dump(accounts, file, indent=4)

# Usage example
file_path = 'linked_accounts.json'
player_accounts = load_accounts(file_path)

# Save accounts when needed
save_accounts(file_path, player_accounts)