
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

openai.api_key = os.environ.get("OPENAI_API_KEY")

encoding = tiktoken.get_encoding("cl100k_base")
logger = logging.getLogger("extractors")
logger.setLevel(logging.DEBUG)


## TOKEN HANDLERS
def count_tokens(text):
    text = encoding.encode(text)
    print("token count:", len(text))
    return len(text)

def token_encoding(text):
    return encoding.encode(text)

def token_decoding(text):
    return encoding.decode(text)

## split list of tokens into chunks of n tokens
def split_tokens(tokens, n):
    return [tokens[i:i+n] for i in range(0, len(tokens), n)]


def remove_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

## MISC FORMATTERS
def add_period(s):
    if not s:
        return s
    else:
        if s[-1] != ".":
            s += "."
        return s

def check_comma_list(string):
    if "," in string:
        return True
    else:
        return False
    
def add_underscores(string):
    if "_" in string:
        string = string.replace("_", "_" * 8, 1)
    return string

## turn string of comma separated terms into list of terms
def comma_list_to_list(string):
    return string.split(",")

def clean_text(text):
    # Decode Unicode escape sequences into actual characters
    text = codecs.decode(text, 'unicode_escape')
    # Replace newline characters with spaces
    # This pattern matches any character that is not a letter, digit, whitespace, or regular punctuation.
    pattern = r"[^\w\s.,;:?!-’'\"()]+"
    cleaned_text = re.sub(pattern, "", text)
    return cleaned_text

def get_replacement_value(value, prefix='', suffix=''):
    if value:
        return prefix + value + suffix
    return ''





def render_latex(latex_code):
    unicode_str = LatexNodes2Text().latex_to_text(latex_code)
    return unicode_str

def double_backslashes(s):
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

def decode_latex_in_string(string):
    # Define a regular expression pattern to match LaTeX formulas
    pattern = r'(\$[^\$]*\$|\\\([^\)]*\\\))'
    # Use the pattern to find all LaTeX formulas in the string
    matches = re.findall(pattern, string)
    # Loop over the matches and replace each LaTeX formula with its decoded equivalent
    for match in matches:
        decoded = render_latex(match)
        string = string.replace(match, decoded)
    
    return string


def fix_json(s):
    try:
        json.loads(s)
        return s
    except json.JSONDecodeError as e:
        # JSONDecodeError is raised if the string is not in valid JSON format
        # We can attempt to fix the error by removing any trailing commas or fixing the quotes
        s = s[:e.pos] + s[e.pos:].replace(',', '')
        s = s.replace("'", "\"")
        print("--------------------------------------------fixing json ------------------------------------------------------------")

        try:
            print("--------------------------------------------fixed json ------------------------------------------------------------")
            json.loads(s)
            return s
        except:
            raise ValueError("Unable to fix JSON string")
        
        
def create_pdf(string):
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
