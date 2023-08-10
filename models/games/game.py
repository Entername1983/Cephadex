from datetime import datetime
from models.extensions import db, migrate

class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    creator = db.Column(db.Integer, db.ForeignKey('user.id',
                                                   ondelete='CASCADE'), nullable=False)
    current_flashcard_id = db.Column(db.Integer, db.ForeignKey('card.id'))
    deck_id = db.Column(db.Integer, db.ForeignKey('deck.id'))
    rounds = db.Column(db.Integer, default=0)
    time_limit = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    start_time = db.Column(db.DateTime)
    current_round = db.Column(db.Integer, default=0)
    players = db.relationship('PlayerGame', backref='game')