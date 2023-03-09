import string

def remove_punctuation(words):
    s = words
    punct = string.punctuation  # contains all punctuation characters

    # Remove punctuation using list comprehension
    s_clean = ''.join([char for char in s if char not in punct])
    print(s_clean)  # Output: Hello World

    # Remove punctuation using loop
    #s_clean = ''

    return s_clean


