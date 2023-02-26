
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
    'Definitions': ' Given the passage below, extract {qmin} {qmax} uncommon or technical terms {c2} and provide a {length} definition for each. {lang} Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "T" as well as one named "D". \n The resulting JSON object should be in this format: [{"T":"string","D":"string"}] \n The passage: \n',
    "Translate": '{c2}Given the passage below, extract {qmin} uncommon or technical terms {qmax} and provide a {trans} translation for each. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "T", for the term, as well as one named "TR", for the {} translation. \n The resulting JSON object should be in this format: [{"T":"string","TR":"string"}] \n The passage: \n',    "Rhyme": 'Given the passage below, extract as many uncommon or technical terms as possible and create a four verse poem for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the terms extracted and have a property named "T", for the term, as well as one named "R", for the poem. \n The resulting JSON object should be in this format: [{"T":"string","R":"string"}] \n The passage: \n',
    "Rhyme": '{c2}Given the passage below, extract {qmin} uncommon or technical terms {qmax} and create a four verse poem for each {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "T", for the term, as well as one named "R", for the poem. \n The resulting JSON object should be in this format: [{"T":"string","R":"string"}] \n The passage: \n',
    "People": '{c2}Given the passage below, extract all the names of people and provide a {length} biography for each {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the terms extracted and have a property named "P", for the person, as well as one named "B", for the biography. \n The resulting JSON object should be in this format: [{"P":"string","B":"string"}] \n The passage: \n',    "Theories": 'Given the passage below, identify all the relevant theories and concepts and provide an explanation for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the theories or concepts extracted and have a property named "TC", for the theory or concept, as well as one named "E", for the explanation. \n The resulting JSON object should be in this format: [{"TC":"string","E":"string"}] \n The passage: \n',
    "Theories": '{c2}Given the passage below, identify {qmin} relevant theories and concepts {qmax} and provide an {length} explanation for each {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the theories or concepts extracted and have a property named "TC", for the theory or concept, as well as one named "E", for the explanation. \n The resulting JSON object should be in this format: [{"TC":"string","E":"string"}] \n The passage: \n',
    "Cloze": '{c2}Given the passage below, create {qmin} cloze deletion questions {qmax} {lang}. The goal is to test my understanding of the text. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the cloze deletion texts and have a property named "C" for the cloze deletion text, and "F" for the missing word(s). \n The resulting JSON object should be in this format: [{"C":"string","F":"string"}] \n The passage: \n',    "Mcq":'Given the passage below, create at least one multiple choice question for each key piece of information.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the multiple choice questions and have a property named "Q" for the question, one named A for the correct answer and 3 other properties for the wrong answers, W1, W2, W3.  \n The resulting JSON object should be in this format: [{"Q": "string", "A":"Answer", "W1":"Wrong answer 1", "W2":"Wrong answer 2", "W3":"Wrong answer 3"}] \n The passage \n',
    "Mcq":'{c2}Given the passage below, create {qmin} {length} multiple choice questions {qmax} {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the multiple choice questions and have a property named "Q" for the question, one named A for the correct answer and 3 other properties for the wrong answers, W1, W2, W3. \n The resulting JSON object should be in this format: [{"Q": "string", "A":"Answer", "W1":"Wrong answer 1", "W2":"Wrong answer 2", "W3":"Wrong answer 3"}] \n The passage \n',
    "Comprehension":'{c2}Given the passage below, create {qmin} {length} questions {qmax} to test comprehension of the key information contained within {lang}. Create a JSON object which enumerates a set of child objects. Each of the child objects should correspond to one of the comprehension questions and have a property named "QC" for the question, and "AC" for the answer. \n The resulting JSON object should be in this format: [{"QC":"string","AC":"string"}] \n The passage: \n',    
    "Vocab_builder": 'Given the passage below, extract all unique words and provide a definition for each.  Create a JSON object which enumerates a set of child objects.  Each of the child objects should correspond to one of the words extracted and have a property named "W", for the word, as well as one named "D", for the definition. \n The resulting JSON object should be in this format: [{"W":"string","D":"string"}] \n The passage: \n', } 

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
    
    
    if prompt_option not in prompt_choices:
        raise ValueError("Invalid prompt option")
    
    print(prompt_select)
    prompt_select = prompt_select.replace('{qmin}', qmin)
    prompt_select = prompt_select.replace('{c2}', c2)
    prompt_select = prompt_select.replace('{qmax}', qmax)
    prompt_select = prompt_select.replace('{length}', length)
    prompt_select = prompt_select.replace('{lang}', lang)
    print(prompt_select)

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
    print(prompt_option)
    print(prompt_select)
    x = response.choices[0]["text"].strip()
    print(x)
    x = json.loads(x)
    print(x)
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
    ls_terms = []
    for item in items:
        response = extract_terms(item, prompt_option, prompt_option2, lang_option, trans_option, len_option, qmin_option, qmax_option)
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
