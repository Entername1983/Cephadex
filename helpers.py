import string
import tiktoken 
import numpy as np
from flask import redirect, render_template, request, session


encoding = tiktoken.get_encoding("cl100k_base")

def remove_punctuation(words):
    s = words
    punct = string.punctuation  # contains all punctuation characters

    # Remove punctuation using list comprehension
    s_clean = ''.join([char for char in s if char not in punct])
    print(s_clean)  # Output: Hello World

    # Remove punctuation using loop
    #s_clean = ''

    return s_clean


def split_text(text, n = 1700):
    print("entered split text")
    tokens = count_tokens(text)
    print("tokens:",tokens)

    if tokens > n:
        print("tokens:",tokens)
        n_chunks = tokens//n
        print("chunks", n_chunks)
        if n_chunks < 1:
            n_chunks = 1
        chunks = np.array_split(text.split(), n_chunks)
        str_chunks = [' '.join(chunk) for chunk in chunks]
        return str_chunks
    else:
        return text
    
    
## TOKEN HANDLERS
def count_tokens(text):
    tokens = encoding.encode(text)
    return len(tokens)

def token_encoding(text):
    return encoding.encode(text)

def token_decoding(text):
    return encoding.decode(text)

## split list of tokens into chunks of n tokens
def split_tokens(tokens, n):
    return [tokens[i:i+n] for i in range(0, len(tokens), n)]


## replace commas with semi colons

def apology(message, code=400):
    """Render message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), ("_", "__"), ("?", "~q"),
                            ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=code, bottom=escape(message)), code