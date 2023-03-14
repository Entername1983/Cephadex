import string
import tiktoken 
import numpy as np
import json
import urllib.request

encoding = tiktoken.get_encoding('gpt2')

def remove_punctuation(words):
    s = words
    punct = string.punctuation  # contains all punctuation characters

    # Remove punctuation using list comprehension
    s_clean = ''.join([char for char in s if char not in punct])
    print(s_clean)  # Output: Hello World

    # Remove punctuation using loop
    #s_clean = ''

    return s_clean


def split_text(text, n = 2000):
    print("entered split text")
    tokens = count_tokens(text)
    if tokens > 2000:
        print(tokens)
        n_chunks = tokens//n
        print(n_chunks)
        if n_chunks < 1:
            n_chunks = 1
        chunks = np.array_split(text.split(), n_chunks)
        str_chunks = [' '.join(chunk) for chunk in chunks]
        return str_chunks
    else:
        return text
    
    
## TOKEN HANDLERS
def count_tokens(text):
    encoding.encode(text)
    return len(text)

def token_encoding(text):
    return encoding.encode(text)

def token_decoding(text):
    return encoding.decode(text)

## split list of tokens into chunks of n tokens
def split_tokens(tokens, n):
    return [tokens[i:i+n] for i in range(0, len(tokens), n)]





################# ANKI FUNCTIONS #######################



def request(action, **params):
    return {'action': action, 'params': params, 'version': 6}

def invoke(action, **params):
    requestJson = json.dumps(request(action, **params)).encode('utf-8')
    response = json.load(urllib.request.urlopen(urllib.request.Request('http://localhost:8765', requestJson)))
    if len(response) != 2:
        raise Exception('response has an unexpected number of fields')
    if 'error' not in response:
        raise Exception('response is missing required error field')
    if 'result' not in response:
        raise Exception('response is missing required result field')
    if response['error'] is not None:
        raise Exception(response['error'])
    return response['result']

invoke('createDeck', deck='test1')
result = invoke('deckNames')
print('got list of decks: {}'.format(result))