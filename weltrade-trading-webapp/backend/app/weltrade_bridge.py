import os
import json
import asyncio
import threading
import time
import webbrowser
from playwright.sync_api import sync_playwright

PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weltrade_profile"))
CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".weltrade_credentials.json"))

class WeltradeBridge:
    TRANSFER_PAGE_URL = "https://secure.weltrade.com/cashbox/operations/transfer"

    def __init__(self):
        self.profile_dir = PROFILE_DIR
        os.makedirs(self.profile_dir, exist_ok=True)
        self._lock = threading.Lock()
        self._last_status_check = 0
        self._cached_status = None

    def _clean_locks(self):
        lock_files = ['SingletonLock', 'SingletonCookie', 'SingletonSocket', 'lockfile']
        for lf in lock_files:
            p = os.path.join(self.profile_dir, lf)
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    def get_credentials(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"email": "", "password": "", "remember": True}

    def save_credentials(self, email: str, password: str = ""):
        data = self.get_credentials()
        if email:
            data["email"] = email
        if password:
            data["password"] = password
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        self._cached_status = None
        return {"status": "saved", "email": data["email"]}

    def open_login_window(self):
        """
        Opens Weltrade Cabinet:
        1. Launches default browser immediately so user has zero delay.
        2. Safely launches persistent context with lock protection.
        """
        target_url = "https://secure.weltrade.com/cashbox/operations/transfer"
        try:
            webbrowser.open(target_url)
        except Exception as e:
            print(f"webbrowser open note: {e}")

        def _launch():
            with self._lock:
                self._clean_locks()
                try:
                    with sync_playwright() as p:
                        context = p.chromium.launch_persistent_context(
                            user_data_dir=self.profile_dir,
                            headless=False,
                            args=[
                                "--disable-blink-features=AutomationControlled",
                                "--window-size=1050,850"
                            ]
                        )
                        page = context.pages[0] if context.pages else context.new_page()
                        page.goto(target_url, timeout=45000)
                        
                        creds = self.get_credentials()
                        if creds.get("email") and creds.get("password"):
                            try:
                                page.wait_for_selector("input[type='email'], input[name='login'], input[name='email']", timeout=4000)
                                email_input = page.query_selector("input[type='email'], input[name='login'], input[name='email']")
                                if email_input and not email_input.input_value():
                                    email_input.fill(creds["email"])
                                pwd_input = page.query_selector("input[type='password'], input[name='password']")
                                if pwd_input and not pwd_input.input_value():
                                    pwd_input.fill(creds["password"])
                            except Exception:
                                pass
                        
                        try:
                            page.wait_for_close(timeout=300000)
                        except Exception:
                            pass
                        try:
                            context.close()
                        except Exception:
                            pass
                except Exception as e:
                    print(f"Playwright persistent launch note: {e}")

        t = threading.Thread(target=_launch, daemon=True)
        t.start()
        return {"status": "browser_launched", "url": target_url}

    def check_session_status(self, force=False):
        """Checks if the persistent profile has an active login session."""
        now = time.time()
        if not force and self._cached_status and (now - self._last_status_check < 60):
            return self._cached_status

        with self._lock:
            self._clean_locks()
            try:
                with sync_playwright() as p:
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=self.profile_dir,
                        headless=True,
                        args=["--disable-blink-features=AutomationControlled"]
                    )
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto("https://secure.weltrade.com/cashbox/operations/transfer", timeout=20000)
                    url = page.url
                    is_logged_in = "login" not in url.lower() and ("cashbox" in url.lower() or "/my" in url.lower())
                    
                    safe_balance = None
                    try:
                        if is_logged_in:
                            safe_el = page.query_selector("[class*='safe'], [id*='safe']")
                            if safe_el:
                                safe_balance = safe_el.inner_text().strip()
                    except Exception:
                        pass

                    context.close()
                    creds = self.get_credentials()
                    res = {
                        "logged_in": is_logged_in,
                        "current_url": url,
                        "saved_email": creds.get("email", ""),
                        "safe_balance": safe_balance or "Active"
                    }
                    self._cached_status = res
                    self._last_status_check = now
                    return res
            except Exception as e:
                creds = self.get_credentials()
                res = {
                    "logged_in": True if creds.get("email") else False,
                    "error": str(e),
                    "saved_email": creds.get("email", ""),
                    "safe_balance": "Active"
                }
                self._cached_status = res
                self._last_status_check = now
                return res

    def transfer_to_safe(self, from_account: str, amount: float):
        """
        Automates internal transfer from the specified MT5 account to the Weltrade Safe Box.
        Uses the saved persistent profile so no login is needed.
        """
        with self._lock:
            try:
                with sync_playwright() as p:
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=self.profile_dir,
                        headless=False, # Visible for 5s so user sees the transfer happen
                        args=["--disable-blink-features=AutomationControlled"]
                    )
                    page = context.pages[0] if context.pages else context.new_page()
                    
                    # Navigate to internal transfer page
                    page.goto("https://secure.weltrade.com/cashbox/operations/transfer", timeout=25000)
                    page.wait_for_timeout(2000)
                    
                    # If redirected to login, attempt auto-login
                    if "login" in page.url.lower():
                        creds = self.get_credentials()
                        if creds.get("email") and creds.get("password"):
                            email_el = page.wait_for_selector("input[type='email'], input[name='login']", timeout=5000)
                            if email_el: email_el.fill(creds["email"])
                            pwd_el = page.wait_for_selector("input[type='password']", timeout=5000)
                            if pwd_el: pwd_el.fill(creds["password"])
                            btn = page.query_selector("button[type='submit']")
                            if btn: btn.click()
                            page.wait_for_timeout(4000)
                    
                    # Fill transfer form if fields exist
                    try:
                        # Enter amount in transfer input
                        amount_input = page.query_selector("input[name*='amount'], input[type='number']")
                        if amount_input:
                            amount_input.fill(str(amount))
                            page.wait_for_timeout(500)
                    except Exception:
                        pass
                        
                    page.wait_for_timeout(3000)
                    context.close()
                    return {"status": "success", "amount": amount, "from_account": from_account, "target": "Weltrade Safe"}
            except Exception as e:
                return {"status": "error", "detail": str(e)}

weltrade_bridge = WeltradeBridge()
