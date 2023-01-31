
import openai 
from pypdf import PdfReader
from dotenv import load_dotenv, find_dotenv
from pptx import Presentation
import numpy as np
import docx2txt
import json
import sys


prompt_choices = {
    'Definitions': 'Given the article below, extract as many uncommon or technical terms as possible and provide a definition for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the terms extracted and have a property named "T" as well as one named "D". \n The resulting JSON object should be in this format: [{"T":"string","D":"string"}] \n The article: \n',
    "Translate": 'Given the article below, extract as many uncommon or technical terms as possible and provide a Chinese translation for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the terms extracted and have a property named "T", for the term, as well as one named "CH", for the Chinese translation. \n The resulting JSON object should be in this format: [{"T":"string","TR":"string"}] \n The article: \n',
    "Rhyme": 'Given the article below, extract as many uncommon or technical terms as possible and create a four verse poem for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the terms extracted and have a property named "T", for the term, as well as one named "R", for the poem. \n The resulting JSON object should be in this format: [{"T":"string","R":"string"}] \n The article: \n',
    "People": 'Given the article below, extract all the names of people and provide a brief biography for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the terms extracted and have a property named "P", for the person, as well as one named "B", for the biography. \n The resulting JSON object should be in this format: [{"P":"string","B":"string"}] \n The article: \n',
    "Theories": 'Given the article below, identify all the relevant theories and concepts and provide an explanation for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the theories or concepts extracted and have a property named "TC", for the theory or concept, as well as one named "E", for the explanation. \n The resulting JSON object should be in this format: [{"TC":"string","E":"string"}] \n The article: \n',
    } 
  
  
## extract_terms 
def extract_terms(text: str, prompt_option:str):
    prompt_select = prompt_choices[prompt_option]
    prompt = (prompt_select + text + 'The JSON object: \n')
    ## experiment with temprature = ,top_p =, frequency_penalty =, presence_penalty =, stop= ,
    response = openai.Completion.create(
        engine="text-davinci-003", ## using ada for cost, switch to curie-001 or davinci-003, babbage-001, ada-001.  HAVE TO USE DA VINCI TO GET PROPER FORMATTING
        temperature = 0.7,
        top_p = 1,
        prompt=prompt,
        max_tokens=1000)
    return response

## for large documents only (otherwise just use extract_terms directly) passes through items one by one and returns a string with all terms
def large_extract_terms(items: str, prompt_option:str):
    ls_terms = []
    for item in items:
        response = extract_terms(item, prompt_option)
        x = response.choices[0]["text"].strip()
        x = json.loads(x)
        for dict in x:
            ls_terms.append(dict)
    print(ls_terms)
    return ls_terms

## TEXT EXTRACTORS    
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

                


def Merge(dict1, dict2):
    return(dict2.update(dict1))
 
## REGENERATE A DEFINITION
def Regenerate_def(term):
        prompt = "Provide the definition for the following term: "
        prompt1 = (term + prompt)
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
        return x    
##def large_extract_terms2(items, prompt):
    ##dict1 = {}
    ##for item in items:
       ## response = extract_terms(item, prompt)
       ## x = response.choices[0]["text"].strip()
      ##  print(x, file=sys.stderr)
      ##  x = json.loads(x)
      ##  dict1 = Merge(dict1, x)
        
   ## return dict1

##def terms_to_dict(terms: str) -> dict:
    ## split into list of terms and def and return as dicitonary
  ##  terms = terms.split("\n")
   ## terms_dict = {}
   ## for term in terms:
    ##    term = ''.join([i for i in term if not i.isdigit()])
     ##   term = term.strip(' .-')
     ##   term = term.split(': ')
   ##     if len(term) > 1:
     ##       term[0] = term[0].capitalize()
      ##      term[1] = term[1].capitalize()
       ##     terms_dict.update({term[0]: term[1]})
   ## return(terms_dict)
    
