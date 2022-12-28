import os 
import openai 
from flask import Flask, redirect, render_template, request, url_for
import json
from pypdf import PdfReader
from dotenv import load_dotenv, find_dotenv
import csv


load_dotenv(find_dotenv())

##app = Flask(__name__)

## open AI api, 
openai.api_key = os.environ.get("OPENAI_API_KEY")

practice_list = '1. Greenhouse gas emissions:  Gases that trap heat in the atmosphere. \n 2. Climate change: A long term shift in global weather patterns \n 3. Natural gas: A fossil fuel composed mainly of methane.'

def main():
        
    ## text_input is input id, cards output id
    file_prompt = input("Enter path to input file: ")
    print(file_prompt)
    ##input("file: ")
    file_name = input("Enter a name for your output file: ") + ".csv"
    
    if file_prompt.endswith('.pdf'):
        prompt = extract_from_pdf(file_prompt)
        temp = []
        for item in prompt:
            response = extract_terms(item)
            x = response.choices[0]["text"]
            ls.append(x)
        terms = "".join(temp)
        terms = terms_to_dict(terms)
        
    else:
        ##checks if file has been selected, if not expected text to be entered manually
        if file_prompt == "":
            prompt = input("Enter text here: ")
        else:
            prompt = []
            with open(file_prompt) as file:
                prompt = file.read()
            ## extract terms    
        response = extract_terms(prompt)
        terms = response.choices[0]["text"]
        terms = (terms_to_dict(terms))
    
    
    write_to_csv(terms, file_name)


    ## extract_terms 
def extract_terms(text: str):
    prompt = ("Extract as many uncommon or technical terms as possible from the following text and provide a definition for each in a non numbered list: " + text)
    ## experiment with temprature = ,top_p =, frequency_penalty =, presence_penalty =, stop= ,
    response = openai.Completion.create(
        engine="text-davinci-003", ## using ada for cost, switch to curie-001 or davinci-003, babbage-001, ada-001
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
    
    
def extract_from_pdf(pdf_file) -> [str]:

    reader = PdfReader(pdf_file)
    total_pages = len(reader.pages)
    text = []
    for i in range(len(reader.pages)):
        page = reader.pages[i]
        page = page.extract_text()
        page = page.replace("\n", " ")
        text.append(page)
        
    return text
    
    
def write_to_csv(definitions: str, filename: str):
    
    with open(filename, 'w', encoding="utf-8", newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=' ')
        for key, value in definitions.items():
            writer.writerow([key, value])

if __name__ == "__main__":
    main()