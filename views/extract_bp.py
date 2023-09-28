
import logging
from flask import (
    Blueprint, render_template, flash,
    redirect, session, url_for, jsonify
)
from flask_login import login_required, current_user
from models.user.user_settings import UserSettings
from models.extractors.extractor import Extractor, tokens_general
from models.exceptions.flask_error_handlers import (
    handle_audio_error, handle_youtube_error,
    handle_file_not_found_error, handle_unknown_error
)
from models.tracking.events import event_tracker
from models.forms.forms import UploadFileForm
from models.exceptions.exceptions import YoutubeError, AudioError
from run.extensions import db
from models.helpers.log_decorators import log_decorator
from config.settings import TOKENS_PER_PAGE

logger = logging.getLogger("flask_app")

extract_bp = Blueprint(
    'extract_bp', 
    __name__,
    template_folder='templates/extract_bp',
    static_folder='static'
)

@extract_bp.route("/extract", methods = ["GET", "POST"])
@login_required
@log_decorator
def extract():
    user_settings = initialize_user_settings()
    ## plan level requried for genereting images
    form = UploadFileForm()
    if form.validate_on_submit():
        extract_obj = Extractor(db.session, form)
        session['slug'] = extract_obj.slug
        try:
            extract_obj.get_content()
            deck, new_deck_created = extract_obj.get_deck(form)
            if new_deck_created:
                db.session.add(deck)
                db.session.commit()
            extract_obj.quantity_tokens()
            if current_user.perform_operation('extract', extract_obj.tokens) is False:
                db.session.delete(extract_obj.deck)
                db.session.commit()
                flash('You have reached your monthly usage limit.'
                'Please upgrade your account to continue.')
                event_tracker(current_user.id, 'extract_start',
                            'fail', "limit_reached")
                return redirect(url_for('user_bp.upgrade'))
            extract_obj.save_source_text()
            extract_obj.create_jobs()
        except AudioError as e:
            handle_audio_error(e)
            raise e
        except YoutubeError as e:
            handle_youtube_error(e)
            raise e
        except FileNotFoundError as e:
            handle_file_not_found_error(e)
            raise e
        except Exception as e:
            handle_unknown_error(e)
            raise e
        return redirect('/deck_bp/view_decks')
    return render_template("extract_bp/extract.html", title="Extract", form=form,
                            settings = user_settings)


@extract_bp.route("/call_credit_counter", methods = ["POST"])
@log_decorator
def call_credit_counter():
    form = UploadFileForm()
    try:
        credit = round(tokens_to_credit(tokens_general(form)), 1)
        return jsonify(credit)
    except YoutubeError as e:
        raise YoutubeError from e
    except FileNotFoundError as e:
        flash("File not found. Please try again.")
        redirect(url_for('extract_bp.extract'))
        raise e
    except Exception as e:
        logger.error(f"general exception in call credit counter {e}")
        raise e

def tokens_to_credit(tokens):
    return tokens / TOKENS_PER_PAGE


def initialize_user_settings():
    user_settings = UserSettings.query.filter_by(user=current_user.id).first()
    if user_settings is None:
        user_settings = UserSettings(user=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
    return user_settings