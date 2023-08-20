from datetime import datetime, timedelta
from flask_login import UserMixin
from models.decks.deck import Deck
from models.group.group import Group
from models.quiz.quiz import Test
from models.user.subscription_plan import SubscriptionPlan
from models.association_tables import user_group_association, distribution, source_files
from models.user.usage_record import UsageRecord
from run.extensions import db


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
        return sum(len(deck.cards) for deck in self.decks)
    
    def quantity_tests(self):
        return Test.query.filter_by(creator=self.id).count()

    def quantity_files(self):
        return (
            Deck.query.join(source_files)
            .filter(source_files.c.deck_id == Deck.id)
            .filter(Deck.user_id == self.id)
            .count()
        )
    
    def quantity_groups(self):
        return Group.query.filter_by(creator_id=self.id).count()
    
    def quantity_decks_public(self):
        return Deck.query.filter_by(user_id=self.id, public=True).count()

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
        if usage_record := (
            UsageRecord.query.filter_by(user_id=self.id)
            .order_by(UsageRecord.date.desc())
            .first()
        ):
            return round(usage_record.remaining_count/341)
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
        return round(new_record.remaining_count/682)
    
    def roll_over_date(self):
        if self.latest_roll_over:
            next_roll_over = self.latest_roll_over + timedelta(days=31)
        else:
            next_roll_over = self.subscription_start_date + timedelta(days=31)
        return next_roll_over.strftime('%b %d, %Y')
    

    def perform_operation(self, operation_type, n, operation_details=None):
    # Check the user's remaining count for this time period
        usage_record = (
                UsageRecord.query
                .filter_by(user_id=self.id)
                .order_by(UsageRecord.date.desc()).first()
        )
        subscription_plan = (
                SubscriptionPlan.query
                .filter_by(id=self.subscription_plan).first() 
        ) 
        if usage_record is None:
            remaining_count = subscription_plan.limit_count
        else:
            remaining_count = usage_record.remaining_count
        if remaining_count - n <= 0:
            return False
        # Perform the operation and update the usage record
        # Update the usage reco
        new_record = UsageRecord(user_id=self.id, operation_type=operation_type,
                                time_period='month',
                                    limit_count=subscription_plan.limit_count)
        new_record.operation_count = n
        if usage_record is None:

            new_record.remaining_count = subscription_plan.limit_count - n
        else:
            new_record.remaining_count = usage_record.remaining_count - n
        db.session.add(new_record)

    def check_subscription_plan(self):
        subscription_plan = (
            SubscriptionPlan.query
            .filter_by(id=self.subscription_plan).first()
        )
        return subscription_plan