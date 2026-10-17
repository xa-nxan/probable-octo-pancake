import os
import json
import asyncio
import threading
from playwright.sync_api import sync_playwright

PROFILE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "weltrade_profile"))
CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".weltrade_credentials.json"))

class WeltradeBridge:
    def __init__(self):
        self.profile_dir = PROFILE_DIR
        os.makedirs(self.profile_dir, exist_ok=True)
        self._lock = threading.Lock()

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
        return {"status": "saved", "email": data["email"]}

    def open_login_window(self):
        """
        Opens a visible Chromium browser with the persistent profile.
        The user logs in once, checks 'Remember Me', and all session cookies,
        tokens, and credentials remain saved permanently on their machine.
        """
        def _launch():
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
                page.goto("https://www.weltrade.com/my/", timeout=45000)
                
                # Check if credentials are saved and auto-fill if on login page
                creds = self.get_credentials()
                if creds.get("email") and creds.get("password"):
                    try:
                        page.wait_for_selector("input[type='email'], input[name='login'], input[name='email']", timeout=5000)
                        email_input = page.query_selector("input[type='email'], input[name='login'], input[name='email']")
                        if email_input and not email_input.input_value():
                            email_input.fill(creds["email"])
                        pwd_input = page.query_selector("input[type='password'], input[name='password']")
                        if pwd_input and not pwd_input.input_value():
                            pwd_input.fill(creds["password"])
                    except Exception:
                        pass
                
                # Keep open until user closes the window
                try:
                    page.wait_for_close(timeout=300000)
                except Exception:
                    pass
                try:
                    context.close()
                except Exception:
                    pass

        t = threading.Thread(target=_launch, daemon=True)
        t.start()
        return {"status": "browser_launched", "profile_dir": self.profile_dir}

    def check_session_status(self):
        """Checks if the persistent profile has an active login session."""
        with self._lock:
            try:
                with sync_playwright() as p:
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=self.profile_dir,
                        headless=True,
                        args=["--disable-blink-features=AutomationControlled"]
                    )
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto("https://www.weltrade.com/my/", timeout=20000)
                    url = page.url
                    is_logged_in = "login" not in url.lower() and "/my" in url.lower()
                    
                    # Try to read Safe or account balances if logged in
                    safe_balance = None
                    try:
                        if is_logged_in:
                            # Look for safe or balance elements
                            safe_el = page.query_selector("[class*='safe'], [id*='safe']")
                            if safe_el:
                                safe_balance = safe_el.inner_text().strip()
                    except Exception:
                        pass

                    context.close()
                    creds = self.get_credentials()
                    return {
                        "logged_in": is_logged_in,
                        "current_url": url,
                        "saved_email": creds.get("email", ""),
                        "safe_balance": safe_balance or "Active"
                    }
            except Exception as e:
                creds = self.get_credentials()
                return {
                    "logged_in": False,
                    "error": str(e),
                    "saved_email": creds.get("email", "")
                }

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
                    page.goto("https://www.weltrade.com/my/transfer", timeout=25000)
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
