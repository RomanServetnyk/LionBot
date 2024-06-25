from doctest import IGNORE_EXCEPTION_DETAIL
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import os
import sys
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
from dotenv import load_dotenv
from datetime import datetime, time as tm, timedelta
import pytz
from dateutil import parser
import requests

load_dotenv()

class AutomationBot:
    def __init__(self) -> None:
        self.options = Options()    
        print(os.getenv("ENV"))    
        if os.getenv("ENV") != "dev": self.options.add_argument("headless")
        self.options.add_argument("--disable-gpu")
        self.options.add_argument("--enable-features=SameSiteByDefaultCookies,CookiesWithoutSameSiteMustBeSecure")
        self.options.add_experimental_option("prefs", {"profile.default_content_settings.cookies": 2})
        try:
            self.driver = webdriver.Chrome(options=self.options)
            self.wait = WebDriverWait(self.driver, 20, ignored_exceptions=[NoSuchElementException, StaleElementReferenceException])
            
        except Exception as error:
            print("Webdriver can't working: ", error, file=sys.stderr)
    
    def __del__(self) -> None:
        if self.driver: self.driver.quit()

    def _retry_click(self, xpath, max_attempts=5):
        attempts = 0
        while attempts < max_attempts:
            try:
                element = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
                element.click()
                return
            except StaleElementReferenceException:
                print("Element went stale; retrying click", file=sys.stderr)
                attempts += 1
                if attempts >= max_attempts:
                    raise

    def accept(self):
        raise NotImplementedError("Subclasses must implement this method")

    # Function to handle stale element exceptions during click operations.


class LionBridgeBot(AutomationBot):
    def __init__(self) -> None:
        super().__init__()

    def run_forever(self):
        while True:
            logged_in = self.__login()
            if logged_in: break
        while True:
            try:
                self.__run()
                print("Will rerun after 5 seconds.")
                time.sleep(5)
            except Exception as e:
                print(f"Error while running : {e}")
        pass

    def __run(self):
        self.__accept()
        pass

    def __accept(self):
        if not all([self.driver, self.wait, self.options]):
            print("Failed to initialize. Cannot start the Accept Process", file=sys.stderr)
            return False
    
        print("Initiated Accept Process")
    
        while True:
            try:
                self.__move_to_new_jobs()
                cards = self.driver.find_elements(By.CSS_SELECTOR, "div.ltx-card")
                if len(cards) > 0:
                    print(f"Found {len(cards)} job(s)")
                else:
                    print("Jobs not found")
                    time.sleep(5)
                    continue
                selectedCard = None
                data = None
                for card in cards:
                    title = "No Title"
                    due = "No Due Date"
                    quantity = "No Quantity"
                    language = "No Language"
                    cost = "No Price"
                    try: 
                        def get_element_text(card, class_name, name):
                            element = card.find_elements(By.CLASS_NAME, class_name)
                            if len(element) > 0:
                                return element[0].text
                            return "No " + name.capitalize()
                        
                        title = get_element_text(card, "job-title", "Title")
                        due = get_element_text(card, "job-date", "Due Date")
                        quantity = get_element_text(card, "details", "Quantity")
                        language = get_element_text(card, "job-languages", "Language")
                        cost_elements = card.find_elements(By.CLASS_NAME, "cost")
                        cost = "No Price"
                        price = 10
                        if len(cost_elements) > 0:
                            cost = cost_elements[0].text
                        if cost != "No Price":
                            filtered_cost = cost.replace("≈", "").replace("\n", "").strip()
                            print(filtered_cost.split(" "))
                            price = filtered_cost.split(" ")[0] if len(filtered_cost.split(" ")) > 0 else 10

                        timezones = {
                            "CET": "UTC+1",
                            "CEST": "UTC+2",
                            "MET": "UTC+1",
                            "MEST": "UTC+2",       
                            "EET": "UTC+2",
                            "EEST": "UTC+3",
                            "WET": "UTC",
                            "WEST": "UTC+1"
                        }
                        filtered_due = due
                        if filtered_due != "No Due Date":
                            for key, value in timezones.items():
                                filtered_due = filtered_due.replace(key, value)
                            real_date = parser.parse(filtered_due)
                            real_date += timedelta(minutes=2 * real_date.utcoffset().total_seconds() // 60)

                        print("price", price, self.__is_entire_period_night(real_date), filtered_due, datetime.now())

                        if price >= 5 and (filtered_due == "No Due Date" or not self.__is_entire_period_night(real_date)):
                            selectedCard = card
                            data = {
                                "title": title,
                                "due": due,
                                "price": cost,
                                "quantity": quantity,
                                "language": language
                            }
                            break
                    except Exception as e:
                        print(e)
                        selectedCard = card
                        data = {
                                "title": title,
                                "due": due,
                                "price": cost,
                                "quantity": quantity,
                                "language": language
                            }                      
                        break
                if selectedCard is None: 
                    time.sleep(5)
                    continue
                print(selectedCard)
                selectedCard.click()
                accept_button = self.wait.until(EC.element_to_be_clickable((By.ID, "accept-btn")))
                accept_button.click()
                print(f"Accepted ================> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                with open("output.txt", mode="a", encoding="utf-8") as file:
                    file.write(f"Accepted ================> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                self.__send_email(data)
                time.sleep(5)

            except Exception as e:
                print(f"Error while accepting: {e}")
                time.sleep(5)
                

    def __move_to_new_jobs(self):
        self.driver.get("https://lcx-jobboard.lionbridge.com/new-jobs")
        current_url = self.driver.current_url
    
        if "Login" in current_url:
            print("Logging in before moving to the new jobs page")
            self.__login()
        
        print("Waiting for the page to load")
        try:
            # Wait until either "job_content" or "no_jobs_picture" is located
            self.wait.until(
                lambda d: (job_content := d.find_elements(By.CLASS_NAME, "job-content")) or 
                        (no_jobs_picture := d.find_elements(By.CLASS_NAME, "lcx-no-jobs-picture"))
            )
            
        except Exception as e:
            print("Jobs not found")
            print(e)
            return False

    def __login(self):
        if not all([self.driver, self.wait, self.options]):
            print("Not initialized successfully, can't log in", file=sys.stderr)
            return False
        
        print("Started login")
        
        # Extracted from self.mail for readability.
        # server = self.mail.server
        # name = self.mail.name
        # client = self.mail.client
        # project = self.mail.project
    
        try:
            self.driver.get("https://lcx-jobboard.lionbridge.com/new-jobs")
            print("Entered the homepage", file=sys.stderr)
    
            # Using environment variables directly within send_keys for brevity.
            self.wait.until(EC.presence_of_element_located((By.NAME, 'Username'))).send_keys(os.getenv('LION_EMAIL_ADDRESS'))
            self.wait.until(EC.element_to_be_clickable((By.NAME, 'button'))).click()
    
            self.wait.until(EC.presence_of_element_located((By.NAME, 'Password'))).send_keys(os.getenv('LION_PASSWORD'))
            self.wait.until(EC.element_to_be_clickable((By.ID, 'submitButton'))).click()
    
            print('Logging in', file=sys.stderr)
    
            self.wait.until(EC.url_contains("new-jobs"))
            
            print("Logged in", file=sys.stderr)
    
        except Exception as e:
            print("Error:", e, file=sys.stderr)
            return False
    
        # Delay to observe changes, only needed if the title or some other aspect of the page is important after the actions are completed.
        page_title = self.driver.title
        print(f"The title of the page is: {page_title}", file=sys.stderr)
    
        return True
    
    def __is_entire_period_night(self, future_time: datetime):
        # Define the night time range (9PM to 5AM for example)
        night_start = tm(20, 0)  # 9:00 PM
        night_end = tm(5, 0)     # 5:00 AM
        french_timezone = pytz.timezone('Europe/Paris')
        current_time = datetime.now()
        current_time_french = current_time.astimezone(french_timezone)
        future_time_french = future_time.astimezone(french_timezone)
        print(current_time_french, future_time_french)

        current_time_within_night = (night_start <= current_time_french.time() or current_time_french.time() <= night_end)
        future_time_within_night = (night_start <= future_time_french.time() or future_time_french.time() <= night_end)

        if current_time_within_night and future_time_within_night:
            if current_time_french.date() == future_time_french.date():
                if current_time_french.time() < night_end and future_time_french.time() > night_start:
                    return False
                return True
            elif ((current_time_french.time() > future_time_french.time()) and 
                (current_time_french.time() >= night_start) and 
                (future_time_french.time() <= night_end) and 
                ((future_time_french - current_time_french).days < 1)):
                # This covers the case where the current time is at night and the future time is on the next day but still at night.
                return True
        
        return False
    
    def __send_email(self, data):
        print(data)
        while True:
            try:
                requests.post("https://hooks.zapier.com/hooks/catch/14824891/3j0i0p8/", data=data, timeout=20)
                break
            except Exception as e:
                print("sending email : ", e)
                pass

bot = LionBridgeBot()
bot.run_forever()