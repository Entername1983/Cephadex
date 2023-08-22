from datetime import datetime
from run.extensions import db
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models.models_ import Deck

class Card(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    term = db.Column(db.String(1000), nullable=False) 
    # content == Back of card 1
    content = db.Column(db.String(5000), nullable=False)
    ## used for MCQ wrong answers
    boc_2 = db.Column(db.String(1000), nullable=True) 
    boc_3 = db.Column(db.String(1000), nullable=True) 
    boc_4 = db.Column(db.String(1000), nullable=True)
    formula = db.Column(db.String(255), nullable=True)
    img = db.Column(db.String(255), nullable=True) 
    sound = db.Column(db.String(255), nullable=True) 
    boc_id = db.Column(db.Float(10), nullable=True)
    box_id = db.Column(db.Float(10), nullable=True, default=0)
    srs_interval = db.Column(db.Integer, default=1)
    time_updated = db.Column(db.DateTime, default=datetime.utcnow)
    times_asked = db.Column(db.Integer, default=0)
    times_correct = db.Column(db.Integer, default=0)
    times_correct_row = db.Column(db.Integer, default=0)
    create_method = db.Column(db.String(255), nullable=True)
    time_created = db.Column(db.DateTime, default=datetime.utcnow) 
    category = db.Column(db.String(255), nullable=True)
    edited = db.Column(db.Integer, default=0)
    diff_lvl = db.Column(db.Float(10), default=1)
    subject = db.Column(db.String(255), nullable=True)
    topic = db.Column(db.String(255), nullable=True)
    prompt_option = db.Column(db.String(255), nullable=True)
    prompt_option2 = db.Column(db.String(255), nullable=True)
    trans_option = db.Column(db.String(255), nullable=True)
    len_option = db.Column(db.String(255), nullable=True)
    qmin_option = db.Column(db.String(255), nullable=True)
    qmax_option = db.Column(db.String(255), nullable=True)
    
    def to_json(self):
        return {
            "id": self.id,
            "term": self.term,
            "content": self.content,               
        }
        
    def update_srs_interval(self, value: float):
        self.srs_interval = self.srs_interval * value
        db.session.commit()
        
    def edit_card(self, term: str, content: str):
        self.term = term
        self.content = content
        db.session.commit()
    
    def delete_card(self):
        db.session.delete(self)
        db.session.commit()
        
    def regen_def(self, prompt = None):
        pass
    
    def copy_card(self, deck: 'Deck'):
        new_card = Card(term=self.term, content=self.content)
        deck.cards.append(new_card)
        db.session.add(new_card)            
        db.session.commit()
        
    def increment(self):
        self.times_correct = self.times_correct + 1
        self.times_asked = self.times_asked + 1
        self.times_correct_row = self.times_correct_row + 1
        if self.times_correct_row > 2:
            self.box_id = self.box_id + 1
            self.box_id = min(self.box_id, 3)
        if self.box_id == 0:
            self.srs_interval = self.srs_interval * 2    
        elif self.box_id == 1:
            self.srs_interval = self.srs_interval * 4
        elif self.box_id == 2:
            self.srs_interval = self.srs_interval * 6
        elif self.box_id == 3:
            self.srs_interval = self.srs_interval * 10
        self.srs_interval = min(self.srs_interval, 525600)
        ## ensure that at minimum if someone answer 3 questions in a row correctly,
        #  they will be asked again in 24 hours
        if self.times_correct_row > 3:
            self.srs_interval += 1440
        db.session.commit()
        
    def decrement(self):
        self.times_asked = self.times_asked + 1
        self.times_correct_row = 0
        if self.box_id == 1:
            self.srs_interval = self.srs_interval * 0.5
        elif self.box_id == 2:
            self.srs_interval - self.srs_interval * 0.8
        elif self.box_id == 3:
            self.srs_interval - self.srs_interval * 0.9
            
        if self.box_id != 1 and self.srs_interval < 5:
            self.srs_interval = 5
            
        if self.box_id > 0:
            self.box_id = self.box_id-1; 
             
        db.session.commit()
    
    def reset_srs_interval(self):
        self.srs_interval = 10
        db.session.commit()
        
    def update_time(self):
        self.time_updated = datetime.utcnow()
        db.session.commit()