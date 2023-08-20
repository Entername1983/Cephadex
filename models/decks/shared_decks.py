
from models.association_tables import cards_shared
from datetime import datetime
from run.extensions import db

class SharedDecks(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False) 
    sender = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'),
                        nullable=True)
    receiver = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'),
                          nullable=True)
    time_created = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.Column(db.Integer) 
    public = db.Column(db.Integer, default=0) 
    edited = db.Column(db.Integer, default=0)
    cards = db.relationship('Card', secondary=cards_shared, backref="decks",
                             lazy="select")
    share_id = db.Column(db.String(36), nullable=True, unique=True)

    def delete(self):
        db.session.delete(self)
        db.session.commit()