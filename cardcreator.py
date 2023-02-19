import os 
import openai 
from pypdf import PdfReader
from dotenv import load_dotenv, find_dotenv
import csv
from pptx import Presentation
import numpy as np
from extractors import extract_from_pdf, large_extract_terms, extract_from_pptx, extract_terms, extract_from_docx
import base64
import requests

load_dotenv(find_dotenv())

## open AI api, 
openai.api_key = os.environ.get("OPENAI_API_KEY")

def card_creator(file, prompt, prompt_option2 = None):
    
    if file.endswith('.pdf'):
        items = extract_from_pdf(file) 
    elif file.endswith('.pptx'):
        items = extract_from_pptx(file) 
    elif file.endswith('.docx'):
        items = extract_from_docx(file)
    elif file.endswith('.txt'):
         with open(file) as file:
            items = file.read()
    terms = large_extract_terms(items, prompt, prompt_option2)
    return terms

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


## obsolete?
##def card_creator2(file, prompt):
    
    ## text_input is input id, cards output id
    ##input("file: ")
    
    ##if file.endswith('.pdf'):
      ##  items = extract_from_pdf(file)
       # ## problem is that terms is only returning terms, not definitions seperated by a semi colon
       ## terms = large_extract_terms2(items, prompt)
       ## return terms