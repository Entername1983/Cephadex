import string
import tiktoken 
import numpy as np

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


## replace commas with semi colons

def replace_commas(string):
    return string.replace(',', ';')


