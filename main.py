import logging
import threading
import time

import telebot

import config  # Settings file with BOT_TOKEN and ADMIN_ID
from b3sitechecker import check_site_card_form, get_base_url  # Your checker logic module

bot = telebot.TeleBot(config.BOT_TOKEN)


def extract_url_from_message(text: str):
    """Extract URL from the command text."""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return None
    raw = parts[1].strip()
    return extract_site_token(raw)


def extract_site_token(raw: str) -> str:
    """
    Extract a clean site token from a line that may contain extra text.
    Examples:
      "jewelryexchange.com ==> [Payment Methods: ...]" -> "jewelryexchange.com"
      "https://shop.example.com path"                  -> "https://shop.example.com"
    """
    if not raw:
        return raw

    # First split on '==>' if present, keep the left part
    if "==>" in raw:
        raw = raw.split("==>", 1)[0].strip()

    # Then take the first whitespace-separated token
    token = raw.split()[0].strip()
    return token


def is_admin(user_id) -> bool:
    """Check if user is admin (ID is stored as string in config)."""
    return str(user_id) == str(config.ADMIN_ID)


@bot.message_handler(commands=["start"])
def handle_start(message):
    bot.reply_to(
        message,
        "Welcome!\n"
        "- Use /check <site_url> to check if /my-account/ has a REGISTER section.\n"
        "- Send me a text file (.txt) with one site per line to scan a list.",
    )


@bot.message_handler(commands=["help"])
def handle_help(message):
    help_msg = (
        "Commands:\n"
        "/check <site_url> - check if /my-account/ shows a registration section on a single site.\n"
        "File mode (admin only):\n"
        " - Send a .txt file with one site per line (e.g. https://example.com or example.com/path)\n"
        "I will extract the base URLs and check /my-account/ for a registration section. "
        "If found, I will send you the base URL of the site."
    )
    bot.reply_to(message, help_msg)


@bot.message_handler(commands=["check"])
def handle_check_command(message):
    url = extract_url_from_message(message.text)
    if not url:
        bot.reply_to(message, "Usage: /check <site_url>")
        return
    
    # Send initial "Start checking..." message and get message_id for editing
    status_msg = bot.send_message(message.chat.id, "Start checking...")
    message_id = status_msg.message_id

    # Run checker in a separate thread to avoid blocking bot
    thread = threading.Thread(target=run_site_check, args=(message.chat.id, url, message_id))
    thread.daemon = True
    thread.start()


def run_site_check(chat_id, url: str, message_id: int):
    start_time = time.time()
    
    try:
        result = check_site_card_form(url)
        
        # Calculate execution time
        elapsed_time = time.time() - start_time
        time_str = f"{elapsed_time:.2f}s"
        
        base = result.get("base_url", url)
        
        # Detect country from domain
        from b3sitechecker import detect_country_from_domain
        country_code = detect_country_from_domain(base)
        
        # Check if registration succeeded
        registration_succeeded = result.get("register_found") and "ACCOUNT CREATED" in result.get("details", "")
        
        # Get Braintree info
        braintree_info = result.get("braintree_info", {})
        has_braintree = braintree_info.get("has_braintree", False) if braintree_info else False
        braintree_type = braintree_info.get("braintree_type", "none") if braintree_info else "none"
        
        # Check for captcha
        captcha_status = "Yes" if result.get("has_captcha", False) else "No"
        if captcha_status == "No" and result.get("register_found"):
            details = result.get("details", "").lower()
            if "captcha" in details or "recaptcha" in details or "reCAPTCHA" in details:
                captcha_status = "Yes"
        
        # Get payment result if available
        payment_result = result.get("payment_result", {})
        payment_message = payment_result.get("message", "") if payment_result else ""
        
        # If registration failed, set Type and Site response to None
        if result.get("register_found") and not registration_succeeded:
            # Registration failed - show Braintree and Capcha if detected, but Type and Site response are None
            braintree_status = "Yes" if has_braintree else "No"
            type_str = "None"  # Always None if registration failed
            site_response = "None"  # Always None if registration failed
        elif payment_result and payment_message:
            # Payment method was added/attempted - use payment result message
            # Use payment result type if available, otherwise use braintree_info type
            if payment_result.get("braintree_type"):
                braintree_type = payment_result.get("braintree_type", "none")
            
            braintree_status = "Yes" if braintree_type != "none" else "No"
            type_str = braintree_type if braintree_type != "none" else "None"
            captcha_status = "Yes" if result.get("has_captcha", False) else "No"
            # Use payment result message (e.g., "Payment method successfully added")
            site_response = payment_message
        elif registration_succeeded:
            # Registration succeeded but payment method not added (or no payment_result)
            braintree_info = result.get("braintree_info", {})
            has_braintree = braintree_info.get("has_braintree", False) if braintree_info else False
            braintree_type = braintree_info.get("braintree_type", "none") if braintree_info else "none"
            
            braintree_status = "Yes" if has_braintree else "No"
            type_str = braintree_type if braintree_type != "none" else "None"
            captcha_status = "Yes" if result.get("has_captcha", False) else "No"
            site_response = "Account created"
        else:
            # No registration form found
            braintree_info = result.get("braintree_info", {})
            has_braintree = braintree_info.get("has_braintree", False) if braintree_info else False
            braintree_type = braintree_info.get("braintree_type", "none") if braintree_info else "none"
            
            braintree_status = "Yes" if has_braintree else "No"
            type_str = braintree_type if braintree_type != "none" else "None"
            captcha_status = "Yes" if result.get("has_captcha", False) else "No"
            site_response = "None"
        
        # Build final message
        msg = (
            f"Site: <code>{base}</code>\n"
            f"Braintree: {braintree_status}\n"
            f"Country: {country_code}\n"
            f"Capcha: {captcha_status}\n"
            f"Type: {type_str}\n"
            f"Site response: {site_response}\n"
            f"Time: {time_str}"
        )
        
        # Edit the message with final result
        try:
            bot.edit_message_text(msg, chat_id, message_id, parse_mode="HTML")
        except Exception as edit_error:
            # If edit fails (e.g., message not modified), send new message
            if "message is not modified" not in str(edit_error).lower():
                bot.send_message(chat_id, msg, parse_mode="HTML")
        
    except Exception as e:
        logging.exception(f"Error checking site: {url}")
        elapsed_time = time.time() - start_time
        # Detect country even on error
        from b3sitechecker import detect_country_from_domain
        country_code = detect_country_from_domain(url)
        
        error_msg = (
            f"Site: <code>{url}</code>\n"
            f"Braintree: No\n"
            f"Country: {country_code}\n"
            f"Capcha: No\n"
            f"Type: None\n"
            f"Site response: None\n"
            f"Time: {elapsed_time:.2f}s"
        )
        try:
            bot.edit_message_text(error_msg, chat_id, message_id, parse_mode="HTML")
        except Exception:
            bot.send_message(chat_id, error_msg, parse_mode="HTML")


@bot.message_handler(content_types=["document"])
def handle_sites_file(message):
    """Handle uploaded file with list of sites (admin only)."""
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "This feature is restricted to admin.")
        return

    doc = message.document
    if not doc.file_name.lower().endswith(".txt"):
        bot.reply_to(message, "Please send a .txt file with one site URL per line.")
        return

    try:
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
        content = downloaded.decode("utf-8", errors="ignore")
    except Exception as e:
        logging.exception("Failed to download file from Telegram")
        bot.reply_to(message, f"Failed to read file: {str(e)}")
        return

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        bot.reply_to(message, "The file is empty or contains only blank lines.")
        return

    # Create inline keyboard with counters
    from telebot import types
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("Good sites (0)", callback_data="counter_good"),
        types.InlineKeyboardButton("To check site (0)", callback_data="counter_check")
    )
    keyboard.add(
        types.InlineKeyboardButton("Not B3 (0)", callback_data="counter_notb3")
    )
    
    # Send initial message with inline buttons
    status_msg = bot.reply_to(
        message,
        f"Start checking...\nReceived {len(lines)} sites.",
        reply_markup=keyboard
    )
    message_id = status_msg.message_id

    # Run mass check in separate thread
    thread = threading.Thread(target=run_mass_check, args=(message.chat.id, message_id, lines))
    thread.daemon = True
    thread.start()


def update_counters_message(chat_id: int, message_id: int, counters: dict):
    """Update the message with current counters."""
    from telebot import types
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton(f"Good sites ({counters['good_sites']})", callback_data="counter_good"),
        types.InlineKeyboardButton(f"To check site ({counters['to_check_sites']})", callback_data="counter_check")
    )
    keyboard.add(
        types.InlineKeyboardButton(f"Not B3 ({counters['not_b3_sites']})", callback_data="counter_notb3")
    )
    
    try:
        bot.edit_message_reply_markup(chat_id, message_id, reply_markup=keyboard)
    except Exception as e:
        # Ignore edit errors (message not modified, etc.)
        pass


def run_mass_check(chat_id: int, message_id: int, lines: list[str]):
    """Run mass check using mass_chk.py with 5 workers."""
    from mass_chk import MassChecker
    
    checker = MassChecker(num_workers=5)
    checker.set_callback(lambda cid, mid, cnt: update_counters_message(cid, mid, cnt))
    
    # Process all sites
    results = checker.process_sites(chat_id, message_id, lines)
    
    # Send "Good sites" results
    for result in results["good_sites"]:
        msg = (
            f"Site: <code>{result['site']}</code>\n"
            f"Braintree: {result['braintree']}\n"
            f"Country: {result['country']}\n"
            f"Capcha: {result['captcha']}\n"
            f"Type: {result['type']}\n"
            f"Site response: {result['response']}\n"
            f"Time: {result['time']}"
        )
        # Send to user
        bot.send_message(chat_id, msg, parse_mode="HTML")
        # Forward to channel if configured
        if hasattr(config, 'CHANNEL_ID') and config.CHANNEL_ID:
            try:
                bot.send_message(config.CHANNEL_ID, msg, parse_mode="HTML")
            except Exception as e:
                logging.exception(f"Failed to forward good site to channel: {e}")
    
    # Send "To check site" results with same format
    for result in results["to_check_sites"]:
        msg = (
            f"Site: <code>{result['site']}</code>\n"
            f"Braintree: {result['braintree']}\n"
            f"Country: {result['country']}\n"
            f"Capcha: {result['captcha']}\n"
            f"Type: {result['type']}\n"
            f"Site response: {result['response']}\n"
            f"Time: {result['time']}"
        )
        # Send to user
        bot.send_message(chat_id, msg, parse_mode="HTML")
        # Forward to channel if configured
        if hasattr(config, 'CHANNEL_ID') and config.CHANNEL_ID:
            try:
                bot.send_message(config.CHANNEL_ID, msg, parse_mode="HTML")
            except Exception as e:
                logging.exception(f"Failed to forward to_check site to channel: {e}")
    
    # Update final message
    from telebot import types
    final_keyboard = types.InlineKeyboardMarkup()
    final_keyboard.add(
        types.InlineKeyboardButton(f"Good sites ({checker.counters['good_sites']})", callback_data="counter_good"),
        types.InlineKeyboardButton(f"To check site ({checker.counters['to_check_sites']})", callback_data="counter_check")
    )
    final_keyboard.add(
        types.InlineKeyboardButton(f"Not B3 ({checker.counters['not_b3_sites']})", callback_data="counter_notb3")
    )
    
    total_checked = checker.counters['good_sites'] + checker.counters['to_check_sites'] + checker.counters['not_b3_sites']
    final_msg = (
        f"✅ Finished checking {total_checked} sites.\n"
        f"Good sites: {checker.counters['good_sites']}\n"
        f"To check: {checker.counters['to_check_sites']}\n"
        f"Not B3: {checker.counters['not_b3_sites']}"
    )
    
    try:
        bot.edit_message_text(final_msg, chat_id, message_id, reply_markup=final_keyboard)
    except Exception:
        bot.send_message(chat_id, final_msg, reply_markup=final_keyboard)


if __name__ == "__main__":
    print("Telegram bot is running...")
    bot.infinity_polling()
