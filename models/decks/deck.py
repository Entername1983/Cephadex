from datetime import datetime
from models.association_tables import cards, source_files, deck_relationships
from flask import jsonify
from run.extensions import db
import json
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import select, func

class Deck(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=True) 
    ## make relational table instead of using user_id?
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'),
                         nullable=True) 
    cards = db.relationship('Card', secondary=cards, backref="decks_backref",
                             lazy="select")
    deck_files = db.relationship('DeckFiles', secondary=source_files,
                                  backref="decks", lazy="select")
    time_created = db.Column(db.DateTime, default=datetime.utcnow)   
    time_updated = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.Column(db.Integer) 
    public = db.Column(db.Integer, default=0) 
    edited = db.Column(db.Integer, default=0)
    create_method = db.Column(db.String(255), nullable=True)
    category = db.Column(db.String(255), nullable=True)
    times_accessed = db.Column(db.Integer, default=0)
    access_date = db.Column(db.DateTime, default=datetime.utcnow)
    subject = db.Column(db.String(255), nullable=True)
    topic = db.Column(db.String(255), nullable=True)
    shared = db.Column(db.Boolean, default=False)
    accepted = db.Column(db.Boolean, default=False)
    sharer = db.Column(db.Integer) 
    source = db.Column(db.String(1000), nullable=True)
    share_date = db.Column(db.DateTime, default=datetime.utcnow)
    share_id = db.Column(db.String(36), nullable=True, unique=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id")) ## obsolete?
    group = db.relationship("Group", back_populates="decks")
    children = db.relationship("Deck",
                    secondary=deck_relationships,
                    primaryjoin=(deck_relationships.c.parent_deck == id),
                    secondaryjoin=(deck_relationships.c.child_deck == id),
                    backref=db.backref("parents", lazy="dynamic"),
                    lazy="dynamic")

    @property
    def num_cards(self):
        return len(self.cards)
    
    def correct_incorrect(self) -> list[int]:
        correct = 0
        incorrect = 0
        for card in self.cards:
            if card.times_correct is not None and card.times_asked is not None:
                try:
                    correct = correct + int(card.times_correct)
                    incorrect = incorrect + int(card.times_asked) - int(card.times_correct)
                except ValueError:
                    # handle invalid values here
                    pass
        return correct, incorrect
    
    def total_answered(self) -> int:
        total = 0
        for card in self.cards:
            if card.times_asked is not None:
                try:
                    total = total + int(card.times_asked)
                except ValueError:
                    # handle invalid values here
                    pass
        return total

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }



    def force_study(self) -> json:
        due_cards = []
        current_time = datetime.utcnow()
        for card in self.cards:
            time_diff = (current_time - card.time_updated).total_seconds() / 60
            due_cards.append({
                'term': card.term,
                'content': card.content,
                'boc_2': card.boc_2,
                'boc_3': card.boc_3,
                'boc_4': card.boc_4,
                'category': card.category,
                'id': card.id,
                'img': card.img,
                'sound': card.sound,
                'time_remain': card.srs_interval - time_diff,
            })
        due_cards.sort(key=lambda x: x['time_remain'])
        return jsonify(due_cards)
     
        
    def get_due_cards(self, n: int =20) -> json:
        due_cards = []
        current_time = datetime.utcnow()
        new_card_counter = 0
        for card in self.cards:
            time_diff = (current_time - card.time_updated).total_seconds() / 60
            if (time_diff + 1440)>= card.srs_interval:
                if card.box_id > 0:
                    due_cards.append({
                        'term': card.term,
                        'content': card.content,
                        'boc_2': card.boc_2,
                        'boc_3': card.boc_3,
                        'boc_4': card.boc_4,
                        'formula': card.formula,
                        'category': card.category,
                        'id': card.id,
                        'img': card.img,
                        'sound': card.sound,
                    })
                if card.box_id == 0 and new_card_counter < n:
                    new_card_counter += 1
                    due_cards.append({
                        'term': card.term,
                        'content': card.content,
                        'boc_2': card.boc_2,
                        'boc_3': card.boc_3,
                        'boc_4': card.boc_4,
                        'formula': card.formula,
                        'category': card.category,
                        'id': card.id,
                        'img': card.img,
                        'sound': card.sound,
                    })

        due_cards.sort(key=lambda x: x['id'])
        if not due_cards:
            return jsonify({'info': 'No due cards found'}), 204
        return jsonify(due_cards)
    
    def cards_due(self) -> int:
        """ both functions do the same thing? """
        due_cards = 0
        current_time = datetime.utcnow()
        for card in self.cards:
            time_diff = (current_time - card.time_updated).total_seconds() / 60
            if (time_diff + 1440) >= card.srs_interval:
                due_cards = due_cards + 1
        return due_cards
    
    def qty_cards_due(self) -> int:
        current_time = datetime.utcnow()
        qty = 0
        for card in self.cards:
            if card.time_updated is None:
                card.time_updated = current_time
            else:
                time_diff = (current_time - card.time_updated).total_seconds() / 60
                if time_diff >= card.srs_interval:
                    qty = qty + 1
        return qty

    def check_cat(self) -> str:
        Mcq = 0
        Cloze = 0
        Definitions = 0
        Comprehension = 0
        Vocab_builder = 0
        Theories = 0
        Rhyme = 0
        Translate = 0
        People = 0

        ## check if all cards have same category
        for card in self.cards:
            if card.category == "Mcq":
                Mcq += 1
            elif card.category == "Cloze":
                Cloze += 1
            elif card.category == "Definitions":
                Definitions += 1
            elif card.category == "Comprehension":
                Comprehension += 1
            elif card.category == "Vocab_builder":
                Vocab_builder += 1
            elif card.category == "Theories":
                Theories += 1
            elif card.category == "Rhyme":
                Rhyme += 1
            elif card.category == "Translate":
                Translate += 1
            elif card.category == "People":
                People += 1
        ## loop through each category and check if it is the highest count
        categories = {'Mcq': Mcq, 'Cloze': Cloze, 'Definitions': Definitions,
                  'Comprehension': Comprehension, 'Vocab_builder': Vocab_builder,
                  'Theories': Theories, 'Rhyme': Rhyme, 'Translate': Translate,
                  'People': People}
        max_category, max_count = max(categories.items(), key=lambda x: x[1])
        if max_count > len(self.cards) / 2:
            self.category = max_category
            db.session.commit()
            return max_category
        else:
            self.category = "Mixed"
            db.session.commit()

            return "Mixed"
        
    def to_json(self) -> json:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "cards": [card.to_json() for card in self.cards]
        }
        
    def quantity_cards(self) -> int:
        return len(self.cards)
    
    def add_card(self, card):
        self.cards.append(card)            
        db.session.commit()
        
    def remove_card(self, card):
        self.cards.remove(card)            
        db.session.commit()
        
    def rename_deck(self, new_name):
        Deck.name = new_name
        db.session.commit()            
        
    def delete_deck(self):
        db.session.delete(self)            
        db.session.commit()
    
    def rename(self, new_name):
        self.name = new_name
        db.session.commit()            
        
        
    def copy_deck(self, new_deck_name):
        new_deck = Deck(name=self.name, description=self.description,
                         user_id=self.user_id)  
        new_deck.name = new_deck_name                      
        db.session.add(new_deck)            
        db.session.commit()
        
    
    def assign_deck(self, user):
        pass
    
    def export_deck_csv(self):
        pass
    
    def import_deck_csv(self):
        pass