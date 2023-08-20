from datetime import datetime
from run.extensions import db
from sqlalchemy.orm import relationship
from models.association_tables import source_files

class DeckFiles(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    file_name = db.Column(db.String(100))
    file_path = db.Column(db.String(50))
    file_type = db.Column(db.String(500))	
    file_size = db.Column(db.String(50))
    text_string = db.Column(db.Text)
    create_type = db.Column(db.String(50))
    time_created = db.Column(db.DateTime, default=datetime.utcnow)
