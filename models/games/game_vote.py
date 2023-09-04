from run.extensions import db

class GameVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    answer_id = db.Column(db.Integer, db.ForeignKey('game_answer.id', ondelete='CASCADE'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'))
    round = db.Column(db.Integer)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id', ondelete='CASCADE'))