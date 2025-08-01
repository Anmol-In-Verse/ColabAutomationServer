import time
import json
import logging
import threading
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# Setup logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S')



from selenium.webdriver.common.by import By
import time

def interrupt_colab(driver):
    print("[*] Attempting to interrupt cell execution...")
    try:
        # Try clicking the stop button 3 times
        for i in range(3):
            clicked = driver.execute_script("""
                const btn = document.querySelector('div.cell-execution.running button#run-button');
                const svg = btn?.querySelector('svg#stop-symbol');
                if (btn && svg) {
                    btn.click();
                    return true;
                }
                return false;
            """)
            if clicked:
                print(f"[✓] Clicked stop button ({i+1}/3)")
            else:
                print(f"[!] Stop button not found on attempt {i+1}")
            time.sleep(1.5)

        # Now try keyboard shortcut: Ctrl + M, then I (3 times)
        actions = ActionChains(driver)
        for i in range(3):
            actions.key_down(Keys.CONTROL).send_keys('m').key_up(Keys.CONTROL).send_keys('i').perform()
            print(f"[✓] Sent Ctrl+M then I ({i+1}/3)")
            time.sleep(1.5)

        print("[✓] Interrupt attempts completed.")
        time.sleep(2)  # Allow time for interrupt to take effect

    except Exception as e:
        print(f"[ERROR] interrupt_colab() failed: {e}")



def wait_with_log(seconds, message=""):
    for i in range(seconds):
        logging.info(f"{message} ({i+1}/{seconds}s)")
        time.sleep(1)

def heartbeat():
    i = 0
    while True:
        i += 1
        print(f"[{i}s] Still running...")
        time.sleep(1)

def load_cookies(driver, cookie_file):
    with open(cookie_file, 'r') as f:
        cookies = json.load(f)
        for cookie in cookies:
            driver.add_cookie(cookie)
    logging.info("✅ Cookies loaded successfully.")

import re
import time

def extract_public_url(driver, timeout=600):
    print("⏳ Waiting for ngrok public URL...")
    url_pattern = r"https://[a-z0-9\-]+\.ngrok\-free\.app"
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            pre_blocks = driver.find_elements(By.CSS_SELECTOR, "div.output_text pre")
            for pre in pre_blocks:
                output_text = pre.text.strip()
                print(f"🔍 Output: {output_text[:100]}...")  # preview
                match = re.search(url_pattern, output_text)
                if match:
                    url = match.group(0)
                    print(f"✅ Found ngrok URL: {url}")
                    return url
        except Exception as e:
            print(f"⚠️ Exception: {e}")
        time.sleep(2)

    raise TimeoutError("❌ Public URL not found in output after timeout.")

from urllib.parse import urlparse

def start_colab_session():
    threading.Thread(target=heartbeat, daemon=True).start()

    options = Options()
    options.headless = True

    driver = webdriver.Firefox(options=options)
    driver.get("https://colab.research.google.com/")
    wait_with_log(5, "🌐 Opening Colab")

    driver.delete_all_cookies()
    load_cookies(driver, "cookies.json")
    driver.refresh()
    wait_with_log(10, "🔄 Refreshing after cookies load")
    
    


    parsed_url = urlparse(driver.current_url)
    print(parsed_url)
    print(driver.current_url)
    
    driver.get("https://colab.research.google.com/drive/1SYoYLAALYgvNVwPRAYxsJBKK_6aTHjNc")
    # 🕵️ Monitor URL for sign-in redirect (max 30s)
    for i in range(30):
        current_url = driver.current_url
        parsed_url = urlparse(current_url)
        if "accounts.google.com" in parsed_url.netloc and "/signin/" in parsed_url.path:
            logging.error("❌ Detected redirect to login page. Session cookies are invalid.")
            logging.info(f"🔗 Redirected URL: {current_url}")
            driver.quit()
            raise RuntimeError("💥 Terminating session: cookie expired.")
        time.sleep(1)

    logging.info("📓 Opening notebook directly")
    wait_with_log(15, "⏳ Waiting for notebook to load")

    try:
        logging.info("🔍 Trying to click 'Connect'")
        connect_button = driver.execute_script("""
            return document.querySelector('colab-connect-button')
                .shadowRoot.querySelector('#connect');
        """)
        connect_button.click()
        logging.info("🔌 Connect button clicked.")
    except Exception as e:
        logging.error(f"❌ Failed to click connect: {e}")
    wait_with_log(10, "⚙️ Waiting after clicking connect")

    print("⌛ Waiting for the first cell run button to appear...")
    for i in range(60):
        try:
            run_btn = driver.find_element(By.CSS_SELECTOR, 'colab-run-button')
            print(f"[{i+1}s] ✅ Found run button.")
            break
        except:
            print(f"[{i+1}s] ⏳ Run button not found yet...")
            time.sleep(1)
    else:
        raise TimeoutError("❌ Run button not found after 60 seconds.")

    print("🚀 Clicking the run button now...")
    driver.execute_script("""
        let runBtn = document.querySelector('colab-run-button');
        if (runBtn && runBtn.shadowRoot) {
            let btn = runBtn.shadowRoot.querySelector('#run-button');
            if (btn) btn.click();
        }
    """)
    print("✅ Run button clicked.")
    wait_with_log(5, "⏱️ Waiting after cell run")

    # 🔍 Extract public URL from output
    public_url = extract_public_url(driver)
    logging.info(f"🎯 Extracted public URL: {public_url}")

    return driver

if __name__ == "__main__":
    driver = start_colab_session()
    

__all__ = ["start_colab_session", "extract_public_url", "interrupt_colab"]