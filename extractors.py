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


encoding = tiktoken.get_encoding('gpt2')



## terms choices
prompt_choices = {
    'Definitions': ' Given the passage below, extract {qmin} {qmax} uncommon or technical terms {c2} and provide a {length} definition for each. {lang} Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "A" as well as one named "B". \n The resulting JSON object should be in this format: [{"A":"term","B":"definition"}] \n The passage: \n',
    "Translate": 'Given the passage below, extract {qmin} {qmax} uncommon or technical terms {c2} and provide a {trans} translation for each. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "A", for the term, as well as one named "B", for the {} translation. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',    "Rhyme": 'Given the passage below, extract as many uncommon or technical terms as possible and create a four verse poem for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the terms extracted and have a property named "A", for the term, as well as one named "B", for the poem. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',
    "Rhyme": 'Given the passage below, extract {qmin} {qmax} uncommon or technical terms {c2} and create a four verse poem for each {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "A", for the term, as well as one named "B", for the poem. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',
    "People": 'Given the passage below, extract all the names of people and provide a {length} biography for each {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "A", for the person, as well as one named "B", for the biography. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',    "Theories": 'Given the passage below, identify all the relevant theories and concepts and provide an explanation for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the theories or concepts extracted and have a property named "A", for the theory or concept, as well as one named "B", for the explanation. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',
    "Theories": 'Given the passage below, identify {qmin} {qmax} relevant theories and concepts {c2} and provide an {length} explanation for each {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the theories or concepts extracted and have a property named "A", for the theory or concept, as well as one named "B", for the explanation. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',
    "Cloze": 'Given the passage below, create {qmin} {qmax} cloze deletion questions  {lang}.{c2} The goal is to test my understanding of the text. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the cloze deletion texts and have a property named "A" for the cloze deletion text, and "B" for the missing word(s). \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',    "Mcq":'Given the passage below, create at least one multiple choice question for each key piece of information.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the multiple choice questions and have a property named "A" for the question, one named A for the correct answer and 3 other properties for the wrong answers, B, C, D.  \n The resulting JSON object should be in this format: [{"A": "string", "B":"string", "C":"string", "D":"string", "E":"string"}] \n The passage \n',
    "Mcq":'{c2}Given the passage below, create {qmin} {qmax} {length} multiple choice questions {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the multiple choice questions and have a property named "A" for the question, one named "B" for the correct answer and 3 other properties for the wrong answers, "C", "D", "E". \n The resulting JSON object should be in this format: [{"A": "string", "B":"Answer", "C":"Wrong answer 1", "D":"Wrong answer 2", "E":"Wrong answer 3"}] \n The passage \n',
    "Comprehension":'Given the passage below, create {qmin}  {qmax} {length} questionsto test comprehension of the key information contained within {c2} {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the comprehension questions and have a property named "A" for the question, and "B" for the answer. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n',    
    "Vocab_builder": 'Given the passage below, extract all unique words and provide a definition for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the words extracted and have a property named "A", for the word, as well as one named "B", for the definition. \n The resulting JSON object should be in this format: [{"A":"string","B":"string"}] \n The passage: \n', } 

prompt_choices2 =  {
    "Econ": "Economics",
    "Finance": "Finance",
    "Lit": "Literature",
    "Chem": "Chemistry",
    "Science":  "Science",
    "Physics": "Physics",
    "Philo": "Philosophy",
    "CS": "Computer Science",
    "Bio": "Biology",
    "Math": "Mathematics",
    "Geo": "Geography",
    "Hist": "History",
    "Anatomy": "Anatomy",
    "Psych": "Psychology",
    "Soc": "Sociology",
    "Law": "Law",
    "Music": "Music",
    "Art": "Art",
    "Dance": "Dance",
    "Theatre": "Theatre",
    "Film": "Film",
    "Med": "Medicine",
    "Eng": "Engineering",
    "Bus": "Business",
    "Politics": "Political science",
    }
lang_choices = {
    "English": "The language used should be English",
    "French": "The language used should be French",
    "Spanish": "The language used should be Spanish",
    "German": "The language used should be German",
    "Portuguese": "The language used should be Portuguese",
    "Chinese": "The language used should be Chinese",
    "Russian": "The language used should be Russian",
    "Swahili": "The language used should be Swahili",
    "Japanese": "The language used should be Japanese",
    "Dothraki": "The language used should be Dothraki",
    "Klingon": "The language used should be Klingon",
    "Dutch": "The language used should be Dutch",
    "Italian": "The language used should be Italian",
    "Greek": "The language used should be Greek",
    "Arabic": "The language used should be Arabic",
    "Hindi": "The language used should be Hindi",
    "Polish": "The language used should be Polish",
    "Hebrew": "The language used should be Hebrew",
    "Finnish": "The language used should be Finnish",
    "Norwegian": "The language used should be Norwegian",
    "Swedish": "The language used should be Swedish",
    "Turkish": "The language used should be Turkish",
    "Czech": "The language used should be Czech",
    "Romanian": "The language used should be Romanian",
    "Hungarian": "The language used should be Hungarian",
    "Bulgarian": "The language used should be Bulgarian",
    "Croatian": "The language used should be Croatian",
    "Serbian": "The language used should be Serbian",
    "Estonian": "The language used should be Estonian",
    "Latvian": "The language used should be Latvian",
    "Lithuanian": "The language used should be Lithuanian",
    "Farsi": "The language used should be Farsi",
    "Korean": "The language used should be Korean",
    "Indonesian": "The language used should be Indonesian",
    "Vietnamese": "The language used should be Vietnamese",
    "Urdu": "The language used should be Urdu",
    "Hebrew": "The language used should be Hebrew",
    "Persian": "The language used should be Persian",
    "Thai": "The language used should be Thai",
    "Malay": "The language used should be Malay",
    "Tagalog": "The language used should be Tagalog",
    }

len_choices = {
    "long": "very long",
    "short": "short",}

## CALLS TO OPEN AI API
def extract_terms(text: str, prompt_option: str, prompt_option2: str = None, lang_option: str = None, trans_option: str = None,
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
        prompt_select = prompt_select.replace('{}', trans_option)
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

    response = response['choices'][0]['message']['content'].strip()
    print(response)
    byte_string = response.encode('utf-8')
    x = byte_string.decode('utf-8')

    x = json.loads(x)

    return x
   

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
        return response
            
    else:
        print("recognized items as list")
        print(len(items))
        for item in items:
            api_counter = api_counter + 1
            print("api call number: " + str(api_counter))
            response = extract_terms(item, prompt_option, prompt_option2, lang_option, trans_option, len_option, qmin_option, qmax_option)
            for dict in response:
                ls_terms.append(dict)
            print("finished large extract term function")
            print("API calls: " + str(api_counter))
        print(ls_terms)
        return ls_terms







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