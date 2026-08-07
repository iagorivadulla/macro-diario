import os
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys

def upload_youtube(video_path, title, description):
    # load options
    # In cmd uses "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="C:\ChromeSelenium"
    # open chrome sesion and select youtube channel, now seems to work

    chrome_options = Options()
    chrome_options.add_argument(r"--user-data-dir=C:\ChromeSelenium") #Neded to copy the default chrome user to this path
    chrome_options.add_argument("--profile-directory=Default")

    chrome_options.add_experimental_option("detach", True)

    #starts driver
    driver = webdriver.Chrome(options=chrome_options)

    #goes to youtube to start sesion
    driver.get("https://www.youtube.com/")

    driver.implicitly_wait(5)

    #goes to the upload page
    driver.get("https://www.youtube.com/upload")

    driver.implicitly_wait(5)

    #finds the file upload and sends it
    driver.find_element(By.CSS_SELECTOR, "input[type='file']").send_keys(video_path)

    driver.implicitly_wait(15)

    #find the title field
    titulo = driver.find_element(By.XPATH,'//div[@contenteditable="true" and contains(@aria-label,"Añade un título")]')

    #changes the title
    titulo.click()
    titulo.send_keys(Keys.CONTROL, "a") #selects the sujested title
    titulo.send_keys(title)

    driver.implicitly_wait(5)

    #find description field
    descripcion = driver.find_element(By.XPATH, '//div[@contenteditable="true" and contains(@aria-label,"Cuenta a los usuarios")]')

    #writes description
    descripcion.click()
    descripcion.send_keys(description)

if __name__ == "__main__":
    video_path = r"C:\Users\usuario\Desktop\Python\Macro News\video\episode.mp4"
    title = 'Tests 1 - 2'
    description = 'Tests 3 - 4'
    upload_youtube(video_path, title, description)