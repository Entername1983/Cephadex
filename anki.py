################# ANKI FUNCTIONS #######################

import json
import urllib.request
import requests

## action deckNamesAndIds --> returns deck IDs use as param for findCards
## action findCards --> returns card IDs use as param for cardsInfo
## action cardsInfo --> returns card info

def request(action, **params):
    return {'action': action, 'params': params, 'version': 6}


def request_params(deckName, term, content, interval=None):
    params = {
        "deckName": deckName,
        "modelName": "Basic",
        "fields": {
            "Front": term,
            "Back": content
        },
        "options": {
            "allowDuplicate": False
        },
        "tags": []
    }
    if interval is not None:
        params["fields"]["Interval"] = str(interval)

    payload = {
        "action": "addNote",
        "params": params,
        "version": 6
    }
    return payload

def invoke(action, **params):
    requestJson = json.dumps(request(action, **params)).encode('utf-8')
    response = request_anki(requestJson)
    if len(response) != 2:
        raise Exception('response has an unexpected number of fields')
    if 'error' not in response:
        raise Exception('response is missing required error field')
    if 'result' not in response:
        raise Exception('response is missing required result field')
    if response['error'] is not None:
        raise Exception(response['error'])
    return response['result']

def anki_create_deck(deck_name):
    invoke('createDeck', deck=deck_name)
    print("deck_created")


def anki_create_card(deck_name, term, content):
    payload = {
        "action": "addNote",
        "params": {
            "note": {
                "deckName": deck_name,
                "modelName": "Basic",
                "fields": {
                    "Front": term,
                    "Back": content
                },
                "options": {
                    "allowDuplicate": False
                },
                "tags": []
            }
        },
        "version": 6
    }
    print(payload)
    requestJson = json.dumps(payload).encode('utf-8')
    
    # Send the API request and handle errors
    response = request_anki(requestJson)
    print("anki json response", response)
    

    
def anki_import_all():
    response = []
    decks = invoke('deckNamesAndIds')
    for key, value in decks.items():
        card_ids = invoke('findCards', query='deck:{}'.format(key))
        cards = []
        for id in card_ids:
            card_deets = invoke('cardsInfo', cards=[id])
            cards.append(card_deets)
        entry = {key: cards}
        response.append(entry)
    response=pretty_json(json.dumps(response))
    return response

def anki_import_deck(deck_name):
    response = []
    name = deck_name
    card_ids = invoke('findCards', query='deck:{}'.format(name))
    cards = []
    for id in card_ids:
        card_deets = invoke('cardsInfo', cards=[id])
        cards.append(card_deets)
    entry = {name: cards}
    response.append(entry)
    response=pretty_json(json.dumps(response))
    return response

def pretty_json(json_str):
    parsed = json.loads(json_str)
    return json.dumps(parsed, indent=4)


def find_notes2(query):
    print(query)
    # Connect to Anki Connect API
    anki_url = "http://localhost:8765"
    headers = {
        "Content-Type": "application/json",
    }
    payload = {
        "action": "findNotes",
        "version": 6,
        "params": {
            "query": query
        }
    }
    response = requests.post(anki_url, data=json.dumps(payload), headers=headers)
    
    # Parse the response
    if response.status_code == 200:
        note_ids = json.loads(response.text)
        print(note_ids)
        if note_ids['result'] != []:
            print("matches found")
            return True
        else:
            print("no matches found")
            return False
    else:
        raise Exception("Anki Connect error: " + response.text)
    
    
def find_notes(query):
    print(query)
    payload = {
    "action": "findNotes",
    "version": 6,
    "params": {
        "query": query
    }
    }
    payload = json.dumps(payload).encode('utf-8')
    response = request_anki(payload)
    print("Find notes", response)
    if response['result'] != []:
        print("matches found")
        return True
    else:
        return False


def request_anki(payload):
    response = json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8765/', payload)))
    return response
