import pytest
from unittest.mock import patch, Mock
from models.creators.creator import AiCaller  # Replace with the actual import path if this is incorrect
import os


from dotenv import load_dotenv
# Calculate the path to the .env file
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')

# Load the .env file
load_dotenv(dotenv_path=env_path)

key = os.getenv('OPENAI_API_KEY')
@pytest.mark.asyncio
async def test_call_ai_terms():
    ai_caller = AiCaller(api_key = key)
    sys_instruction = "You are conversational bot"
    user_prompt = "Hello, how are you?"

    try:
        response = await ai_caller.call_ai_terms(sys_instruction, user_prompt)
        assert response is not None
    except Exception as e:
        pytest.fail(f"call_ai_terms() raised an exception: {e}, response is {type(response)}, {response}")

@pytest.mark.asyncio
async def test_transcribe_whisper():
    ai_caller = AiCaller(api_key = key)
    audio_file_path = "tests\\test_files\\wav_sample_eng.wav"

    try:
        transcript = await ai_caller.transcribe_whisper(audio_file_path)
        assert transcript is not None
        assert isinstance(transcript, str)

    except Exception as e:
        pytest.fail(f"transcribe_whisper() raised an exception: {e}, transcript is {type(transcript)}, {transcript}")