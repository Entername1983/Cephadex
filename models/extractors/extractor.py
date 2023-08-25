import pathlib
import requests
import re
import codecs
import random
import json
import os
import math
import datetime as dt

from werkzeug.utils import secure_filename
from flask import session
from flask_login import current_user

from pdf2image import convert_from_path
from pdfminer.high_level import extract_pages
from pptx import Presentation
import docx2txt
from pydub import AudioSegment
from youtube_transcript_api import YouTubeTranscriptApi
from bs4 import BeautifulSoup
from pydub.utils import mediainfo
from pytesseract import image_to_string

import openai
import tiktoken

from models.models_ import Deck, Job, JobNotification, DeckFiles
from tools.lists import DECK_NAMES
from models.helpers.helpers import count_tokens, split_text
from models.exceptions.exceptions import (
    YoutubeError, UnsupportedFileError, AudioError, ExtractionError,
    ExtractionWikiError
)

from models.extractors.extractor_config import PAGES_PER_MIN, TOKENS_PER_PAGE

from typing import TYPE_CHECKING, Any, Optional, Union, IO
if TYPE_CHECKING:
    from sqlalchemy.orm import Session  # Or whatever the correct import path is for your db_session
    from flask_wtf import FlaskForm


openai.api_key = os.environ.get("OPENAI_API_KEY")
encoding = tiktoken.get_encoding("cl100k_base")
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER")


""" This class is responsible for storing the data and instructions related to content creation 
and creating a job object that will be later used for the actual processing.  It accepts either 
a flask form or a dictionary of options and will create a job object accordingly.  It also
 contains the main extraction function which will be called by the main controller. """
class Extractor:
    def __init__(self, db_session: 'Session', form: 'Optional[FlaskForm]' =None, slug: str =None, **kwargs: Any):
        self.db_session: 'Session' = db_session
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

        self.prompt_options: dict = options

        self.description = kwargs.get('description', None)
        deck = kwargs.get('deck_list', None)
        if deck is not None:
            self.deck: Deck = deck
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
            self.file_data: Optional[str] = form.file.data or kwargs.get('file', None)
            self.text_data: Optional[str] = form.text_input.data or kwargs.get('text_input', None)
            self.link_data: Optional[str] = form.link_input.data or kwargs.get('link_input', None)
        else:
            self.file_data: Optional[str] = kwargs.get('file', None)
            self.text_data: Optional[str] = kwargs.get('text_input', None)
            self.link_data: Optional[str] = kwargs.get('link_input', None)
        self.slug: str = slug or str(current_user.id) + dt.datetime.now(dt.timezone.utc).isoformat()
        self.extension: str = None
        self.text: str = None
        self.tokens: int = None

    def __repr__(self):
        return (f"Extractor(prompt_options={self.prompt_options}, "
                f"description={repr(self.description)}, "
                f"deck={repr(self.deck)}, "
                f"file_data={repr(self.file_data)}, "
                f"text_data={repr(self.text_data)}, "
                f"link_data={repr(self.link_data)}, "
                f"slug={repr(self.slug)})")

    def get_deck(self, form: 'FlaskForm') -> tuple['Deck', bool]:
        """ Retrieves the deck object and a boolean to determine whether a new deck was created """
        if form.deck_list.data:
            self.deck = form.deck_list.data
            return form.deck_list.data, False
        else:
            chosen_name = form.name.data if form.name.data else random.choice(DECK_NAMES)
            deck = Deck(name=chosen_name, user_id=current_user.id,
                            description=self.description)
            self.deck = deck
            return deck, True


    def get_content(self) -> str:
        """ Retrieves the text content from input, or in the case of an audio file the duration
        of the the file """
        if self.file_data:
            extension = os.path.splitext(self.file_data.filename)[1].lower()
            self.extension = extension
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

    def quantity_tokens(self) -> int:
        """ Gives a token cost depending on number of characters (or length of audio file)"""
        if self.extension in ['.wav', '.mp3']:
            self.tokens = convert_time_to_tokens(self.duration)
        else:
            self.tokens = count_tokens(self.text)
        return self.tokens

    def save_source_text(self) -> None:
        """ Saves the source text as a deckfile object to be stored in the db"""
        if self.extension not in ['.wav', '.mp3']:
            name = f"{self.deck.name}_source"
            file_storage = DeckFiles(file_name=name,
                    text_string=self.text, create_type = "source",
                    time_created = dt.datetime.now(dt.timezone.utc))
            self.db_session.add(file_storage)
            self.deck.deck_files.append(file_storage)
            self.db_session.commit()

    def create_jobs(self) -> None:
        """ creates either audio job or regular job and matching job notification object"""
        if self.extension in ['.wav', '.mp3']:
            self.type = "audio"
            self.audio_job_creator()
        else:
            texts= split_text(self.text)
            self.text = texts
            if not isinstance(texts, list):
                self.text = [texts]
            if self.prompt_options['main_opt'] == 'Mix':
                prompt = 'Definitions'
                self.job_creator(prompt)
                prompt = 'Mcq'
                self.job_creator(prompt)
            else:
                prompt = self.prompt_options['main_opt']
                self.job_creator(prompt)
            self.job_creator('Summarize')
        self.notification_creator()

    def audio_job_creator(self) -> None:
        """ renames and stores the audio file """
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

    def job_creator(self, prompt: str) -> None:
        prompt_options = self.prompt_options
        prompt_options['main_opt'] = prompt
        counter = 0
        for text in self.text:
            total_len = len(self.text)
            counter = counter + 1
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
                self.db_session.commit()

    def notification_creator(self) -> None:
        job_notification = JobNotification(user_id=current_user.id,
            slug = self.slug,  cost = self.tokens, date_created = dt.datetime.now(dt.timezone.utc),
              input_details=self.type)
        self.db_session.add(job_notification)
        self.db_session.commit()





    ## AUDIO EXTRACTORS
    def extract_audio(self, file: str) -> None:
        """ Divides up audio if necessary into segments and stores them, then creating individual jobs"""
        folder_path = "audio_segments"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        try:
            segments = divide_audio(file)
            item_quantity = len(segments)
            for segment in segments:
                item_number = segments.index(segment) + 1
                self.create_audio_job(segment, item_number, item_quantity)
            os.remove(file)
        except Exception as e:
            # Handle any exceptions that may occur during audio extraction
            print(f"Error occurred during audio extraction: {str(e)}")
            raise AudioError 



    def create_audio_job(self, segment: str, item_number: int, item_quantity: int) -> None:
        """ creates the actual audio job to be stored in the db"""
        payload = {"prompt_options": self.prompt_options,
                    "segment": segment, 'deck': self.deck.id, 'task_type': 'audio'}
        payload_string = json.dumps(payload)
        audio_job = Job(task_type = "audio", state = "queued",
                    user = current_user.id, deck_id = self.deck.id,
                    payload = payload_string, slug = self.slug, 
                    item_number = item_number, item_quantity = item_quantity)
        self.db_session.add(audio_job)
        self.db_session.commit()


def tokens_general(form: 'FlaskForm') -> int:
    """ counts tokens from flask form """
    if form.file.data:
        extension = os.path.splitext(form.file.data.filename)[1].lower()
        if extension in ['.wav', '.mp3']:
            duration = get_audio_content(form.file.data, form.file.data.filename)
            return convert_time_to_tokens(duration)
        elif extension in ['.pdf']:
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
        text = form.text_input.data
    elif form.link_input.data:
        text, link_type = extract_from_url(form.link_input.data)
    return count_tokens(text)



def save_file_to_upload_folder(file: str) -> str:
    """ saves a file to appropriate folder"""
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


def get_audio_content(file_data: str, name: str) -> float:
    """ returns the duration of an audio file"""
    duration = get_duration(file_data, name)
    file_data.seek(0)
    return duration

def extract_from_pdf(file_data: str, n: int = 3) -> str:
    """ extracts text from a pdf, if a page has less than n characters attempts OCR
    otherwise defautls to pdf miner"""
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
                    ## TO DO figure out how to handle this properly

            text.append(current_page_text)
        return "\n".join(text)

    except FileNotFoundError as e:
        raise e
    except Exception as e:
        raise ExtractionError(f"Failed to extract data: {e}") from e

def extract_from_pptx(file_data: str) -> Optional[str]:
    """ extracts text from a pptx file"""
    try:
        prs = Presentation(file_data)
        text_runs = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    cleaned_text = clean_text(shape.text)
                    print(cleaned_text)
                    text_runs.append(cleaned_text)
        return " ".join(text_runs)
    except FileNotFoundError as e:
        raise e
    except Exception as e:
        raise ExtractionError(f"Failed to extract data: {e}") from e
    
def extract_from_docx(file_data: str) -> Optional[str]:
    print("entered docx function")
    try:
        text = docx2txt.process(file_data)
        text = text.replace("\n", " ")
        return text
    except FileNotFoundError as e:
        raise e from e
    except Exception as e:
        raise ExtractionError(f"Failed to extract data: {e}") from e

def extract_from_txt(file_data: str) -> str:
    """ extracts text from a text file """
    try:
        return pathlib.Path(file_data).read_text()
    except Exception as e:
        raise ExtractionError(f"Failed to extract data: {e}") from e    


def extract_from_url(link_data: str) -> tuple[str, str]:
    """ extracts text from a url, either wiki or youtube """
    text = None
    try:
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
            link_type = 'youtube'
            if check_comma_list(link_data):
                links = link_data.split(";")
                for link in links:
                    link = get_video_id(link)
                    part = extract_from_youtube(link)
                    text = part if text is None else text + part
            else:
                link = get_video_id(link_data)
                text = extract_from_youtube(link)
        return text, link_type
    except Exception as e:
        raise ExtractionError(f"Failed to extract data: {e}") from e

def extract_from_wiki(wiki_url: str) -> str:
    """ extract from wikilinks"""
    try:
        content = make_request(wiki_url)
        return process_soup(content)
    except requests.exceptions.RequestException as e:
        raise e from e
    except Exception as e:
        raise ExtractionWikiError(f"Failed to extract data: {e}") from e

def extract_from_youtube(youtube_url: str) -> str:
    """ extracts from youtube """
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
            raise YoutubeError("Transcript not found")
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
        raise YoutubeError(f"Failed to extract data: {e}") from e
    

def get_video_id(link: Union[str, list[str]]) -> Optional[str]:
    """ cleans up youtube links nad puts them in teh appropriate format to use
    with the youtube extraction api"""
    link = ''.join(link)
    link = link.strip()
    patterns = [
        r"youtu\.be/([^/]+)",
        r"youtube\.com/watch\?v=([^&]+)",
        r"youtube\.com/embed/([^/]+)",
        r"youtube\.com/v/([^/]+)",
        r"youtube\.googleapis\.com/v/([^/]+)"
    ]
    for pattern in patterns:
        if match := re.search(pattern, link):
            return match[1]



def check_comma_list(string: str) -> bool:
    """ checks if there is a comma in a string --> indicating more htan one link"""
    """ deprecated to use semi colon?"""
    return "," in string
    

def clean_text(text: str) -> str:
    """Decode Unicode escape sequences into actual characters"""
    text = codecs.decode(text, 'unicode_escape')
    # Replace newline characters with spaces
    # This pattern matches any character that is not a letter, digit, whitespace, or regular punctuation.
    pattern = r"[^\w\s.,;:?!-’'\"()]+"
    return re.sub(pattern, "", text)

def make_request(wiki_url: str) -> 'bytes':
    # Replace the URL with the mobile version
    wiki_url = re.sub(r"https://(..).wikipedia.org", r"https://\1.m.wikipedia.org", wiki_url)
    page = requests.get(wiki_url)
    page.raise_for_status()  # Check for any HTTP request errors
    return page.content

def process_soup(content: str) -> str:
    """ processes the content of the page to extract the text """
    soup = BeautifulSoup(content, 'html.parser')
    # Remove unwanted HTML elements
    remove_elements(soup)
    return extract_content(soup)

def remove_elements(soup: BeautifulSoup):
    """ remove unwanted elements from wiki page"""
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

def extract_content(soup: BeautifulSoup) -> str:
    """ beautiful soup extractor"""
    wanted_tags = ['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td']
    extracted_content = []
    for tag in wanted_tags:
        elements = soup.find_all(tag)
        extracted_content.extend(element.get_text(strip=True, separator=' ') for element in elements)
    return "\n\n".join(extracted_content)

## returns duration in seconds
def get_duration(file, name: str) -> float:
    """ gets duration of audio file"""
    file_data = file.read()
    temp_filename = f"temp_audio_file{name}"
    with open(temp_filename, "wb") as temp_file:
        temp_file.write(file_data)
    info = mediainfo(temp_filename)
    try:
        duration = float(info["duration"])
    except Exception as e:
        print("An error occurred:", e)
        raise AudioError from e
    time_base = float(info["time_base"].split("/")[1])
    duration = float(info['duration_ts']) / time_base
    os.remove(temp_filename)
    return duration


def convert_time_to_tokens(time: float) -> float:
    """ converts time to tokens"""
    return ((time / 60)/PAGES_PER_MIN) * TOKENS_PER_PAGE

def divide_audio(input_file: 'Union[str, IO[bytes]]', segment_length: int =25) -> list[str]:
    """ divides audio into segments of a length of at most segment_length mb (defautls to 25)"""
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
            # Add the output file path to the list of segment paths
            segment_paths.append(output_file)
        return segment_paths

    except FileNotFoundError as e:
        raise e from e


