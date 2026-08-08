import os
import time
import json
from pathlib import Path
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
    for i in range(300, 0, -1):
        print(f"Esperando {i} segundos hasta publicar", flush=True)
        time.sleep(1)

    #PUBLISH!!!!!
    publish = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="done-button"]/ytcp-button-shape/button')))
    publish.click()

    time.sleep(10)
    driver.quit()

def upload_youtube_short(video_path, title, description, long_title):
    # load options
    # In cmd uses "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="C:\ChromeSelenium"
    # open chrome sesion and select youtube channel, now seems to work

    chrome_options = Options()
    chrome_options.add_argument(
        r"--user-data-dir=C:\ChromeSelenium")  # Neded to copy the default chrome user to this path
    chrome_options.add_argument("--profile-directory=Default")

    chrome_options.add_experimental_option("detach", True)

    # starts driver
    driver = webdriver.Chrome(options=chrome_options)

    # goes to youtube to start sesion
    driver.get("https://www.youtube.com/")

    driver.implicitly_wait(5)

    # goes to the upload page
    driver.get("https://www.youtube.com/upload")

    driver.implicitly_wait(5)

    # finds the file upload and sends it
    driver.find_element(By.CSS_SELECTOR, "input[type='file']").send_keys(video_path)

    driver.implicitly_wait(15)

    # find the title field
    titulo = driver.find_element(By.XPATH, '//div[@contenteditable="true" and contains(@aria-label,"Añade un título")]')

    # changes the title
    titulo.click()
    titulo.send_keys(Keys.CONTROL, "a")  # selects the sujested title
    titulo.send_keys(title)

    driver.implicitly_wait(5)

    # find description field
    descripcion = driver.find_element(By.XPATH,
                                      '//div[@contenteditable="true" and contains(@aria-label,"Cuenta a los usuarios")]')

    # writes description
    descripcion.click()
    descripcion.send_keys(description)

    wait = WebDriverWait(driver, 20)

    # click mostrar mas section
    mostrar_mas = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//*[@id="toggle-button"]/ytcp-button-shape/button')))
    mostrar_mas.click()

    # click confirm the video has ia
    ia_confirm = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//tp-yt-paper-radio-button[.//*[normalize-space(text())="Sí"]]')))
    ia_confirm.click()

    # next click
    next = driver.find_element(By.XPATH, '//*[@id="next-button"]/ytcp-button-shape/button')
    next.click()
    driver.implicitly_wait(15)

    #select long video
    add = driver.find_element(By.XPATH, '//*[@id="shorts-content-links-add-button"]/ytcp-button-shape/button')
    add.click()
    video_relacionado = wait.until(EC.element_to_be_clickable((By.XPATH,
            f'//ytcp-entity-card[contains(@aria-label, "{long_title}")]')))
    video_relacionado.click()

    # next click
    next = driver.find_element(By.XPATH, '//*[@id="next-button"]/ytcp-button-shape/button')
    next.click()
    driver.implicitly_wait(15)

    # next click
    next = driver.find_element(By.XPATH, '//*[@id="next-button"]/ytcp-button-shape/button')
    next.click()
    driver.implicitly_wait(15)

    # click public button to publish the video now
    publico = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//*[@id="privacy-radios"]/tp-yt-paper-radio-button[3]')))
    publico.click()
    driver.implicitly_wait(15)

    # wait for 5 minutes to yt test our video
    for i in range(300, 0, -1):
        print(f"Esperando {i} segundos hasta publicar", flush=True)
        time.sleep(1)

    # PUBLISH!!!!!
    publish = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="done-button"]/ytcp-button-shape/button')))
    publish.click()

    time.sleep(15)
    driver.quit()

def upload_tiktok(video_path, description):
    #upload shorts to tiktok

    chrome_options = Options()
    chrome_options.add_argument(
        r"--user-data-dir=C:\ChromeSelenium")  # Neded to copy the default chrome user to this path
    chrome_options.add_argument("--profile-directory=Default")

    chrome_options.add_experimental_option("detach", True)

    # starts driver
    driver = webdriver.Chrome(options=chrome_options)

    driver.get("https://www.tiktok.com/tiktokstudio/upload?from=webapp&tab=video")

    driver.implicitly_wait(5)

    # finds the file upload and sends it
    driver.find_element(By.CSS_SELECTOR, "input[type='file']").send_keys(video_path)

    driver.implicitly_wait(15)

    # find description field
    descripcion = driver.find_element(By.XPATH,
                                      '//div[@contenteditable="true"]')

    # writes description
    descripcion.click()
    descripcion.send_keys(Keys.CONTROL, "a")
    descripcion.send_keys(description)

    wait = WebDriverWait(driver, 20)

    # wait for 5 minutes to yt test our video
    for i in range(150, 0, -1):
        print(f"Esperando {i} segundos hasta publicar", flush=True)
        time.sleep(1)

    #PUBLISH!!!
    publish = wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div/div/div[2]/div[2]/div/div/div/div/div/div[6]/div/button[1]')))
    publish.click()

    time.sleep(10)
    driver.quit()



def publish(seo_dict: json):

    #loads the seo_dict and uses the title and the description

    with open(seo_dict, 'r', encoding='utf-8') as f:
        seo = json.load(f)

    print('[Publishing] Starting youtube long video upload..')
    #get all the long video info
    long_title = seo['episode']['title']
    long_description = seo['episode']['description']
    long_hashtags = " ".join(seo['episode']['hashtags'])
    long_description_hashtags = long_description + '\n\n' + long_hashtags

    VIDEO_PATH = r"C:\Users\usuario\Desktop\Python\Macro News\video\episode.mp4"

    #uploads all the info
    upload_youtube_long(VIDEO_PATH, long_title, long_description_hashtags)

    #now uploads the shorts
    SHORTS_PATH = r"C:\Users\usuario\Desktop\Python\Macro News\video\shorts"

    print("[Publishing] Starting youtube short videos upload..")
    #do this once for every short in youtube
    for i, file in enumerate(os.listdir(SHORTS_PATH)): #get all names and index
        path = os.path.join(SHORTS_PATH, file)
        title = seo['shorts'][i]['title']
        description = seo['shorts'][i]['description']
        hashtags = " ".join(seo['shorts'][i]['hashtags'])
        description_hashtags = description + '\n\n' + hashtags

        upload_youtube_short(path, title, description_hashtags, long_title)

    print("[Publishing] Starting tik tok short videos upload..")
    #now every short to tik tok
    for i, file in enumerate(os.listdir(SHORTS_PATH)): #get all names and index
        path = os.path.join(SHORTS_PATH, file)
        title = seo['shorts'][i]['title']
        description = seo['shorts'][i]['description']
        hashtags = " ".join(seo['shorts'][i]['hashtags'])
        description_hashtags = description + '\n\n' + hashtags

        upload_tiktok(path, description_hashtags)




if __name__ == "__main__":
    seo = r'C:\Users\usuario\Desktop\Python\Macro News\seo_dict.json'
    publish(seo)