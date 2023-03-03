import os 
import openai 
from pypdf import PdfReader
from dotenv import load_dotenv, find_dotenv
import csv
from pptx import Presentation
import numpy as np
from extractors import extract_from_pdf, large_extract_terms, extract_from_pptx, extract_terms, extract_from_docx, extract_audio, transcribe_and_translate
import base64
import requests
import tiktoken


encoding = tiktoken.get_encoding("gpt2")
load_dotenv(find_dotenv())

## open AI api, 
openai.api_key = os.environ.get("OPENAI_API_KEY")

def creator(text, prompt_option: str, prompt_option2: str = None, lang_option: str = None, trans_option: str = None, len_option: str = None, qmin_option: int = None, qmax_option: int = None):
    text_ = text
    if prompt_option != "Transcribe":
        print("entered not transcribe")
        text_ = split_text(text_)
        print(text_)
        print(type(text))
        terms = large_extract_terms(text_, prompt_option, prompt_option2, lang_option, trans_option, len_option, qmin_option, qmax_option)
        return terms
    elif prompt_option == "Transcribe":
        if trans_option == None:
            return text_
        else:
            text_ = transcribe_and_translate(text_, prompt_option, trans_option)
            return text_   
    elif prompt_option == "List":
        pass
        

   ## takes a term and returns a card with term image.  Will need to be modified later to have a different one per user
def create_image(term):
    try:
        response = openai.Image.create(
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

def write_to_csv(definitions: str, filename: str):
    with open(filename, 'w', encoding="utf-8", newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=' ')
        for key, value in definitions.items():
            if key != "" and value != "":
                writer.writerow([key, value])



## Takes a text and divides it into a list, with each item being at most n tokens long
def split_text(text, n = 2000):
    print("entered split text")
    tokens = count_tokens(text)
    print(tokens)
    n_chunks = tokens//n
    print(n_chunks)
    if n_chunks < 1:
        n_chunks = 1
    chunks = np.array_split(text.split(), n_chunks)
    str_chunks = [' '.join(chunk) for chunk in chunks]
    return str_chunks

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




########## OBSOLETE CODE ##########

def card_creator(file, prompt_option: str, prompt_option2: str = None, lang_option: str = None, trans_option: str = None, len_option: str = None, qmin_option: int = None, qmax_option: int = None):
    print(file)
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
    terms = large_extract_terms(items, prompt_option, prompt_option2, lang_option, trans_option, len_option, qmin_option, qmax_option)
    return terms
