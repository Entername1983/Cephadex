from models.extensions import db, migrate

class PlayerGame(db.Model):
    __tablename__ = 'player_game'
    player_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    username = db.Column(db.String(64))
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), primary_key=True)
    score = db.Column(db.Integer, default=0)
    turns_as_main_player = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default = 0)