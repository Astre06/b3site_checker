

import json
import re
import requests


class BraintreeCreditCardError(Exception):
    """Custom error for the braintree_credit_card gateway."""


SESSION_TIMEOUT = 20


def _get_session(existing: requests.Session | None = None) -> requests.Session:
    """Return an existing requests.Session or create a new one."""
    return existing or requests.Session()


def fetch_checkout_page(session: requests.Session, base_url: str, proxies=None, headers=None) -> tuple[str, str]:
    """
    GET the WooCommerce checkout page.

    Returns (html_text, final_url).
    """
    url = f"{base_url.rstrip('/')}/checkout"
    resp = session.get(url, headers=headers, proxies=proxies, timeout=SESSION_TIMEOUT, verify=False)
    resp.raise_for_status()
    return resp.text, resp.url


def parse_checkout_nonces(checkout_html: str) -> dict:
    """
    Extract important WooCommerce/Braintree fields from the checkout HTML:
      - woocommerce-process-checkout-nonce
      - client_token_nonce for braintree_credit_card
      - address_validation_nonce (if present)
    """
    checkout_nonce = None
    client_token_nonce = None
    address_validation_nonce = None

    m = re.search(
        r'id="woocommerce-process-checkout-nonce"[^>]*value="([^"]+)"',
        checkout_html,
    )
    if m:
        checkout_nonce = m.group(1)

    m = re.search(r'"type":"credit_card","client_token_nonce":"([^"]+)"', checkout_html)
    if m:
        client_token_nonce = m.group(1)

    m = re.search(r'"address_validation_nonce":\s*"([^"]+)"', checkout_html)
    if m:
        address_validation_nonce = m.group(1)

    return {
        "checkout_nonce": checkout_nonce,
        "client_token_nonce": client_token_nonce,
        "address_validation_nonce": address_validation_nonce,
    }


def get_braintree_client_token(
    session: requests.Session,
    base_url: str,
    client_token_nonce: str,
    proxies=None,
    headers=None,
) -> dict:
    """
    Call admin-ajax.php?action=wc_braintree_credit_card_get_client_token
    and return the decoded JSON object containing authorizationFingerprint.
    """
    url = f"{base_url.rstrip('/')}/wp-admin/admin-ajax.php"
    data = {"action": "wc_braintree_credit_card_get_client_token", "nonce": client_token_nonce}
    resp = session.post(url, data=data, headers=headers, proxies=proxies, timeout=SESSION_TIMEOUT, verify=False)
    resp.raise_for_status()

    try:
        payload = resp.json()
    except Exception as e:  # defensive
        raise BraintreeCreditCardError(f"Client token response is not JSON: {resp.text[:200]}") from e

    if not isinstance(payload, dict) or not payload.get("success"):
        raise BraintreeCreditCardError(f"Failed to get client token: {payload}")

    # Woo plugin usually returns base64 JSON string in 'data'
    data_field = payload.get("data")
    if not isinstance(data_field, str):
        raise BraintreeCreditCardError(f"Unexpected client token data format: {type(data_field)}")

    try:
        decoded_bytes = requests.utils.unquote_to_bytes(data_field)
        decoded_json = json.loads(decoded_bytes.decode("utf-8"))
    except Exception as e:  # defensive
        raise BraintreeCreditCardError(f"Failed to decode client token data: {data_field[:200]}") from e

    return decoded_json


def tokenize_card_via_graphql(
    session: requests.Session,
    bearer_token: str,
    card: tuple[str, str, str, str],
    billing_zip: str,
    billing_street: str,
    proxies=None,
) -> str:
    """
    Tokenize card via Braintree GraphQL.

    card = (number, exp_month, exp_year, cvv)
    Returns payment nonce string.
    """
    number, exp_m, exp_y, cvv = card

    url = "https://payments.braintree-api.com/graphql"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Braintree-Version": "2018-05-10",
        "Content-Type": "application/json",
        "Origin": "https://assets.braintreegateway.com",
        "Referer": "https://assets.braintreegateway.com/",
    }
    payload = {
        "clientSdkMetadata": {
            "source": "client",
            "integration": "custom",
            "sessionId": "python-session",
        },
        "query": (
            "mutation TokenizeCreditCard($input: TokenizeCreditCardInput!) {"
            "  tokenizeCreditCard(input: $input) {"
            "    token"
            "  }"
            "}"
        ),
        "variables": {
            "input": {
                "creditCard": {
                    "number": number,
                    "expirationMonth": exp_m,
                    "expirationYear": exp_y,
                    "cvv": cvv,
                    "billingAddress": {
                        "postalCode": billing_zip,
                        "streetAddress": billing_street,
                    },
                },
                "options": {"validate": False},
            }
        },
        "operationName": "TokenizeCreditCard",
    }
    resp = session.post(url, headers=headers, json=payload, proxies=proxies, timeout=SESSION_TIMEOUT, verify=False)
    resp.raise_for_status()
    j = resp.json()
    try:
        token = j["data"]["tokenizeCreditCard"]["token"]
    except Exception as e:  # defensive
        raise BraintreeCreditCardError(f"Failed to tokenize card: {j}") from e
    return token


def call_wc_ajax_checkout(
    session: requests.Session,
    base_url: str,
    billing: dict,
    checkout_nonce: str,
    card_brand: str,
    card_nonce: str,
    country: str = "US",
    proxies=None,
) -> tuple[dict, str]:
    """
    POST to ?wc-ajax=checkout with billing + braintree_credit_card fields.

    This is the same internal flow WooCommerce uses when you are on
    `/my-account/add-payment-method/` with the `braintree_credit_card` gateway:
    it submits a checkout-like request with zero/verification amount to save
    the card as a payment method.

    Returns:
      (raw_json_dict, messages_text_without_html)
    """
    url = f"{base_url.rstrip('/')}/?wc-ajax=checkout"
    data = {
        "billing_first_name": billing["first_name"],
        "billing_last_name": billing["last_name"],
        "billing_company": billing.get("company", ""),
        "billing_country": country,
        "billing_address_1": billing["address_1"],
        "billing_address_2": billing.get("address_2", ""),
        "billing_city": billing["city"],
        "billing_state": billing["state"],
        "billing_postcode": billing["zip"],
        "billing_phone": billing["phone"],
        "billing_email": billing["email"],
        "payment_method": "braintree_credit_card",
        "wc-braintree-credit-card-card-type": card_brand,
        "wc_braintree_credit_card_payment_nonce": card_nonce,
        "terms": "on",
        "terms-field": 1,
        "woocommerce-process-checkout-nonce": checkout_nonce,
        "_wp_http_referer": "/?wc-ajax=update_order_review",
    }
    resp = session.post(url, data=data, proxies=proxies, timeout=SESSION_TIMEOUT, verify=False)
    resp.raise_for_status()

    raw = resp.text
    # Remove any stray <script> blocks then decode JSON
    cleaned = re.sub(r"<script\b[^>]*>.*?</script>", "", raw, flags=re.I | re.S)
    payload = json.loads(cleaned)

    messages_html = payload.get("messages", "")
    # Strip HTML tags and normalise whitespace
    from bs4 import BeautifulSoup

    text = BeautifulSoup(messages_html, "html.parser").get_text(" ", strip=True)
    return payload, text


def process_braintree_credit_card(
    base_url: str,
    card: tuple[str, str, str, str],
    billing: dict,
    country: str = "US",
    proxies=None,
    session: requests.Session | None = None,
) -> tuple[str, dict]:
    """
    High-level gateway wrapper for sites using payment_method=braintree_credit_card.

    Flow:
      1. Load `/checkout`, extract `woocommerce-process-checkout-nonce` and
         `client_token_nonce`.
      2. Call `admin-ajax.php?action=wc_braintree_credit_card_get_client_token`
         to obtain the client token / authorizationFingerprint.
      3. Tokenize the card via Braintree GraphQL (no validation).
      4. POST to `?wc-ajax=checkout` with the token + billing data so WooCommerce
         can run its "add payment method" flow for this gateway.

    This mirrors how the add‑payment‑method button works on these sites. It does
    not select cart products or totals itself; the amount/behaviour is decided
    by the WooCommerce/Braintree plugin (often zero or small verification).

    Returns:
      (message_text_from_site, info_dict_with_token_and_metadata)
    """
    sess = _get_session(session)

    checkout_html, _ = fetch_checkout_page(sess, base_url, proxies=proxies)
    nonces = parse_checkout_nonces(checkout_html)

    if not nonces["checkout_nonce"] or not nonces["client_token_nonce"]:
        raise BraintreeCreditCardError("Missing checkout or client_token nonce in checkout HTML")

    client_token_obj = get_braintree_client_token(
        sess,
        base_url,
        nonces["client_token_nonce"],
        proxies=proxies,
    )

    bearer = client_token_obj.get("authorizationFingerprint")
    if not bearer:
        raise BraintreeCreditCardError("authorizationFingerprint not found in client token data")

    number, exp_m, exp_y, cvv = card
    card_nonce = tokenize_card_via_graphql(
        sess,
        bearer_token=bearer,
        card=(number, exp_m, exp_y, cvv),
        billing_zip=billing["zip"],
        billing_street=billing["address_1"],
        proxies=proxies,
    )

    # Now call the WooCommerce checkout AJAX to actually attach the card as
    # a payment method. Use a generic brand guess (most gateways ignore it
    # beyond basic display).
    card_brand = "visa" if number.startswith("4") else "mastercard"

    checkout_json, message = call_wc_ajax_checkout(
        session=sess,
        base_url=base_url,
        billing=billing,
        checkout_nonce=nonces["checkout_nonce"],
        card_brand=card_brand,
        card_nonce=card_nonce,
        country=country,
        proxies=proxies,
    )

    info = {
        "status": "checkout_called",
        "card_nonce": card_nonce,
        "authorization_fingerprint_present": bool(bearer),
        "country": country,
        "checkout_raw": checkout_json,
    }

    return message or "No gateway message returned", info