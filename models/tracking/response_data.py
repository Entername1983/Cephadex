from datetime import datetime
from models.extensions import db, migrate


class ResponseData(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    prompt = db.Column(db.Text)	
    response = db.Column(db.Text)
    content = db.Column(db.Text)	
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    success = db.Column(db.Boolean)
          