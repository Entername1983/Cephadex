from datetime import datetime
from run.extensions import db


class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50))
    email = db.Column(db.String(120))
    message = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    type_feedback = db.Column(db.String(50))
    def __repr__(self):
        return f'<Feedback {self.email}>'
    
    def send_feedback(self):
        db.session.add(self)            	
        db.session.commit()
        
    def delete_feedback(self):
        db.session.delete(self)            	
        db.session.commit() 
                 