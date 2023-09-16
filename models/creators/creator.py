
import openai 
import json
import os
import tiktoken
import logging
from prompts.prompts import prompt_choices, prompt_choices2, lang_choices, len_choices
from prompts.prompts import  regen_choices, prompt_from_scratch
import requests
import asyncify
from models.creators.formatters import remove_html_tags, add_period, add_underscores
from typing import TYPE_CHECKING, Union, Any
if TYPE_CHECKING:
    from models.models_ import DeckAttributes

processing_logger = logging.getLogger("job_processing")
encoding = tiktoken.get_encoding("cl100k_base")

TEMPERATURE = 0.2

class AiCaller:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        openai.api_key = self.api_key
        
    async def call_ai_terms(self, sys_instruct, user_prompt) -> str:
        return await asyncify(openai.ChatCompletion.create)(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": sys_instruct},
                {"role": "user", "content": user_prompt},
            
            ],
            temperature = TEMPERATURE,
        )
    
    ## currently unused
    async def add_more_cards(self, attributes: 'DeckAttributes',
                              extract_type: str ="Mcq") -> Union[dict[str, Any], None]:
        sys_instruct = "You are an excellent teacher, you respond to all questions in a JSON object like string, do not answer with anything outside of the JSON object"  
        prompt = self.build_add_more_cards_prompt(
                    attributes.subject, attributes.topic,
                    attributes.concepts, attributes.grade,
                    attributes.language)
        response_ = None
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                response = await self.call_ai_terms(sys_instruct, prompt)
                if not response or 'choices' not in response:
                    raise RuntimeError("Invalid response from AI service")
                response_ = response['choices'][0]['message']['content'].strip()
                if extract_type == "Cloze":
                    response_ = add_underscores(response_)
                byte_string = response_.encode('utf-8')
                x = byte_string.decode('utf-8')
                x = self.extract_json_from_string(x)
                return load_json_string(x)
            except Exception as e:
                processing_logger.exception(f"Error occurred while in attempt {attempt} add more cards {str(e)}. AI content response is {response_}")  # noqa: E501
                if attempt == max_attempts:
                    raise e
                continue

    ## currently unused
    @staticmethod
    def extract_json_from_string(s: str) -> Union[str, None]:
        json_start = s.find('[')
        if json_start == -1:
            return None
        json_end = s.rfind(']')
        if json_end == -1:
            return None
        return s[json_start:json_end+1]


    def build_add_more_cards_prompt(self, subject: str,
                    topic: str, concepts: str, grade: str, language: str, extract_type: str="Mcq") -> str:
        language = f"Return the results in {language} only."
        prompt = prompt_from_scratch[extract_type]
        prompt = prompt.replace("{subject}", subject)
        prompt = prompt.replace("{topic}", topic)
        prompt = prompt.replace("{concepts}", concepts)
        prompt = prompt.replace("{grade}", grade)
        prompt = prompt.replace("{lang}", language)
        return prompt
    
    async def extract_deck_attributes(self, text: str) -> json:
        sys_instruct = "You are an expert at education and classification of content by subject, topic and level of difficulty as well as language. You are diligent and think about things carefully and only return content in JSON format" # noqa: E501
        user_prompt = 'Identify the main subject, topic, concepts and level of difficulty as well as language of the following text, the levels of difficulty should be based upon the educational level at which one would be expected to encounter the identified concepts, either primary school, middle school, high school, college or post-graduate level.  Return your response as a JSON object only in the following format: {"subject": "main subject identified", "topic": "main topic identified", "concepts": ["concept1", "concept2", ...], "difficulty": "difficulty level", "language": "identified language of text"}\n  The passage: \n {text}'# noqa: E501
        user_prompt = user_prompt.replace('{text}', text)
        response = await self.call_ai_terms(sys_instruct, user_prompt)

        response_ = response['choices'][0]['message']['content'].strip()
        
        byte_string = response_.encode('utf-8')
        x = byte_string.decode('utf-8')
        return load_json_string(x)
    

    async def extract_terms(self, text: str, prompt_options: dict) -> json:
        text = remove_html_tags(text)
        main_opt = prompt_options['main_opt']
        prompt = self.build_prompt(prompt_options)
        sys_instruct = f"You are a helpful teacher who wants to help students learn {prompt_options['subject_opt']}." # noqa: E501
        user_prompt = (prompt + text + 'The JSON object: \n')
        response = await self.call_ai_terms(sys_instruct, user_prompt)
        response_ = response['choices'][0]['message']['content'].strip()
        if main_opt == "Cloze":
            response_ = add_underscores(response_)
        byte_string = response_.encode('utf-8')
        x = byte_string.decode('utf-8')
        return load_json_string(x)



    def build_prompt(self, prompt_options: dict) -> str:
        if prompt_options['main_opt'] not in prompt_choices:
            raise ValueError("Invalid prompt option")
        else:
            prompt = prompt_choices[prompt_options['main_opt']]
            if prompt_options['subject_opt']:
                subject = "related to the subject of " + prompt_choices2[prompt_options['subject_opt']]
            else:
                subject = ""
            if prompt_options['lang_opt']:
                lang = lang_choices[prompt_options['lang_opt']]
            else:
                lang = ""
            if prompt_options['detail_lvl_opt']:
                detail = len_choices[prompt_options['detail_lvl_opt']]
            else:
                detail = ""
            if prompt_options['min_opt']:
                qmin = "at least " + prompt_options['min_opt']
            else:
                qmin = "all"
            if prompt_options['max_opt']:
                qmax = ", and at most " + prompt_options['max_opt']
            else:
                qmax = ""
            if prompt_options['trans_opt']:
                trans_opt = prompt_options['trans_opt']
            else:
                trans_opt = ""
            if prompt_options['custom_term']:
                custom_term = prompt_options['custom_term']
            else:
                custom_term = ""
            if prompt_options['custom_content']:
                custom_content = prompt_options['custom_content']
            else:
                custom_content = ""
            prompt = prompt.replace('{qmin}', qmin).replace('{subject}', subject).replace('{qmax}', qmax).replace('{length}', detail).replace('{lang}', lang).replace('{trans}', trans_opt).replace('{custom_term}', custom_term).replace('{custom_content}', custom_content) # noqa: E501
        return prompt
    


    async def process_text(self, instruction: str, task:str, extra_info: str, items: str) -> str:
        items = remove_html_tags(items)
        option_1 = f"You are an expert at {instruction} and respond in the same language as the passage"
        option_2 = f"{task} the following passage and return it using HTML formatting, using header tags, paragraph tags and list tags where appropriate, {extra_info} ignore table of contents and indexes, {items}" # noqa: E501
        response = await self.call_ai_terms(option_1, option_2)
        response = response['choices'][0]['message']['content']
        byte_string = response.encode('utf-8')
        response = byte_string.decode('utf-8')   
        return response

    async def summarize(self, items: str, prompt_options:dict = None) -> str:
        return await self.process_text("summarizing key points in a passage", "Summarize", "headers should refer to the content or topic of the passage, avoid headers such as summary or key points, your summary should get straight to the point and not include content such as 'in this passage'", items)

    async def turn_to_notes(self, items: str, prompt_options: dict = None) -> str:
        return await self.process_text("turning text into study notes", "Turn into notes", "headers should refer to the content or topic of the passage, avoid headers such as summary or key points, your summary should get straight to the point and not include content such as 'in this passage'", items)
    
    async def transcribe_and_translate(self, items: str, prompt_options: dict) -> str:
        items = remove_html_tags(items)
        language = prompt_options['trans_opt']
        option_1 = f"You are a helpful {language} translator"
        option_2 = f"translate the following passage to {language} return it with html formatting, use paragraph and header tags as appropriate: {items}" # noqa: E501
        response = await self.call_ai_terms(option_1, option_2)
        response = response['choices'][0]['message']['content']
        byte_string = response.encode('utf-8')
        response = byte_string.decode('utf-8')   
        return response
    
    async def transcribe_whisper(self, audio_file) -> str:
        audio_file= open(audio_file, "rb")
        transcript = await asyncify(openai.Audio.transcribe)("whisper-1", audio_file)
        transcript = transcript["text"]
        return transcript
    

    def call_ai_terms_non_async(self, sys_instruct: str, user_prompt: str) -> str:
        return openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": sys_instruct},
                {"role": "user", "content": user_prompt},
            ],
        )
    
    def regenerate_definition(self, term: str, prompt_options: dict) -> list:
        retries = 0

        prompt = self.build_prompt_regen(term, prompt_options)
        while retries < 3:
            try:
                sys_instruct = "You are a helpful teacher who wants to help students learn."
                user_prompt = prompt
                response = self.call_ai_terms_non_async(sys_instruct, user_prompt)
                x = response['choices'][0]['message']['content'].strip()
                z = [term, ":"]
                y = "".join(z)
                if x.startswith(term):
                    x = x.replace(term, "",)
                if x.startswith(y):
                    x = x.replace(y, "", 1)
                x = x.strip()
                x = add_period(x)
                return x, user_prompt, response, x

            except Exception as e:
                retries += 1
                processing_logger.error(f"Error: {e}. Retrying ({retries}/3)")
                if retries == 3:
                    raise e


    
    def build_prompt_regen(self, term: str, prompt_options: dict) -> str:
        if prompt_options['main_opt'] not in regen_choices:
            raise ValueError("Invalid prompt option")
        else:
            prompt = regen_choices[prompt_options['main_opt']]
            if prompt_options['subject_opt'] is not None:
                subject = "related to the subject of " + prompt_choices2[prompt_options['subject_opt']]
            else:
                subject = ""
            if prompt_options['lang_opt'] is not None:
                lang = lang_choices[prompt_options['lang_opt']]
            else:
                lang = ""
            if prompt_options['detail_lvl_opt']:
                detail = len_choices[prompt_options['detail_lvl_opt']]
            else:
                detail = ""
            if prompt_options['trans_opt']:
                trans_opt = prompt_options['trans_opt']
            else:
                trans_opt = ""
            prompt = prompt.replace('{length}', detail).replace('{lang}', lang).replace('{trans}', trans_opt).replace('{term}', term).replace('{subject}', subject) # noqa: E501
        return prompt
    
    def explain_more(self, term: str, subject: str = None, content:str = None) -> str:
        retries = 0
        prompt = self.build_prompt_explain_more(term, subject, content)
        while retries < 3:
            try:
                sys_instruct = "You are a helpful teacher who is an expert and providing clear and detailed explanations. There is no need to introduce yourself, but if questioned you should answer that you are a teacher named Ceph who is here to help."
                response = self.call_ai_terms_non_async(sys_instruct, prompt)
                return response['choices'][0]['message']['content'].strip()
            except Exception as e:
                retries += 1
                processing_logger.error(f"Error: {e}. Retrying ({retries}/3)")
                if retries == 3:
                    raise e
            
    def build_prompt_explain_more(self, term: str, subject: str = None, content: str = None) -> str:
        prompt = "You are a helpful teacher who wants to help students learn {subject_opt}. You are explaining the concept of {term} to a student. The student asks you to explain {term} in a lot of detail, providing not just explanations but where possible examples and analogies. You respond: " # noqa: E501
        prompt = prompt.replace('{term}', term)
        if subject is not None:
            prompt = prompt.replace('{subject_opt}', subject)
        return prompt


    def why_wrong_generator(self, ww_prompt: str) -> str:
        retries = 0
        prompt = self.build_prompt_why_wrong(ww_prompt)
        while retries < 3:
            try:
                sys_instruct = "You are a helpful teacher who is an expert and providing clear and detailed explanations. There is no need to introduce yourself, but if questioned you should answer that you are a teacher named Ceph who is here to help." # noqa: E501
                response = self.call_ai_terms_non_async(sys_instruct, prompt)
                return response['choices'][0]['message']['content'].strip()
            except Exception as e:
                retries += 1
                processing_logger.error(f"Error: {e}. Retrying ({retries}/3)")
                if retries == 3:
                    raise e
                
    def build_prompt_why_wrong(self, ww_prompt: dict) -> str:
        subject = ww_prompt['subject']
        term = ww_prompt['term']
        content = ww_prompt['content']
        boc_2 = ww_prompt['boc_2']
        boc_3 = ww_prompt['boc_3']
        boc_4 = ww_prompt['boc_4']
        category = ww_prompt['category']
        if category == "Mcq":
            prompt = "You are a helpful teacher who wants to help students learn {subject_opt}.   The student has just answered this multiple choice question incorrectly: {term}. The student asks you why this answer is correct: {content}, whereas these are wrong {boc_2} and {boc_3} and {boc_4}. You respond: " # noqa: E501
            prompt = prompt.replace('{term}', term)
            prompt = prompt.replace('{content}', content)
            prompt = prompt.replace('{boc_2}', boc_2)
            prompt = prompt.replace('{boc_3}', boc_3)
            prompt = prompt.replace('{boc_4}', boc_4)
            if subject is not None:
                prompt = prompt.replace('{subject_opt}', subject)
            else:
                prompt = prompt.replace('{subject_opt}', "")
        else:
            prompt = "You are a helpful teacher who wants to help students learn {subject_opt}. The student is studying flashcards and doesn't understand why {content} is the appropriate answer to this question: {term}. The student asks you why this answer is correct: {content} You respond: "  # noqa: E501
            prompt = prompt.replace('{term}', term)
            prompt = prompt.replace('{content}', content)
            if subject is not None:
                prompt = prompt.replace('{subject_opt}', subject)
            else:
                prompt = prompt.replace('{subject_opt}', "")
        return prompt


    def send_question_generator(self, term: str, content: str, latest_paragraph: str, question: str) -> str:
        retries = 0
        prompt = self.question_prompt_builder(self, term, content, latest_paragraph, question)
        while retries < 3:
            try:
                sys_instruct = "You are a helpful teacher who is an expert and providing clear and detailed explanations. There is no need to introduce yourself, but if questioned you should answer that you are a teacher named Ceph who is here to help.  You respond to the student in the same language as their question"  # noqa: E501
                response = self.call_ai_terms_non_async(sys_instruct, prompt)
                return response['choices'][0]['message']['content'].strip()
            except Exception as e:
                retries += 1
                processing_logger.error(f"Error: {e}. Retrying ({retries}/3)")
                if retries == 3:
                    raise e
                

    def question_prompt_builder(self, term: str, content: str, latest_paragraph: str, question: str) -> str:
        prompt = "You have previously interacted with the student and have helped them learn {term} {content} {paragraph}. The student has asked you a question: {question}. You respond:"  # noqa: E501
        prompt = prompt.replace('{term}', term)
        prompt = prompt.replace('{content}', content)
        if latest_paragraph != "":
            paragraph = "You have previously told the student that {latest_paragraph}."
            paragraph = paragraph.replace('{latest_paragraph}', latest_paragraph)
            prompt = prompt.replace('{paragraph}', paragraph)
        return prompt.replace('{question}', question)
    

    async def create_image(self, term: str) -> str:
        try:
            response = await asyncify (openai.Image.create)(
                prompt=term,
                n=1,
                response_format='url',
                size="256x256"
            )
            image_url = response['data'][0]['url']
            img_name = term.replace(' ', '_') + '.webp'
            img_path = os.path.join('static\card_img', img_name)  # Create the full path to the image file
            r = requests.get(image_url)
            r.raise_for_status()  # Raises an exception if the request was unsuccessful
            with open(img_path, 'wb') as f:
                f.write(r.content)
            return img_path
        except (openai.error.InvalidRequestError, requests.exceptions.RequestException) as e:
            raise e

        
    async def insert_paragraph(self, text:str) -> str:
        prompt = "Go through the following block of text and insert '&-&-&' where you think a paragraph break should be. \n  block of text: \n" + text + "\n The JSON object: \n"
        response = await asyncify(openai.ChatCompletion.create)(
                model="gpt-3.5-turbo",
                messages=[
                        {"role": "system", "content": "You are an expert at the written word"},
                        {"role": "user", "content": prompt},
                    ],
                )
        return response['choices'][0]['message']['content']
    
def isolate_json_string(json_string: str) -> str:
    # Isolate JSON-like object
    start_index = json_string.find('[')
    end_index = json_string.rfind(']')
    return json_string[start_index:end_index+1]


def load_json_string(x:str) -> json:
    json_result, success = try_json_load(x)
    if not success:
        processing_logger.info("failed to decode json, trying with single quote")
        json_result, success = try_json_load(fix_end_json_string_single(x))
    if not success:
        processing_logger.info("failed to decode json, trying with double quote")
        json_result, success = try_json_load(fix_end_json_string_double(x))
    if not success:
        processing_logger.error("Failed to decode JSON")
        processing_logger.error(f"First 100 characters:{x[:100]}")
        processing_logger.error(f"Last 100 characters:{x[-100:]}")
        raise json.JSONDecodeError("Failed to decode JSON", x, 0)
    return json_result


def try_json_load(json_string):
    try:
        return json.loads(json_string), True
    except json.JSONDecodeError:
        return None, False
    
def fix_end_json_string_single(json_string):
    if json_string.endswith("'"):
        json_string = json_string[:-1] + "}]"
    elif json_string.endswith('"'):
        json_string = json_string[:-1] + "}]"
    elif json_string.endswith("}"):
        json_string += "]"
    else:
        json_string += "'}]"
    return json_string

def fix_end_json_string_double(json_string):
    if json_string.endswith("'"):
        json_string = json_string[:-1] + "}]"
    elif json_string.endswith('"'):
        json_string = json_string[:-1] + "}]"
    elif json_string.endswith("}"):
        json_string += "]"
    else:
        json_string += '"}]'
    return json_string