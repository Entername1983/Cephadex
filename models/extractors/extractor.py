import pathlib
from pdf2image import convert_from_path
from pdfminer.high_level import extract_pages
import openai
from pptx import Presentation
import docx2txt
import json
from pydub import AudioSegment
import os
import math
from youtube_transcript_api import YouTubeTranscriptApi
import tiktoken
from bs4 import BeautifulSoup
import requests
import re
import codecs
import logging
from datetime import datetime
import random
from pytesseract import image_to_string
from models.decks.deck import Deck
from models.decks.deck_files import DeckFiles
from tools.lists import DECK_NAMES
from flask import session
from flask_login import current_user
import datetime as dt
from pydub.utils import mediainfo
from models.helpers.helpers import count_tokens, split_text
from models.decks.job import Job
from models.decks.job_notification import JobNotification
from models.exceptions.exceptions import YoutubeError, UnsupportedFileError, AudioError
from werkzeug.utils import secure_filename
from models.extractors.extractor_config import PAGES_PER_MIN, TOKENS_PER_PAGE



openai.api_key = os.environ.get("OPENAI_API_KEY")

encoding = tiktoken.get_encoding("cl100k_base")
logger = logging.getLogger("extractors")
logger.setLevel(logging.DEBUG)

UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER")

class Extractor:
    def __init__(self, db_session, form=None, slug=None, **kwargs):
        self.db_session = db_session
        options = {
            'main_opt': kwargs.get('prompt', None),
            'subject_opt': kwargs.get('subject', None),
            'trans_opt': kwargs.get('languages', None),
            'lang_opt': kwargs.get('main_lang', None),
            'detail_lvl_opt': kwargs.get('length', None),
            'min_opt': kwargs.get('qmin_option', None),
            'max_opt': kwargs.get('qmax_option', None),
            'images_opt': kwargs.get('generate_images', None),
            'save_text_opt': kwargs.get('save_text', None),
            'custom_term': kwargs.get('custom_term', None),
            'custom_content': kwargs.get('custom_content', None),
        }
        if form is not None:
            options['main_opt'] = form.prompt.data
            options['subject_opt'] = form.subject.data
            options['trans_opt'] = form.languages.data
            options['lang_opt'] = form.main_lang.data
            options['detail_lvl_opt'] = form.length.data
            options['min_opt'] = form.qmin_option.data
            options['max_opt'] = form.qmax_option.data
            options['images_opt'] = form.generate_images.data
            options['save_text_opt'] = form.save_text.data
            options['custom_term'] = form.custom_term.data
            options['custom_content'] = form.custom_content.data

        self.prompt_options = options

        self.description = kwargs.get('description', None)
        deck = kwargs.get('deck_list', None)
        if deck is not None:
            self.deck = deck
        else:
            if not kwargs.get('name', None):
                chosen_name = random.choice(DECK_NAMES)
            else:
                chosen_name = kwargs.get('name')
            deck = Deck(name=chosen_name, user_id=current_user.id,
                        description=self.description)
            db_session.add(deck)
            db_session.commit()
            self.deck = deck

        if form is not None:
            self.file_data = form.file.data or kwargs.get('file', None)
            self.text_data = form.text_input.data or kwargs.get('text_input', None)
            self.link_data = form.link_input.data or kwargs.get('link_input', None)
        else:
            self.file_data = kwargs.get('file', None)
            self.text_data = kwargs.get('text_input', None)
            self.link_data = kwargs.get('link_input', None)
        self.slug = slug or str(current_user.id) + dt.datetime.now(dt.timezone.utc).isoformat()
        self.extension = None
        self.text = None
        self.tokens = None

    def __repr__(self):
        return (f"Extractor(prompt_options={self.prompt_options}, "
                f"description={repr(self.description)}, "
                f"deck={repr(self.deck)}, "
                f"file_data={repr(self.file_data)}, "
                f"text_data={repr(self.text_data)}, "
                f"link_data={repr(self.link_data)}, "
                f"slug={repr(self.slug)})")

    def get_deck(self, form):
        if form.deck_list.data:
            self.deck = form.deck_list.data
            return form.deck_list.data, False
        else:
            if not form.name.data:
                chosen_name = random.choice(DECK_NAMES)
            else:
                chosen_name = form.name.data
            deck = Deck(name=chosen_name, user_id=current_user.id,
                            description=self.description)
            self.deck = deck
            return deck, True


    def get_content(self):
        print("Getting content")
        print(self)
        ## if file is audio returns size of audio, otherwise the text
        if self.file_data:
            print(self.file_data.filename)
            extension = os.path.splitext(self.file_data.filename)[1].lower()
            self.type = extension
            if extension in ['.wav', '.mp3']:
                self.duration = get_audio_content(self.file_data, self.file_data.filename)
                if self.prompt_options['main_opt'] == 'Mix':
                    self.prompt_options['main_opt'] = 'Definitions'
                return self.duration
            elif extension in ['.pdf']:
                file_path = save_file_to_upload_folder(self.file_data)
                self.text = clean_text(extract_from_pdf(file_path))
                os.remove(file_path)
            elif extension in ['.pptx']:
                self.text = clean_text(extract_from_pptx(self.file_data))
            elif extension in ['.docx']:
                self.text = clean_text(extract_from_docx(self.file_data))
            elif extension in ['.txt']:
                self.text = self.extract_from_txt()
            else:
                raise UnsupportedFileError
        elif self.text_data:
            self.text = self.text_data
            self.type = 'text'
        elif self.link_data:
            self.text, self.type = extract_from_url(self.link_data)
        return self.text

    def quantity_tokens(self):
        print("Getting quantity tokens")
        try:
            if self.extension in ['.wav', '.mp3']:
                self.tokens = convert_time_to_tokens(self.duration)
            else:
                print(self.text)
                tokens = count_tokens(self.text)
                print(tokens)
                self.tokens = count_tokens(self.text)
            return self.tokens
        except Exception as e:
            print(f"Error occurred while counting tokens: {str(e)}")


    def save_source_text(self):
        if self.type not in ['.wav', '.mp3']:
            name = f"{self.deck.name}_source"
            file_storage = DeckFiles(file_name=name,
                    text_string=self.text, create_type = "source",
                    time_created = dt.datetime.now(dt.timezone.utc))
            self.db_session.add(file_storage)
            self.deck.deck_files.append(file_storage)
            self.db_session.commit()

    def create_jobs(self):
        if self.extension in ['.wav', '.mp3']:
            self.audio_job_creator()
        else:
            print("abotu to split text")
            texts= split_text(self.text)
            print(type(texts))
            self.text = texts
            if not isinstance(texts, list):
                self.text = [texts]
            if self.prompt_options['main_opt'] == 'Mix':
                print("Mixing")
                prompt = 'Definitions'
                self.job_creator(prompt)
                prompt = 'Mcq'
                self.job_creator(prompt)
            else:
                prompt = self.prompt_options['main_opt']
                self.job_creator(prompt)
            self.job_creator('Summarize')
            self.notification_creator()

    def audio_job_creator(self):
        upload_folder = UPLOAD_FOLDER
        random_string = ''.join(random.choices('0123456789', k=5))
        original_filename = self.file_data.filename
        filename, extension = os.path.splitext(original_filename)
        new_filename = f"{filename}_{random_string}{extension}"
        new_filename_secure = secure_filename(new_filename)
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, new_filename_secure)
        self.file_data.save(file_path)
        self.file_data = None
        self.extract_audio(file_path)

    def job_creator(self, prompt):
        print("Creating jobs", prompt)
        prompt_options = self.prompt_options
        prompt_options['main_opt'] = prompt
        print(type(self.text))
        counter = 0

        for text in self.text:
            print(text)
            total_len = len(self.text)
            print(total_len)
            counter = counter + 1
            print(counter)
            payload_dict = {'deck': self.deck.id, 'text': text,
                'prompt_options': prompt_options, 'task_type': 'standard'}
            payload = json.dumps(payload_dict)
            data = Job(slug=self.slug, user = current_user.id,
                       task_type = prompt, payload = payload,
                       item_number = counter, deck_id = self.deck.id,
                       item_quantity = total_len)
            if counter == total_len:
                session['slug'] = self.slug
                self.db_session.add(data)
                print(data)
                print(self.db_session)
                self.db_session.commit()

    def notification_creator(self):
        job_notification = JobNotification(user_id=current_user.id,
            slug = self.slug,  cost = self.tokens, date_created = dt.datetime.now(dt.timezone.utc),
              input_details=self.type)
        self.db_session.add(job_notification)
        self.db_session.commit()





    ## AUDIO EXTRACTORS
    def extract_audio(self, file):
        print("Entered extract audio function")
        print(file)
        # Create the "audio_segments" folder if it doesn't exist
        folder_path = "audio_segments"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        try:
            segments = divide_audio(file)
            item_quantity = len(segments)
            for segment in segments:
                item_number = segments.index(segment) + 1
                self.create_audio_job(segment, item_number, item_quantity)
        except Exception as e:
            # Handle any exceptions that may occur during audio extraction
            print(f"Error occurred during audio extraction: {str(e)}")
        try:
            os.remove(file)
            print(f"File {file} deleted successfully.")
        except Exception as e:
            print(f"Error occurred while deleting file {file}: {str(e)}")


    def create_audio_job(self, segment, item_number, item_quantity):
        payload = {"prompt_options": self.prompt_options,
                    "segment": segment, 'deck': self.deck.id, 'task_type': 'audio'}
        payload_string = json.dumps(payload)
        audio_job = Job(task_type = "audio", state = "queued",
                    user = current_user.id, deck_id = self.deck.id,
                    payload = payload_string, slug = self.slug, 
                    item_number = item_number, item_quantity = item_quantity)
        self.db_session.add(audio_job)
        self.db_session.commit()


def tokens_general(form):
        print(form)
        ## if file is audio returns size of audio, otherwise the text
        if form.file.data:
            print("entered file function")
            print(form.file.data)
            extension = os.path.splitext(form.file.data.filename)[1].lower()
            if extension in ['.wav', '.mp3']:
                duration = get_audio_content(form.file.data, form.file.data.filename)
                return convert_time_to_tokens(duration)
            elif extension in ['.pdf']:
                print("entered pdf function")
                file_loc = save_file_to_upload_folder(form.file.data)
                text = clean_text(extract_from_pdf(file_loc))
                os.remove(file_loc)
            elif extension in ['.pptx']:
                text = clean_text(extract_from_pptx(form.file.data))
            elif extension in ['.docx']:
                text = clean_text(extract_from_docx(form.file.data))
            elif extension in ['.txt']:
                text = extract_from_txt(form.file.data)
            else:
                raise UnsupportedFileError
        elif form.text_input.data:
            print(form.text_input.data)

            print("entered text function")
            text = form.text_input.data
        elif form.link_input.data:
            print("entered link function")
            print(form.link_input.data)
            text, link_type = extract_from_url(form.link_input.data)
        return count_tokens(text)



def save_file_to_upload_folder(file):
    upload_folder = UPLOAD_FOLDER
    random_string = ''.join(random.choices('0123456789', k=5))
    original_filename = file.filename
    filename, extension = os.path.splitext(original_filename)
    new_filename = f"{filename}_{random_string}{extension}"
    new_filename_secure = secure_filename(new_filename)
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, new_filename_secure)
    file.save(file_path)
    return file_path


def get_audio_content(file_data, name):
    print("entered audio function")
    print(file_data)
    duration = get_duration(file_data, name)
    file_data.seek(0)
    return duration

def extract_from_pdf(file_data):
    n=3
    print(file_data)
    try:
        text = []
        # Using pdfminer.six to extract pages from PDF
        for i, page_layout in enumerate(extract_pages(file_data), start=1):
            current_page_text = ''
            for element in page_layout:
                if hasattr(element, "get_text"):
                    current_page_text += element.get_text()
            if len(current_page_text.strip()) < n: # Threshold check
                # If the text is less than n, then use OCR
                print(f"Using OCR for page {i}")
                try:
                    # Convert page to image
                    images = convert_from_path(file_data, first_page=i, last_page=i)
                    for image in images:
                        # Perform OCR on the image
                        current_page_text = image_to_string(image)
                except Exception as e:
                    print(f"Error occurred during OCR: {str(e)}")
            else:
                print(f"Using PDFMiner for page {i}")
            text.append(current_page_text)
        print(text)
        return "\n".join(text)
    
    except FileNotFoundError as e:
        print("File not found.")
        raise e
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
 

def extract_from_pptx(file_data):
    print("entered pptx function")
    print(file_data)
    try:
        prs = Presentation(file_data)
        print(prs)
        text_runs = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    cleaned_text = clean_text(shape.text)
                    print(cleaned_text)
                    text_runs.append(cleaned_text)
        return " ".join(text_runs)
    except FileNotFoundError as e:
        print("File not found. Exception message:", str(e))
    except Exception as e:
        print("An error occurred:", e)
    return None
    
def extract_from_docx(file_data):
    print("entered docx function")
    try:
        text = docx2txt.process(file_data)
        text = text.replace("\n", " ")
        return text
    except FileNotFoundError:
        print("File not found.")
    except Exception as e:
        print("An error occurred:", e)
    return None

def extract_from_txt(file_data):
    return pathlib.Path(file_data).read_text()    


def extract_from_url(link_data):
    print("entered url function")
    print(link_data)
    text = None
    if "wikipedia" in link_data:
        link_type = 'wiki'
        if check_comma_list(link_data):
            links = link_data.split(";")
            for link in links:
                part = extract_from_wiki(link)
                text = part if text is None else text + part
        else:
            text = extract_from_wiki(link_data)
    else:
        print("youtube link detected")
        link_type = 'youtube'
        if check_comma_list(link_data):
            links = link_data.split(";")
            for link in links:
                link = get_video_id(link)
                part = extract_from_youtube(link)
                text = part if text is None else text + part
        else:
            print("no commas")
            link = get_video_id(link_data)
            print(link)
            text = extract_from_youtube(link)
            print(text)
    return text, link_type

def extract_from_wiki(wiki_url):
    try:
        print("entered wiki function")
        content = make_request(wiki_url)
        return process_soup(content)
    except requests.exceptions.RequestException as e:
        print("Error making the HTTP request:", e)
    except Exception as e:
        print("An error occurred:", e)
        return None

def extract_from_youtube(youtube_url):
    try:
        full_text = None
        transcripts = YouTubeTranscriptApi.list_transcripts(youtube_url)
        transcript = None
        # Iterate over transcripts and choose the first manually created transcript, if it exists
        for t in transcripts:
            if not t.is_generated:
                transcript = t
                break
        # If no manually created transcript found, choose the first auto-generated transcript
        if transcript is None:
            for t in transcripts:
                if t.is_generated:
                    transcript = t
                    break
        # If no transcript is found, raise an error
        if transcript is None:
            raise YoutubeError
        # Fetch the transcript
        srt = transcript.fetch()
        for dict in srt:
            x = dict['text']
            if full_text is None:
                full_text = x
            else:
                full_text += x
        return full_text

    except Exception as e:
        print("An error occurred:", e)
        raise YoutubeError
    

## remove unecessary elements of youtube link
def get_video_id(link):
    # Remove any whitespace from the link
    link = ''.join(link)
    link = link.strip()

    # Define regular expression patterns for different YouTube video URL formats
    patterns = [
        r"youtu\.be/([^/]+)",
        r"youtube\.com/watch\?v=([^&]+)",
        r"youtube\.com/embed/([^/]+)",
        r"youtube\.com/v/([^/]+)",
        r"youtube\.googleapis\.com/v/([^/]+)"
    ]

    # Try to match the link to one of the patterns
    for pattern in patterns:
        if match := re.search(pattern, link):
            return match[1]
    # If the link does not match any of the patterns, return None
    return None


def check_comma_list(string):
    if "," in string:
        return True
    else:
        return False
    

def clean_text(text):
    # Decode Unicode escape sequences into actual characters
    text = codecs.decode(text, 'unicode_escape')
    # Replace newline characters with spaces
    # This pattern matches any character that is not a letter, digit, whitespace, or regular punctuation.
    pattern = r"[^\w\s.,;:?!-’'\"()]+"
    return re.sub(pattern, "", text)

def make_request(wiki_url):
    # Replace the URL with the mobile version
    wiki_url = re.sub(r"https://(..).wikipedia.org", r"https://\1.m.wikipedia.org", wiki_url)
    page = requests.get(wiki_url)
    page.raise_for_status()  # Check for any HTTP request errors
    return page.content

def process_soup(content):
    soup = BeautifulSoup(content, 'html.parser')
    # Remove unwanted HTML elements
    remove_elements(soup)
    return extract_content(soup)

def remove_elements(soup):
    unwanted_tags = ['script', 'style', 'table', 'noscript', 'nav', 'header', 'footer', 'sup', 'div', 'h2', 'li', 'a']
    unwanted_class_types = ['reference', 'toc', 'thumbcaption', 'reflist', 'navbox', 'section-heading', 'references']
    unwanted_selectors = ['.portalbox-entry', '.firstHeading', '#footer-info-lastmod', '#footer-info-copyright', '#footer-places-privacy', '#footer-places-about', '#footer-places-disclaimers', '#footer-places-contact', '#footer-places-terms-use', '#footer-places-desktop-toggle', '#footer-places-developers', '#footer-places-statslink', '#footer-places-cookiestatement']
    unwanted_attrs = [{'id': 'toc'}, {'id': 'page-secondary-actions'}, {'id': 'toc'}]
    unwanted_list = ['interlanguage-link']

    for tag, cls in zip(unwanted_tags, unwanted_class_types):
        for item in soup.find_all(tag, class_=cls):
            item.extract()

    for selector in unwanted_selectors:
        for tag in soup.select(selector):
            tag.extract()

    for attrs in unwanted_attrs:
        for div in soup.find_all('div', attrs):
            div.extract()

    for item in unwanted_list:
        for li in soup.find_all('li', class_=item):
            li.extract()
    for li in soup.find_all('li'):
        if li.find('a'):
            li.extract()

def extract_content(soup):
    wanted_tags = ['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td']
    extracted_content = []
    for tag in wanted_tags:
        elements = soup.find_all(tag)
        extracted_content.extend(element.get_text(strip=True, separator=' ') for element in elements)
    return "\n\n".join(extracted_content)

## returns duration in seconds
def get_duration(file, name):
    file_data = file.read()
    temp_filename = "temp_audio_file" + name
    with open(temp_filename, "wb") as temp_file:
        temp_file.write(file_data)
    info = mediainfo(temp_filename)
    try:
        duration = float(info["duration"])
    except Exception as e:
        print("An error occurred:", e)
        raise AudioError
    time_base = float(info["time_base"].split("/")[1])
    duration = float(info['duration_ts']) / time_base
    os.remove(temp_filename)
    return duration


def convert_time_to_tokens(time):
    logger.info("converting time to tokens")
    tokens = ((time / 60)/PAGES_PER_MIN) * TOKENS_PER_PAGE
    logger.info("tokens %s", tokens)
    return tokens

def divide_audio(input_file, segment_length=25):
    try:
        # Open the audio file
        random_string = ''.join(random.choices('0123456789', k=5))
        audio = AudioSegment.from_file(input_file)
        # Calculate the segment size in bytes
        segment_size = segment_length * 1024 * 1024
        # Calculate the total number of segments
        num_segments = math.ceil(len(audio) / segment_size)
        # Create a list to hold the file paths for the audio segments
        segment_paths = []
        # Split the audio file into segments and save each segment as an MP3 file
        for i in range(num_segments):
            start = i * segment_size
            end = min((i + 1) * segment_size, len(audio))
            segment = audio[start:end]
            # Define the output file path for the segment
            output_file = os.path.join(os.path.dirname(input_file), f"{random_string}segment_{i}.mp3")
            # Export the segment as an MP3 file
            segment.export(output_file, format="mp3")
            print(output_file)
            # Add the output file path to the list of segment paths
            segment_paths.append(output_file)
        return segment_paths

    except FileNotFoundError:
        print("File not found.")
    except Exception as e:
        print("An error occurred:", str(e))

    return None