import threading
import queue
import time
import logging
from typing import Dict, List, Tuple
from b3sitechecker import check_site_card_form, get_base_url, detect_country_from_domain


class MassChecker:
    def __init__(self, num_workers: int = 5):
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
            "not_b3_sites": 0
        }
        self.lock = threading.Lock()
        self.callback = None  # Will be set to bot callback function
        
    def set_callback(self, callback_func):
        """Set callback function to update message with counters."""
        self.callback = callback_func
    
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
                self._categorize_site(chat_id, message_id, site_line, None, "not_b3", start_time)
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
            
            # Determine if registration succeeded
            registration_succeeded = result.get("register_found") and payment_result and payment_message
            
            # Categorize the site
            # Check if site has site response (payment method successfully added or address error = good site)
            payment_success = payment_result.get("success", False) if payment_result else False
            is_good_site = payment_result.get("is_good_site", False) if payment_result else False
            has_site_response = payment_success or is_good_site  # Good site = success or address error
            
            if has_site_response and payment_message:
                # Good site - has site response (payment method added successfully or address error)
                braintree_status = "Yes" if has_braintree else "No"
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
                
            elif has_braintree and braintree_type != "none":
                # To check site - has Braintree but no site response
                type_str = braintree_type if braintree_type != "none" else "None"
                
                # Determine site response
                if result.get("register_found"):
                    if registration_succeeded and payment_message:
                        site_response = payment_message
                    elif registration_succeeded:
                        site_response = "Account created"
                    else:
                        site_response = "None"
                else:
                    site_response = "None"
                
                formatted_result = {
                    "site": base,
                    "braintree": "Yes",
                    "country": country_code,
                    "captcha": captcha_status,
                    "type": type_str,
                    "response": site_response,
                    "time": time_str
                }
                
                self._categorize_site(chat_id, message_id, site_line, formatted_result, "to_check_sites", start_time)
                
            else:
                # Not B3 - dead or no Braintree
                self._categorize_site(chat_id, message_id, site_line, None, "not_b3", start_time)
                
        except Exception as e:
            logging.exception(f"Error checking site: {site_line}")
            self._categorize_site(chat_id, message_id, site_line, None, "not_b3", start_time)
    
    def _categorize_site(self, chat_id: int, message_id: int, site_line: str, result: Dict, category: str, start_time: float):
        """Categorize site and update counters/callbacks."""
        with self.lock:
            self.counters[category] += 1
            
            if result:
                if category == "good_sites":
                    self.results["good_sites"].append(result)
                elif category == "to_check_sites":
                    self.results["to_check_sites"].append(result)
            
            # Update callback with new counters
            if self.callback:
                try:
                    self.callback(chat_id, message_id, self.counters)
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
            "not_b3_sites": 0
        }
        
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

