from datetime import datetime
from models.extensions import db, migrate
from sqlalchemy import UniqueConstraint


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
    concepts = db.Column(db.String(256), nullable=True)
    difficulty = db.Column(db.String(64), default=False)

    __table_args__ = (UniqueConstraint('input_type', 'output_type', name='uix_1'), )

