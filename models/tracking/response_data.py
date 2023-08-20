from datetime import datetime
from run.extensions import db


class ResponseData(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    prompt = db.Column(db.Text)	
    response = db.Column(db.Text)
    content = db.Column(db.Text)	
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    success = db.Column(db.Boolean)
          