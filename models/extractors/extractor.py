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
from models.storage.s3 import upload_to_s3
import openai
import tiktoken
from models.jobs.jobs_config import LONG_FORM_JOBS

from models.models_ import Deck, Job, JobNotification, DeckFiles
from tools.lists import DECK_NAMES
from models.helpers.helpers import count_tokens, split_text
from models.exceptions.exceptions import (
    YoutubeError, UnsupportedFileError, AudioError, ExtractionError,
    ExtractionWikiError
)
import logging
from config.settings import PAGES_PER_MIN, TOKENS_PER_PAGE, MAX_TOKENS_PER_JOB
from models.helpers.log_decorators import log_decorator

from typing import TYPE_CHECKING, Any, Optional, Union, IO
if TYPE_CHECKING:
    from sqlalchemy.orm import Session  # Or whatever the correct import path is for your db_session
    from flask_wtf import FlaskForm


openai.api_key = os.environ.get("OPENAI_API_KEY")
encoding = tiktoken.get_encoding("cl100k_base")
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER")

logger = logging.getLogger("flask_app")

"""
This class serves as the central hub for content creation tasks, orchestrating the conversion of input data 
into actionable jobs for further processing. It plays a key role in the following:

1. Data Storage: Holds data and instructions pertinent to content creation.
2. Job Object Creation: Creates job objects based on either a Flask form or a dictionary of options.
   (Note: 'deck' and 'description' fields are disabled when using a dictionary.) <-- TO DO
3. Extraction Function: Houses the primary function for data extraction, invoked by the main controller.

Features:
- Slug ID: A unique identifier shared across all jobs and their corresponding notification entries for each extraction.
- Audio Job Special Handling: Audio jobs undergo a two-step process. The initial step is transcription, 
  which is queued before standard jobs for the same audio source are generated.

Usage:
The class takes in a form or a dictionary and performs the following tasks:
1. Transforms the form into a 'payload,' which comprises sets of instructions for an AI model.
2. Creates a new 'deck' entry in the database.
3. Generates a notification entry to keep track of job status.
"""
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
            'create_summary_opt': kwargs.get('create_summary', None),
            'create_notes_opt': kwargs.get('create_notes', None),
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
            options['create_summary_opt'] = form.create_summary.data
            options['create_notes_opt'] = form.create_notes.data

        self.prompt_options: dict = options
        # self.description = kwargs.get('description', None)
        # deck = kwargs.get('deck_list', None)
        # if deck is not None:
        #     print(f"recognized deck not none {deck}")
        #     self.deck: Deck = deck
        # else:
        #     print("deck is none, creating deck")
        #     if not kwargs.get('name', None):
        #         chosen_name = random.choice(DECK_NAMES)
        #     else:
        #         chosen_name = kwargs.get('name')
        #     deck = Deck(name=chosen_name, user_id=current_user.id,
        #                 description=self.description)
        #     db_session.add(deck)
        #     db_session.commit()
        #     self.deck = deck

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
        self.description: str = None

    def __repr__(self):
        return (f"Extractor(prompt_options={self.prompt_options}, "
                f"file_data={repr(self.file_data)}, "
                f"text_data={repr(self.text_data)}, "
                f"link_data={repr(self.link_data)}, "
                f"slug={repr(self.slug)})")
    
    @log_decorator
    def get_deck(self, form: 'FlaskForm') -> tuple['Deck', bool]:
        """ Retrieves the deck object and a boolean to determine whether a new deck was created """
        if form.deck_list.data:
            self.deck = form.deck_list.data
            return form.deck_list.data, False
        else:
            chosen_name = form.name.data or random.choice(DECK_NAMES)
            description = form.description.data or None
            deck = Deck(name=chosen_name, user_id=current_user.id,
                            description=description)
            self.deck = deck
            return deck, True

    @log_decorator
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
                self.type = 'pdf'
                os.remove(file_path)
            elif extension in ['.pptx']:
                self.text = clean_text(extract_from_pptx(self.file_data))
                self.type = 'pptx'
            elif extension in ['.docx']:
                self.text = clean_text(extract_from_docx(self.file_data))
                self.type = 'docx'
            elif extension in ['.txt']:
                self.text = self.extract_from_txt()
                self.type = 'txt'
            else:
                raise UnsupportedFileError
        elif self.text_data:
            self.text = self.text_data
            self.type = 'text'
        elif self.link_data:
            self.text, self.type = extract_from_url(self.link_data)
        return self.text
    
    @log_decorator
    def quantity_tokens(self) -> int:
        """ Gives a token cost depending on number of characters (or length of audio file)"""
        if self.extension in ['.wav', '.mp3']:
            self.tokens = convert_time_to_tokens(self.duration)
        else:
            self.tokens = count_tokens(self.text)
        return self.tokens
    
    @log_decorator
    def save_source_text(self) -> None:
        """ Saves the source text as a deckfile object to be stored in the db"""
        if self.prompt_options['save_text_opt'] is True and self.extension not in ['.wav', '.mp3']:
            name = f"{self.deck.name}_Source_Content"
            file_storage = DeckFiles(file_name=name,
                    text_string=self.text, create_type = "source",
                    time_created = dt.datetime.now(dt.timezone.utc))
            self.db_session.add(file_storage)
            self.deck.deck_files.append(file_storage)
            self.db_session.commit()

    @log_decorator
    def create_jobs(self) -> None:
        """ creates either audio job or regular job and matching job notification object"""
        if self.extension in ['.wav', '.mp3']:
            self.type = "audio"
            self.audio_job_creator()
        else:
            texts= split_text(self.text, MAX_TOKENS_PER_JOB)
            self.text = texts
            if not isinstance(texts, list):
                self.text = [texts]
            if self.prompt_options['main_opt'] == 'Mix':
                prompt = 'Definitions'
                self.job_creator(prompt)
                prompt = 'Mcq'
                self.job_creator(prompt)
                if self.prompt_options['create_notes_opt'] is True:
                    self.job_creator('Turn2notes')
                else:
                    self.job_creator('Summarize')
            else:
                prompt = self.prompt_options['main_opt']
                self.job_creator(prompt)
                if self.prompt_options['create_summary_opt'] is True:
                    self.job_creator('Summarize')
                elif self.prompt_options['create_notes_opt'] is True:
                    self.job_creator('Turn2notes')
        self.notification_creator()

    @log_decorator
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

    @log_decorator
    def job_creator(self, prompt: str) -> None:
        prompt_options = self.prompt_options
        prompt_options['main_opt'] = prompt
        counter = 0
        for text in self.text:
            total_len = len(self.text)
            counter = counter + 1
            payload_dict = {'deck': self.deck.id, 'text': text,
                'prompt_options': prompt_options, 'task_type': 'standard'}
            payload = json.dumps(payload_dict, ensure_ascii=False)
            logger.debug(f"payload is: {text[:50]}")
            data = Job(slug=self.slug, user = current_user.id,
                       task_type = "standard", payload = payload,
                       item_number = counter, deck_id = self.deck.id,
                       item_quantity = total_len)
            self.db_session.add(data)
            if counter == total_len:
                session['slug'] = self.slug
                self.db_session.commit()


    @log_decorator
    def notification_creator(self) -> None:
        job_notification = JobNotification(user_id=current_user.id,
            slug = self.slug,  cost = self.tokens, date_created = dt.datetime.now(dt.timezone.utc),
              input_details=self.type)
        self.db_session.add(job_notification)
        self.db_session.commit()


    ## AUDIO EXTRACTORS
    @log_decorator
    def extract_audio(self, file: str) -> None:
        """ Divides up audio if necessary into segments and stores them, then creating individual jobs 
        audio files need to be divided up into max chunks of 25mb for whisper """
        folder_path = "audio_segments"
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(folder_path)
        try:
            segments = divide_audio(file, self.duration)
            item_quantity = len(segments)
            print(file)
            for segment in segments:
                item_number = segments.index(segment) + 1
                self.create_audio_job(segment, item_number, item_quantity)
            os.remove(file)
        except Exception as e:
            # Handle any exceptions that may occur during audio extraction
            logger.error(f"Error occurred during audio extraction: {str(e)}, raising AudioError")
            raise AudioError 


    @log_decorator
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

@log_decorator
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


@log_decorator
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

@log_decorator
def get_audio_content(file_data: str, name: str) -> float:
    """ returns the duration of an audio file"""
    duration = get_duration(file_data, name)
    file_data.seek(0)
    return duration

@log_decorator
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
                try:
                    # Convert page to image
                    images = convert_from_path(file_data, first_page=i, last_page=i)
                    for image in images:
                        # Perform OCR on the image
                        current_page_text = image_to_string(image)
                except Exception as e:
                    logger.error(f"Error occurred during OCR: {str(e)}")
                    raise e

            text.append(current_page_text)
        return "\n".join(text)

    except FileNotFoundError as e:
        raise e
    except Exception as e:
        raise ExtractionError(f"Failed to extract data: {e}") from e
    
@log_decorator
def extract_from_pptx(file_data: str) -> Optional[str]:
    """ extracts text from a pptx file"""
    try:
        prs = Presentation(file_data)
        text_runs = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    cleaned_text = clean_text(shape.text)
                    text_runs.append(cleaned_text)
        return " ".join(text_runs)
    except FileNotFoundError as e:
        raise e
    except Exception as e:
        raise ExtractionError(f"Failed to extract data: {e}") from e
    
@log_decorator
def extract_from_docx(file_data: str) -> Optional[str]:
    try:
        text = docx2txt.process(file_data)
        text = text.replace("\n", " ")
        return text
    except FileNotFoundError as e:
        raise e from e
    except Exception as e:
        raise ExtractionError(f"Failed to extract data: {e}") from e
    
@log_decorator
def extract_from_txt(file_data: str) -> str:
    """ extracts text from a text file """
    try:
        return pathlib.Path(file_data).read_text()
    except Exception as e:
        raise ExtractionError(f"Failed to extract data: {e}") from e    

@log_decorator
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
        elif "youtube" in link_data:
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
        else:
            link_type = 'url'
            if check_comma_list(link_data):
                links = link_data.split(";")
                for link in links:
                    part = extract_from_other_url(link)
            else:
                text = extract_from_other_url(link_data)
        return text, link_type
    except Exception as e:
        raise ExtractionError(f"Failed to extract data: {e}") from e
    
@log_decorator
def extract_from_other_url(link: str) -> str:
    response = requests.get(link)
    text = ""
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        for paragraph in soup.find_all('p'):
            text = text + paragraph.text
        return text
    else:
        logger.error(f"Failed to retrieve the URL. Status code: {response.status_code}")
        raise ExtractionError(f"Failed to retrieve the URL. Status code: {response.status_code}")


@log_decorator
def extract_from_wiki(wiki_url: str) -> str:
    """ extract from wikilinks"""
    try:
        content = make_request(wiki_url)
        return process_soup(content)
    except requests.exceptions.RequestException as e:
        raise e from e
    except Exception as e:
        raise ExtractionWikiError(f"Failed to extract data: {e}") from e
    
@log_decorator
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
    
@log_decorator
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
    
@log_decorator
def clean_text(text: str) -> str:
    """Decode Unicode escape sequences into actual characters"""
    text = codecs.decode(text, 'unicode_escape')
    # Replace newline characters with spaces
    # This pattern matches any character that is not a letter, digit, whitespace, or regular punctuation.
    pattern = r"[^\w\s.,;:?!-’'\"()]+"
    return re.sub(pattern, "", text)

@log_decorator
def make_request(wiki_url: str) -> 'bytes':
    # Replace the URL with the mobile version
    wiki_url = re.sub(r"https://(..).wikipedia.org", r"https://\1.m.wikipedia.org", wiki_url)
    page = requests.get(wiki_url)
    page.raise_for_status()  # Check for any HTTP request errors
    return page.content

@log_decorator
def process_soup(content: str) -> str:
    """ processes the content of the page to extract the text """
    soup = BeautifulSoup(content, 'html.parser')
    # Remove unwanted HTML elements
    remove_elements(soup)
    return extract_content(soup)

@log_decorator
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

@log_decorator
def extract_content(soup: BeautifulSoup) -> str:
    """ beautiful soup extractor"""
    wanted_tags = ['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td']
    extracted_content = []
    for tag in wanted_tags:
        elements = soup.find_all(tag)
        extracted_content.extend(element.get_text(strip=True, separator=' ') for element in elements)
    return "\n\n".join(extracted_content)

## returns duration in seconds
@log_decorator
def get_duration(file, name: str) -> float:
    """ gets duration of audio file"""
    file_data = file.read()
    temp_filename = f"temp_audio_file{name}"
    with open(temp_filename, "wb") as temp_file:
        temp_file.write(file_data)
    logger.info(f"get duration of audio file {temp_filename}")
    info = mediainfo(temp_filename)
    try:
        duration = float(info["duration"])
    except Exception as e:
        logging.error("An error occurred when trying to get duration of audio file", e)
        raise AudioError from e
    time_base = float(info["time_base"].split("/")[1])
    duration = float(info['duration_ts']) / time_base
    os.remove(temp_filename)
    return duration


def convert_time_to_tokens(time: float) -> float:
    """ converts time to tokens - using estimates of how many pages a min of audio is
    worth and how many tokens a page is worth"""
    return ((time / 60)/PAGES_PER_MIN) * TOKENS_PER_PAGE

@log_decorator
def divide_audio(input_file: Union[str, IO[bytes]], duration: float, max_segment_size_MB: int = 20) -> list[str]:
    """Divides up the audio file into segments of at max 20mb of length, checks if any segments are below 0.1mb
    deletes those to avoid empty segments - """
    min_segment_size_MB = 0.1
    try:
        file_size_bytes = os.path.getsize(input_file)
        max_segment_size_bytes = max_segment_size_MB * 1024 * 1024
        num_segments = math.ceil(file_size_bytes / max_segment_size_bytes)
        random_string = ''.join(random.choices('0123456789', k=5))
        file_extension = os.path.splitext(input_file)[-1].replace(".", "")
        audio = AudioSegment.from_file(input_file, format=file_extension)
        segment_length_ms = duration // num_segments
        start_time = 0
        end_time = segment_length_ms * 1000  # milliseconds in segment_length seconds
        total_length = len(audio)
        segment_paths = []
        while start_time < total_length:
            segment = audio[start_time:end_time]
            output_file = f"{random_string}_segment_{start_time}.mp3"
            logger.info(output_file)            
            segment.export((output_file), format="mp3")
            upload_to_s3('cephadex', 'audio_segments', output_file)

            if os.path.getsize(output_file) > min_segment_size_MB * 1024 * 1024:
                segment_paths.append(str(output_file))
            else:
                os.remove(output_file)
            start_time += segment_length_ms * 1000 
            end_time += segment_length_ms * 1000
        return segment_paths
            
    except FileNotFoundError as e:
        logging.error(f"File not found in divide_audio: {e}")
        raise e from e
    # except Exception as e:
    #     logging.error(f"An unexpected error occurred during divide audio: {e}")
    #     raise e from e

# Sample call
# Assuming your input_file is "example.mp3" and you want each segment to be 25 seconds long



# def divide_audio1(input_file_path, segment_length=25):
#     print("entered divide audio")
#     segment_paths = []
#     random_string = ''.join(random.choices('0123456789', k=5))
#     ##segment_size = segment_length * 1024 * 1024  # size in bytes

#     start_ms = 0  # start time in milliseconds
#     end_ms = segment_length * 1000  # end time in milliseconds
#     audio = AudioSegment.from_mp3(input_file_path)
#     total_length = len(audio)

#     while start_ms < total_length:
#         segment = audio[start_ms:end_ms]
#         output_file = os.path.join(os.path.dirname(input_file_path), f"{random_string}_segment_{start_ms}.mp3")
#         segment.export(output_file, format="mp3")
#         segment_paths.append(output_file)
        
#         # move to next segment
#         start_ms += segment_length * 1000
#         end_ms += segment_length * 1000

#     return segment_paths

# def divide_audio2(input_file: 'Union[str, IO[bytes]]', segment_length: int =25) -> list[str]:
#     print("entered divide audio")
#     """ divides audio into segments of a length of at most segment_length mb (defautls to 25)"""
#     try:
#         # Open the audio file
#         random_string = ''.join(random.choices('0123456789', k=5))
#         audio = AudioSegment.from_file(input_file)
#         # Calculate the segment size in bytes
#         segment_size = segment_length * 1024 * 1024
#         # Calculate the total number of segments
#         num_segments = math.ceil(len(audio) / segment_size)
#         # Create a list to hold the file paths for the audio segments
#         segment_paths = []
#         # Split the audio file into segments and save each segment as an MP3 file
#         for i in range(num_segments):
#             start = i * segment_size
#             end = min((i + 1) * segment_size, len(audio))
#             segment = audio[start:end]
#             # Define the output file path for the segment
#             output_file = os.path.join(os.path.dirname(input_file), f"{random_string}segment_{i}.mp3")
#             # Export the segment as an MP3 file
#             segment.export(output_file, format="mp3")
#             # Add the output file path to the list of segment paths
#             segment_paths.append(output_file)
#         return segment_paths

#     except FileNotFoundError as e:
#         raise e from e
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")


