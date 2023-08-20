
import openai 
import json
import os
import tiktoken
from prompts.prompts import prompt_choices, prompt_choices2, lang_choices, len_choices
from prompts.prompts import  regen_choices, prompt_from_scratch
import requests
import asyncify
import logging
from models.creators.formatters import remove_html_tags, add_period, add_underscores

encoding = tiktoken.get_encoding("cl100k_base")
logger = logging.getLogger("extractors")
logger.setLevel(logging.DEBUG)


class AiCaller:
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        openai.api_key = self.api_key
        
    async def call_ai_terms(self, sys_instruct, user_prompt):
        try:
            response = await asyncify(openai.ChatCompletion.create)(
                model="gpt-3.5-turbo",
                messages=[
                        {"role": "system", "content": sys_instruct},
                        {"role": "user", "content": user_prompt},
                    ],
                )
        except Exception as e:
            print(e)
        return response
 
    async def add_more_cards(self, attributes, extract_type="Mcq"):
        print("entered add more cards")
        sys_instruct = "You are an excellent teacher, knowledgeable on all subjects who is an expert at making detailed content, you only return data in JSON format"
        prompt = self.build_add_more_cards_prompt(
                    attributes.subject, attributes.topic,
                    attributes.concepts, attributes.grade,
                    attributes.language)
        response = await self.call_ai_terms(sys_instruct, prompt)
        response_ = response['choices'][0]['message']['content'].strip()
        print("raw response:", response)
        print("response:", response_)
        if extract_type == "Cloze":
            response_ = add_underscores(response_)
        byte_string = response_.encode('utf-8')
        x = byte_string.decode('utf-8')
        json_start = x.find('[')
        if json_start != -1:
            json_end = x.rfind(']')  # Find the position of the last closing bracket in the string
            if json_end != -1:
                json_part = x[json_start:json_end+1] 
        else:
            print("No valid JSON found")

        try:
            data = json.loads(json_part)
        except json.JSONDecodeError as e:
            print(f"Could not parse as JSON: {json_part}")
            print(f"Error details: {e}")
        return data


    def build_add_more_cards_prompt(self, subject, topic, concepts, grade, language, extract_type="Mcq"):
        language = "Return the results in " + language + " only."
        prompt = prompt_from_scratch[extract_type]
        prompt = prompt.replace("{subject}", subject)
        prompt = prompt.replace("{topic}", topic)
        prompt = prompt.replace("{concepts}", concepts)
        prompt = prompt.replace("{grade}", grade)
        prompt = prompt.replace("{lang}", language)
        print("prompt:", prompt)
        return prompt
    
    async def extract_deck_attributes(self, text):
        print("entered extract deck attributes function")
        sys_instruct = "You are an expert at education and classification of content by subject, topic and level of difficulty as well as language. You are diligent and think about things carefully and only return content in JSON format"
        user_prompt = 'Identify the main subject, topic, concepts and level of difficulty as well as language of the following text, the levels of difficulty should be based upon the educational level at which one would be expected to encounter the identified concepts, either primary school, middle school, high school, college or post-graduate level.  Return your response as a JSON object only in the following format: {"subject": "main subject identified", "topic": "main topic identified", "concepts": ["concept1", "concept2", ...], "difficulty": "difficulty level", "language": "identified language of text"}\n  The passage: \n {text}'
        user_prompt = user_prompt.replace('{text}', text)
        try:
            response = await self.call_ai_terms(sys_instruct, user_prompt)
        except Exception as e:
            print(e)
        print("after call ai terms")

        print(response)
        response_ = response['choices'][0]['message']['content'].strip()
        
        byte_string = response_.encode('utf-8')
        x = byte_string.decode('utf-8')
        print(x)
        x = json.loads(x)
        return x
    

    async def extract_terms(self, text: str, prompt_options: dict):
        text = remove_html_tags(text)
        print("CALLING EXTRACT TERMS")

        main_opt = prompt_options['main_opt']
        print(main_opt)
        prompt = self.build_prompt(prompt_options)
        print("prompt built")
        try:
            sys_instruct = f"You are a helpful teacher who wants to help students learn {prompt_options['subject_opt']}."
            user_prompt = (prompt + text + 'The JSON object: \n')
            response = await self.call_ai_terms(sys_instruct, user_prompt)
            response_ = response['choices'][0]['message']['content'].strip()
            print("raw response:", response)
            print("response:", response_)
            if main_opt == "Cloze":
                response_ = add_underscores(response_)
            byte_string = response_.encode('utf-8')
            x = byte_string.decode('utf-8')
            x = json.loads(x)
            return x
        except Exception as e:
            print(f"Error calling ai terms: {e}.")


    def build_prompt(self, prompt_options: dict):
        print("entered build prompt function")
        print(prompt_options)
        if prompt_options['main_opt'] not in prompt_choices:
            print("Invalid prompt option")
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
            prompt = prompt.replace('{qmin}', qmin).replace('{subject}', subject).replace('{qmax}', qmax).replace('{length}', detail).replace('{lang}', lang).replace('{trans}', trans_opt).replace('{custom_term}', custom_term).replace('{custom_content}', custom_content)
            print(prompt[:50])
        return prompt
    


    async def process_text(self, instruction, task, items):
        items = remove_html_tags(items)
        print(f"entered {task} function")
        option_1 = f"You are an expert at {instruction}"
        option_2 = f"{task} the following passage and return it using HTML formatting, using header tags, paragraph tags and list tags where appropriate, ignore table of contents and indexes {items}"
        response = await self.call_ai_terms(option_1, option_2)
        response = response['choices'][0]['message']['content']
        byte_string = response.encode('utf-8')
        response = byte_string.decode('utf-8')   
        return response

    async def summarize(self, items, prompt_options = None):
        return await self.process_text("summarizing key points in a passage", "Summarize", items)

    async def turn_to_notes(self, items, prompt_options = None):
        return await self.process_text("turning text into study notes", "Turn into notes", items)
    


    async def transcribe_and_translate(self, items, prompt_options):
        items = remove_html_tags(items)
        language = prompt_options['trans_opt']
        print(language)
        option_1 = f"You are a helpful {language} translator"
        option_2 = f"translate the following passage to {language}  return it with html formatting, use paragraph and header tags as appropriate: {items}"
        response = await self.call_ai_terms(option_1, option_2)
        response = response['choices'][0]['message']['content']
        byte_string = response.encode('utf-8')
        response = byte_string.decode('utf-8')   
        return response
    
    async def transcribe_whisper(self, audio_file):
        print("entered transcribe function")
        audio_file= open(audio_file, "rb")
        transcript = await asyncify(openai.Audio.transcribe)("whisper-1", audio_file)
        transcript = transcript["text"]
        return transcript
    

    def call_ai_terms_non_async(self, sys_instruct, user_prompt):
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                    {"role": "system", "content": sys_instruct},
                    {"role": "user", "content": user_prompt},
                ],
            )
        return response
    
    def regenerate_definition(self, term, prompt_options):
        retries = 0

        prompt = self.build_prompt_regen(term, prompt_options)
        print("entered regenerate_def function")
        while retries < 3:
            print("attempt:", retries)
            try:
                sys_instruct = f"You are a helpful teacher who wants to help students learn."
                user_prompt = prompt
                response = self.call_ai_terms_non_async(sys_instruct, user_prompt)
                x = response['choices'][0]['message']['content'].strip()
                print(x[:50])
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
                print(f"Error: {e}. Retrying ({retries}/3)")


    
    def build_prompt_regen(self, term, prompt_options: dict):
        if prompt_options['main_opt'] not in regen_choices:
            print("Invalid prompt option")
            raise ValueError("Invalid prompt option")
        else:
            prompt = regen_choices[prompt_options['main_opt']]
            if prompt_options['subject_opt'] != None:
                subject = "related to the subject of " + prompt_choices2[prompt_options['subject_opt']]
            else:
                subject = ""
            if prompt_options['lang_opt']!= None:
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

            prompt = prompt.replace('{length}', detail).replace('{lang}', lang).replace('{trans}', trans_opt).replace('{term}', term)
            print("prompt built")
    
        return prompt
    

    def explain_more(self, term, subject = None, content = None):
        print("entered explain more function")

        retries = 0
        prompt = self.build_prompt_explain_more(term, subject, content)
        print("prompt is:", prompt)
        while retries < 3:
            print("attempt:", retries)
            try:
                sys_instruct = f"You are a helpful teacher who is an expert and providing clear and detailed explanations. There is no need to introduce yourself, but if questioned you should answer that you are a teacher named Ceph who is here to help."
                response = self.call_ai_terms_non_async(sys_instruct, prompt)
                response_ = response['choices'][0]['message']['content'].strip()
                print(response_[:50])
                return response_
            
            except Exception as e:
                retries += 1
                print(f"Error: {e}. Retrying ({retries}/3)")
            
    def build_prompt_explain_more(self, term, subject = None, content = None):
        print("entered build prompt explain more function")
        prompt = "You are a helpful teacher who wants to help students learn {subject_opt}. You are explaining the concept of {term} to a student. The student asks you to explain {term} in a lot of detail, providing not just explanations but where possible examples and analogies. You respond: "
        prompt = prompt.replace('{term}', term)
        if subject != None:
            prompt = prompt.replace('{subject_opt}', subject)
        return prompt


    def why_wrong_generator(self, ww_prompt):
        print("entered why wrong function")
        retries = 0
        prompt = self.build_prompt_why_wrong(ww_prompt)
        while retries < 3:
            print("attempt:", retries)
            try:
                sys_instruct = f"You are a helpful teacher who is an expert and providing clear and detailed explanations. There is no need to introduce yourself, but if questioned you should answer that you are a teacher named Ceph who is here to help."
                response = self.call_ai_terms_non_async(sys_instruct, prompt)
                response_ = response['choices'][0]['message']['content'].strip()
                print(response_[:30])
                return response_
            
            except Exception as e:
                retries += 1
                print(f"Error: {e}. Retrying ({retries}/3)")
                
    def build_prompt_why_wrong(self, ww_prompt):
        subject = ww_prompt['subject']
        term = ww_prompt['term']
        content = ww_prompt['content']
        boc_2 = ww_prompt['boc_2']
        boc_3 = ww_prompt['boc_3']
        boc_4 = ww_prompt['boc_4']
        category = ww_prompt['category']
        if category == "Mcq":
            prompt = "You are a helpful teacher who wants to help students learn {subject_opt}.   The student has just answered this multiple choice question incorrectly: {term}. The student asks you why this answer is correct: {content}, whereas these are wrong {boc_2} and {boc_3} and {boc_4}. You respond: "
            prompt = prompt.replace('{term}', term)
            prompt = prompt.replace('{content}', content)
            prompt = prompt.replace('{boc_2}', boc_2)
            prompt = prompt.replace('{boc_3}', boc_3)
            prompt = prompt.replace('{boc_4}', boc_4)
            if subject != None:
                prompt = prompt.replace('{subject_opt}', subject)
            else:
                prompt = prompt.replace('{subject_opt}', "")
        else:
            prompt = "You are a helpful teacher who wants to help students learn {subject_opt}. The student is studying flashcards and doesn't understand why {content} is the appropriate answer to this question: {term}. The student asks you why this answer is correct: {content} You respond: "
            prompt = prompt.replace('{term}', term)
            prompt = prompt.replace('{content}', content)
            if subject != None:
                prompt = prompt.replace('{subject_opt}', subject)
            else:
                prompt = prompt.replace('{subject_opt}', "")
                
        return prompt


    def send_question_generator(self, term, content, latest_paragraph, question):
        print("entered send question generator function")
        retries = 0
        prompt = self.question_prompt_builder(self, term, content, latest_paragraph, question)
        while retries < 3:
            try:
                sys_instruct = f"You are a helpful teacher who is an expert and providing clear and detailed explanations. There is no need to introduce yourself, but if questioned you should answer that you are a teacher named Ceph who is here to help."
                response = self.call_ai_terms_non_async(sys_instruct, prompt)
                response_ = response['choices'][0]['message']['content'].strip()
                print(response_[:50])
                return response_
            
            except Exception as e:
                retries += 1
                print(f"Error: {e}. Retrying ({retries}/3)")
                

    def question_prompt_builder(self, term, content, latest_paragraph, question):
        print("entered question prompt builder function")
        prompt = "You have previously interacted with the student and have helped them learn {term} {content} {paragraph}. The student has asked you a question: {question}. You respond:"
        prompt = prompt.replace('{term}', term)
        prompt = prompt.replace('{content}', content)
        if latest_paragraph != "":
            paragraph = "You have previously told the student that {latest_paragraph}."
            paragraph = paragraph.replace('{latest_paragraph}', latest_paragraph)
            prompt = prompt.replace('{paragraph}', paragraph)
        prompt = prompt.replace('{question}', question)
        return prompt
    

    async def create_image(term):
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
            print(f"Error creating image for term '{term}': {e}")
            return None
        
    async def insert_paragraph(text):
        prompt = "Go through the following block of text and insert '&-&-&' where you think a paragraph break should be. \n  block of text: \n" + text + "\n The JSON object: \n"
        response = await asyncify(openai.ChatCompletion.create)(
                model="gpt-3.5-turbo",
                messages=[
                        {"role": "system", "content": "You are an expert at the written word"},
                        {"role": "user", "content": prompt},
                    ],
                )
        x = response['choices'][0]['message']['content']
        return x