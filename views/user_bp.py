import os
import datetime as dt
import tempfile
from bleach import clean
import stripe
import logging
import json
from werkzeug.utils import secure_filename
from google.oauth2 import id_token
from google.auth.transport import requests
from flask import (
    flash, redirect, render_template, request, session, Blueprint,
    url_for, jsonify
)
from flask_login import login_user, login_required, logout_user, current_user
from models.models_ import (
    Card, Deck, PlayerGame, Subscriber,
    UserSettings, User, Feedback, DeletedAccounts,
    Test, TestResult
)
from models.send_email import send_email
from models.tracking.events import event_tracker
from models.forms.forms import (
    RegSub, RegisterForm, UploadFileForm,
    AccountForm, DeleteAccountForm, UpdateProfilePicForm,
    Unsubscribe, FeedbackForm
)
from config.settings import AUTH2_CLIENT_ID
from run.extensions import db
from models.storage.s3 import upload_to_s3, delete_s3_object_in_folder
from models.helpers.log_decorators import log_decorator
from models.helpers.helpers import apology
from models.user.sub_handler import StripeEventHandler

logger = logging.getLogger("flask_app")

user_bp = Blueprint(
    'user_bp', 
    __name__,
    template_folder='templates/user_bp',
    static_folder='static'
)


@user_bp.route("/googleSignIn", methods=["POST"])
@log_decorator
def googleSignIn():
    csrf_error_message, csrf_error_code = verify_csrf_token()
    if csrf_error_message:
        return jsonify({'error': csrf_error_message}), csrf_error_code
    credential = request.form.get('credential')
    try:
        idinfo = id_token.verify_oauth2_token(credential,
                                            requests.Request(), AUTH2_CLIENT_ID)
    except ValueError as e:
        logger.error(f"Value error in google sign in, invalid token {e}")
        return jsonify({'error': 'Invalid token'}), 400
    userid = idinfo['sub']
    if not (user := User.query.filter_by(external_id=userid).first()):
        return handle_new_user(idinfo)
    login_user(user)
    if 'shared_deck_id' in session:
        return found_shared_deck_id_in_session()
    if 'game_id' in session:
        return found_game_id_in_session()
    if 'shared_quiz_id' in session:
        return found_quiz_id_in_session()
    if 'quiz_result_id' in session:
        return found_quiz_result_id_in_session()
    flash('You have been logged in!', 'success')
    event_tracker(user.id, "login", "google")
    return redirect(url_for('deck_bp.view_decks'))
   
def handle_new_user(idinfo):
    session['google_id_token'] = idinfo['sub']
    session['google_email'] = idinfo.get('email', 'n/a')
    session['given_name'] = idinfo.get('given_name', 'Anonymous')
    session['family_name'] = idinfo.get('family_name', 'Anonymous')
    return redirect(url_for('user_bp.register'))

def verify_csrf_token():
    csrf_token_cookie = request.cookies.get('g_csrf_token')
    csrf_token_body = request.form.get('g_csrf_token')
    if not csrf_token_cookie:
        return 'No CSRF token in Cookie', 400
    if not csrf_token_body:
        return 'No CSRF token in post body', 400
    if csrf_token_cookie != csrf_token_body:
        return 'Failed to verify double submit cookie', 400
    return None, None

def found_shared_deck_id_in_session():
    if session.get('shared_deck_id'):
        shared_deck = Deck.query.filter_by(share_id = session['shared_deck_id']).first()
        new_deck = Deck(user_id = current_user.id,
                name=shared_deck.name,
                description=shared_deck.description,
                time_created=dt.datetime.now(dt.timezone.utc))
        db.session.add(new_deck)
        for card in shared_deck.cards:
            new_card = Card(term=card.term,
                content=card.content, boc_2=card.boc_2, boc_3=card.boc_3,
                boc_4=card.boc_4,img=card.img, sound=card.sound,
                subject=card.subject, topic=card.topic,
                category=card.category,
                prompt_option=card.prompt_option,
                prompt_option2=card.prompt_option2,
                trans_option=card.trans_option, len_option=card.len_option,
                qmin_option=card.qmin_option,
                qmax_option=card.qmax_option, diff_lvl=card.diff_lvl)
            new_deck.cards.append(new_card)
    
        del session['shared_deck_id']
        db.session.commit()
        flash("Your deck has been saved", "success")
    else:
        flash("There was an issue saving your deck, please try again", "failure")
    return redirect(url_for('deck_bp.view_decks'))

def found_game_id_in_session():
    if session.get('game_id'):
        game_id = session.get('game_id')
        if current_user.username:
            username = current_user.username
        else:
            username  = current_user.email
        player = PlayerGame(player_id = current_user.id, game_id = game_id, username = username)
        db.session.add(player)
        db.session.commit()
        del session['game_id']
        return redirect(url_for('game_bp.game_lobby', game_id=game_id))
    else:
        return apology("There was an issue saving your game, please try again", 400)

def found_quiz_id_in_session():
    if session.get('shared_quiz_id'):
        quiz = Test.query.filter_by(share_id = session['shared_quiz_id']).first()
        del session['shared_quiz_id']
        return redirect(url_for('quiz_bp.take_quiz',
            quiz_id=quiz.id, user_id=current_user.id))
    else:
        return apology("There was an loading your quiz, please try again", 400)

def found_quiz_result_id_in_session():
    if session.get('quiz_result_id'):
        quiz_result = TestResult.query.filter_by(id = session['quiz_result_id']).first()
        quiz_result.taker = current_user.id
        db.session.commit()
        del session['quiz_result_id']
        flash("Your results have been saved", "success")
    else:
        flash("There was an issue saving your results, please contact us for assistance", "failure")
    return redirect(url_for('quiz_bp.quiz_overview'))

@user_bp.route("/accountsettings", methods = ["GET", "POST"])
@login_required
@log_decorator
def account_settings():
    return render_template("accountsettings.html", title="Account Settings")

@user_bp.route("/feedback", methods=["GET", "POST"])
@log_decorator
def feedback():
    form = FeedbackForm()
    if form.validate_on_submit():
        if form.name.data != "RobertEmelo":
            entry = Feedback(name=form.name.data,
                            email=form.email.data,
                            message=form.message.data,
                            type_feedback=form.type_feedback.data)
            entry.send_feedback()
        return jsonify(status="success", message="Thank you for your feedback!")
    errors = []
    for field, error_msgs in form.errors.items():
        errors.extend(f"{field}: {msg}" for msg in error_msgs)
    return jsonify(status="error", errors=errors)


@user_bp.route("/delete_account", methods=["GET", "POST"])
@login_required
@log_decorator
def delete_account():
    form = DeleteAccountForm()
    if form.validate_on_submit():
        user = User.query.filter_by(id=current_user.id).first()
        if user.email == form.del_email.data:
            user.account_status = 'inactive'
            user.expiration = dt.datetime.now(dt.timezone.utc)
            user.account_expiration_reason = "Deleted"
            if form.reason.data == 'other':
                reason = form.other_reason.data
            else:
                reason = form.reason.data

            details = form.more.data or None
            deleted_entry = DeletedAccounts(user_id=current_user.id,
                    email = current_user.email, date_created = current_user.time_created,
                    date_deleted = dt.datetime.now(dt.timezone.utc), reason=reason,
                    reason_details = details)
            db.session.add(deleted_entry)
            db.session.commit()
            flash('We are sorry to see you go. Your account is now inactive and will be permanently deleted within 48 hours.')  # noqa: E501
            return redirect(url_for('user_bp.logout'))
    return render_template('user_bp/delete_account.html', form_del=form)

@user_bp.route('/login', methods=['GET', 'POST'])
@log_decorator
def login():
    if current_user.is_authenticated:
        return redirect(url_for('deck_bp.view_decks'))
    else:
        return redirect(url_for('index'))

@user_bp.route('/check_username/<username>', methods=["GET", "POST"])
@log_decorator
def check_username(username):
    user = User.query.filter_by(username=username).first()
    if user is not None:
        response = jsonify({'username_taken': True})
    else:
        response = jsonify({'username_taken': False})
    response.status_code = 200
    return response
    
@user_bp.route("/register", methods=["GET", "POST"])
@log_decorator
def register():
    if 'google_email' not in session or 'google_id_token' not in session:
        flash('Please sign in through Google first.', 'warning')
        return redirect(url_for('index')) 
    error_occured = False
    try:
        form = RegisterForm()
        if request.method == 'POST':
            username = request.form['username']
            ##timezone = request.form['password']
            ##role = request.form['role']
            subscribe = request.form.get('subscribe')
            role = request.form.get('role')
            timezone = form.timezone.data
            if timezone is None:
                timezone = "Europe/Dublin"
            # Get the user's email address and ID token from the session
            email = session['google_email']
            userid= session['google_id_token']
            given_name = session['given_name']
            family_name = session['family_name']
            if guest_user := User.query.filter_by(email=email, guest=True).first():
                user = turn_guest_into_regular_user(guest_user, username, userid, given_name, family_name,
                        role, timezone)
            else:
                user = User(email=email, first_name=given_name, last_name=family_name,external_id=userid,
                    external_type='google', contacted_email=True, username=username, timezone = timezone,
                    subscription_start_date = dt.datetime.now(dt.timezone.utc), role = role)
                db.session.add(user)
            send_email(email, given_name, 'welcome')
            user_settings = UserSettings(user=user.id)
            db.session.add(user_settings)
            if subscribe == "subscribe":
                sub_exists = Subscriber.query.filter_by(email=email).first()
                if not sub_exists:
                    timestamp = dt.datetime.now(dt.timezone.utc)
                    subscriber = Subscriber(email=email, first_name=given_name,
                                             last_name=family_name, timestamp = timestamp)
                    db.session.add(subscriber)
            event_tracker(user.id, "register", "google")
            db.session.commit()
            login_user(user)
            if 'shared_test_id' in session:
                return found_quiz_id_in_session()
            if 'shared_deck_id' in session:
                return found_shared_deck_id_in_session()
            if 'game_id' in session:
                return found_game_id_in_session()
            if 'quiz_result_id' in session:
                return found_quiz_result_id_in_session()
            flash("You have been registered and logged in!", "success")
            return redirect(url_for('deck_bp.view_decks'))
        return render_template('/user_bp/register.html', title='Register', form = form)
    except Exception as e:
        error_occured = True
        logger.error(f"An error occured during registration {e}")
        raise e
    finally:
        if error_occured:
            return apology("An error occurred during registration", 500)


def turn_guest_into_regular_user(guest_user, username, userid, given_name, family_name,
                        role, timezone, external_type='google', subscription_plan = 1):
    guest_user.username = username
    guest_user.guest = False
    guest_user.external_id = userid
    guest_user.first_name = given_name
    guest_user.last_name = family_name
    guest_user.external_type = external_type
    guest_user.subscription_plan = subscription_plan
    guest_user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
    guest_user.role = role
    guest_user.timezone = timezone
    return guest_user

@user_bp.route('/subscribe', methods=['GET', 'POST'])
@log_decorator
def subscribe():
    subscribe_form = RegSub()
    if subscribe_form.validate_on_submit():
        subscriber = Subscriber(email=subscribe_form.email.data,
                                first_name=subscribe_form.first_name.data,
                                last_name=subscribe_form.last_name.data,
                                timestamp = dt.datetime.now(dt.timezone.utc))
        db.session.add(subscriber)
        db.session.commit()
        flash('You are now subscribed to our newsletter!')
    return render_template('user_bp/subscribe.html', title='Subscribe', form=subscribe_form)

@user_bp.route('/subscribe2', methods=['GET', 'POST'])
@log_decorator
def subscribe2():
    data = request.json
    first_name = clean(data['first-name'])
    last_name = clean(data['last-name'])
    email = data['email']
    existing_subscriber = Subscriber.query.filter_by(email=email).first()
    if existing_subscriber and existing_subscriber is not None:
        flash("You are already subscribed!")
        return jsonify({'status': 'failure', 'message': 'You are already subscribed!'})
    else:
        subscriber = Subscriber(email=email, first_name=first_name,
                    last_name=last_name, timestamp = dt.datetime.now(dt.timezone.utc))
        db.session.add(subscriber)
        db.session.commit()
        flash("Thanks for subscribing!")
        return jsonify({'status': 'success', 'message': 'Subscription successful!'})

@user_bp.route('/logout', methods=['GET', 'POST'])
@login_required
@log_decorator
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out!')
    return redirect(url_for('index'))

@user_bp.route("/unsubscribe", methods=["GET", "POST"])
@log_decorator
def unsubscribe():
    form = Unsubscribe()
    if request.method == 'POST':
        email = request.form['email']
        newsletter = request.form.get('newsletter')
        contacted = request.form.get('contacted')
        subscriber = Subscriber.query.filter_by(email=email).first()
        user = User.query.filter_by(email=email).first()
        if contacted == 'y':
            user.contacted_email = False
            flash("You will no longer receive emails from us regarding your account")
        if subscriber and newsletter == 'y':
            db.session.delete(subscriber)
            flash("You will no longer receive our newsletter")
        db.session.commit()
        return redirect(url_for('user_bp/unsubscribe'))
    return render_template('user_bp/unsubscribe.html', title='Unsubscribe', form = form)

@user_bp.route("/account", methods = ["POST", "GET"])
@login_required
@log_decorator
def account():
    error_occured = False
    form = AccountForm()
    user = User.query.filter_by(id=current_user.id).first()
    subscriber = Subscriber.query.filter_by(email=user.email).first()
    form_del = DeleteAccountForm()
    form2 = UpdateProfilePicForm()
    try:
        if form.validate_on_submit():
            user.first_name = form.first_name.data
            user.last_name = form.last_name.data
            user.username = form.username.data
            if form.gender.data != "":
                user.gender = form.gender.data
            if form.role.data != "":
                user.role = form.role.data
            if form.timezone.data != "":
                user.timezone = form.timezone.data
            user.timezone = form.timezone.data
            user.contacted_email = form.contacted_email.data
            ###logger.debug("contacted", form.contacted_email.data)
            db.session.commit()
            if form.subscribe.data:
                if not subscriber:
                    subscriber = Subscriber(email=user.email, first_name=user.first_name, last_name=user.last_name,
                            timestamp=dt.datetime.now(dt.timezone.utc))
                    db.session.add(subscriber)
                    db.session.commit()
                    flash("You have been subscribed to our mailing list")
            elif subscriber:
                db.session.delete(subscriber)
                db.session.commit()
                subscriber = Subscriber.query.filter_by(email=user.email).first()
                flash("You have been unsubscribed from our mailing list")

            db.session.commit
            flash("Your account has been updated")
        return render_template("user_bp/account.html", title="Account", form_del = form_del, form = form,
                    user = user, subscriber = subscriber, form2 = form2)
    except Exception as e:
        error_occured = True
        logger.error(f"An error occured while accessing the account page: {e}")
        raise e
    finally:
        if error_occured:
            flash("There was an error updating your account")
            return redirect(url_for('user_bp.account'))

@user_bp.route('/update_profile_pic', methods=['POST'])
@login_required
@log_decorator
def update_profile_pic():
    form = UpdateProfilePicForm()
    if form.validate_on_submit():
        if profile_picture := form.profile_pic.data:
            filename = f"{current_user.id}_{secure_filename(profile_picture.filename)}"
            temp_path = os.path.join(tempfile.gettempdir(), filename)
            profile_picture.save(temp_path)
            upload_to_s3('cephadex', 'profile_pictures', temp_path, filename)
            os.remove(temp_path)
            user = User.query.filter_by(id=current_user.id).first()
            if user.pic is not None:
                try:
                    delete_s3_object_in_folder('cephadex', 'profile_pictures', user.pic)
                except Exception as e:
                    logger.error(f"Error deleting profile pic from s3: {e}")
            user.pic = filename
            db.session.commit()
        else:
            flash('No file selected')
    else:
        for error in form.profile_pic.errors:
            flash(error)
    return redirect(url_for('user_bp.account'))
@user_bp.route("/new_user_settings_tests", methods = ["POST", "GET"])
@login_required
@log_decorator
def new_user_settings_tests():
    data = request.get_json()
    if data.get('checked'):
        user_settings = UserSettings.query.filter_by(user=current_user.id).first()
        user_settings.new_user_tests = False
        db.session.add(user_settings)
        db.session.commit()
    return jsonify({'success': True})

@user_bp.route("/new_user_settings", methods = ["POST", "GET"])
@login_required
@log_decorator
def new_user_settings():
    data = request.get_json()
    if data.get('checked'):
        user_settings = UserSettings.query.filter_by(user=current_user.id).first()
        user_settings.new_user_study = False
        db.session.add(user_settings)
        db.session.commit()
    return jsonify({'success': True})

@user_bp.route("/new_user_settings_create", methods = ["POST", "GET"])
@login_required
@log_decorator
def new_user_settings_create():
    data = request.get_json()
    if data.get('checked'):
        user_settings = UserSettings.query.filter_by(user=current_user.id).first()
        user_settings.new_user = False
        db.session.add(user_settings)
        db.session.commit()
    return jsonify({'success': True})

@user_bp.route("/new_user_settings_view_decks", methods = ["POST", "GET"])
@login_required
@log_decorator
def new_user_settings_viewdecks():
    print("entered new user settings view decks")
    data = request.get_json()
    if data.get('checked'):
        print("recognized as checked")
        user_settings = UserSettings.query.filter_by(user=current_user.id).first()
        user_settings.new_user_decks = False
        db.session.add(user_settings)
        db.session.commit()
    return jsonify({'success': True})

@user_bp.route("/new_user_settings_cards", methods = ["POST", "GET"])
@login_required
@log_decorator
def new_user_settings_cards():
    data = request.get_json()
    if data.get('checked'):
        user_settings = UserSettings.query.filter_by(user=current_user.id).first()
        user_settings.new_user_cards = False
        db.session.add(user_settings)
        db.session.commit()
    return jsonify({'success': True})

@user_bp.route("/check_credit", methods=["GET", "POST"])
@log_decorator
def check_credit():
    form = UploadFileForm()
    return render_template("/user_bp/check_credit.html", title="Check Credit", form = form)

@user_bp.route('/upgrade', methods=['GET', 'POST'])
@login_required
@log_decorator
def upgrade():
    if not current_user.is_authenticated:
        flash('You must first have an account and be logged in'
            'before upgrading your account', 'warning')
        return redirect(url_for('index'))
    publishable_key = os.environ.get("STRIPE_PUBLISHABLE_KEY")
    pricing_table_id = os.environ.get("STRIPE_PRICING_TABLE_ID")
    return render_template('user_bp/upgrade.html',
            pricing_table_id = pricing_table_id, publishable_key = publishable_key)

@log_decorator
@user_bp.route("/stripe_webhook", methods=['POST'])
def stripe_webhook():
    endpoint_secret = os.environ.get("STRIPE_SIGNING_SECRET")
 
    valid_events = ['checkout.session.completed', 'customer.subscription.renewing',
                    'customer.deleted', 'customer.updated', 'customer.subscription.deleted',
                    'customer.subscription.updated', 'customer.subscription.created',
                    'customer.subscription.trial_will_end', 'invoice.created',
                    'invoice.payment_failed', 'invoice.payment_succeeded','invoice.updated',
                    'invoice.finalized', 'invoice_finalization_failed',
                    ]
    payload = request.data.decode('utf-8')
    sig_header = request.headers.get('stripe-signature')
    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        logger.exception("An exception occurred in stribe_webhook() route): %s", e)
        return 'Invalid payload', 401
    except stripe.error.SignatureVerificationError as e:
        logger.debug(f"Signature verification error: {str(e)}")
        logger.error("An exception occurred in stribe_webhook() route): %s", e)
        return 'Invalid signature', 402
    if event['type'] in valid_events:
        try:
            stripe_event_handler = StripeEventHandler()
            stripe_event_handler.handle_event(event)
        except Exception as e:
            logger.critical(f"Unhandled stripe event error {e}: {json.dumps(event, indent=4)}")
    else:
        return 'Unused event type', 200
    return 'Success', 200



