from .card import Card
from .deck import Deck
from sqlalchemy.orm import joinedload
from sqlalchemy import select

class CardFactory:
    def __init__(self, session, deck):
        self.session = session
        self.deck = deck
        self.card_counter = 0

    def create_cards(self, content, type):
        print(content)
        print("entered create cards...")
        if type == "Mcq":
            return self.create_mcq(content)
        elif type == "Formulas":
            return self.create_formulas(content)
        elif type == "Discuss":
            return self.create_discuss(content)
        else:
            return self.create_default(content, type)
        
    async def async_create_cards(self, content, type):
        print(content)
        print("entered async create cards...")
        if type == "Mcq":
            return await self.async_create_mcq(content)
        elif type == "Formulas":
            return await self.async_create_formulas(content)
        elif type == "Discuss":
            return await self.async_create_discuss(content)
        else:
            return await self.async_create_default(content, type)
        
    def create_default(self, content, type):
        print("entered create default...")
        print(self.session)
        for item in content:
            key = item['A']
            value = item['B']
            if not self.check_card_exist(key):
                card = Card(term=key, content=value, category=type)
                self.deck.cards.append(card)
                self.session.add(card)
                self.session.commit()
                self.card_counter += 1

    def create_mcq(self, content):
        print("entered create mcq...")
        print("content: ", content)
        for item in content:
            key = item['A']
            value = item['B']
            if not self.check_card_exist(key):
                card = Card(term=key, content=value.get("content"), category="Mcq",
                            boc_2=value.get("boc_2"), boc_3=value.get("boc_3"),
                            boc_4=value.get("boc_4"))
                self.deck.cards.append(card)
                self.session.add(card)
                self.session.commit()
                self.card_counter += 1

    def create_formulas(self, content):
        print("entered create formulas...")
        for item in content:
            key = item['A']
            value = item['B']
            if not self.check_card_exist(key):
                card = Card(term=key, content=value.get("content"), category="Formulas", formula=value.get("formula"))
                self.deck.cards.append(card)
                self.session.add(card)
                self.session.commit()
                self.card_counter += 1

    def create_discuss(self, content):
        print("entered create discuss...")
        for item in content:
            key = item['A']
            value = item['B']
            if not self.check_card_exist(key):
                card = Card(term=key, content=value.get("content"), category="Discuss")
                self.deck.cards.append(card)
                self.session.add(card)
                self.session.commit()
                self.card_counter += 1

    def check_card_exist(self, term):
        print("entered check card exist...")
        # Explicitly query for the deck with the related cards
        deck = self.session.execute(select(Deck).options(joinedload(Deck.cards)).where(Deck.id == self.deck.id))
        deck = deck.unique().scalar_one()

        for card in deck.cards:
            if card.term.lower() == term.lower():
                print(f"card {term} already exists")
                return True
        return False

    async def async_create_default(self, content, type):
        print("entered async create default...")
        for item in content:
            key = item['A']
            value = item['B']
            if not await self.async_check_card_exist(key):  # Assuming this method is also async
                card = Card(term=key, content=value, category=type)
                self.deck.cards.append(card)
                self.session.add(card)
                await self.session.commit()
                self.card_counter += 1

    async def async_create_mcq(self, content):
        print("entered async create mcq...")
        print(f"content, {content}")
        for item in content:
            question = item['A']
            content = item['B']
            boc_2 = item['C']
            boc_3 = item['D']
            boc_4 = item['E']
            if not await self.async_check_card_exist(question):
                card = Card(term=question, content=content, category="Mcq",
                            boc_2=boc_2, boc_3=boc_3,
                            boc_4=boc_4)
                self.deck.cards.append(card)
                self.session.add(card)
                await self.session.commit()
                self.card_counter += 1

    async def async_create_formulas(self, content):
        print("entered async create formulas...")
        for item in content:
            key = item['A']
            value = item['B']
            if not await self.async_check_card_exist(key):
                card = Card(term=key, content=value.get("content"), category="Formulas", formula=value.get("formula"))
                self.deck.cards.append(card)
                self.session.add(card)
                await self.session.commit()
                self.card_counter += 1

    async def async_create_discuss(self, content):
        print("entered async create discuss...")
        for item in content:
            key = item['A']
            value = item['B']
            if not await self.async_check_card_exist(key):
                card = Card(term=key, content=value.get("content"), category="Discuss")
                self.deck.cards.append(card)
                self.session.add(card)
            await self.session.commit()
            self.card_counter += 1

    async def async_check_card_exist(self, term):
        print("entered async check card exist...")
        # Explicitly query for the deck with the related cards
        deck = await self.session.execute(select(Deck).options(joinedload(Deck.cards)).where(Deck.id == self.deck.id))
        deck = deck.unique().scalar_one()

        for card in deck.cards:
            if card.term.lower() == term.lower():
                print(f"card {term} already exists")
                return True
        return False