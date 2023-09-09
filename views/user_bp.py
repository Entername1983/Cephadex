import os
import json
import datetime as dt
import time
from bleach import clean
import stripe
import uuid
from werkzeug.utils import secure_filename
from google.oauth2 import id_token
from google.auth.transport import requests
from flask import (
    flash, redirect, render_template, request, session, Blueprint,
    url_for, jsonify
)
from flask_login import login_user, login_required, logout_user, current_user
from models.models_ import (
    Card, Deck, Game, PlayerGame, Subscriber,
    UsageRecord, UserSettings, User, Feedback, DeletedAccounts
)
from models.send_email import send_email
from models.stripe_events import StripeEvents
from models.tracking.events import event_tracker
from models.forms.forms import (
    RegSub, RegisterForm, TryOut, UploadFileForm,
    AccountForm, DeleteAccountForm, UpdateProfilePicForm,
    Unsubscribe, FeedbackForm
)
from config.settings import AUTH2_CLIENT_ID
from run.extensions import db
from models.user.stripe_config import STRIPE_PLANS

from models.helpers.log_decorators import log_decorator

user_bp = Blueprint(
    'user_bp', 
    __name__,
    template_folder='templates/user_bp',
    static_folder='static'
)

endpoint_secret = os.environ.get("STRIPE_SIGNING_SECRET")

@user_bp.route("/googleSignIn", methods=["POST"])
@log_decorator
def googleSignIn():
    print("entered google sign in")
    #Security validation
    form = TryOut()
    csrf_token_cookie = request.cookies.get('g_csrf_token')
    if not csrf_token_cookie:
        return jsonify({'error': 'No CSRF token in Cookie'}), 400
    csrf_token_body = request.form.get('g_csrf_token')
    if not csrf_token_body:
        return jsonify({'error': 'No CSRF token in post body.'}), 400
    if csrf_token_cookie != csrf_token_body:
        return jsonify({'error': 'Failed to verify double submit cookie.'}), 400
    #encrypted credential
    credential = request.form.get('credential')
    # Decrypt credential, third parameter comes from google API console client ID
    try:
        idinfo = id_token.verify_oauth2_token(credential,
                                            requests.Request(), AUTH2_CLIENT_ID)
    except ValueError as e:
        # Invalid token
        return jsonify({'error': 'Invalid token'}), 400
    # ID token is valid. Get the user's Google Account ID from the decoded token.
    #  (UniqueID to use for login)
    userid = idinfo['sub']
    user = User.query.filter_by(external_id=userid).first()
    if user:
        login_user(user)
        game_id = session.get('game_id')
        if 'shared_deck_id' in session:
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
            flash("You have been logged in and the deck has been added to your decks", "success")
            return redirect(url_for('deck_bp.viewdecks'))
        if 'game_id' in session:
            game_id = session.get('game_id')
            if user.username:
                username = user.username
            else:
                username  = user.email
            player = PlayerGame(player_id = user.id, game_id = game_id, username = username)
            db.session.add(player)
            db.session.commit()
            del session['game_id']
            return redirect(url_for('game_bp.game_lobby', game_id=game_id))
        if 'shared_test_id' in session:
            shared_test_id = session.get('shared_test_id')
            del session['shared_test_id']
            return redirect(url_for('take_test_2',
                share_id=shared_test_id, user_id = user.id))
        flash('You have been logged in!', 'success')
        event_tracker(user.id, "login", "google")
        return redirect(url_for('deck_bp.viewdecks'))
    else:
        print("recognized not user")
        session['google_id_token'] = idinfo['sub']
        if idinfo.get('email'):
            session['google_email'] = idinfo['email']
        else: 
            session['google_email'] = "n/a"
        if idinfo.get('given_name'):
            session['given_name'] = idinfo['given_name']
        else: 
            session['given_name'] = "Anonymous"
        if idinfo.get('family_name'):
            session['family_name'] = idinfo['family_name']
        else: 
            session['family_name'] = "Anonymous"
        print("about to redirect")
        return redirect(url_for('user_bp.register'))


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
        entry = Feedback(name=form.name.data,
                        email=form.email.data,
                        message=form.message.data,
                        type_feedback=form.type_feedback.data)
        entry.send_feedback()
        return jsonify(status="success", message="Thank you for your feedback!")
    errors = []
    for field, error_msgs in form.errors.items():
        for msg in error_msgs:
            errors.append(f"{field}: {msg}")
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

            details = form.more.data if form.more.data else None
            deleted_entry = DeletedAccounts(user_id=current_user.id,
                    email = current_user.email, date_created = current_user.time_created,
                    date_deleted = dt.datetime.now(dt.timezone.utc), reason=reason,
                    reason_details = details)
            db.session.add(deleted_entry)
            db.session.commit()
            flash('We are sorry to see you go. Your account is now inactive and will be'
                  'permanently deleted within 48 hours.')
            return redirect(url_for('user_bp.logout'))
    return render_template('user_bp/delete_account.html', form_del=form)

@user_bp.route('/login', methods=['GET', 'POST'])
@log_decorator
def login():
    if current_user.is_authenticated:
        return redirect(url_for('deck_bp.viewdecks'))
    else:
        return redirect(url_for('index'))

@user_bp.route('/check_username/<username>', methods=["GET", "POST"])
@log_decorator
def check_username(username):
    user = User.query.filter_by(username=username).first()
    # Check if username already exists
    user = User.query.filter_by(username=username).first()
    if user is not None:
        response = jsonify({'username_taken': True})
        response.status_code = 200
        return response
    else:
        response = jsonify({'username_taken': False})
        response.status_code = 200
        return response
    
@user_bp.route("/register", methods=["GET", "POST"])
@log_decorator
def register():
    error_occured = False
    try:
        form = RegisterForm()
        if request.method == 'POST':
            # Get the user's name and password from the form data
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
            account_type = "free"
            subscription_plan = 1
            existing_user = User.query.filter_by(email=email, guest=True).first()
            if existing_user:
                existing_user.username = username
                existing_user.guest = False
                existing_user.external_id = userid
                existing_user.external_type = 'google'
                existing_user.subscription_plan = 1
                existing_user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
                existing_user.role = role
                existing_user.timezone = timezone
                db.session.commit()
                user = existing_user
                return redirect(url_for('deck_bp.viewdecks'))
            else: 
                user = User(email=email, first_name=given_name, account_type = account_type,
                            last_name=family_name,external_id=userid,
                            external_type='google', subscription_plan = subscription_plan,
                            contacted_email=True, username=username,
                            timezone = timezone,
                            subscription_start_date = dt.datetime.now(dt.timezone.utc),
                            role = role)
                db.session.add(user)
            send_email(email, given_name, 'welcome')
            user_settings = UserSettings(user=user.id)
            if subscribe == "subscribe":
                sub_exists = Subscriber.query.filter_by(email=email).first()
                if not sub_exists:
                    timestamp = dt.datetime.now(dt.timezone.utc)
                    subscriber = Subscriber(email=email, first_name=given_name,
                                             last_name=family_name, timestamp = timestamp)
                    db.session.add(subscriber)
            event_tracker(user.id, "register", "google")
            db.session.add(user_settings)
            db.session.commit()
            login_user(user)
            game_id = session.get('next_game_id')
            if 'shared_test_id' in session:
                shared_test_id = session['shared_test_id']
                del session['shared_test_id']
                return redirect(url_for('quiz_bp.take_test_2',
                    share_id=shared_test_id, user_id = user.id))
            if 'shared_deck_id' in session:
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
                flash("You have been registered and logged in!", "success")
                return redirect(url_for('deck_bp.viewdecks'))
            if game_id is not None:
                game = Game.query.get(game_id)
                game.players.append(current_user)
                db.session.commit()
                del session['game_id']
                return redirect(url_for('game_bp.game_lobby', game_id=game_id))
            flash("You have been registered and logged in!", "success")
            return redirect(url_for('deck_bp.viewdecks'))
        return render_template('/user_bp/register.html', title='Register', form = form)
    except Exception as e:
        error_occured = True
        print(e)
        raise e
    finally:
        if error_occured:
            return "An error occurred during registration", 500

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
                    subscriber = Subscriber(email=user.email, first_name=user.first_name,
                                            last_name=user.last_name,
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
        return render_template("user_bp/account.html", title="Account",
                                form_del = form_del, form = form,
                                user = user, subscriber = subscriber, form2 = form2)
    except Exception as e:
        error_occured = True
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
            # Generate a random and secure filename
            filename = secure_filename(profile_picture.filename)
            # Save the file to our server
            pic_path = os.path.join('static', 'profile_pictures', filename)
            profile_picture.save(pic_path)
            # Update the user's profile picture
            user = User.query.filter_by(id=current_user.id).first()
            user.pic = pic_path
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

@user_bp.route("/new_user_settings_viewdecks", methods = ["POST", "GET"])
@login_required
@log_decorator
def new_user_settings_viewdecks():
    data = request.get_json()
    if data.get('checked'):
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
@log_decorator
def upgrade():
    if not current_user.is_authenticated:
        flash('You must first have an account and be logged in'
            'before upgrading your account', 'warning')
        return redirect(url_for('index'))
    return render_template('user_bp/upgrade.html')

counter = 0
@user_bp.route("/stripe_webhook", methods=['POST'])
@log_decorator
def stripe_webhook():
    valid_events = ['checkout.session.completed','customer.updated']
    global counter
    counter += 1
    payload = request.data.decode('utf-8')
    sig_header = request.headers.get('stripe-signature')
    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except Exception as e:
        raise e
    # except ValueError as e:
    #     # Invalid payload
    #     logger.exception("An exception occurred in stribe_webhook() route): %s", e)
    #     return 'Invalid payload', 401
    # except stripe.error.SignatureVerificationError as e:
    #     # Invalid signature
    #     logger.debug(f"Signature verification error: {str(e)}")
    #     logger.error("An exception occurred in stribe_webhook() route): %s", e)

    #     return 'Invalid signature', 402
    # Handle the checkout.session.completed event
    if event['type'] in valid_events:
        # Fulfill the purchase...
        process_event_in_background(event)
    else:
        # Unknown event type
        return 'Unused event type', 200
    return 'Success', 200

def process_event_in_background(event):
    stripe_event_id = event['id']
    event_type = event['type']
    event_data = json.dumps(event)
    created_at = dt.datetime.now(dt.timezone.utc)
    if event['type'] == 'checkout.session.completed':
        user_id = event['data']['object']['client_reference_id']
    else:
        user_id = None
    if event['type'] != 'customer.updated':
        stripe_customer_id = event['data']['object']['customer']
    else:
        stripe_customer_id = None
    stripe_event = StripeEvents(
        stripe_event_id=stripe_event_id,
        event_type=event_type,
        event_data=event_data,
        event_created=created_at,
        user_id=user_id,
        stripe_customer_id=stripe_customer_id,
    )
    db.session.add(stripe_event)
    db.session.commit()

    if event['type'] == 'checkout.session.completed':
        associate_stripe_customer_with_user(event)
        # Add a small delay to give the webhook function enough time to return a response
        time.sleep(1)
        # Store the event data in the StripeEvents table
        stripe_event_id = event['id']
        event_type = event['type']
        event_data = json.dumps(event)
        created_at = dt.datetime.now(dt.timezone.utc)
        user_id = event['data']['object']['client_reference_id']
        stripe_customer_id = event['data']['object']['customer']
        # logger.debug("CLIENT REF ID %s", event['data']['object']['client_reference_id'])
        # logger.debug("CUSTOMER ID %s", event['data']['object']['customer'])
        stripe_event = StripeEvents(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            event_data=event_data,
            event_created=created_at,
            user_id=user_id,
            stripe_customer_id=stripe_customer_id,
        )
        db.session.add(stripe_event)
        db.session.commit()
        try:
            # Your event processing logic
            handle_checkout_session(event)
            # Update the event as processed in the StripeEvents table
            stripe_event.processed = True
            stripe_event.processed_at = dt.datetime.now(dt.timezone.utc)

        except Exception as e:
            # Update the StripeEvents table with the error message if processing fails
            stripe_event.error_message = str(e)
            current_user.logger.error('Exception in process_event_background'
                                    'function):%s', e)
            raise e

        finally:
            db.session.commit()
    else:
        ## handle other event types
        pass

def associate_stripe_customer_with_user(event):
    try:
        idempo = str(uuid.uuid4())
        user_id = event['data']['object']['client_reference_id']
        stripe_customer_id = event['data']['object']['customer']
        ## modify user entry in DB
        user = User.query.filter_by(id=user_id).first()
        user.stripe_customer_id = stripe_customer_id
        ## modify stripe customer entry
        stripe.Customer.modify(
            stripe_customer_id,
            metadata={'user_id': user_id},
            idempotency_key=idempo, 
            )
        db.session.commit()
    except Exception as e:
        raise e

def handle_checkout_session(event):

    # Extract customer ID and subscription ID from the invoice object
    customer_id = event['data']['object']['customer']
    ##subscription_id = event['data']['object']['subscription']
    checkout_session_id = event['data']['object']['id']
    line_items = stripe.checkout.Session.list_line_items(checkout_session_id)
    # Look up the user in your database using the customer ID
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if line_items.data:
        # Assuming there is only one line item
        item = line_items.data[0]
        product_id = item['price']['product']        
        price_id = item['price']['id']
        # Retrieve the product details from Stripe API
        product = stripe.Product.retrieve(product_id)
        product_name = product['name']
        plan = STRIPE_PLANS[price_id]
    try:
        if user:
            update_plan(user, plan)
    except Exception as e:
            # ## log user not found error
            # logger.debug("user not found")
            # logger.error(f"Exception occurred in handle_checkout_session: {str(e)}") 
            raise e

def update_plan(user,plan):
    try:
        if plan == 'standard_yearly':
            user.subscription_plan = 6
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
            set_usage_limit(user, 682700)
            if user.contacted_email is True:
                send_email(user.email, user.first_name, 'upgrade')
        elif plan == 'standard_monthly':
            user.subscription_plan = 4
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
            set_usage_limit(user, 682700)
            if user.contacted_email is True:
                send_email(user.email, user.first_name, 'upgrade')
        elif plan == 'premium_yearly':
            user.subscription_plan = 7
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
            set_usage_limit(user, 2048000)
            if user.contacted_email is True:
                send_email(user.email, user.first_name, 'upgrade')
        elif plan == 'premium_monthly':
            user.subscription_plan = 5
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
            set_usage_limit(user, 2048000)
            if user.contacted_email is True:
                send_email(user.email, user.first_name, 'upgrade')
        elif plan == 'basic_monthly':
            user.subscription_plan = 2
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
            set_usage_limit(user, 204800)
            if user.contacted_email is True:
                send_email(user.email, user.first_name, 'upgrade')
        elif plan == 'basic_yearly':
            user.subscription_plan = 3
            user.subscription_start_date = dt.datetime.now(dt.timezone.utc)
            user.subscription_latest_roll_over = dt.datetime.now(dt.timezone.utc)
            set_usage_limit(user, 204800)
            if user.contacted_email is True:
                send_email(user.email, user.first_name, 'upgrade')
        else:
            pass
        #     logger.debug("plan not found")
        # logger.debug("%s, %s", user.id, user.subscription_plan)
        db.session.commit()
    except Exception as e:
        # logger.debug(e)
        # logger.debug("error updating plan")
        raise e

def set_usage_limit(user, n):
    new_record = UsageRecord(
        user_id=user.id,
        operation_type="Change plan",
        limit_count=n,
        operation_count=0,
        remaining_count=n,
        date=dt.datetime.now(dt.timezone.utc),
        time_period = "month",
    )
    db.session.add(new_record)
    db.session.commit()