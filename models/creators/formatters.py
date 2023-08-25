
from reportlab.pdfgen import canvas
import openai 
import json
import os
from io import BytesIO
import tiktoken
import textwrap
from reportlab.lib.pagesizes import letter
from pylatexenc.latex2text import LatexNodes2Text
import re
import codecs
import logging
from typing import List
openai.api_key = os.environ.get("OPENAI_API_KEY")

encoding = tiktoken.get_encoding("cl100k_base")
logger = logging.getLogger("extractors")
logger.setLevel(logging.DEBUG)


## TOKEN HANDLERS
def count_tokens(text: str) -> int:
    text = encoding.encode(text)
    return len(text)

def token_encoding(text: str) -> str:
    return encoding.encode(text)

def token_decoding(text: str) -> str:
    return encoding.decode(text)

def split_tokens(tokens: List[str], n: int) -> List[List[str]]:
    return [tokens[i:i+n] for i in range(0, len(tokens), n)]


def remove_html_tags(text: str):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

## MISC FORMATTERS
def add_period(s: str) -> str:
    if s:
        if s[-1] != ".":
            s += "."
    return s

def check_comma_list(string: str) -> bool:
    return "," in string
    
def add_underscores(string: str) -> str:
    if "_" not in string:
        string = string.replace(" ", "_")
    return string
## turn string of comma separated terms into list of terms
def comma_list_to_list(string: str) -> List[str]:
    return string.split(",")

def clean_text(text: str) -> str:
    # Decode Unicode escape sequences into actual characters
    text = codecs.decode(text, 'unicode_escape')
    # Replace newline characters with spaces
    # This pattern matches any character that is not a letter, digit, whitespace, or regular punctuation.
    pattern = r"[^\w\s.,;:?!-’'\"()]+"
    return re.sub(pattern, "", text)

def get_replacement_value(value: str, prefix: str='', suffix: str='') -> str:
    return prefix + value + suffix if value else ''





def render_latex(latex_code: str) -> str:
    return LatexNodes2Text().latex_to_text(latex_code)

def double_backslashes(s: str) -> str:
    result = ''
    pattern = r'\\\[.*?\\\]|\\\(.*?\\\)|(?<!\\)\$.+?(?<!\\)\$'
    # Match LaTeX formulas delimited by \[...\] or \(...\), or inline formulas delimited by $...$
    matches = re.findall(pattern, s)
    last_end = 0
    for match in matches:
        start = s.index(match, last_end)
        result += s[last_end:start]
        result += re.sub(r'\\', r'\\\\', match)
        last_end = start + len(match)
    result += s[last_end:]
    return result

def decode_latex_in_string(string: str) -> str:
    # Define a regular expression pattern to match LaTeX formulas
    pattern = r'(\$[^\$]*\$|\\\([^\)]*\\\))'
    # Use the pattern to find all LaTeX formulas in the string
    matches = re.findall(pattern, string)
    # Loop over the matches and replace each LaTeX formula with its decoded equivalent
    for match in matches:
        decoded = render_latex(match)
        string = string.replace(match, decoded)
    
    return string


def fix_json(s: str) -> json:
    try:
        json.loads(s)
        return s
    except json.JSONDecodeError as e:
        # JSONDecodeError is raised if the string is not in valid JSON format
        # We can attempt to fix the error by removing any trailing commas or fixing the quotes
        s = s[:e.pos] + s[e.pos:].replace(',', '')
        s = s.replace("'", "\"")
        print("--------------------------------------------fixing json ------------------------------------------")

        try:
            print("--------------------------------------------fixed json --------------------------------------")
            json.loads(s)
            return s
        except json.JSONDecodeError as e:
            print("unable to fix json string")
            raise ValueError("Unable to fix JSON string") from e
        
        
def create_pdf(string: str) -> BytesIO:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer)
    # Define the width and height of the canvas
    width, height = letter
    # Define the margin and the maximum line width
    margin = 36
    max_width = width - 2*margin
    # Wrap the string to fit within the canvas
    lines = textwrap.wrap(string, width=max_width//8)
    # Draw each line on the canvas
    y = height - margin
    for line in lines:
        pdf.drawString(margin, y, line)
        y -= 20  # Move down to the next line
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return buffer
