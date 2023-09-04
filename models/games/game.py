from datetime import datetime
from run.extensions import db

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator = db.Column(db.Integer, db.ForeignKey('user.id',
                                                   ondelete='CASCADE'), nullable=False)
    current_flashcard_id = db.Column(db.Integer, db.ForeignKey('card.id', ondelete='SET NULL'))
    deck_id = db.Column(db.Integer, db.ForeignKey('deck.id', ondelete='SET NULL'))
    rounds = db.Column(db.Integer, default=0)
    time_limit = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    start_time = db.Column(db.DateTime)
    current_round = db.Column(db.Integer, default=0)
    players = db.relationship('PlayerGame', backref='game')