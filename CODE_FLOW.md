# Code Flow: How Site Checking Works

## Overview
This document explains the complete flow of how the bot checks sites, from user input to final results.

---

## 📥 **Entry Points**

### 1. **Single Site Check** (`/check` command)
- User sends: `/check https://example.com`
- Handler: `handle_check_command()` in `main.py`
- Calls: `run_site_check()` → `check_site_card_form()`

### 2. **Mass Site Check** (File upload)
- User uploads `.txt` file with multiple sites
- Handler: `handle_sites_file()` in `main.py`
- Creates progress board with counters
- Auto-pins the progress message
- Calls: `run_mass_check()` → `MassChecker.process_sites()`

---

## 🔄 **Main Checking Flow**

### **Step 1: Initial Setup** (`check_site_card_form()` in `b3sitechecker.py`)

```
1. Extract base URL from input
   └─> extract_base_url() - Normalizes URL (adds http:// if missing)

2. Create HTTP session
   └─> requests.Session() with random User-Agent

3. Build account URL
   └─> base_url + "/my-account/"
```

### **Step 2: Access /my-account/ Page** (Lines 2248-2300)

```
1. GET request to /my-account/ with retries (up to 5 attempts)
   ├─> Handles 403 Forbidden errors
   ├─> Changes User-Agent on retries
   └─> Returns error if all attempts fail

2. Parse HTML response
   └─> BeautifulSoup parsing

3. Check for CAPTCHA
   └─> Searches for 'recaptcha', 'g-recaptcha' in HTML
   └─> Sets has_captcha flag
```

### **Step 3: Detect Braintree** (Lines 2312-2380)

```
1. Check for Braintree scripts/styles in HTML
   ├─> Searches for <script> and <link> tags with 'braintree' in ID/src/href
   ├─> Checks for braintreegateway.com domains
   └─> Determines type: braintree_cc, braintree_credit_card, or braintree_paypal

2. Fallback detection
   ├─> Uses detect_braintree_type() function
   └─> Simple text search for 'braintree' in HTML

3. Result stored in braintree_info dict:
   {
     "has_braintree": True/False,
     "braintree_type": "braintree_cc" | "braintree_credit_card" | "braintree_paypal" | "none",
     "detected_on": "my-account",
     "details": "..."
   }
```

### **Step 4: Find Registration Form** (Lines 2382-2385)

```
1. Check for pre-register button
   └─> _maybe_click_register_button_first()
       └─> Some sites show only a REGISTER button first
       └─> Clicks it to reveal the actual registration form

2. Search for registration form
   └─> _find_registration_form()
       ├─> Looks for form with id="register" or class="register"
       ├─> Checks for email input field
       └─> Checks for password field or register submit button
```

### **Step 5: Registration Process** (If form found)

#### **5A. Playwright Registration** (`register_new_account_selenium()`)

```
1. Launch browser (headless=False for VPS, can be set to True)
   └─> Uses Playwright with Chromium

2. Navigate to /my-account/
   └─> Waits for page to fully load (networkidle)

3. Check if form is visible
   ├─> If not visible, look for REGISTER button
   │   └─> Click it to reveal form
   │   └─> Wait for page to fully load again
   └─> Verify email field is now visible

4. Fill registration form
   ├─> Generate random email (e.g., user_abc123@gmail.com)
   ├─> Generate random username (e.g., user_xyz789)
   ├─> Generate random password (12 chars)
   └─> Wait for page to fully load before entering email

5. Find and click submit button
   ├─> Multiple methods to find submit button:
   │   ├─> In form context
   │   ├─> Near email field
   │   ├─> CSS selectors (language-agnostic)
   │   └─> Text search (multi-language support)
   └─> Wait for page to fully load before clicking

6. Wait for registration response
   └─> Wait for page to fully load (networkidle)

7. Check if registration succeeded
   ├─> If register form/button NO LONGER EXISTS → SUCCESS
   ├─> If register form/button STILL EXISTS → FAILED
   └─> Check for error messages (email validation, CAPTCHA, etc.)

8. Extract cookies from browser
   └─> Transfer cookies to requests.Session for later use
```

#### **5B. Alternative: Requests-based Registration** (`register_new_account()`)

```
1. GET registration page
   └─> Parse form fields

2. Analyze required fields
   ├─> Email (always required)
   ├─> Username (optional)
   ├─> Password (optional)
   └─> Hidden fields (nonces, tokens)

3. Generate credentials
   └─> Random email, username, password

4. POST registration form
   └─> Submit with only required fields

5. Verify registration success
   └─> Check if redirected or form disappeared
```

### **Step 6: Add Payment Method** (If registration succeeded)

```
1. Navigate to /my-account/add-payment-method/
   └─> Uses registered session with cookies

2. Detect payment page format
   ├─> Format 1: braintree_cc
   ├─> Format 2: braintree_credit_card
   ├─> Format 3: braintree_cc_config_data (with bot detector)
   └─> Format 4: ct_bot_detector_event_token

3. Extract Braintree client token
   ├─> From JavaScript variables
   ├─> From AJAX endpoints
   └─> From HTML data attributes

4. Tokenize credit card
   └─> POST to Braintree GraphQL API
       ├─> Card: 4895040596803748
       ├─> Exp: 01/2031
       └─> CVV: 105

5. Submit payment method to site
   ├─> Format 1: Direct POST with nonce
   ├─> Format 2: WooCommerce AJAX with nonce
   ├─> Format 3: With bot detector tokens
   └─> Format 4: With Cleantalk tokens

6. Check response
   ├─> SUCCESS: "Payment method successfully added"
   ├─> GOOD SITE: "Address is required" or "Billing address required"
   │   └─> This means site accepts cards but needs address
   └─> FAILED: Error message or no response
```

### **Step 7: Return Result** (`check_site_card_form()` returns)

```python
{
    "register_found": True/False,
    "base_url": "https://example.com",
    "details": "REGISTER FOUND and ACCOUNT CREATED...",
    "has_captcha": True/False,
    "braintree_info": {
        "has_braintree": True/False,
        "braintree_type": "braintree_cc" | "none",
        ...
    },
    "payment_result": {
        "success": True/False,
        "is_good_site": True/False,  # True if address error
        "message": "Payment method successfully added" | "Address is required" | "Error...",
        "braintree_type": "braintree_cc" | ...
    },
    "session": requests.Session()  # Registered session with cookies
}
```

---

## 📊 **Mass Check Flow** (`mass_chk.py`)

### **Step 1: Initialize MassChecker**

```
1. Create MassChecker instance
   ├─> num_workers = 5 (concurrent threads)
   ├─> Initialize counters (good_sites, to_check_sites, not_b3_sites)
   └─> Set bot instance for sending messages

2. Start worker threads
   └─> 5 threads process sites concurrently
```

### **Step 2: Process Each Site** (`_check_site()`)

```
For each site in queue:

1. Extract site URL from line
   └─> get_base_url() - Normalize URL

2. Call check_site_card_form()
   └─> Full checking process (see above)

3. Extract results
   ├─> Country code (from domain TLD)
   ├─> Braintree info
   ├─> CAPTCHA status
   └─> Payment result

4. Categorize site:
   
   IF has_site_response AND payment_message:
       → "good_sites"
       └─> Payment method added OR address error (good site)
   
   ELIF has_braintree AND braintree_type != "none":
       → "to_check_sites"
       └─> Has Braintree but no payment success
   
   ELSE:
       → "not_b3"
       └─> No Braintree or dead site

5. Format result
   └─> Create dict with: site, braintree, country, captcha, type, response, time

6. Call _categorize_site()
   ├─> Increment counter
   ├─> Store result
   ├─> Send message immediately (if good_sites or to_check_sites)
   │   ├─> Send to user
   │   └─> Forward to channel
   └─> Update progress board
```

### **Step 3: Update Progress** (`_categorize_site()`)

```
1. Increment category counter
   ├─> good_sites++
   ├─> to_check_sites++
   └─> not_b3_sites++

2. Increment checked_count
   └─> For progress tracking

3. Store result (if not not_b3)
   └─> Append to results list

4. Send message immediately (if good_sites or to_check_sites)
   ├─> Format: Site, Braintree, Country, Capcha, Type, Site response, Time
   ├─> Send to user
   └─> Forward to channel (if configured)

5. Update progress board
   ├─> Update message text: "Start checking (50/224)..."
   ├─> Update counters in buttons
   └─> Call callback function
```

### **Step 4: Finalize** (`run_mass_check()` in `main.py`)

```
1. Wait for all sites to complete
   └─> queue.join() - Blocks until all done

2. Auto-unpin progress board
   └─> bot.unpin_chat_message()

3. Update final message
   └─> "✅ Finished checking X sites..."

4. Create and send files:
   
   IF good_sites exist:
       ├─> Create .txt file with all good sites
       ├─> Send to user
       └─> Forward to channel
   
   IF to_check_sites exist:
       ├─> Create .txt file with all to_check sites
       ├─> Send to user
       └─> Forward to channel
   
   NOT B3 sites:
       └─> NOT sent (only counted)
```

---

## 🎯 **Categorization Logic**

### **Good Sites** ✅
- **Condition**: `has_site_response AND payment_message`
- **Meaning**: Payment method was successfully added OR address error occurred
- **Action**: 
  - Send individual message immediately
  - Forward to channel
  - Include in "Good Sites" file at end

### **To Check Sites** 🔍
- **Condition**: `has_braintree AND braintree_type != "none"` BUT no payment success
- **Meaning**: Has Braintree but payment method not added (needs manual check)
- **Action**:
  - Send individual message immediately (Type="None", Response="None")
  - Forward to channel
  - Include in "To Check Sites" file at end

### **Not B3** ❌
- **Condition**: Everything else (not good_sites AND not to_check_sites)
- **Meaning**: No Braintree, dead site, or error
- **Action**:
  - NO individual message sent
  - NOT included in files
  - Only counted in progress board

---

## 🔑 **Key Functions**

### **b3sitechecker.py**
- `check_site_card_form()` - Main checking function
- `register_new_account_selenium()` - Playwright registration
- `register_new_account()` - Requests-based registration
- `add_payment_method_braintree()` - Add payment method
- `get_client_token()` - Extract Braintree token
- `tokenize_card_braintree()` - Tokenize card via Braintree API
- `detect_braintree_type()` - Detect Braintree type from HTML
- `_find_registration_form()` - Find registration form
- `_maybe_click_register_button_first()` - Click pre-register button

### **mass_chk.py**
- `MassChecker.process_sites()` - Process all sites
- `MassChecker._check_site()` - Check single site
- `MassChecker._categorize_site()` - Categorize and send messages

### **main.py**
- `handle_sites_file()` - Handle file upload
- `run_mass_check()` - Run mass check process
- `update_counters_message()` - Update progress board
- `run_site_check()` - Single site check

---

## ⚙️ **Configuration**

### **config.py**
```python
BOT_TOKEN = "..."  # Telegram bot token
ADMIN_ID = "..."   # Admin user ID
CHANNEL_ID = "..."  # Channel ID for forwarding
```

### **Default Card**
```
Card: 4895040596803748
Exp: 01/2031
CVV: 105
```

---

## 🚀 **Performance**

- **Concurrent Workers**: 5 threads process sites simultaneously
- **Retries**: Up to 5 retries for HTTP errors, 3 retries for registration
- **Timeouts**: 15-30 seconds for HTTP requests, 20 seconds for clicks
- **Page Load**: Waits for `networkidle` state (no network activity for 500ms)

---

## 📝 **Notes**

1. **Playwright vs Requests**: Currently uses Playwright for registration (visible browser), can be set to headless for VPS
2. **Error Handling**: All errors are caught and sites are categorized as "not_b3"
3. **Progress Updates**: Real-time updates as each site is processed
4. **Message Format**: All messages use the same format as manual `/check` command
5. **File Generation**: Only "Good Sites" and "To Check Sites" are included in files

