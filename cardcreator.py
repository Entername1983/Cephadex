import os 
import openai 
from pypdf import PdfReader
from dotenv import load_dotenv, find_dotenv
import csv
from pptx import Presentation
import numpy as np
from extractors import extract_from_pdf, large_extract_terms, terms_to_dict, extract_from_pptx, extract_terms, extract_from_docx



load_dotenv(find_dotenv())

##app = Flask(__name__)

## open AI api, 
openai.api_key = os.environ.get("OPENAI_API_KEY")

## different prompts available to pass through

prompt_standard = "Extract as many uncommon or technical terms as possible from the following text and provide a definition for each in a non numbered list: "



def card_creator(file):
    
    ## text_input is input id, cards output id

    ##input("file: ")
    
    if file.endswith('.pdf'):
        print("checked pdf)")
        prompt = extract_from_pdf(file)
        
        ## problem is that terms is only returning terms, not definitions seperated by a semi colon
        terms = large_extract_terms(prompt)

## issue with terms to dict
        terms = terms_to_dict(terms)
        
    elif file.endswith('.pptx'):
        prompt = extract_from_pptx(file)
        terms = extract_terms(prompt)
        terms = terms_to_dict(terms)
        
    elif file.endswith('.txt'):
            prompt = []
            with open(file) as file:
                prompt = file.read()
                response = extract_terms(prompt)
                terms = response.choices[0]["text"]
                terms = (terms_to_dict(terms))
                
    elif file.endswith('.docx'):
        prompt = extract_from_docx(file)
        terms = large_extract_terms(prompt)
        terms = terms_to_dict(terms)
        
    
    #else:
        ##checks if file has been selected, if not expected text to be entered manually
        #prompt = input("Enter text here: ")  
        #response = extract_terms(prompt)
        #terms = response.choices[0]["text"]
        #terms = (terms_to_dict(terms))
    
    
    #write_to_csv(terms, file_name)
    
    return terms


def write_to_csv(definitions: str, filename: str):
    
    with open(filename, 'w', encoding="utf-8", newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=' ')
        for key, value in definitions.items():
            writer.writerow([key, value])

