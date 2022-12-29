import os 
import openai 
from flask import Flask, redirect, render_template, request, url_for
import json
from pypdf import PdfReader
from dotenv import load_dotenv, find_dotenv
import csv
from pptx import Presentation
import glob
import numpy as np
import docx2txt
from extractors import extract_from_pdf, large_extract_terms, terms_to_dict, extract_from_pptx, extract_terms, extract_from_docx



load_dotenv(find_dotenv())

##app = Flask(__name__)

## open AI api, 
openai.api_key = os.environ.get("OPENAI_API_KEY")

## different prompts available to pass through
prompt_standard = "Extract as many uncommon or technical terms as possible from the following text and provide a definition for each in a non numbered list: "


def main():
        
    ## text_input is input id, cards output id
    file_prompt = input("Enter path to input file: ")
    print(file_prompt)
    ##input("file: ")
    file_name = input("Enter a name for your output file: ") + ".csv"
    
    if file_prompt.endswith('.pdf'):
        prompt = extract_from_pdf(file_prompt)
        terms = large_extract_terms(prompt)
        terms = terms_to_dict(terms)
        
    elif file_prompt.endswith('.pptx'):
        prompt = extract_from_pptx(file_prompt)
        terms = extract_terms(prompt)
        terms = terms_to_dict(terms)
        
    elif file_prompt.endswith('.txt'):
            prompt = []
            with open(file_prompt) as file:
                prompt = file.read()
                response = extract_terms(prompt)
                terms = response.choices[0]["text"]
                terms = (terms_to_dict(terms))
                
    elif file_prompt.endswith('.docx'):
        prompt = extract_from_docx(file_prompt)
        terms = large_extract_terms(prompt)
        terms = terms_to_dict(terms)
        
    
    else:
        ##checks if file has been selected, if not expected text to be entered manually
        prompt = input("Enter text here: ")  
        response = extract_terms(prompt)
        terms = response.choices[0]["text"]
        terms = (terms_to_dict(terms))
    
    
    write_to_csv(terms, file_name)




def write_to_csv(definitions: str, filename: str):
    
    with open(filename, 'w', encoding="utf-8", newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=' ')
        for key, value in definitions.items():
            writer.writerow([key, value])



if __name__ == "__main__":
    main()