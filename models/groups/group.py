from datetime import datetime
from models.extensions import db

class Group(db.Model):
    __tablename__ = "group"
    id = db.Column(db.Integer, primary_key=True)  # pylint: disable=no-member
    name = db.Column(db.String(255))  # pylint: disable=no-member
    description = db.Column(db.String(255))  # pylint: disable=no-member
    group_type = db.Column(db.String(255))  # pylint: disable=no-member
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # pylint: disable=no-member
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)  # pylint: disable=no-member
    creator_id = db.Column(db.Integer, db.ForeignKey("user.id"))  # pylint: disable=no-member
    creator = db.relationship("User", foreign_keys=[creator_id])  # pylint: disable=no-member
    avatar = db.Column(db.String(255)) # pylint: disable=no-member
    is_private = db.Column(db.Boolean, default=False)  # pylint: disable=no-member
    decks = db.relationship("Deck", back_populates="group")  # pylint: disable=no-member
