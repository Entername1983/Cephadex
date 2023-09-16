import pytest
from models.creators.creator import AiCaller, fix_end_json_string_single, fix_end_json_string_double, load_json_string
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



def test_fix_end_json_string_single():
    assert fix_end_json_string_single("{'key':'value'}") == "{'key':'value'}]"
    assert fix_end_json_string_single('{"key":"value"}') == '{"key":"value"}]'
    assert fix_end_json_string_single('{"key":"value"}') == '{"key":"value"}]'
    assert fix_end_json_string_single('{key:value') == "{key:value'}]"

def test_fix_end_json_string_double():
    assert fix_end_json_string_double("{'key':'value'}") == "{'key':'value'}]"
    assert fix_end_json_string_double('{"key":"value"}') == '{"key":"value"}]'
    assert fix_end_json_string_double('{"key":"value"}') == '{"key":"value"}]'
    assert fix_end_json_string_double('{"key":"value') == '{"key":"value"}]'


@patch('your_module.processing_logger')  # Replace 'your_module' with the actual module name
def test_load_json_string(mock_logger):
    # Test case: JSON string is valid
    valid_json_str = '{"key": "value"}'
    result = load_json_string(valid_json_str)
    assert result == {'key': 'value'}
    
    # Test case: JSON string is invalid and cannot be fixed
    invalid_json_str = '{key value'
    with pytest.raises(json.JSONDecodeError):
        load_json_string(invalid_json_str)
    mock_logger.error.assert_called()  # Check if error is logged
    
    # Test case: JSON string is invalid but can be fixed with single quotes
    single_quote_json_str = "{'key':'value'}"
    result = load_json_string(single_quote_json_str)
    assert result == {'key': 'value'}
    mock_logger.info.assert_any_call('failed to decode json, trying with single quote')
    
    # Test case: JSON string is invalid but can be fixed with double quotes
    double_quote_json_str = '{key:"value"}'
    result = load_json_string(double_quote_json_str)
    assert result == {'key': 'value'}
    mock_logger.info.assert_any_call('failed to decode json, trying with double quote')