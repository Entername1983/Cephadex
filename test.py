
import openai 
from dotenv import load_dotenv
import os
import asyncio
import asyncify

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