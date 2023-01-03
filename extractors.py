
import openai 
from pypdf import PdfReader
from dotenv import load_dotenv, find_dotenv
from pptx import Presentation
import numpy as np
import docx2txt

prompt_standard = "Extract as many uncommon or technical terms as possible from the following text and provide a definition for each in a non numbered list: "
  
    ## extract_terms 
def extract_terms(text: str):
    prompt = (prompt_standard + text)
    ## experiment with temprature = ,top_p =, frequency_penalty =, presence_penalty =, stop= ,
    response = openai.Completion.create(
        engine="text-davinci-001", ## using ada for cost, switch to curie-001 or davinci-003, babbage-001, ada-001.  HAVE TO USE DA VINCI TO GET PROPER FORMATTING
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