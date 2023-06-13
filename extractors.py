
from pdf2image import convert_from_path
from pdfminer.high_level import extract_pages
from reportlab.pdfgen import canvas
import openai 
from error_handlers import YoutubeError
from pptx import Presentation
import docx2txt
import json
from pydub import AudioSegment
import os
from io import BytesIO
import math
from youtube_transcript_api import YouTubeTranscriptApi
import tiktoken
import textwrap
from reportlab.lib.pagesizes import letter
from prompts import prompt_choices, prompt_choices2, lang_choices, len_choices
from prompts import  regen_choices, prompt_from_scratch
from bs4 import BeautifulSoup
import requests
from pylatexenc.latex2text import LatexNodes2Text
import re
import asyncify
import codecs
import logging
from models import Job
from datetime import datetime
import random
from models import db
from pytesseract import image_to_string

openai.api_key = os.environ.get("OPENAI_API_KEY")

encoding = tiktoken.get_encoding("cl100k_base")
logger = logging.getLogger("extractors")
logger.setLevel(logging.DEBUG)


## CALLS TO OPEN AI API
async def call_ai_terms(sys_instruct, user_prompt):
    print("entered call ai terms")
    print(openai.api_key)
    print(f"Process {os.getpid()} before call: API key is {os.environ.get('OPENAI_API_KEY')}")

    try:
        response = await asyncify(openai.ChatCompletion.create)(
            model="gpt-3.5-turbo",
            messages=[
                    {"role": "system", "content": sys_instruct},
                    {"role": "user", "content": user_prompt},
                ],
            )
    except Exception as e:
        print(e)
    print(f"Process {os.getpid()} before call: API key is {os.environ.get('OPENAI_API_KEY')}")

    print("after supposed api call")
    print(openai.api_key)

    return response


async def add_more_cards(subject, topic, concepts, grade, extract_type):
    print("entered add more cards")
    sys_instruct = "You are an excellent teacher, knowledgeable on all subjects who is an expert at making detailed content, you only return data in JSON format"
    prompt = build_add_more_cards_prompt(subject, topic, concepts, grade, extract_type)
    response = await call_ai_terms(sys_instruct, prompt)
    response_ = response['choices'][0]['message']['content'].strip()
    print("response:", response_)
    if extract_type == "Cloze":
        response_ = add_underscores(response_)
    byte_string = response_.encode('utf-8')
    x = byte_string.decode('utf-8')
    json_start = x.find('[')
    if json_start != -1:
        json_end = x.rfind(']')  # Find the position of the last closing bracket in the string
        if json_end != -1:
            json_part = x[json_start:json_end+1] 
    else:
        print("No valid JSON found")

    try:
        data = json.loads(json_part)
    except json.JSONDecodeError as e:
        print(f"Could not parse as JSON: {json_part}")
        print(f"Error details: {e}")
    return data



def build_add_more_cards_prompt(subject, topic, concepts, grade, extract_type):
    prompt = prompt_from_scratch[extract_type]
    prompt = prompt.replace("{subject}", subject)
    prompt = prompt.replace("{topic}", topic)
    prompt = prompt.replace("{concepts}", concepts)
    prompt = prompt.replace("{grade}", grade)
    return prompt

async def extract_deck_attributes(text):
    print("entered extract deck attributes function")
    sys_instruct = "You are an expert at education and classification of content by subject, topic and level of difficulty. You are diligent and think about things carefully and only return content in JSON format"
    user_prompt = 'Identify the main subject, topic, concepts and level of difficulty of the following text, the levels of difficulty should be based upon the educational level at which one would be expected to encounter the identified concepts, either primary school, middle school, high school, college or post-graduate level.  Return your response as a JSON object only in the following format: {"subject": "main subject identified", "topic": "main topic identified", "concepts": ["concept1", "concept2", ...], "difficulty": "difficulty level"}\n  The passage: \n {text}'
    user_prompt = user_prompt.replace('{text}', text)
    print("before call ai terms")
    print(openai.api_key)
    print(f"Process {os.getpid()} before call: API key is {os.environ.get('OPENAI_KEY')}")

    try:
        response = await call_ai_terms(sys_instruct, user_prompt)
    except Exception as e:
        print(e)
    print("after call ai terms")
    print(openai.api_key)

    print(response)
    response_ = response['choices'][0]['message']['content'].strip()
    
    byte_string = response_.encode('utf-8')
    x = byte_string.decode('utf-8')
    print(x)
    x = json.loads(x)
    return x

async def extract_terms(text: str, prompt_options: dict):
    text = remove_html_tags(text)
    print("entered extract term function")
    main_opt = prompt_options['main_opt']
    print(main_opt)
    prompt = build_prompt(prompt_options)
    try:
        sys_instruct = f"You are a helpful teacher who wants to help students learn {prompt_options['subject_opt']}."
        user_prompt = (prompt + text + 'The JSON object: \n')
        response = await call_ai_terms(sys_instruct, user_prompt)
        response_ = response['choices'][0]['message']['content'].strip()
        if main_opt == "Cloze":
            response_ = add_underscores(response_)
        byte_string = response_.encode('utf-8')
        x = byte_string.decode('utf-8')
        x = json.loads(x)
        return x, user_prompt, response, x
    except Exception as e:
        print(f"Error: {e}.")

def build_prompt(prompt_options: dict):
    if prompt_options['main_opt'] not in prompt_choices:
        print("Invalid prompt option")
        raise ValueError("Invalid prompt option")
    else:
        prompt = prompt_choices[prompt_options['main_opt']]
        if prompt_options['subject_opt'] != None:
            subject = "related to the subject of " + prompt_choices2[prompt_options['subject_opt']]
        else:
            subject = ""
        if prompt_options['lang_opt']!= None:
            lang = lang_choices[prompt_options['lang_opt']]
        else:
            lang = ""
        if prompt_options['detail_lvl_opt']:
            detail = len_choices[prompt_options['detail_lvl_opt']]
        else:
            detail = ""
        if prompt_options['min_opt']:
            qmin = "at least " + prompt_options['min_opt']
        else:
            qmin = "all"
        if prompt_options['max_opt']:
            qmax = ", and at most " + prompt_options['max_opt']
        else:
            qmax = ""
        if prompt_options['trans_opt']:
            trans_opt = prompt_options['trans_opt']
        else:
            trans_opt = ""
        if prompt_options['custom_term']:
            custom_term = prompt_options['custom_term']
        else:
            custom_term = ""
        if prompt_options['custom_content']:
            custom_content = prompt_options['custom_content']
        else:
            custom_content = ""
        prompt = prompt.replace('{qmin}', qmin).replace('{subject}', subject).replace('{qmax}', qmax).replace('{length}', detail).replace('{lang}', lang).replace('{trans}', trans_opt).replace('{custom_term}', custom_term).replace('{custom_content}', custom_content)
        print(prompt[:50])
    return prompt

async def summarize(items, prompt_options):
    items = remove_html_tags(items)
    print("entered summarize function")
    option_1 = "You are an expert and summarizing key points in a passage" 
    option_2 = f"Summarize the following passage and return it with HTML formatting, using header tags, paragraph tags and list tags where appropriate {items}"
    response = await call_ai_terms(option_1, option_2)
    response = response['choices'][0]['message']['content']
    byte_string = response.encode('utf-8')
    response = byte_string.decode('utf-8') 
    return response

async def turn_to_notes(items, prompt_options):
    items = remove_html_tags(items)
    print("entered text_to_notes function")
    option_1 = "You are an expert at turning text into study notes" 
    option_2 = f"Turn the following passage into study notes and return it using HTML formatting, using header tags, paragraph tags and list tags where appropriate, ignore table of contents and indexes {items}"
    response = await call_ai_terms(option_1, option_2)
    response = response['choices'][0]['message']['content']
    byte_string = response.encode('utf-8')
    response = byte_string.decode('utf-8')   
    return response

## TAKES TEXT OR LIST OF TEXT AND TRANSLATES IT TO THE LANGUAGE CHOSEN
## ISSUE IS HOW TO HAVE PARAGRAPH BREAKS
async def transcribe_and_translate(items, prompt_options):
    items = remove_html_tags(items)
    language = prompt_options['trans_opt']
    print(language)
    option_1 = f"You are a helpful {language} translator"
    option_2 = f"translate the following passage to {language}  return it with html formatting, use paragraph and header tags as appropriate: {items}"
    response = await call_ai_terms(option_1, option_2)
    response = response['choices'][0]['message']['content']
    byte_string = response.encode('utf-8')
    response = byte_string.decode('utf-8')   
    return response

## AUDIO TRANSCRIPTION
async def transcribe_whisper(audio_file):
    print("entered transcribe function")
    audio_file= open(audio_file, "rb")
    transcript = await asyncify(openai.Audio.transcribe)("whisper-1", audio_file)
    transcript = transcript["text"]
    return transcript
    
def call_ai_terms_non_async(sys_instruct, user_prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
                {"role": "system", "content": sys_instruct},
                {"role": "user", "content": user_prompt},
            ],
        )
    return response
## REGENERATE A DEFINITION
def regenerate_definition(term, prompt_options):
    retries = 0

    prompt = build_prompt_regen(term, prompt_options)
    print("entered regenerate_def function")
    while retries < 3:
        print("attempt:", retries)
        try:
            sys_instruct = f"You are a helpful teacher who wants to help students learn."
            user_prompt = prompt
            response = call_ai_terms_non_async(sys_instruct, user_prompt)
            x = response['choices'][0]['message']['content'].strip()
            print(x[:50])
            z = [term, ":"]
            y = "".join(z)
            if x.startswith(term):
                x = x.replace(term, "",)
            if x.startswith(y):
                x = x.replace(y, "", 1)
            x = x.strip()
            x = add_period(x)
            return x, user_prompt, response, x
        
        except Exception as e:
            retries += 1
            print(f"Error: {e}. Retrying ({retries}/3)")



def build_prompt_regen(term, prompt_options: dict):
    if prompt_options['main_opt'] not in regen_choices:
        print("Invalid prompt option")
        raise ValueError("Invalid prompt option")
    else:
        prompt = regen_choices[prompt_options['main_opt']]
        if prompt_options['subject_opt'] != None:
            subject = "related to the subject of " + prompt_choices2[prompt_options['subject_opt']]
        else:
            subject = ""
        if prompt_options['lang_opt']!= None:
            lang = lang_choices[prompt_options['lang_opt']]
        else:
            lang = ""
        if prompt_options['detail_lvl_opt']:
            detail = len_choices[prompt_options['detail_lvl_opt']]
        else:
            detail = ""
        if prompt_options['trans_opt']:
            trans_opt = prompt_options['trans_opt']
        else:
            trans_opt = ""

        prompt = prompt.replace('{length}', detail).replace('{lang}', lang).replace('{trans}', trans_opt).replace('{term}', term)
        print("prompt built")
   
    return prompt


###################################
def get_replacement_value(value, prefix='', suffix=''):
    if value:
        return prefix + value + suffix
    return ''



async def insert_paragraph(text):
    prompt = "Go through the following block of text and insert '&-&-&' where you think a paragraph break should be. \n  block of text: \n" + text + "\n The JSON object: \n"
    response = await asyncify(openai.ChatCompletion.create)(
            model="gpt-3.5-turbo",
            messages=[
                    {"role": "system", "content": "You are an expert at the written word"},
                    {"role": "user", "content": prompt},
                ],
            )
    x = response['choices'][0]['message']['content']
    return x

def render_latex(latex_code):
    unicode_str = LatexNodes2Text().latex_to_text(latex_code)
    return unicode_str

def double_backslashes(s):
    result = ''
    pattern = r'\\\[.*?\\\]|\\\(.*?\\\)|(?<!\\)\$.+?(?<!\\)\$'
    # Match LaTeX formulas delimited by \[...\] or \(...\), or inline formulas delimited by $...$
    matches = re.findall(pattern, s)
    last_end = 0
    for match in matches:
        start = s.index(match, last_end)
        result += s[last_end:start]
        result += re.sub(r'\\', r'\\\\', match)
        last_end = start + len(match)
    result += s[last_end:]
    return result

def decode_latex_in_string(string):
    # Define a regular expression pattern to match LaTeX formulas
    pattern = r'(\$[^\$]*\$|\\\([^\)]*\\\))'
    # Use the pattern to find all LaTeX formulas in the string
    matches = re.findall(pattern, string)
    # Loop over the matches and replace each LaTeX formula with its decoded equivalent
    for match in matches:
        decoded = render_latex(match)
        string = string.replace(match, decoded)
    
    return string

###################################



## TEXT EXTRACTORS
def text_extractor(file):
    print("entered text extractor function")
    print(file)
    if file.endswith('.pdf'):
        print("entered extract from pdf")
        items = extract_from_pdf(file) 
    elif file.endswith('.pptx'):
        items = extract_from_pptx(file) 
    elif file.endswith('.ppt'):
        items = extract_from_pptx(file) 
    elif file.endswith('.docx'):
        items = extract_from_docx(file)
    elif file.endswith('.doc'):
        items = extract_from_docx(file)

    elif file.endswith('.txt'):
        with open(file) as file:
            items = file.read()
    print("yeaaa")
    items = clean_text(items)
    print("what")
    tokens = count_tokens(items)
    print(items)
    print(tokens)
    return items, tokens



def audio_processing(file, current_user, deck_id, prompt_options, slug):
    print("entered audio processing function")
    if file.endswith('.wav'):
        extract_audio(file, current_user, deck_id, prompt_options, slug, '.wav')
    elif file.endswith('.mp3'):
        extract_audio(file, current_user, deck_id, prompt_options, slug, 'mp3')

## AUDIO EXTRACTORS
def extract_audio(file, current_user, deck_id, prompt_options, slug, extension):
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
            create_audio_job(segment, current_user, deck_id,
                              prompt_options,slug, item_number, item_quantity)
    except Exception as e:
        # Handle any exceptions that may occur during audio extraction
        print(f"Error occurred during audio extraction: {str(e)}")
    except Exception as e:
        raise e
    
def create_audio_job(segment, current_user, deck_id,
                      prompt_options, slug, item_number, item_quantity):
    payload = {"prompt_options": prompt_options,
                "segment": segment, 'user_id': current_user.id}
    payload_string = json.dumps(payload)
    print("DEEEEECCCCKK")
    print(deck_id)
    audio_job = Job(task_type = "audio", state = "pending",
                user = current_user.id, deck_id = deck_id,
                payload = payload_string, slug = slug, 
                item_number = item_number, item_quantity = item_quantity)
    db.session.add(audio_job)
    db.session.commit()

## DIVIDE AUDIO
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

"""
def extract_from_pdf_1(pdf_file):
    try:
        with open(pdf_file, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            total_pages = len(reader.pages)
            text = []
            for i in range(total_pages):
                page = reader.pages[i]
                page_content = page.extract_text()
                page_content = clean_text(page_content)
                text.append(page_content)
            concatenated_text = " ".join(text)
        return concatenated_text
    except FileNotFoundError as e:
        print("File not found.")
        raise e
    except Exception as e:
        print(f"An error occurred: {e}, attempting fallback method")
        text = fallback_text_extraction(pdf_file)
    return None
"""


def extract_from_pdf(pdf_file, n=50):
    try:
        text = []
        # Using pdfminer.six to extract pages from PDF
        for i, page_layout in enumerate(extract_pages(pdf_file), start=1):
            current_page_text = ''
            for element in page_layout:
                if hasattr(element, "get_text"):
                    current_page_text += element.get_text()
            if len(current_page_text.strip()) < n: # Threshold check
                # If the text is less than n, then use OCR
                print(f"Using OCR for page {i}")
                try:
                    # Convert page to image
                    images = convert_from_path(pdf_file, first_page=i, last_page=i)
                    for image in images:
                        # Perform OCR on the image
                        current_page_text = image_to_string(image)
                except Exception as e:
                    print(f"Error occurred during OCR: {str(e)}")
            else:
                print(f"Using PDFMiner for page {i}")
            text.append(current_page_text)
        # Join all the text together
        full_text = "\n".join(text)
        return full_text
    except FileNotFoundError as e:
        print("File not found.")
        raise e
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

"""

## try using OCR
def extract_from_pdf(pdf_path):
    # Convert the PDF to images
    print("entered extract from pdf function")
    print(pdf_path)
    try:
        images = convert_from_path(pdf_path)

    except Exception as e:
        print(f"Error occurred during PDF conversion: {str(e)}")
        return None
    print(images)
    # Process each image with OCR
    text = []
    for i, image in enumerate(images):
        print(f"Processing page {i + 1}")
        try:
            page_text = image_to_string(image)
        except Exception as e:
            print(e)
        text.append(page_text)
    
    # Join all the text together
    full_text = "\n".join(text)
    print(full_text)

    return full_text
    """
def clean_text(text):
    # Decode Unicode escape sequences into actual characters
    text = codecs.decode(text, 'unicode_escape')
    # Replace newline characters with spaces
    # This pattern matches any character that is not a letter, digit, whitespace, or regular punctuation.
    pattern = r"[^\w\s.,;:?!-’'\"()]+"
    cleaned_text = re.sub(pattern, "", text)
    return cleaned_text
# PPTX
def extract_from_pptx(ppt_file):
    try:
        prs = Presentation(ppt_file)
        text_runs = []
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    cleaned_text = clean_text(shape.text)
                    text_runs.append(cleaned_text)
        concatenated_text = " ".join(text_runs)
        return concatenated_text
    except FileNotFoundError:
        print("File not found.")
    except Exception as e:
        print("An error occurred:", str(e))
    return None

#DOCX
def extract_from_docx(docx_file):
    try:
        text = docx2txt.process(docx_file)
        text = text.replace("\n", " ")
        return text
    except FileNotFoundError:
        print("File not found.")
    except Exception as e:
        print("An error occurred:", str(e))
    return None
def extract_from_wiki(wiki_url):
    try:
        print("entered wiki function")
        # Replace the URL with the mobile version
        wiki_url = wiki_url.replace("https://en.wikipedia.org", "https://en.m.wikipedia.org")
        page = requests.get(wiki_url)
        page.raise_for_status()  # Check for any HTTP request errors
        soup = BeautifulSoup(page.content, 'html.parser')
        for a in soup.find_all('a'):
            a.replace_with(a.text)
        # Remove unwanted elements
        for tag in soup(['script', 'style', 'table', 'noscript', 'nav', 'header', 'footer']):
            tag.extract()
        for elem in soup.find_all('sup', class_='reference'):
            elem.extract()
        for div in soup.find_all('div', class_='toc'):
            div.extract()
        for div in soup.find_all('div', class_='thumbcaption'):
            div.extract()
        for div in soup.find_all('div', class_='reflist'):
            div.extract()
        for div in soup.find_all('div', class_='navbox'):
            div.extract()

        for h2 in soup.find_all('h2', class_='section-heading'):
            h2.extract()
        for ref in soup.find_all(class_='references'):
            ref.extract()
        for tag in soup.select('.portalbox-entry, .firstHeading'):
             tag.extract()
        for tag in soup.select('#footer-info-lastmod, #footer-info-copyright, #footer-places-privacy, #footer-places-about, #footer-places-disclaimers, #footer-places-contact, #footer-places-terms-use, #footer-places-desktop-toggle, #footer-places-developers, #footer-places-statslink, #footer-places-cookiestatement'):
            tag.extract()
        # Remove table of contents and language list
        for div in soup.find_all('div', {'id': 'toc'}):
            div.extract()
        for div in soup.find_all('div', {'id': 'page-secondary-actions'}):
            div.extract()
        for li in soup.find_all('li', class_='interlanguage-link'):
            li.extract()
        for li in soup.find_all('li', {'id': 'toc'}):
            li.extract()
        for li in soup.find_all('li'):
            if li.find('a'):
                li.extract()
        tags_to_extract = ['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td']
        extracted_content = []
        for tag in tags_to_extract:
            elements = soup.find_all(tag)
            for element in elements:
                extracted_content.append(str(element))

        text = "\n\n".join(extracted_content)
        return text

    except requests.exceptions.RequestException as e:
        print("Error making the HTTP request:", str(e))
    except Exception as e:
        print("An error occurred:", str(e))
    return None




##YOUTUBE
def extract_from_youtube(youtube_url):
    try:
        full_text = None
        print("entered youtube function")
        srt = YouTubeTranscriptApi.get_transcript(youtube_url)
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



## TOKEN HANDLERS
def count_tokens(text):
    text = encoding.encode(text)
    print("token count:", len(text))
    return len(text)

def token_encoding(text):
    return encoding.encode(text)

def token_decoding(text):
    return encoding.decode(text)

## split list of tokens into chunks of n tokens
def split_tokens(tokens, n):
    return [tokens[i:i+n] for i in range(0, len(tokens), n)]


## MISC FORMATTERS
def add_period(s):
    if not s:
        return s
    else:
        if s[-1] != ".":
            s += "."
        return s

def check_comma_list(string):
    if "," in string:
        return True
    else:
        return False
    
def add_underscores(string):
    if "_" in string:
        string = string.replace("_", "_" * 8, 1)
    return string

## turn string of comma separated terms into list of terms
def comma_list_to_list(string):
    return string.split(",")

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
        match = re.search(pattern, link)
        if match:
            video_id = match.group(1)
            return video_id

    # If the link does not match any of the patterns, return None
    return None





### JSON ERROR HANDLER

def fix_json(s):
    try:
        json.loads(s)
        return s
    except json.JSONDecodeError as e:
        # JSONDecodeError is raised if the string is not in valid JSON format
        # We can attempt to fix the error by removing any trailing commas or fixing the quotes
        s = s[:e.pos] + s[e.pos:].replace(',', '')
        s = s.replace("'", "\"")
        print("--------------------------------------------fixing json ------------------------------------------------------------")

        try:
            print("--------------------------------------------fixed json ------------------------------------------------------------")
            json.loads(s)
            return s
        except:
            raise ValueError("Unable to fix JSON string")
        
        
def create_pdf(string):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    # Define the width and height of the canvas
    width, height = letter
    # Define the margin and the maximum line width
    margin = 36
    max_width = width - 2*margin
    # Wrap the string to fit within the canvas
    lines = textwrap.wrap(string, width=max_width//8)
    # Draw each line on the canvas
    y = height - margin
    for line in lines:
        pdf.drawString(margin, y, line)
        y -= 20  # Move down to the next line
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer


#####  EXPLAINERS AND TUTORING ########
def explain_more(term, subject = None, content = None):
    print("entered explain more function")

    retries = 0
    prompt = build_prompt_explain_more(term, subject, content)
    print("prompt is:", prompt)
    while retries < 3:
        print("attempt:", retries)
        try:
            sys_instruct = f"You are a helpful teacher who is an expert and providing clear and detailed explanations. There is no need to introduce yourself, but if questioned you should answer that you are a teacher named Ceph who is here to help."
            response = call_ai_terms_non_async(sys_instruct, prompt)
            response_ = response['choices'][0]['message']['content'].strip()
            print(response_[:50])
            return response_
        
        except Exception as e:
            retries += 1
            print(f"Error: {e}. Retrying ({retries}/3)")
            
def build_prompt_explain_more(term, subject = None, content = None):
    print("entered build prompt explain more function")
    prompt = "You are a helpful teacher who wants to help students learn {subject_opt}. You are explaining the concept of {term} to a student. The student asks you to explain {term} in a lot of detail, providing not just explanations but where possible examples and analogies. You respond: "
    prompt = prompt.replace('{term}', term)
    if subject != None:
        prompt = prompt.replace('{subject_opt}', subject)
    return prompt


def why_wrong_generator(ww_prompt):
    print("entered why wrong function")
    retries = 0
    prompt = build_prompt_why_wrong(ww_prompt)
    while retries < 3:
        print("attempt:", retries)
        try:
            sys_instruct = f"You are a helpful teacher who is an expert and providing clear and detailed explanations. There is no need to introduce yourself, but if questioned you should answer that you are a teacher named Ceph who is here to help."
            response = call_ai_terms_non_async(sys_instruct, prompt)
            response_ = response['choices'][0]['message']['content'].strip()
            print(response_[:30])
            return response_
        
        except Exception as e:
            retries += 1
            print(f"Error: {e}. Retrying ({retries}/3)")
            
def build_prompt_why_wrong(ww_prompt):
    subject = ww_prompt['subject']
    term = ww_prompt['term']
    content = ww_prompt['content']
    boc_2 = ww_prompt['boc_2']
    boc_3 = ww_prompt['boc_3']
    boc_4 = ww_prompt['boc_4']
    category = ww_prompt['category']
    if category == "Mcq":
        prompt = "You are a helpful teacher who wants to help students learn {subject_opt}.   The student has just answered this multiple choice question incorrectly: {term}. The student asks you why this answer is correct: {content}, whereas these are wrong {boc_2} and {boc_3} and {boc_4}. You respond: "
        prompt = prompt.replace('{term}', term)
        prompt = prompt.replace('{content}', content)
        prompt = prompt.replace('{boc_2}', boc_2)
        prompt = prompt.replace('{boc_3}', boc_3)
        prompt = prompt.replace('{boc_4}', boc_4)
        if subject != None:
            prompt = prompt.replace('{subject_opt}', subject)
        else:
            prompt = prompt.replace('{subject_opt}', "")
    else:
        prompt = "You are a helpful teacher who wants to help students learn {subject_opt}. The student is studying flashcards and doesn't understand why {content} is the appropriate answer to this question: {term}. The student asks you why this answer is correct: {content} You respond: "
        prompt = prompt.replace('{term}', term)
        prompt = prompt.replace('{content}', content)
        if subject != None:
            prompt = prompt.replace('{subject_opt}', subject)
        else:
            prompt = prompt.replace('{subject_opt}', "")
            
    return prompt


def send_question_generator(term, content, latest_paragraph, question):
    print("entered send question generator function")
    retries = 0
    prompt = question_prompt_builder(term, content, latest_paragraph, question)
    while retries < 3:
        try:
            sys_instruct = f"You are a helpful teacher who is an expert and providing clear and detailed explanations. There is no need to introduce yourself, but if questioned you should answer that you are a teacher named Ceph who is here to help."
            response = call_ai_terms_non_async(sys_instruct, prompt)
            response_ = response['choices'][0]['message']['content'].strip()
            print(response_[:50])
            return response_
        
        except Exception as e:
            retries += 1
            print(f"Error: {e}. Retrying ({retries}/3)")
            

def question_prompt_builder(term, content, latest_paragraph, question):
    print("entered question prompt builder function")
    prompt = "You have previously interacted with the student and have helped them learn {term} {content} {paragraph}. The student has asked you a question: {question}. You respond:"
    prompt = prompt.replace('{term}', term)
    prompt = prompt.replace('{content}', content)
    if latest_paragraph != "":
        paragraph = "You have previously told the student that {latest_paragraph}."
        paragraph = paragraph.replace('{latest_paragraph}', latest_paragraph)
        prompt = prompt.replace('{paragraph}', paragraph)
    prompt = prompt.replace('{question}', question)
    return prompt






###################################################################
###################################################################

## OBSOLETE?        
def Merge(dict1, dict2):
    return(dict2.update(dict1))


def extract_terms_obs(text: str, prompt_option: str, prompt_option2: str = None, lang_option: str = None, trans_option: str = None,
                  len_option: str = None, qmin_option: int = None, qmax_option: int = None):
    print("entered extract term function")
    
    ## get prompt choice
    prompt = prompt_choices[prompt_option]
    ## get prompt chocie 2
    if prompt_option2 != None:
        c2 = "related to the subject of " + prompt_choices2[prompt_option2]
    else:
        c2 = ""
    ## get language
    if lang_option != None:
        lang = lang_choices[lang_option]
    else:
        lang = ""
    ## get len_option
    if len_option:
        length = len_choices[len_option]
    else:
        length = ""

    if qmin_option:
        qmin = "at least " + qmin_option 
    else:
        qmin = "all"
    if qmax_option:
        qmax = ", and at most " + qmax_option
    else:
        qmax = ""
    
    if prompt_option not in prompt_choices:
        raise ValueError("Invalid prompt option")
    
    prompt = prompt.replace('{qmin}', qmin)
    prompt = prompt.replace('{c2}', c2)
    prompt = prompt.replace('{qmax}', qmax)
    prompt = prompt.replace('{length}', length)
    prompt = prompt.replace('{lang}', lang)

    if trans_option != None:
        print(prompt[:50])
        prompt = prompt.replace('{}', trans_option)
    prompt = (prompt + text + 'The JSON object: \n')
    response = openai.Completion.create(
        engine="text-davinci-003",
        temperature=0.7,
        top_p=1,
        prompt=prompt,
        max_tokens=1000
    )
    try:
        x = response.choices[0]["text"].strip()
        x = json.loads(x)
        return x
    except json.JSONDecodeError:
        print("JSONDecodeError occurred, skipping this part.")
        
        
def small_extract_terms_obs(item, prompt_option: str, prompt_option2: str = None, lang_option: str = None, trans_option: str = None,
                        len_option: str = None, qmin_option: int = None, qmax_option: int = None):
    ls_terms = []
    response = extract_terms(item, prompt_option, prompt_option2, lang_option, trans_option, len_option, qmin_option, qmax_option)
    for dict in response:
        ls_terms.append(dict)
    return ls_terms

## for large documents only (otherwise just use extract_terms directly) passes through items one by one and returns a string with all terms
def large_extract_terms_obs(items, prompt_option: str, prompt_option2: str = None, lang_option: str = None, trans_option: str = None,
                        len_option: str = None, qmin_option: int = None, qmax_option: int = None):
    print("entered large extract term function")
    ls_terms = []
    for item in items:
        print(item)
        response = extract_terms(item, prompt_option, prompt_option2, lang_option, trans_option, len_option, qmin_option, qmax_option)
        for dict in response:
            ls_terms.append(dict)
    return ls_terms



""""
Old function kept in case new one does not work
def get_video_id(link):
    print(type(link))
    link = ''.join(link)
    link = link.strip()
    # Check if the link is in the "youtu.be" format
    if "youtu.be" in link:
        video_id = link.split("/")[-1]
    # Check if the link is in the "youtube.com" format
    elif "watch?v=" in link:
        video_id = link.split("v=")[1].split("&")[0]
    else:
        video_id = None
    return video_id
"""

def large_extract_terms(items, prompt_options):
    print("entered large extract term function")
    api_counter = 0
    ls_terms = []
    if isinstance(items, str):
        response = extract_terms(items, prompt_options)
        return response[0], response[1], response[2], response[3]
            
    else:
        prompt = []
        response_ =[]
        content = []
        for item in items:
            api_counter = api_counter + 1
            print("api call number: " + str(api_counter))
            response = extract_terms(item, prompt_options)

            if response[0] != None:
                for dict in response[0]:
                    ls_terms.append(dict)
                prompt.append(response[1])
                response_.append(response[2]) 
                content.append(response[3])
            print("finished large extract term function")
            print("API calls: " + str(api_counter))
        
        return ls_terms, prompt, response_, content
    


def small_extract_terms(item, prompt_option: str, prompt_option2: str = None, lang_option: str = None, trans_option: str = None,
                    len_option: str = None, qmin_option: int = None, qmax_option: int = None):
    ls_terms = []
    response = extract_terms(item, prompt_option, prompt_option2, lang_option, trans_option, len_option, qmin_option, qmax_option)
    for dict in response:
        ls_terms.append(dict)
    return ls_terms



async def create_image(term):
    try:
        response = await asyncify (openai.Image.create)(
            prompt=term,
            n=1,
            response_format='url',
            size="256x256"
        )
        image_url = response['data'][0]['url']
        img_name = term.replace(' ', '_') + '.webp'
        img_path = os.path.join('static\card_img', img_name)  # Create the full path to the image file
        r = requests.get(image_url)
        r.raise_for_status()  # Raises an exception if the request was unsuccessful
        with open(img_path, 'wb') as f:
            f.write(r.content)
        return img_path
    except (openai.error.InvalidRequestError, requests.exceptions.RequestException) as e:
        print(f"Error creating image for term '{term}': {e}")
        return None
    


def remove_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)