from .card import Card
from .deck import Deck
from sqlalchemy.orm import joinedload
from sqlalchemy import select
from typing import TYPE_CHECKING
import logging
from models.helpers.log_decorators import job_log_decorator

processing_logger = logging.getLogger("job_processing")

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

class CardFactory:
    def __init__(self, session: 'AsyncSession', deck: Deck):
        self.session: 'AsyncSession' = session
        self.deck: Deck = deck
        self.card_counter: int = 0

    def create_cards(self, content: str, type: str) -> None:
        if type == "Mcq":
            self.create_mcq(content)
        elif type == "Formulas":
            self.create_formulas(content)
        elif type == "Discuss":
            self.create_discuss(content)
        else:
            self.create_default(content, type)

    @job_log_decorator  
    async def async_create_cards(self, content: str, type: str) -> None:
        if type == "Mcq":
            await self.async_create_mcq(content)
        elif type == "Formulas":
            await self.async_create_formulas(content)
        elif type == "Discuss":
            await self.async_create_discuss(content)
        else:
            await self.async_create_default(content, type)
        
    def create_default(self, content: str, type: str) -> None:
        for item in content:
            try:
                key = item['A']
                if not self.check_card_exist(key):
                    value = item['B']
                    card = Card(term=key, content=value, category=type)
                    self.deck.cards.append(card)
                    self.session.add(card)
                    self.session.commit()
                    self.card_counter += 1
            except KeyError:
                processing_logger.error(f"KeyError in create_default, item {item}")

    def create_mcq(self, content: str) -> None:
        for item in content:
            try:
                key = item['A']
                if not self.check_card_exist(key):
                    value = item['B']
                    card = Card(term=key, content=value.get("content"), category="Mcq",
                                boc_2=value.get("boc_2"), boc_3=value.get("boc_3"),
                                boc_4=value.get("boc_4"))
                    self.deck.cards.append(card)
                    self.session.add(card)
                    self.session.commit()
                    self.card_counter += 1
            except KeyError:
                processing_logger.error(f"KeyError in create_mcq, item {item}")

    def create_formulas(self, content: str) -> None:
        for item in content:
            try:
                key = item['A']
                if not self.check_card_exist(key):
                    value = item['B']
                    card = Card(term=key, content=value.get("content"), category="Formulas", formula=value.get("formula"))
                    self.deck.cards.append(card)
                    self.session.add(card)
                    self.session.commit()
                    self.card_counter += 1
            except KeyError:
                processing_logger.error(f"KeyError in create_formulas, item {item}")

    def create_discuss(self, content: str) -> None:
        for item in content:
            try:
                key = item['A']
                if not self.check_card_exist(key):
                    value = item['B']

                    card = Card(term=key, content=value.get("content"), category="Discuss")
                    self.deck.cards.append(card)
                    self.session.add(card)
                    self.session.commit()
                    self.card_counter += 1
            except KeyError:
                processing_logger.error(f"KeyError in create_discuss, item {item}")


    def check_card_exist(self, term: str) -> bool:
        deck = self.session.execute(
            select(Deck).options(joinedload(Deck.cards)).where(Deck.id == self.deck.id)
        )
        deck = deck.unique().scalar_one()
        term = term.lower()
        singular_term = to_singular(term)
        for card in deck.cards:
            card_term = card.term.lower()
            singular_card_term = to_singular(card_term)
            if term == card_term or singular_term == singular_card_term:
                return True
        return False

    async def async_create_default(self, content: str, type: str) -> None:
        for item in content:
            try:
                key = item['A']
                if not await self.async_check_card_exist(key):  
                    value = item['B']
                    card = Card(term=key, content=value, category=type)
                    self.deck.cards.append(card)
                    self.session.add(card)
                    await self.session.commit()
                    self.card_counter += 1
            except KeyError:
                processing_logger.error(f"KeyError in async_create_default, item {item}")


    async def async_create_mcq(self, content: str) -> None:
        for item in content:
            try:
                question = item['A']
                if not await self.async_check_card_exist(question):
                    content = item['B']
                    boc_2 = item['C']
                    boc_3 = item['D']
                    boc_4 = item['E']
                    card = Card(term=question, content=content, category="Mcq",
                                boc_2=boc_2, boc_3=boc_3,
                                boc_4=boc_4)
                    self.deck.cards.append(card)
                    self.session.add(card)
                    await self.session.commit()
                    self.card_counter += 1
            except KeyError:
                processing_logger.error(f"KeyError in async_create_mcq, item {item}")

    async def async_create_formulas(self, content: str) -> None:
        for item in content:
            try:
                key = item['A']
                if not await self.async_check_card_exist(key):
                    value = item['B']
                    card = Card(term=key, content=value.get("content"), category="Formulas", formula=value.get("formula"))
                    self.deck.cards.append(card)
                    self.session.add(card)
                    await self.session.commit()
                    self.card_counter += 1
            except KeyError:
                processing_logger.error(f"KeyError in async_create_formulas, item {item}")

    async def async_create_discuss(self, content: str) -> None:
        for item in content:
            try:
                key = item['A']
                if not await self.async_check_card_exist(key):
                    value = item['B']
                    card = Card(term=key, content=value.get("content"), category="Discuss")
                    self.deck.cards.append(card)
                    self.session.add(card)
                await self.session.commit()
                self.card_counter += 1
            except KeyError:
                processing_logger.error(f"KeyError in async_create_discuss, item {item}")

    async def async_check_card_exist(self, term: str) -> None:
        # Explicitly query for the deck with the related cards
        deck = await self.session.execute(select(Deck).options(joinedload(Deck.cards)).where(Deck.id == self.deck.id))
        deck = deck.unique().scalar_one()
        term = term.lower()
        singular_term = to_singular(term)
        for card in deck.cards:
            card_term = card.term.lower()
            singular_card_term = to_singular(card_term)
            if term == card_term or singular_term == singular_card_term:
                return True
        return False

def to_singular(word: str) -> str:
    if word.endswith('ies'):
        return f'{word[:-3]}y'
    elif word.endswith('es'):
        return word[:-2]
    elif word.endswith('s'):
        return word[:-1]
    return word