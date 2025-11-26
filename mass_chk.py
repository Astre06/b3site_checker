import threading
import queue
import time
import logging
from typing import Dict, List, Tuple
from b3sitechecker import check_site_card_form, get_base_url, detect_country_from_domain
import config


class MassChecker:
    def __init__(self, num_workers: int = 5, bot=None):
        self.num_workers = num_workers
        self.site_queue = queue.Queue()
        self.results = {
            "good_sites": [],
            "to_check_sites": [],
            "not_b3_sites": []
        }
        self.counters = {
            "good_sites": 0,
            "to_check_sites": 0,
            "not_b3": 0  # Changed from "not_b3_sites" to match category parameter
        }
        self.lock = threading.Lock()
        self.callback = None  # Will be set to bot callback function
        self.bot = bot  # Bot instance for sending messages immediately
        self.total_sites = 0
        self.checked_count = 0
        self.last_callback_time = 0  # For throttling callback updates
        self.callback_throttle = 0.5  # Update at most every 0.5 seconds
        
    def set_callback(self, callback_func):
        """Set callback function to update message with counters."""
        self.callback = callback_func
    
    def set_bot(self, bot):
        """Set bot instance for sending messages."""
        self.bot = bot
    
    def worker(self, worker_id: int):
        """Worker thread that processes sites from queue."""
        while True:
            try:
                site_data = self.site_queue.get(timeout=1)
                if site_data is None:  # Poison pill to stop worker
                    break
                
                chat_id, message_id, site_line, index = site_data
                self._check_site(chat_id, message_id, site_line, index)
                self.site_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logging.exception(f"Worker {worker_id} error: {e}")
    
    def _check_site(self, chat_id: int, message_id: int, site_line: str, index: int):
        """Check a single site and categorize it."""
        start_time = time.time()
        
        try:
            # Extract site URL
            site_token = site_line.strip().split()[0] if site_line.strip() else ""
            if not site_token:
                elapsed_time = time.time() - start_time
                time_str = f"{elapsed_time:.2f}s"
                country_code = detect_country_from_domain(site_line.strip() if site_line.strip() else "")
                formatted_result = {
                    "site": site_line.strip() if site_line.strip() else "Unknown",
                    "braintree": "No",
                    "country": country_code,
                    "captcha": "No",
                    "type": "None",
                    "response": "None",
                    "time": time_str
                }
                self._categorize_site(chat_id, message_id, site_line, formatted_result, "not_b3", start_time)
                return
            
            base = get_base_url(site_token) or site_token
            result = check_site_card_form(base)
            
            # Calculate execution time
            elapsed_time = time.time() - start_time
            time_str = f"{elapsed_time:.2f}s"
            
            # Get basic info
            country_code = detect_country_from_domain(base)
            braintree_info = result.get("braintree_info", {})
            has_braintree = braintree_info.get("has_braintree", False) if braintree_info else False
            braintree_type = braintree_info.get("braintree_type", "none") if braintree_info else "none"
            has_captcha = result.get("has_captcha", False)
            captcha_status = "Yes" if has_captcha else "No"
            
            # Check payment result
            payment_result = result.get("payment_result", {})
            payment_message = payment_result.get("message", "") if payment_result else ""
            
            # Categorize the site
            # Check if site has site response (payment method successfully added or address error = good site)
            payment_success = payment_result.get("success", False) if payment_result else False
            is_good_site = payment_result.get("is_good_site", False) if payment_result else False
            has_site_response = payment_success or is_good_site  # Good site = success or address error
            
            # Determine if it's B3 (has Braintree)
            is_b3 = has_braintree and braintree_type != "none"
            
            if has_site_response and payment_message:
                # Good site - has site response (payment method added successfully or address error)
                braintree_status = "Yes" if has_braintree else "No"
                # Use payment result type if available, otherwise use braintree_info type
                if payment_result.get("braintree_type"):
                    braintree_type = payment_result.get("braintree_type", "none")
                type_str = braintree_type if braintree_type != "none" else "None"
                site_response = payment_message
                
                formatted_result = {
                    "site": base,
                    "braintree": braintree_status,
                    "country": country_code,
                    "captcha": captcha_status,
                    "type": type_str,
                    "response": site_response,
                    "time": time_str
                }
                
                self._categorize_site(chat_id, message_id, site_line, formatted_result, "good_sites", start_time)
                
            elif is_b3:
                # To check site - has Braintree but no site response
                # Set Type and Site response to None as requested
                braintree_status = "Yes"
                type_str = "None"  # Always None for "To check site"
                site_response = "None"  # Always None for "To check site"
                
                formatted_result = {
                    "site": base,
                    "braintree": braintree_status,
                    "country": country_code,
                    "captcha": captcha_status,
                    "type": type_str,
                    "response": site_response,
                    "time": time_str
                }
                
                self._categorize_site(chat_id, message_id, site_line, formatted_result, "to_check_sites", start_time)
                
            else:
                # Not B3 - automatically categorized if not Good site and not To check site
                # (no Braintree, or braintree_type is "none", or no payment success)
                # Create formatted result for "Not B3" with all None values
                formatted_result = {
                    "site": base,
                    "braintree": "No",
                    "country": country_code,
                    "captcha": captcha_status,
                    "type": "None",
                    "response": "None",
                    "time": time_str
                }
                self._categorize_site(chat_id, message_id, site_line, formatted_result, "not_b3", start_time)
                
        except Exception as e:
            logging.exception(f"Error checking site: {site_line}")
            elapsed_time = time.time() - start_time
            time_str = f"{elapsed_time:.2f}s"
            # Try to extract base URL even on error
            try:
                site_token = site_line.strip().split()[0] if site_line.strip() else ""
                base = get_base_url(site_token) or site_token if site_token else site_line.strip()
            except:
                base = site_line.strip() if site_line.strip() else "Unknown"
            country_code = detect_country_from_domain(base)
            formatted_result = {
                "site": base,
                "braintree": "No",
                "country": country_code,
                "captcha": "No",
                "type": "None",
                "response": "None",
                "time": time_str
            }
            self._categorize_site(chat_id, message_id, site_line, formatted_result, "not_b3", start_time)
    
    def _categorize_site(self, chat_id: int, message_id: int, site_line: str, result: Dict, category: str, start_time: float):
        """Categorize site and update counters/callbacks, send message immediately."""
        # Update counters and store results (inside lock for thread safety)
        with self.lock:
            self.counters[category] += 1
            self.checked_count += 1
            
            if result:
                if category == "good_sites":
                    self.results["good_sites"].append(result)
                elif category == "to_check_sites":
                    self.results["to_check_sites"].append(result)
                elif category == "not_b3":
                    self.results["not_b3_sites"].append(result)
            
            # Get current counters for callback (copy to avoid lock contention)
            current_counters = self.counters.copy()
            current_checked = self.checked_count
            current_total = self.total_sites
        
        # Send message immediately if result exists and bot is available (outside lock)
        # Only send for good_sites and to_check_sites, NOT for not_b3
        if result and self.bot and category != "not_b3":
            try:
                # Format message exactly like manual check
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
                self.bot.send_message(chat_id, msg, parse_mode="HTML")
                
                # Forward to channel if configured
                if hasattr(config, 'CHANNEL_ID') and config.CHANNEL_ID:
                    try:
                        self.bot.send_message(config.CHANNEL_ID, msg, parse_mode="HTML")
                    except Exception as e:
                        logging.exception(f"Failed to forward to channel: {e}")
            except Exception as e:
                logging.exception(f"Error sending message: {e}")
        
        # Update callback with new counters and progress (outside lock, with throttling)
        if self.callback:
            current_time = time.time()
            # Throttle: only update if enough time has passed since last update
            if current_time - self.last_callback_time >= self.callback_throttle:
                try:
                    self.callback(chat_id, message_id, current_counters, current_checked, current_total)
                    with self.lock:
                        self.last_callback_time = current_time
                except Exception as e:
                    logging.exception(f"Error updating callback: {e}")
    
    def process_sites(self, chat_id: int, message_id: int, sites: List[str]) -> Dict:
        """Process list of sites with worker threads."""
        # Clear previous results
        self.results = {
            "good_sites": [],
            "to_check_sites": [],
            "not_b3_sites": []
        }
        self.counters = {
            "good_sites": 0,
            "to_check_sites": 0,
            "not_b3": 0  # Changed from "not_b3_sites" to match category parameter
        }
        self.total_sites = len(sites)
        self.checked_count = 0
        
        # Start worker threads
        workers = []
        for i in range(self.num_workers):
            worker = threading.Thread(target=self.worker, args=(i,), daemon=True)
            worker.start()
            workers.append(worker)
        
        # Add all sites to queue
        for index, site_line in enumerate(sites, start=1):
            self.site_queue.put((chat_id, message_id, site_line, index))
        
        # Wait for all sites to be processed
        self.site_queue.join()
        
        # Stop workers
        for _ in range(self.num_workers):
            self.site_queue.put(None)
        
        for worker in workers:
            worker.join(timeout=5)
        
        return self.results

