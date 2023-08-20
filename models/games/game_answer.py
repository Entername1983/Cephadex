from run.extensions import db

class GameAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(2560))
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'))
    round = db.Column(db.Integer)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_correct = db.Column(db.Boolean, default=False)