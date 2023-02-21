
import openai 
import PyPDF2
from dotenv import load_dotenv, find_dotenv
from pptx import Presentation
import numpy as np
import docx2txt
import json
import sys

## terms choices
prompt_choices = {
    'Definitions': 'Given the passage below, extract as many uncommon or technical terms as possible and provide a definition for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the terms extracted and have a property named "T" as well as one named "D". \n The resulting JSON object should be in this format: [{"T":"string","D":"string"}] \n The passage: \n',
    "Translate": 'Given the passage below, extract as many uncommon or technical terms as possible and provide a {} translation for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the terms extracted and have a property named "T", for the term, as well as one named "TR", for the {} translation. \n The resulting JSON object should be in this format: [{"T":"string","TR":"string"}] \n The passage: \n',
    "Rhyme": 'Given the passage below, extract as many uncommon or technical terms as possible and create a four verse poem for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the terms extracted and have a property named "T", for the term, as well as one named "R", for the poem. \n The resulting JSON object should be in this format: [{"T":"string","R":"string"}] \n The passage: \n',
    "People": 'Given the passage below, extract all the names of people and provide a brief biography for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the terms extracted and have a property named "P", for the person, as well as one named "B", for the biography. \n The resulting JSON object should be in this format: [{"P":"string","B":"string"}] \n The passage: \n',
    "Theories": 'Given the passage below, identify all the relevant theories and concepts and provide an explanation for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the theories or concepts extracted and have a property named "TC", for the theory or concept, as well as one named "E", for the explanation. \n The resulting JSON object should be in this format: [{"TC":"string","E":"string"}] \n The passage: \n',
    "Cloze": 'Given the passage below, create cloze deletion text.  Aim for an average of one cloze deletion text for every two sentences.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the cloze deletion texts and have a property named "C" for the cloze deletion text, and "F" for the missing words. \n The resulting JSON object should be in this format: [{"C":"string","F":"string"}] \n The passage: \n',
    "Mcq":'Given the passage below, create at least one multiple choice question for each key piece of information.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the multiple choice questions and have a property named "Q" for the question, as well as a string named A where the first answer is the correct one and the next 3 are incorrect.  They should be seperated by ##.  \n The resulting JSON object should be in this format: [{"Q": "string", "A":"Answer"}] \n The passage \n',
    "Comprehension":'Given the passage below, create a series of questions to test comprehension of the passage.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the comprehension questions and have a property named "QC" for the question, and "AC" for the answer.  \n The resulting JSON object should be in this format: [{"QC":"string","AC":"string"}] \n The passage: \n',
    } 
 
   
def extract_terms(text: str, prompt_option: str, prompt_option2 = None):
    print("entered extract term function")
    print(prompt_option)
    print(prompt_option2)
    if prompt_option not in prompt_choices:
        raise ValueError("Invalid prompt option")
    prompt_select = prompt_choices[prompt_option]
    if prompt_option2 != None:
        print(prompt_select)
        prompt_select = prompt_select.replace('{}', prompt_option2)
    prompt = (prompt_select + text + 'The JSON object: \n')
    response = openai.Completion.create(
        engine="text-davinci-003",
        temperature=0.7,
        top_p=1,
        prompt=prompt,
        max_tokens=1000
    )
    print(prompt_option)
    print(prompt_select)
    x = response.choices[0]["text"].strip()
    print(x)
    x = json.loads(x)
    print(x)
    return x
   
   
## extract_terms 
##def extract_terms(text: str, prompt_option:str):
    
   ## prompt_select = prompt_choices[prompt_option]
  ##  prompt = (prompt_select + text + 'The JSON object: \n')
    ## experiment with temprature = ,top_p =, frequency_penalty =, presence_penalty =, stop= ,
  ##  response = openai.Completion.create(
   ##     engine="text-davinci-003", ## using ada for cost, switch to curie-001 or davinci-003, babbage-001, ada-001.  HAVE TO USE DA VINCI TO GET PROPER FORMATTING
   ##     temperature = 0.7,
   ##     top_p = 1,
   ##     prompt=prompt,
  ##      max_tokens=1000)
  ##  return response

def small_extract_terms(item: str, prompt_option:str, prompt_option2 = None):
    ls_terms = []
    response = extract_terms(item, prompt_option, prompt_option2)
    for dict in response:
        ls_terms.append(dict)
    return ls_terms

## for large documents only (otherwise just use extract_terms directly) passes through items one by one and returns a string with all terms
def large_extract_terms(items: str, prompt_option:str, prompt_option2 = None):
    print("entered large extract term function")
    print(prompt_option)
    print(prompt_option2)
    ls_terms = []
    for item in items:
        response = extract_terms(item, prompt_option, prompt_option2)
        ## lines below moves to extract function
        ##x = response.choices[0]["text"].strip()
        ##x = json.loads(x)
        for dict in response:
            ls_terms.append(dict)
    print(ls_terms)
    return ls_terms

def add_period(s):
    if s[-1] != ".":
        s += "."
    return s


## TEXT EXTRACTORS    



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

## obsolete?            
def Merge(dict1, dict2):
    return(dict2.update(dict1))
 
## REGENERATE A DEFINITION
def Regenerate_def(term):
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



## pypdf to pydf2, saving old pypdf code
##def extract_from_pdf(pdf_file):
  ##  reader = PdfReader(pdf_file)
   ## total_pages = len(reader.pages)
  ##  text = []
   ## for i in range(len(reader.pages)):
   ##     page = reader.pages[i]
      ##  page = page.extract_text()
   ##     page = page.replace("\n", " ")
    ##    text.append(page)
   ## return text