################# ANKI FUNCTIONS #######################

import json
import urllib.request
import requests
from typing import Any, Optional

## action deckNamesAndIds --> returns deck IDs use as param for findCards
## action findCards --> returns card IDs use as param for cardsInfo
## action cardsInfo --> returns card info

def request(action: str, **params: Any) -> dict[str, Any]:
    return {'action': action, 'params': params, 'version': 6}


def request_params(deckName: str, term: str, content: str, interval: Optional[str] = None) -> dict[str, Any]:
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

    return {"action": "addNote", "params": params, "version": 6}

def invoke(action: str, **params: Any) -> Any:
    requestJson = json.dumps(request(action, **params)).encode('utf-8')
    print(requestJson)
    response = request_anki(requestJson)
    print("anki json response from invoke function", response)
    if len(response) != 2:
        raise Exception('response has an unexpected number of fields')
    if 'error' not in response:
        raise Exception('response is missing required error field')
    if 'result' not in response:
        raise Exception('response is missing required result field')
    if response['error'] is not None:
        raise Exception(response['error'])
    return response['result']

def anki_create_deck(deck_name: str) -> None:
    invoke('createDeck', deck=deck_name)
    print("deck_created")


def anki_create_card(deck_name: str, term: str, content: str) -> None:
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

def check_anki_connect() -> bool:
    print("Entered Anki Connect check")
    """Checks if the Anki Connect server is running and if the required API version is available."""
    try:
        request_data = {
            'action': 'version',
            'version': 6
        }
        request_json = json.dumps(request_data).encode('utf-8')
        request = urllib.request.Request('http://localhost:8765', data=request_json, headers={'Content-Type': 'application/json'})
        response = urllib.request.urlopen(request, timeout=1)

        if response.status == 200:
            response_data = response.read()
            result = json.loads(response_data.decode('utf-8'))

            if result['error'] is not None:
                raise ValueError(result['error'])
            else:
                api_version = result['result']
                if api_version < 6:
                    raise ValueError('Anki Connect API version is too low: {}'.format(api_version))
                else:
                    return True
        else:
            raise ValueError('Anki Connect server returned non-200 status: {}'.format(response.status))
    except Exception as e:
        ## TO DO implement better error handling here
        print(f"Error: {e}")
        return False



    
def anki_import_all() -> str:
    response = []
    decks = invoke('deckNamesAndIds')
    for key in decks.items():
        key1 = quote_deck_name_if_needed(key[0])
        card_ids = invoke('findCards', query='deck:{}'.format(key1))
        print("card ids: ", card_ids)
        cards = []
        for id in card_ids:
            card_deets = invoke('cardsInfo', cards=[id])
            print(card_deets)
            cards.append(card_deets)
        entry = {key[0]: cards}
        response.append(entry)
    response=pretty_json(json.dumps(response))
    return response

def anki_import_deck(deck_name: str) -> str:
    response = []
    name = quote_deck_name_if_needed(deck_name)
    card_ids = invoke('findCards', query='deck:{}'.format(name))
    print("card ids: ", card_ids)
    cards = []
    for id in card_ids:
        card_deets = invoke('cardsInfo', cards=[id])
        cards.append(card_deets)
    entry = {deck_name: cards}
    response.append(entry)
    response=pretty_json(json.dumps(response))
    print(response)
    return response



def quote_deck_name_if_needed(deck_name: str) -> str:
    return f'"{deck_name}"' if ' ' in deck_name else deck_name



def pretty_json(json_str: str) -> str:
    parsed = json.loads(json_str)
    return json.dumps(parsed, indent=4)


def find_notes2(query: str) -> bool:
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
    
    
def find_notes(query: str) -> bool:
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


def request_anki(payload: bytes) -> Optional[dict[str, Any]]:
    try:
        return json.load(
            urllib.request.urlopen(
                urllib.request.Request('http://127.0.0.1:8765/', payload)
            )
        )
    except Exception as e:
        ## TO DO implement better error handling here
        print(f"Error: {e}")
        return None


def request_anki_permission() -> bool:
    print("entered request anki permission")
    payload = {
    "action": "requestPermission",
    "version": 6
}
    payload = json.dumps(payload).encode('utf-8')
    response = request_anki(payload)
    print(response)
    if response['result']['permission'] != 'granted':
        print("permission not granted")
        return False
    else :
        print("permission granted")
    return True