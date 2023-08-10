from datetime import datetime
from models.extensions import db, migrate
from models.association_tables import questions
from models.quiz.question import Question

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(200))
    points = db.Column(db.Integer)
    num_questions = db.Column(db.Integer)
    category = db.Column(db.String(50))
    subject = db.Column(db.String(50))
    topic = db.Column(db.String(50))
    time_created = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.relationship('Question', secondary=questions)
    creator = db.Column(db.Integer, db.ForeignKey('user.id',
                                                   ondelete='SET NULL'), nullable=True)
    result_reveal = db.Column(db.Boolean)
    answer_reveal = db.Column(db.Boolean)
    time_limit = db.Column(db.Integer)
    instructions = db.Column(db.String(255))
    description = db.Column(db.String(255))
    shuffle = db.Column(db.Boolean)
    image = db.Column(db.String(255))
    text = db.Column(db.String(2550))
    deck_id = db.Column(db.Integer, db.ForeignKey('deck.id',
                                                   ondelete='SET NULL'), nullable=True)
    share_id = db.Column(db.String(255))
    
    def sum_points(self):
        points = 0
        for questions in self.questions:
            points = points + questions.points
        self.points = points

    
    def count_questions(self):
        ##count the number of questions in test
        self.num_questions = len(self.questions)