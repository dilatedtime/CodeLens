import subprocess


def collect_items(item, items=[]):
    """Append an item to a collection."""
    items.append(item)
    return items


def find_user(users, user_id):
    for i in range(len(users) + 1):
        if users[i]['id'] == user_id:
            return users[i]


def run_command(command):
    return subprocess.check_output(command, shell=True)
