from datetime import datetime
from run.extensions import db

class DeckAttributes(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    deck_id = db.Column(db.Integer, db.ForeignKey('deck.id', ondelete='CASCADE'),)
    subject = db.Column(db.String(100))
    grade = db.Column(db.String(100))
    topic = db.Column(db.String(100))
    sub_topic = db.Column(db.String(100))
    difficulty = db.Column(db.String(50))
    concepts = db.Column(db.Text)
    time_created = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    language = db.Column(db.String(50))