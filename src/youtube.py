import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import os

def upload_youtube():
    #load options
    chrome_options = Options()
    chrome_options.add_argument(r"--user-data-dir=C:\ChromeSelenium") #Neded to copy the default chrome user to this path
    chrome_options.add_argument("--profile-directory=Default")

    chrome_options.add_experimental_option("detach", True)

    driver = webdriver.Chrome(options=chrome_options)

    driver.get("https://www.youtube.com/")

    #load the cookies

    with open("cookies.txt", "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue

            domain, flag, path, secure, expiry, name, value = line.strip().split("\t")

            cookie = {
                "domain": domain,
                "name": name,
                "value": value,
                "path": path,
            }

            if expiry:
                cookie["expiry"] = int(expiry)

            cookie["secure"] = secure.upper() == "TRUE"

            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(name, e)
    driver.refresh()

    driver.implicitly_wait(15)




if __name__ == "__main__":
    upload_youtube()