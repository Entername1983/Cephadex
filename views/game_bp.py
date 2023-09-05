
from random import shuffle
import qrcode
import json
import base64
import random
from datetime import datetime
import datetime as dt
from bleach import clean
from io import BytesIO
from flask_socketio import emit, join_room
from flask import Blueprint, render_template
from flask import (
    flash, redirect, request, session, url_for, jsonify
    )
from flask_login import login_user, login_required, current_user
from models.forms.forms import CreateGameForm
from models.models_ import (
    Deck, GameAnswer, GameVote, Game, PlayerGame, User
)
from config.settings import ENVIRONMENT
from run.extensions import db, socketio
from models.helpers.log_decorators import log_decorator
import logging
logger = logging.getLogger("flask_app")

game_bp = Blueprint(
    'game_bp', 
    __name__,
    template_folder='templates/game_bp',
    static_folder='static'
)



@login_required
@log_decorator
@game_bp.route('/game_new', methods=['GET', 'POST'])
def game_new():
    form = CreateGameForm()
    decks = Deck.query.filter_by(user_id=current_user.id).all() 
    if decks:
        form.deck.choices = [(deck.id, deck.name) for deck in decks]
    else:
        form.deck.choices = []
    
    if request.method == 'POST':
        deck = request.form.get('deck')
        rounds = request.form.get('rounds')
        time_limit = request.form.get('time_limit')
        participate = request.form.get('participate')
        # Assume current_user is the user who is creating the game
        new_game = Game(creator=current_user.id, rounds = rounds,
                time_limit = time_limit, deck_id = deck)
        db.session.add(new_game)
        db.session.commit()

        if participate == "yes":
            player = PlayerGame(player_id = current_user.id,
                        game_id = new_game.id, username=current_user.username)
            db.session.add(player)
            db.session.commit()
        logging.info(f"player is {player}, deck is {deck}, rounds are {rounds}")
        return redirect(url_for('game_bp.game_lobby', game_id=new_game.id))
    return render_template('/game_bp/game_new.html', decks = decks, form = form)


@game_bp.route('/game_lobby/<int:game_id>', methods=['GET', 'POST'])
@log_decorator
def game_lobby(game_id):
    logging.info("entered game_lobby")
    game = Game.query.get(game_id)
    join_game_url = url_for('game_bp.game_join', game_id=game.id, _external=True)
    ##players = game.players
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(join_game_url)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    stream = BytesIO()
    img.save(stream, "PNG")
    qr_code = base64.b64encode(stream.getvalue()).decode()
    ## if hosts clicks start game, start game
    return render_template('/game_bp/game_lobby.html', game=game,
            qr_code=qr_code, game_url = join_game_url,
            environment=ENVIRONMENT)


@socketio.on('start_game')
@log_decorator
def start_game(data):
    game_id = data['game_id']
    game = Game.query.get(game_id)
    game.start_time = dt.datetime.now(dt.timezone.utc)
    db.session.commit()
    game_id = str(game_id)
    emit('start_game', {'game_id': game_id }, callback=messageReceived, room=(game_id))



@game_bp.route('/game_join/<int:game_id>', methods=['GET', 'POST'])
@log_decorator
def game_join(game_id):
    game = Game.query.get_or_404(game_id)
    session['game_id'] = game.id
    ## if user is logged in add them to the game
    if current_user.is_authenticated:
        return redirect(url_for('game_lobby', game_id=game.id))
    if request.method == "POST":
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if not user:
            player = User(email=email, guest = True)
            db.session.add(player)
            db.session.commit()
            login_user(player)
            if 'game_id' in session:
                del session['game_id']
            return redirect(url_for('game_lobby', game_id=game.id))
        else:
            flash("It looks like that email is already associated with an account.  Please log in to join the game.")
            return redirect(url_for('game_login', game_id=game.id))

    return render_template('/game_bp/game_join.html', game_id=game_id)


@game_bp.route('/game_login', methods=['GET', 'POST'])
@log_decorator
def game_login():
    return render_template('/game_bp/game_login.html')


@game_bp.route('/game_play/<int:game_id>', methods=['GET', 'POST'])
@log_decorator
def game_play(game_id):
    game = Game.query.get_or_404(game_id)
    if not game.start_time:
        return redirect(url_for('game_bp.game_lobby', game_id=game.id,
                                 environment=ENVIRONMENT))
    players = []
    usernames = {}
    for player in game.players:
        players.append(player)
        if username := User.query.get(player.player_id).username:
            usernames[player.player_id] = username
        else:
            usernames[player.player_id] = User.query.get(player.player_id).email

    return render_template('/game_bp/game_play.html',
            game=game, players = players, usernames=usernames)



### GAME PLAY ####
@game_bp.route('/server_time', methods=['GET','POST'])
@log_decorator
def server_time():
    # get current server time
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    # send current_time in response
    return jsonify({'server_time': current_time})


@game_bp.route('/game/<int:game_id>/next_round', methods=['GET'])
@log_decorator
def next_round(game_id):
    game = Game.query.get_or_404(game_id)
    game.current_round += 1
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    db.session.commit()
    return jsonify({'round': game.current_round, 'server_time': current_time})

@game_bp.route('/game/<int:game_id>/reveal_answers', methods=['GET'])
@login_required
@log_decorator
def reveal_answers(game_id):
    round_id = int(request.args.get('round_id'))
    game = Game.query.get_or_404(game_id)
    answers = GameAnswer.query.filter_by(game_id=game.id, round = round_id).all()
    answers_text = [answer.text for answer in answers]
    shuffle(answers_text)
    return jsonify({'answers': answers_text})

@socketio.on('custom_disconnect')
@log_decorator
def handle_custom_disconnect(data):
    # Get the user and game information from the session
    user_id = session.get('user_id')
    game_id = data['game_id']
    
    if user_id and game_id:
        # Remove the player from the game
        game = Game.query.get_or_404(game_id)
        player = game.get_player(user_id)
        if player:
            ##game.remove_player(player)
            ##db.session.commit()
            # Emit a player_left event to notify other players
            emit('player_left', {'user_id': user_id}, room=game_id)


def create_playa(game_id, user_id):
    players_in_game = PlayerGame.query.filter_by(game_id=game_id).first()
    game = Game.query.get_or_404(game_id)
    if current_user.id != game.creator:
        existing_player = PlayerGame.query.filter_by(game_id=game_id, player_id=user_id).first()
        if existing_player is None:
            player = User.query.filter_by(id=user_id).first()
            if player.username:
                username = player.username
            else:
                username = player.email
            new_player = PlayerGame(game_id=game_id, player_id=user_id, username=username)
            db.session.add(new_player)
            db.session.commit()
            return new_player
        return existing_player


@socketio.on('join_game')
@log_decorator
def on_join(data):
    #game_id = data['game_id']
    #players_in_game = PlayerGame.query.filter_by(game_id=game_id).first()
    user_id = data['user_id']
    game_id = data['game_id']
    create_playa(int(game_id), int(user_id))
    join_room(game_id)
    # Get all players currently connected
    players_in_room = PlayerGame.query.filter_by(game_id=game_id).all()
    # Convert to a list of dicts, with only necessary attributes
    players_list = []
    for player in players_in_room:
        players_list.append({'user_id': player.player_id, 'username': player.username})
    # Notify all clients about the new list of players
    emit('players_updated', {'players': players_list}, room=game_id)

@socketio.on('start_round')
@log_decorator
def handle_start_round(data):
    game_id = data['game_id']
    game_round = increase_round(game_id)
    card_term, card_id = get_flashcard(game_id)
    emit('start_round', {'question': card_term,
                          'card_id': card_id, 'round': game_round}, room=game_id)
@socketio.on('submit_vote')
@log_decorator
def submit_vote(data):
    try:
        print("entered submit vote")
        game_id = int(data['game_id'])
        round_id = int(data['round_id'])
        answer = data['answer']
        player_id = data['player_id']
        game = Game.query.get_or_404(game_id)
        # Get the answer index from the request data
        answer_match = GameAnswer.query.filter_by(game_id=game.id, round=round_id, text=answer).first()

        # Create a new vote
        vote = GameVote(answer_id=answer_match.id,
                        user_id=current_user.id, game_id=game.id, round=round_id)

        # Save the vote to the database
        db.session.add(vote)
        db.session.commit()
        return jsonify({'message': 'Vote submitted successfully.'})
    except Exception as e:
        print("exception in submit vote", e)


@socketio.on('submit_answer')
@log_decorator
def handle_submit_answer(data):
    game_id = int(data['game_id'])
    round_id = int(data['round_id'])
    if 'answer' in data:
        if data['answer'] == '':
            answer = 'No answer'
        else:
            answer = clean(data['answer'])
        player_id = data['player_id']
        submit_answer(game_id, round_id, answer, player_id)
    emit('submit_answer', {'answer': answer, 'player_id': player_id}, room=game_id)

@socketio.on('check_if_all_answers_submitted')
@log_decorator
def check_if_all_answers_submitted(data):
    try:
        game_id = int(data['game_id'])
        round_id = int(data['round_id'])
        game = Game.query.get_or_404(game_id)
        answers = GameAnswer.query.filter_by(game_id=game.id, round=round_id).all()
        if len(answers) - 1 == len(game.players):
            emit('check_if_all_answers_submitted', {'round_id':round_id},
                  callback=messageReceived, room=data['game_id'])
    except Exception as e:
        ## TO DO sort this out, what the hell is this?
        print("exception in check if all answers ubmitted", e)

@socketio.on('check_all_votes_are_in')
@log_decorator
def check_all_votes_are_in(data):
    game_id = int(data['game_id'])
    round_id = int(data['round_id'])
    game = Game.query.get_or_404(game_id)
    votes = GameVote.query.filter_by(game_id=game.id, round=round_id).all()
    if len(votes) == len(game.players):
        emit('check_all_votes_are_in', {'round_id':round_id},
              callback=messageReceived, room=data['game_id'])

@socketio.on('end_game')
@log_decorator
def end_game(data):
    emit('end_game', {'game_id': data['game_id']}, room=data['game_id'])

@socketio.on('count_votes')
@log_decorator
def count_votes(data):
    round_id = int(data['round_id'])
    game_id = int(data['game_id'])
    # Get the game and the answers for this round
    game = Game.query.get_or_404(game_id)
    answers = GameAnswer.query.filter_by(game_id=game.id, round=round_id).all()
    # Find the correct answer for this round
    correct_answer = next((answer for answer in answers if answer.is_correct), None)
    votes = GameVote.query.filter_by(game_id=game.id, round=round_id).all()
    votes_counts = {answer.id: 0 for answer in answers}
    correct_vote_players = []
    deceivers = []
    for vote in votes:
        votes_counts[vote.answer_id] += 1
        if vote.answer_id == correct_answer.id:
            correct_vote_players.append({'player': vote.user_id, 'points': 2})
        else:
            whose_answer = GameAnswer.query.filter_by(id=vote.answer_id).first()
            deceivers.append({'player': whose_answer.user_id, 'points': 1})

    total_points = {}

    for player in correct_vote_players + deceivers:
        user_id = player['player']
        points = player['points']

        # Step 3: Create a dictionary to store the total points for each user
        if user_id not in total_points:
            total_points[user_id] = 0

        # Step 4: Update the total points for each user by adding up the points
        if points:
            total_points[user_id] += int(points)

    for user_id, points in total_points.items():
        player_game = PlayerGame.query.filter_by(player_id=user_id, game_id=game_id ).first()
        if player_game:
            if points:
                player_game.points += int(points)
    db.session.commit()
    total_points_json = json.dumps(total_points)
    answers_info = [{'text': answer.text, 'votes': votes_counts[answer.id],
                      'is_correct': answer.is_correct} for answer in answers]

    emit('count_votes', {
        'total_points':total_points_json,
        'correct_answer': correct_answer.text, 
        'round_id': data['round_id'],
        'answers_info': answers_info  # Include the answer information in the event payload
    }, callback=messageReceived, room=data['game_id'])
## check points for votes



@game_bp.route('/game/<int:game_id>/tabulate', methods=['GET', 'POST'])
@log_decorator
def tabulate_answers(game_id):
    round_id = int(request.form.get('round_id'))
    game = Game.query.get_or_404(game_id)
    answers = GameAnswer.query.filter_by(game_id=game.id, round=round_id).all()
    if answers:
        results = []
        for answer in answers:
            quantity_votes = GameVote.query.filter_by(answer_id=answer.id).count()
            belongs_to_user = GameAnswer.query.filter_by(id = answer.id).first()
            result = {answer.id: quantity_votes, 'user_id': belongs_to_user.user_id}
            results.append(result)
        correct_answer = GameAnswer.query.filter_by(game_id=game.id,
                                            round=round_id, is_correct=True).first()
        ## who voted for the correct answer
        correct_answer_voters = GameVote.query.filter_by(answer_id=correct_answer.id).all()
        for voter in correct_answer_voters:
            print(voter.id)
    return jsonify({'results': 'none'})
        

def messageReceived(methods=['GET', 'POST']):
    print('message was received!!!')

@socketio.on('update_scores')
@log_decorator
def update_scores(data):
    game_id = int(data['game_id'])
    game = Game.query.get_or_404(game_id)
    if current_user.id == game.creator:
        players = game.players
        player_scores = []
        for player in players:
            player_game = PlayerGame.query.filter_by(player_id=player.player_id,
                                                      game_id=game_id).first()
            player_scores.append({'player': player_game.player_id,
                                       'score': player_game.points})
        player_scores_json = json.dumps(player_scores)
        emit('update_scores', {'player_scores': player_scores_json},
              callback=messageReceived, room=data['game_id'])



## creates an answer object and adds it to the database
def submit_answer(game_id, round_id, answer_text, user_id):
    game = Game.query.get_or_404(game_id)
    user = User.query.get_or_404(user_id)
    ##if user not in game.players:
    ##    abort(403)
    existing_answer = GameAnswer.query.filter_by(
        game_id=game.id, 
        user_id=current_user.id, 
        round=round_id
    ).first()
    if existing_answer is None:
        answer = GameAnswer(text=answer_text, game_id=game.id,
                            user_id=current_user.id, round=round_id)
        db.session.add(answer)
        db.session.commit()

## gets a random flashcard from the deck
def get_flashcard(game_id):
    game = Game.query.get_or_404(game_id)
    deck = Deck.query.get_or_404(game.deck_id)
    flashcards = deck.cards
    flashcard = random.choice(flashcards)
    answer = flashcard.content[:2500]
    right_answer = GameAnswer(game_id=game.id,
                round=game.current_round, text=answer, is_correct=True)
    db.session.add(right_answer)
    db.session.commit()
    # Return the flashcard details, excluding the answer
    return flashcard.term, flashcard.id

## increases the round number
def increase_round(game_id):
    game = Game.query.get_or_404(game_id)
    game.current_round += 1
    db.session.commit()
    return game.current_round

@socketio.on('remove_player')
@log_decorator
def on_remove_player(data):
    game_id = data['game_id']
    player_id = data['player_id']
    remove_player(game_id, player_id)
    emit('player_removed', {'player_id': player_id}, room=game_id)


def remove_player(game_id, player_id):
    if player := PlayerGame.query.filter_by(
        player_id=player_id, game_id=game_id
    ).first():
        db.session.delete(player)
        db.session.commit()    