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




    ## extract_terms 
def extract_terms(text: str):
    prompt = (prompt_standard + text)
    ## experiment with temprature = ,top_p =, frequency_penalty =, presence_penalty =, stop= ,
    response = openai.Completion.create(
        engine="text-ada-001", ## using ada for cost, switch to curie-001 or davinci-003, babbage-001, ada-001
        temperature = 0,
        prompt=prompt,
        max_tokens=100)
    return response


def terms_to_dict(terms: str) -> dict:
    ## split into list of terms and def and return as dicitonary
    terms = terms.split("\n")
    terms_dict = {}
    for term in terms:
        term = ''.join([i for i in term if not i.isdigit()])
        term = term.strip(' .-')
        term = term.split(': ')
        if len(term) > 1:
            terms_dict.update({term[0]: term[1]})
        
    return(terms_dict)
    
    
def extract_from_pdf(pdf_file):

    reader = PdfReader(pdf_file)
    total_pages = len(reader.pages)
    text = []
    for i in range(len(reader.pages)):
        page = reader.pages[i]
        page = page.extract_text()
        page = page.replace("\n", " ")
        text.append(page)
        
    return text
    


def extract_from_pptx(ppt_file):
    
    prs = Presentation(ppt_file)
    text_runs = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text_runs.append(shape.text)
                
    return text_runs

def extract_from_docx(docx_file):            
    text = docx2txt.process(docx_file)
    text = text.replace("\n", " ")          
    return text


                
## for large documents only (otherwise just use extract_terms directly) passes through items one by one and returns a string with all terms
def large_extract_terms(prompt):
        temp = []
        for item in prompt:
            response = extract_terms(item)
            x = response.choices[0]["text"]
            temp.append(x)
        terms = "".join(temp)
        return terms






def write_to_csv(definitions: str, filename: str):
    
    with open(filename, 'w', encoding="utf-8", newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=' ')
        for key, value in definitions.items():
            writer.writerow([key, value])



if __name__ == "__main__":
    main()