from reportlab.pdfgen import canvas
import openai 
import PyPDF2
from PyPDF2 import PdfWriter, PdfReader
from dotenv import load_dotenv, find_dotenv
from pptx import Presentation
import numpy as np
import docx2txt
import json
import sys
from pydub import AudioSegment
import os
from io import BytesIO
import math
from youtube_transcript_api import YouTubeTranscriptApi
import tiktoken
import io
import textwrap
from reportlab.lib.pagesizes import letter
from prompts import prompt_choices, prompt_choices2, lang_choices, len_choices, new_prompt_choices, regen_choices
from bs4 import BeautifulSoup
import requests
from pylatexenc.latex2text import LatexNodes2Text
import re
from helpers import split_text
import aiohttp
import asyncio
from aiohttp import ClientSession
import asyncify
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

async def call_ai_terms(sys_instruct, user_prompt):
    response = await asyncify(openai.ChatCompletion.create)(
        model="gpt-3.5-turbo",
        messages=[
                {"role": "system", "content": sys_instruct},
                {"role": "user", "content": user_prompt},
            ],
        )
    return response

async def summarize(items):
    try:
        print("entered summarize function")
        option_1 = "You are an expert and summarizing key points in a passage"
        option_2 = f"Summarize the following passage and return it with HTML formatting, using header tags, paragraph tags and list tags where appropriate {items}"
        response = await call_ai_terms(option_1, option_2)
        response = response['choices'][0]['message']['content']
        print(response)
        return response
    except Exception as e:
        print(e)

# Replace 'your_text_here' with the text you want to summarize
text_to_summarize = "your_text_here"
asyncio.run(summarize(text_to_summarize))