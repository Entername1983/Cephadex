from reportlab.pdfgen import canvas
import openai 
import PyPDF2
from PyPDF2 import PdfWriter, PdfReader
from dotenv import load_dotenv, find_dotenv
from pptx import Presentation
import numpy as np
import docx2txt
import json
import sys
from pydub import AudioSegment
import os
from io import BytesIO
import math
from youtube_transcript_api import YouTubeTranscriptApi
import tiktoken
import io
import textwrap
from reportlab.lib.pagesizes import letter
from prompts import prompt_choices, prompt_choices2, lang_choices, len_choices
from bs4 import BeautifulSoup
import requests
from pylatexenc.latex2text import LatexNodes2Text
import re

encoding = tiktoken.get_encoding('gpt2')



testing = "[{\"A\":\"Fibonacci sequence\",\"B\":\"$$F_n=F_{n-1}+F_{n-2}$$\",\"C\":\"The Fibonacci sequence is a sequence of integers in which each number after the first two numbers is the sum of the two preceding ones. The sequence can be defined recursively by the equation F_n = F_{n-1} + F_{n-2}, with initial conditions F_0 = 0 and F_1 = 1. \"},{\"A\":\"Binet's formula\",\"B\":\"$$F_n = \\frac{1}{\\sqrt{5}}\\left[\\left(\\frac{1+\\sqrt{5}}{2}\\right)^n -\\left(\\frac{1-\\sqrt{5}}{2}\\right)^n\\right]$$\",\"C\":\"Binet's formula is an explicit formula used to find the value of the nth term in the Fibonacci sequence. It is based on the golden ratio and can be used to efficiently calculate large Fibonacci numbers.\"}]"

## terms choices

## CALLS TO OPEN AI API
def extract_terms(text: str, prompt_option: str, prompt_option2: str = None, trans_option: str = None, lang_option: str = None, 
                  len_option: str = None, qmin_option: int = None, qmax_option: int = None):
    print("entered extract term function")
    print(prompt_option)
    print(prompt_option2)
    print(lang_option)
    print(trans_option)
    print(len_option)
    print(qmin_option)
    print(qmax_option)
    
    ## get prompt choice
    prompt_select = prompt_choices[prompt_option]
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
    if prompt_option2:    
        option_2 = prompt_choices2[prompt_option2]
    elif trans_option:
        option_2 = trans_option
    
    option_1 = f"You are a helpful teacher who wants to help students learn {prompt_option2}."
    if prompt_option not in prompt_choices:
        raise ValueError("Invalid prompt option")
    prompt_select = prompt_select.replace('{qmin}', qmin)
    prompt_select = prompt_select.replace('{c2}', c2)
    prompt_select = prompt_select.replace('{qmax}', qmax)
    prompt_select = prompt_select.replace('{length}', length)
    prompt_select = prompt_select.replace('{lang}', lang)

    if trans_option != None:
        print(prompt_select)
        prompt_select = prompt_select.replace('{option_2}', option_2)
    print("TEXT TO BE SENT TO OPEN AI")
    print(text)
    prompt = (prompt_select + text + 'The JSON object: \n')
    response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                    {"role": "system", "content": option_1},
                    {"role": "user", "content": prompt},
                ]
            )
    
    response_ = response['choices'][0]['message']['content'].strip()
    if prompt_option == "Formulas":
        print("entered formulas")
        print(response_)
        ##response_ = double_backslashes(response_)
        response = json.dumps(response_)
        print(response)
    
    if prompt_option == "Cloze":
        response_ = add_underscores(response_)
    byte_string = response_.encode('utf-8')
    x = byte_string.decode('utf-8')

    x = json.loads(x)
 
    return x, prompt, response, x
   


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




def small_extract_terms(item, prompt_option: str, prompt_option2: str = None, lang_option: str = None, trans_option: str = None,
                        len_option: str = None, qmin_option: int = None, qmax_option: int = None):
    ls_terms = []
    response = extract_terms(item, prompt_option, prompt_option2, lang_option, trans_option, len_option, qmin_option, qmax_option)
    for dict in response:
        ls_terms.append(dict)
    return ls_terms

## for large documents only (otherwise just use extract_terms directly) passes through items one by one and returns a string with all terms
def large_extract_terms(items, prompt_option: str, prompt_option2: str = None, lang_option: str = None, trans_option: str = None,
                        len_option: str = None, qmin_option: int = None, qmax_option: int = None):
    print("entered large extract term function")
    print(prompt_option)
    print(prompt_option2)
    api_counter = 0
    ls_terms = []
    print("________________________ITEMS TYPE________________________________")
    print(type(items))
    if isinstance(items, str):
        response = extract_terms(items, prompt_option, prompt_option2, lang_option, trans_option, len_option, qmin_option, qmax_option)
        return response[0], response[1], response[2], response[3]
            
    else:
        print("recognized items as list")
        print(len(items))
        for item in items:
            api_counter = api_counter + 1
            print("api call number: " + str(api_counter))
            response = extract_terms(item, prompt_option, prompt_option2, lang_option, trans_option, len_option, qmin_option, qmax_option)
            for dict in response[0]:
                ls_terms.append(dict)
            print("finished large extract term function")
            print("API calls: " + str(api_counter))
        print(ls_terms)
        return ls_terms, response[1], response[2], response[3]







## TAKES TEXT OR LIST OF TEXT AND TRANSLATES IT TO THE LANGUAGE CHOSEN
## ISSUE IS HOW TO HAVE PARAGRAPH BREAKS
def transcribe_and_translate(items, prompt_option, trans_option):
    language = trans_option
    print(language)
    option_1 = f"You are a helpful {language} translator"
    if items is list:
        for item in items:
            option_2 = f"translate the following passage to {language}: {item}"
            response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                    {"role": "system", "content": option_1},
                    {"role": "user", "content": option_2},
                ]
            )
            response = response['choices'][0]['message']['content']
            byte_string = response.encode('utf-8')
            response = byte_string.decode('utf-8')
            long_response = long_response + response
        response = long_response
            
    else:
        option_2 = f"translate the following passage to {language}: {items}"
        response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
                {"role": "system", "content": option_1},
                {"role": "user", "content": option_2},
            ]
        )
        response = response['choices'][0]['message']['content']
        byte_string = response.encode('utf-8')
        response = byte_string.decode('utf-8')   
    return response

## AUDIO TRANSCRIPTION
def transcribe_whisper(audio_file):
    print("entered transcribe function")
    audio_file= open(audio_file, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    transcript = transcript["text"]
    return transcript

## REGENERATE A DEFINITION
def regenerate_def(term):
        prompt = "Provide the definition for the following term: "
        prompt1 = (prompt + term)
        response = openai.Completion.create(
        engine="text-davinci-003", ## using ada for cost, switch to curie-001 or davinci-003, babbage-001, ada-001.  HAVE TO USE DA VINCI TO GET PROPER FORMATTING
        temperature = 0.7,
        top_p = 1,
        prompt=prompt1,
        max_tokens=100)
        x = response.choices[0]["text"].strip()
        z = [term, ":"]
        y = "".join(z)
        if x.startswith(term):
            x = x.replace(term, "",)
        if x.startswith(y):
            x = x.replace(y, "", 1)
        x = x.strip()
        x = add_period(x)
        return x    





###################################
###################################



## TEXT EXTRACTORS
def text_extractor(file):
    if file.endswith('.pdf'):
        items = extract_from_pdf(file) 
    elif file.endswith('.pptx'):
        items = extract_from_pptx(file) 
    elif file.endswith('.docx'):
        items = extract_from_docx(file)
    elif file.endswith('.wav'):
        items = extract_audio(file)
    elif file.endswith('.txt'):
        with open(file) as file:
            items = file.read()
    print(count_tokens(items))
    return items

## AUDIO EXTRACTORS
def extract_audio(file): 
    print("entered extract audio function")
    text = []
    segments = divide_audio(file) 
    for segment in segments:
        transcript = transcribe_whisper(segment)
        text.append(transcript)
    concatenated_text = " ".join(text)
    return concatenated_text

## PDF
def extract_from_pdf(pdf_file):
    with open(pdf_file, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        total_pages = len(reader.pages)
        text = []
        for i in range(total_pages):
            page = reader.pages[i]
            page_content = page.extract_text()
            page_content = page_content.replace("\n", " ")
            text.append(page_content)
        concatenated_text = " ".join(text)
    return concatenated_text

# PPTX
def extract_from_pptx(ppt_file):
    prs = Presentation(ppt_file)
    text_runs = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text_runs.append(shape.text)
        concatenated_text = " ".join(text_runs)
    return concatenated_text

#DOCX
def extract_from_docx(docx_file):            
    text = docx2txt.process(docx_file)
    text = text.replace("\n", " ")          
    return text

def extract_from_wiki(wiki_url):
    page = requests.get(wiki_url)
    
    # scrape webpage
    soup = BeautifulSoup(page.content, 'html.parser')
    
    list(soup.children)
    
    # find all occurrence of p in HTML
    # includes HTML tags
    print(soup.find_all('p'))
    print('\n\n')
    # return only text
    # does not include HTML tags
    items = soup.find_all('p')[0].get_text()
    for i in range(0, len(soup.find_all('p')) - 1):
        items = soup.find_all('p')[i].get_text()
        print("item" + str(i))
        print(items)
        if i == 0:
            text = items
        else:
            text = text + items
    
    return text
    
    
##YOUTUBE
def extract_from_youtube(youtube_url):
    full_text = None
    print("entered youtube function")
    srt = YouTubeTranscriptApi.get_transcript(youtube_url)
    for dict in srt:
        x = dict['text']
        if full_text == None:
            full_text = x
        else:
            full_text = full_text + x
    print(full_text)
    return full_text


## DIVIDE AUDIO
def divide_audio(input_file, segment_length=25):
    """
    Split an audio file into segments of at most 25mb and save each segment as an MP3 file in the same folder as the input file
    :param input_file: the path to the input audio file
    :param segment_length: the maximum size of each audio segment, in megabytes
    :return: a list of audio segment file paths
    """
    # Open the audio file
    audio = AudioSegment.from_file(input_file)
    # Calculate the segment size in bytes
    segment_size = segment_length * 1024 * 1024
    # Calculate the total number of segments
    num_segments = math.ceil(len(audio) / segment_size)
    print("number of segments", num_segments)
    # Create a list to hold the file paths for the audio segments
    segments = []
    # Split the audio file into segments and save each segment as an MP3 file
    for i in range(num_segments):
        start = i * segment_size
        end = min((i + 1) * segment_size, len(audio))
        segment = audio[start:end]
        # Define the output file path for the segment
        output_file = os.path.join(os.path.dirname(input_file), f"segment_{i}.mp3")
        # Export the segment as an MP3 file
        segment.export(output_file, format="mp3")
        # Add the output file path to the list of segments
        segments.append(output_file)
    return segments

## TOKEN HANDLERS
def count_tokens(text):
    encoding.encode(text)
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
    print(type(link))
    link = ''.join(link)
    link = link.strip()
    # Check if the link is in the "youtu.be" format
    if "youtu.be" in link:
        video_id = link.split("/")[-1]
    # Check if the link is in the "youtube.com" format
    elif "watch?v=" in link:
        video_id = link.split("v=")[1].split("&")[0]
    return video_id

###################################################################
###################################################################

## OBSOLETE?        
def Merge(dict1, dict2):
    return(dict2.update(dict1))


def extract_terms_obs(text: str, prompt_option: str, prompt_option2: str = None, lang_option: str = None, trans_option: str = None,
                  len_option: str = None, qmin_option: int = None, qmax_option: int = None):
    print("entered extract term function")
    
    ## get prompt choice
    prompt_select = prompt_choices[prompt_option]
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
    
    prompt_select = prompt_select.replace('{qmin}', qmin)
    prompt_select = prompt_select.replace('{c2}', c2)
    prompt_select = prompt_select.replace('{qmax}', qmax)
    prompt_select = prompt_select.replace('{length}', length)
    prompt_select = prompt_select.replace('{lang}', lang)

    if trans_option != None:
        print(prompt_select)
        prompt_select = prompt_select.replace('{}', trans_option)
    prompt = (prompt_select + text + 'The JSON object: \n')
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
    print(items)
    ls_terms = []
    for item in items:
        print(item)
        response = extract_terms(item, prompt_option, prompt_option2, lang_option, trans_option, len_option, qmin_option, qmax_option)
        for dict in response:
            ls_terms.append(dict)
    print(ls_terms)
    return ls_terms

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