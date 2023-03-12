import requests
from bs4 import BeautifulSoup
import miniaudio
import json
from threading import Thread
from queue import Queue, Empty
import time
import keyboard
import os

if os.path.exists:
    SETTINGS = dict(line.strip().split('=') for line in open('settings.properties') if line.strip() != "" and line[0] != "#")
else:
    raise FileNotFoundError("settings.properties file is missing!")

ARXIV_URL = SETTINGS["arxiv_database_url"]
ASTRO_ARCHIVE_URL = ARXIV_URL + SETTINGS["target_arxiv_partial_url"]

ARXIV_SECTION_INDEXES = [int(index) for index in SETTINGS["arxiv_target_category_indexes"].split(";")]

# https://api.elevenlabs.io/docs#/
# https://api.elevenlabs.io/v1/voices
# Bella Voice ID = EXAVITQu4vr4xnSDxMaL
elevenlabs_voice_id = SETTINGS["elevenlabs_voice_id"]

__elevenlabs_api_key = None
AUDIO_ENABLED = False
if not os.path.exists("./.apikey"):
    print("Account with elevenlabs.io required for audio.\nCreate a file named \".apikey\" in the app folder containing your key to enable audio generation.\nTo just disable this message, create the file, but leave it blank.")
    input("Press return to continue: ")
    print()
    print()
    print()
else:
    with open("./.apikey") as file:
        __elevenlabs_api_key = file.read()
    if __elevenlabs_api_key != "":
        AUDIO_ENABLED = True
__elevenlabs_header = { "xi-api-key": __elevenlabs_api_key }

class ScriptGlobals(object):
    clear_message_length = 0

class AudioPlayer(object):
    __instance = None
    def __init__(self):
        if AudioPlayer.__instance is not None:
#            raise RuntimeError("Only one instance of the AudioPlayer class may exist. Use AudioPlayer.instance to get it.")
            raise RuntimeError("Only one instance of the AudioPlayer class may exist. Use AudioPlayer.play to use it.")
        AudioPlayer.__instance = self

        self._queue = Queue(maxsize = 100)
        self.__kill_flag = False
        self.__active_audio_device = None

        self._thread = Thread(target = self.__run, daemon = True)
        self._thread.start()

    def __run(self):
            while not self.__kill_flag:
                try:
                    audio = self._queue.get(timeout = 1)
                    stream = miniaudio.stream_memory(audio)
                    with miniaudio.PlaybackDevice() as self.__active_audio_device:
                        self.__active_audio_device.start(stream)
                        while self.__active_audio_device.running:
                            time.sleep(0.2)
                except Empty as e:
                    time.sleep(0.2)

    @staticmethod
    def play(audio: bytes):
        if AudioPlayer.__instance is None:
            AudioPlayer()
        AudioPlayer.__instance._queue.put_nowait(audio)

    @staticmethod
    def stop(force = False):
        if (AudioPlayer.__instance is not None and AudioPlayer.__instance.__active_audio_device is not None):
            AudioPlayer.__instance.__active_audio_device.stop()
        if force and AudioPlayer.__instance is not None:
            del AudioPlayer.__instance

    def __del__(self):
        self.__kill_flag = True
        self._thread.join()
        AudioPlayer.__instance = None

    @staticmethod
    def is_playing() -> bool:
        #try:
        #    print(AudioPlayer.__instance.__active_audio_device)
        #    print(AudioPlayer.__instance.__active_audio_device.running)
        #except: pass
        return (AudioPlayer.__instance is not None and AudioPlayer.__instance.__active_audio_device is not None) and AudioPlayer.__instance.__active_audio_device.running

def play_as_audio(text: str):
    responce = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{elevenlabs_voice_id}", headers = __elevenlabs_header, data = json.dumps({ "text": text }))
    if responce.status_code != 200:
        clear_message()
        print("Can't play - likley not enough character quota! ", end = "", flush = True)
        ScriptGlobals.clear_message_length = 48
        #print("--!! ERRO !!-- Unable to play audio.")
        #print(f"--!! ERRO !!-- Error code is {responce.status_code}")
        #print(responce.text)
        #print()
    else:
        AudioPlayer.play(responce.content)

def clear_message():
    print("\b"*ScriptGlobals.clear_message_length + "\033[K", end = "", flush = True)
 
result = requests.get(ASTRO_ARCHIVE_URL)
if result.status_code != 200:
    result.raise_for_status()
 
tree = BeautifulSoup(result.text, "html.parser")
contentDiv = tree.select("div#content")[0]
sections = contentDiv.findChildren("ul", recursive = False)[1].findChildren("li", recursive = False)
check_url_segments = [sections[i].findChildren("a", recursive = False)[0].get_attribute_list("href")[0] for i in ARXIV_SECTION_INDEXES]

for segment_no, url_segment in enumerate(check_url_segments):
    result = requests.get(ARXIV_URL + url_segment.lstrip("/"))
    if result.status_code != 200:
        result.raise_for_status()

    tree = BeautifulSoup(result.text, "html.parser")
    dlpageDiv = tree.select("div#dlpage")[0]
    content_list = dlpageDiv.findChildren("dl", recursive = False)[0]
    headers = content_list.findChildren("dt", recursive = False)
    articles_content = content_list.findChildren("dd", recursive = False)

    titles = [item.findChildren("div", recursive = False)[0].findChildren("div", recursive = False)[0].text.strip("\n").replace("\n", " ") for item in articles_content]
    authors = [item.findChildren("div", recursive = False)[0].findChildren("div", recursive = False)[1].text.strip("\n").replace("\n", " ") for item in articles_content]
    abstracts = [item.findChildren("div", recursive = False)[0].findChildren("p", recursive = False)[0].text.strip("\n").replace("\n", " ") for item in articles_content]
    links = [ARXIV_URL + item.findChildren("span", recursive = False)[0].findChildren("a", recursive = False)[0].get_attribute_list("href")[0].strip("/").replace("\n", " ") for item in headers]
    
    for i in range(len(titles)):
        print(f"{titles[i]}\n\n{authors[i]}\n\n{abstracts[i]}\n\n{links[i]}\n\n\n")

        if segment_no != 1 or i < len(titles) - 1:
            if AUDIO_ENABLED:
                def play():
                    if not AudioPlayer.is_playing():
                        clear_message()
                        print("Playing...", end = "", flush = True)
                        ScriptGlobals.clear_message_length = 10
                        play_as_audio(abstracts[i].replace("$", " "))
                    else:
                        clear_message()
                        print("Already playing...", end = "", flush = True)
                        ScriptGlobals.clear_message_length = 18
                keyboard.on_press(lambda e: play() if e.name == "p" else None)
                print("Press P to play aloud. ", end = "")
            
            print("Return for next article...", end = "", flush = True)
            keyboard.wait("enter")
            if AUDIO_ENABLED and AudioPlayer.is_playing():
                    AudioPlayer.stop()
            print("\r\033[K")
        else:
            print()
            print(f"URLs:\narxiv:         {ARXIV_URL}\nastro archive: {ASTRO_ARCHIVE_URL}")
