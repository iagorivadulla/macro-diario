import os
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def upload_youtube_long(video_path, title, description):
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

    wait = WebDriverWait(driver, 20)

    #click mostrar mas section
    mostrar_mas = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="toggle-button"]/ytcp-button-shape/button')))
    mostrar_mas.click()

    #click confirm the video has ia
    ia_confirm = wait.until(EC.element_to_be_clickable((By.XPATH, '//tp-yt-paper-radio-button[.//*[normalize-space(text())="Sí"]]')))
    ia_confirm.click()

    #next click
    next = driver.find_element(By.XPATH, '//*[@id="next-button"]/ytcp-button-shape/button')
    next.click()
    driver.implicitly_wait(15)

    next.click()
    driver.implicitly_wait(15)

    next.click()
    driver.implicitly_wait(15)

    #click public button to publish the video now
    publico = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="privacy-radios"]/tp-yt-paper-radio-button[3]')))
    publico.click()
    driver.implicitly_wait(15)

    #wait for 5 minutes to yt test our video
    time.sleep(300)

    #PUBLISH!!!!!
    publish = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="done-button"]/ytcp-button-shape/button')))
    publish.click()

if __name__ == "__main__":
    video_path = r"C:\Users\usuario\Desktop\Python\Macro News\video\episode.mp4"
    title = 'Tests 1 - 2'
    description = 'Tests 3 - 4'
    upload_youtube_long(video_path, title, description)