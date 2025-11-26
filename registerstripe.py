import requests
import random
import string
from fake_useragent import UserAgent

REGISTER_URL = "(site base url)/my-account/"
PAYMENT_URL = "(site base url)/my-account/add-payment-method/"


def generate_random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_random_email():
    return f"{generate_random_string()}@gmail.com"

def generate_random_username():
    return f"user_{generate_random_string(8)}"

def register_new_account():
    """Registers a new account with a random username and email, using a new session each time."""
    session = requests.Session()
    user_agent = UserAgent().random
    headers = {"User-Agent": user_agent, "Referer": REGISTER_URL}

    email = generate_random_email()
    username = generate_random_username()
    
    data = {
        "email": email,
        "username": username
    }

    try:
        response = session.post(REGISTER_URL, headers=headers, data=data)
        if response.status_code == 200:
            print(f"[+] Registered new account: {email} | {username}")
            return session
        else:
            print(f"[-] Registration failed: {response.text}")
            return None
    except Exception as e:
        print(f"Error during registration: {e}")
        return None

