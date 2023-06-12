from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask import Flask, flash, redirect, render_template, request, session, url_for, Response, send_file, jsonify
from flask_migrate import Migrate
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()

migrate = Migrate()


# relational database cards & decks
cards = db.Table("cards", 
                 db.Column("card_id", db.Integer, db.ForeignKey("card.id")), 
                 db.Column("deck_id", db.Integer, db.ForeignKey("deck.id")),
                 )
source_files = db.Table("source_files",
                        db.Column("deck_file_id", db.Integer, db.ForeignKey("deck_files.id")), 
                        db.Column("deck_id", db.Integer, db.ForeignKey("deck.id")),  # 
                        )

cards_shared = db.Table("cards_shared", 
                 db.Column("card_id", db.Integer, db.ForeignKey("card.id")), 
                 db.Column("shared_decks_id", db.Integer, db.ForeignKey("shared_decks.id")),
                 )                             
questions = db.Table("questions",
                        db.Column("test_id", db.Integer, db.ForeignKey("test.id")),
                        db.Column("question_id", db.Integer, db.ForeignKey("question.id")),
                        db.Column("position", db.Integer),
                        db.Column("text", db.String(255)),
                        db.Column("image", db.String(255))
                     )
distribution = db.Table("distribution",
                        db.Column("test_id", db.Integer, db.ForeignKey("test.id")),	
                        db.Column("taker_id", db.Integer, db.ForeignKey("user.id"))	
                        )	

deck_relationships = db.Table("deck_relationships", 
                               db.Column("parent_deck", db.Integer, db.ForeignKey("deck.id")),
                               db.Column("child_deck", db.Integer, db.ForeignKey("deck.id"))  # 
                               )

user_group_association = db.Table("user_group_association",
                                  db.Column("user_id", db.Integer, db.ForeignKey("user.id")),
                                  db.Column("group_id", db.Integer, db.ForeignKey("group.id")),
                                  db.Column("role", db.String(255)),
                                  db.Column("permissions", db.String(255)),)



## external auth + external type + external
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(20), nullable=True, unique=True)
    password = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(255), nullable=False)
    email_confirmed_at = db.Column(db.DateTime())
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    decks = db.relationship("Deck", backref=db.backref("user", lazy="joined"), lazy="select")
    ## external auth + external type
    external_id = db.Column(db.String(255), nullable=True) 
    external_type = db.Column(db.String(255), nullable=True)
    time_created = db.Column(db.DateTime, default=datetime.utcnow)
    time_accessed= db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    test= db.relationship('Test', secondary=distribution, backref ="taker")
    account_type = db.Column(db.String(255), nullable=True, default="free")
    account_status = db.Column(db.String(255), nullable=True, default="active")
    account_expiration = db.Column(db.DateTime, nullable=True)
    account_expiration_reason = db.Column(db.String(255), nullable=True)
    gender = db.Column(db.String(255), nullable=True)
    pic = db.Column(db.String(255), nullable=True)
    contacted_email = db.Column(db.Boolean, default=False)
    dob = db.Column(db.DateTime, nullable=True)
    timezone = db.Column(db.String(64))
    subscription_plan = db.Column(db.Integer, db.ForeignKey('subscription_plans.id'), nullable=False, default=1)
    subscription_start_date = db.Column(db.DateTime)
    latest_roll_over = db.Column(db.DateTime)
    groups = db.relationship("Group", secondary=user_group_association, backref="users")
    role = db.Column(db.String(255), nullable = True)
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    guest = db.Column(db.Boolean, default=False)

    def member_since(self):
        return self.time_created.strftime('%b %Y')
    
    def quantity_decks(self):
        return len(self.decks)
    
    def quantity_cards(self):
        return sum([len(deck.cards) for deck in self.decks])
    
    def quantity_tests(self):
        total_tests = Test.query.filter_by(creator=self.id).count()
        return total_tests

    def quantity_files(self):
        ## count files for user by looking at all decks and associated files
        total_files = Deck.query.join(source_files).filter(source_files.c.deck_id == Deck.id).filter(Deck.user_id == self.id).count()
        return total_files
    
    def quantity_groups(self):
        total_groups = Group.query.filter_by(creator_id=self.id).count()
        return total_groups
    
    def quantity_decks_public(self):
        total_decks = Deck.query.filter_by(user_id=self.id, public=True).count()
        return total_decks

    def quantity_cards_mastered(self):
        counter = 0
        for deck in self.decks:
            for card in deck.cards:
                if card.box_id == 3:
                    counter += 1
        return counter

    def quantity_cards_learning(self):
        counter = 0
        for deck in self.decks:
            for card in deck.cards:
                if card.box_id != 3 and card.times_asked != 0:
                    counter += 1
        return counter
    
    def quantity_cards_new(self):
        counter = 0
        for deck in self.decks:
            for card in deck.cards:
                if card.times_asked == 0:
                    counter += 1
        return counter
        
    def remaining_credit(self):
        usage_record = (
            UsageRecord.query
            .filter_by(user_id=self.id)
            .order_by(UsageRecord.date.desc()).first()
        )
        if usage_record:
            remaining_credit = round(usage_record.remaining_count/341)
        else:
            subscription_plan = (
            SubscriptionPlan.query
            .filter_by(id=self.subscription_plan).first() 
                ) 
            new_record = UsageRecord(user_id=self.id, operation_type='initializing',
                        time_period='month',
                        limit_count=subscription_plan.limit_count,
                        operation_count=0,
                        remaining_count = subscription_plan.limit_count,)
            
            db.session.add(new_record)
            db.session.commit()
            remaining_credit = round(new_record.remaining_count/682)    
        return remaining_credit
    
    def roll_over_date(self):
        if self.latest_roll_over:
            next_roll_over = self.latest_roll_over + timedelta(days=31)
        else:
            next_roll_over = self.subscription_start_date + timedelta(days=31)
        return next_roll_over.strftime('%b %d, %Y')

class DeletedAccounts(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer)
    email = db.Column(db.String(255))
    date_created = db.Column(db.DateTime)
    date_deleted = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(255))
    reason_details = db.Column(db.Text)



class StripeEvents(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    stripe_event_id = db.Column(db.String(255), nullable=True)
    event_type = db.Column(db.String(255), nullable=True)
    event_data = db.Column(db.Text, nullable=True)
    event_created = db.Column(db.DateTime, default=datetime.utcnow)
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    processed = db.Column(db.Boolean, default=False)
    processed_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.String(255), nullable=True)
    


class Group(db.Model):
    __tablename__ = "group"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    description = db.Column(db.String(255))
    group_type = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    creator = db.relationship("User", foreign_keys=[creator_id])
    avatar = db.Column(db.String(255))
    is_private = db.Column(db.Boolean, default=False)
    decks = db.relationship("Deck", back_populates="group")


class GroupInvite(db.Model):
    __tablename__ = "group_invite"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"))
    group = db.relationship("Group", foreign_keys=[group_id])
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    invited_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    invited_by_email = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)


class SubscriptionPlan(db.Model):
    __tablename__ = 'subscription_plans'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    limit_count = db.Column(db.Integer, nullable=False)
    limit_time_period = db.Column(db.String(50), nullable=False, default='month')
    price = db.Column(db.Float, nullable=False)
    duration = db.Column(db.Integer, default = 31)

    users = db.relationship('User', backref='subscription_plan_id')

    def __repr__(self):
        return f'<SubscriptionPlan {self.id}>'

class UsageRecord(db.Model):
    __tablename__ = 'usage_records'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    operation_type = db.Column(db.String(50), nullable=False)
    operation_details = db.Column(db.String(1000))
    operation_count = db.Column(db.Integer, nullable=False)
    remaining_count = db.Column(db.Integer, nullable=False)
    time_period = db.Column(db.String(50), nullable=False)
    limit_count = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=False, default='active')
    source_ip = db.Column(db.String(50))
    payment_status = db.Column(db.String(50), default='unpaid')

    def __repr__(self):
        return f'<UsageRecord {self.id}>'

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
    
    # unused
    #data_1 = db.Column(db.float(100), nullable = True)
    #data_2 = db.Column(db.float(100), nullable = True)
    #data_3 = db.Column(db.float(100), nullable = True)
    #data_time = db.Column(db.srs_interval, nullable = True)
    ## consider including a field for explanation of answer
    ## how can we keep track of time studied deck?  
    
    def to_json(self):
        return {
            "id": self.id,
            "term": self.term,
            "content": self.content,               
        }
        
    def update_srs_interval(self, value):
        self.srs_interval = self.srs_interval * value
        db.session.commit()
        
        
    def edit_card(self, term, content):
        self.term = term
        self.content = content
        db.session.commit()
    
    def delete_card(self):
        db.session.delete(self)
        db.session.commit()
        
    def regen_def(self, prompt = None):
        term = self.term
        content = regenerate_definition(term)
        print("regen_def method")
        print(self.content)
        self.content = content
        print(self.content)
        db.session.commit()
    
    def copy_card(self, deck):
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
            if self.box_id > 3:
                self.box_id = 3
        if self.box_id == 0:
            self.srs_interval = self.srs_interval * 2    
        if self.box_id == 1:
            self.srs_interval = self.srs_interval * 4
        if self.box_id == 2:
            self.srs_interval = self.srs_interval * 6
        if self.box_id == 3:
            self.srs_interval = self.srs_interval * 10
        if self.srs_interval > 525600:
            self.srs_interval = 525600
        ## ensure that at minimum if someone answer 3 questions in a row correctly, they will be asked again in 24 hours
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
    
class SharedDecks(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False) 
    sender = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    receiver = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    time_created = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.Column(db.Integer) 
    public = db.Column(db.Integer, default=0) 
    edited = db.Column(db.Integer, default=0)
    cards = db.relationship('Card', secondary=cards_shared, backref="decks", lazy="select")
    
    def delete(self):
        db.session.delete(self)
        db.session.commit()

class Deck(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False) 
    ## make relational table instead of using user_id?
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True) 
    cards = db.relationship('Card', secondary=cards, backref="decks_backref", lazy="select")
    deck_files = db.relationship('DeckFiles', secondary=source_files, backref="decks", lazy="select")
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
    share_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"))
    group = db.relationship("Group", back_populates="decks")
    children = db.relationship("Deck",
                    secondary=deck_relationships,
                    primaryjoin=(deck_relationships.c.parent_deck == id),
                    secondaryjoin=(deck_relationships.c.child_deck == id),
                    backref=db.backref("parents", lazy="dynamic"),
                    lazy="dynamic")
    
    def correct_incorrect(self):
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
    def total_answered(self):
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



    def force_study(self):
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
     
        
    def get_due_cards(self, n=20):
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
    
    def cards_due(self):
        due_cards = 0
        current_time = datetime.utcnow()
        for card in self.cards:
            time_diff = (current_time - card.time_updated).total_seconds() / 60
            if (time_diff + 1440) >= card.srs_interval:
                due_cards = due_cards + 1
        return due_cards
    
    def qty_cards_due(self):
        current_time = datetime.utcnow()
        qty = 0
        for card in self.cards:
            if card.time_updated == None:
                card.time_updated = current_time
            else:
                time_diff = (current_time - card.time_updated).total_seconds() / 60
                if time_diff >= card.srs_interval:
                    qty = qty + 1
        return qty

    def check_cat(self):
        Mcq = 0
        Cloze = 0
        Definitions = 0
        Comprehension = 0
        Vocab_builder = 0
        Theories = 0
        Rhyme = 0
        Translate = 0
        counter = 0
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
        
    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "cards": [card.to_json() for card in self.cards]
        }
        
    def quantity_cards(self):
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
        new_deck = Deck(name=self.name, description=self.description, user_id=self.user_id)  
        new_deck.name = new_deck_name                      
        db.session.add(new_deck)            
        db.session.commit()
        
    
    def assign_deck(self, user):
        pass
    
    def export_deck_csv(self):
        pass
    
    def import_deck_csv(self):
        pass
    
class DeckAttributes(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deck_id = db.Column(db.Integer, db.ForeignKey('deck.id'))
    subject = db.Column(db.String(100))
    grade = db.Column(db.String(100))
    topic = db.Column(db.String(100))
    sub_topic = db.Column(db.String(100))
    difficulty = db.Column(db.String(50))
    concepts = db.Column(db.Text)
    time_created = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    
class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    email = db.Column(db.String(120), unique=True)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    def __repr__(self):
        return '<Newsletter {}>'.format(self.email)
    
    def subscribe(self):
        db.session.add(self)            	
        db.session.commit()
        
    def unsubscribe(self):
        db.session.delete(self)            	
        db.session.commit()
 
class DeckFiles(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    file_name = db.Column(db.String(100))
    file_path = db.Column(db.String(50))
    file_type = db.Column(db.String(500))	
    file_size = db.Column(db.String(50))
    text_string = db.Column(db.Text)
    create_type = db.Column(db.String(50))
    time_created = db.Column(db.DateTime, default=datetime.utcnow)
    
       
class ResponseData(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    prompt = db.Column(db.Text)	
    response = db.Column(db.Text)
    content = db.Column(db.Text)	
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    success = db.Column(db.Boolean)
          
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50))
    email = db.Column(db.String(120))
    message = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    type_feedback = db.Column(db.String(50))
    def __repr__(self):
        return '<Feedback {}>'.format(self.email)
    
    def send_feedback(self):
        db.session.add(self)            	
        db.session.commit()
        
    def delete_feedback(self):
        db.session.delete(self)            	
        db.session.commit() 
                 
#########################TEST TABLES#######################


class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200))
    points = db.Column(db.Integer)
    num_questions = db.Column(db.Integer)
    category = db.Column(db.String(50))
    subject = db.Column(db.String(50))
    topic = db.Column(db.String(50))
    time_created = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.relationship('Question', secondary=questions)
    creator = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    result_reveal = db.Column(db.Boolean)
    answer_reveal = db.Column(db.Boolean)
    time_limit = db.Column(db.Integer)
    instructions = db.Column(db.String(255))
    description = db.Column(db.String(255))
    shuffle = db.Column(db.Boolean)
    image = db.Column(db.String(255))
    text = db.Column(db.String(2550))
    deck_id = db.Column(db.Integer, db.ForeignKey('deck.id', ondelete='SET NULL'), nullable=True)
    
    def sum_points(self):
        sum = 0
        for questions in self.questions:
            sum = sum + questions.points
        self.points = sum

    
    def count_questions(self):
        ##count the number of questions in test
        self.num_questions = len(self.questions)

    
class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question = db.Column(db.String(1000), nullable=False)
    term = db.Column(db.String(1000), nullable=False)
    content = db.Column(db.String(1000), nullable=False)
    boc_2 = db.Column(db.String(1000), nullable=True) 
    boc_3 = db.Column(db.String(1000), nullable=True) 
    boc_4 = db.Column(db.String(255), nullable=True)
    formula = db.Column(db.String(255), nullable=True)
    prompt_option = db.Column(db.String(255), nullable=True)
    q_type = db.Column(db.String(50), nullable=True)
    q_order = db.Column(db.Integer, nullable=True)
    points = db.Column(db.Integer, nullable=True)

class QuestionResult(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))
    taker = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
    answer = db.Column(db.String(50))
    points = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)



class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))
    taker = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    creator = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    due_date = db.Column(db.DateTime)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    points = db.Column(db.Integer)
    correct = db.Column(db.Integer)
    blank = db.Column(db.Integer)
    
    def sum_points(self):
        sum = 0
        question_results = QuestionResult.query.filter_by(test_id=self.test_id, taker=self.taker).all()
        for questions in question_results:
            if questions.points == None:
                questions.points = 0
            sum = sum + questions.points
        self.points = sum
##################### SETTINGS TABLES #####################
class UserSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    language = db.Column(db.String(50))
    theme = db.Column(db.String(50))
    new_user = db.Column(db.Boolean, default = True)
    new_user_study = db.Column(db.Boolean, default = True)
    new_user_decks = db.Column(db.Boolean, default = True)
    new_user_tests = db.Column(db.Boolean, default = True)
    new_user_cards = db.Column(db.Boolean, default = True)
    srs_setting_1 = db.Column(db.Integer)
    srs_setting_2 = db.Column(db.Integer)
    srs_setting_3 = db.Column(db.Integer)
    srs_setting_4 = db.Column(db.Integer)        
        
###################### JOB QUEUE TABLE ####################################
class JobNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    slug = db.Column(db.String(128), nullable=False)
    state = db.Column(db.String(10), nullable=False, default="queued")
    complete = db.Column(db.Boolean, default=False)
    notified = db.Column(db.Boolean, default=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    cost = db.Column(db.Integer, default=0)
    input_details = db.Column(db.String(128), nullable=True)
    extract_type = db.Column(db.String(128), nullable=True)



class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    slug = db.Column(db.String(64), nullable=False)
    task_type = db.Column(db.String(64), nullable=True)
    state = db.Column(db.String(10), nullable=False, default="queued")
    result = db.Column(db.Integer, default=0)
    payload = db.Column(db.Text, nullable=True)
    priority = db.Column(db.Integer, nullable=False, default=0)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    error_traceback = db.Column(db.Text, nullable=True)
    error_type = db.Column(db.String(64), nullable=True)
    item_number = db.Column(db.Integer, nullable=True)
    item_quantity = db.Column(db.Integer, nullable=True)
    processed_content = db.Column(db.Text, nullable=True)
    deck_id = db.Column(db.Integer, db.ForeignKey('deck.id', ondelete='SET NULL'), nullable=True)
    save_source = db.Column(db.Boolean, default=False)
    qty_cards_created = db.Column(db.Integer, default=0)

class EventTracking(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    event_type = db.Column(db.String(64), nullable=True)
    event_data = db.Column(db.Text, nullable=True)
    event_details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)
    
   

######### CACHED RESPONSES #####
class CachedResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    input_type = db.Column(db.String(64), nullable=True)
    input_data = db.Column(db.Text, nullable=True)
    input_text = db.Column(db.Text, nullable=True)
    output_type = db.Column(db.String(64), nullable=True)
    output_data = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    date_accessed = db.Column(db.DateTime, default=datetime.utcnow)
    accessed_count = db.Column(db.Integer, default=0)
    subject = db.Column(db.String(64), nullable=True)
    topic = db.Column(db.String(64), nullable=True)
    subtopic = db.Column(db.String(64), nullable=True)
    concepts = db.Column(db.String(64), nullable=True)
    difficulty = db.Column(db.String(64), default=False)


    __table_args__ = (UniqueConstraint('input_type', 'output_type', name='uix_1'), )








######### GAMIFICATION



skills_category_skill = db.Table('skills_category_skill',
    db.Column('skill_id', db.Integer, db.ForeignKey('skill.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('skills_category.id'), primary_key=True)
)


class Skills_Category(db.Model):
    __tablename__ = 'skills_category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Skill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    users = db.relationship('User_Skill', backref='skill')
    categories = db.relationship('Skills_Category', secondary=skills_category_skill, backref='skills')
class User_Skill(db.Model):
    __tablename__ = 'user_skill'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'), nullable=False)

class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    avatar = db.Column(db.String(100), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey('skills_category.id'), nullable=True)

class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skill.id'), nullable=False)
    skill = db.relationship('Skill', backref='goals')
    target_level = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime)



###  GAMES ####


class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    current_flashcard_id = db.Column(db.Integer, db.ForeignKey('card.id'))
    deck_id = db.Column(db.Integer, db.ForeignKey('deck.id'))
    rounds = db.Column(db.Integer, default=0)
    time_limit = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    start_time = db.Column(db.DateTime)
    current_round = db.Column(db.Integer, default=0)

class PlayerGame(db.Model):
    __tablename__ = 'player_game'
    player_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    username = db.Column(db.String(64))
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), primary_key=True)
    score = db.Column(db.Integer, default=0)
    turns_as_main_player = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default = 0)

class GameAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(2560))
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'))
    round = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_correct = db.Column(db.Boolean, default=False)

class GameVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    answer_id = db.Column(db.Integer, db.ForeignKey('game_answer.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    round = db.Column(db.Integer)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'))