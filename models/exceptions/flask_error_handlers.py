from flask import flash, redirect, url_for
from flask_login import current_user
from models.tracking.events import event_tracker
import logging
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from werkzeug.wrappers import Response


logger = logging.getLogger("flask_app")


def handle_audio_error(e) -> 'Response':
    event_tracker(current_user.id, 'extract_start', 'fail', 'audioerror')
    flash('We were unable to extract the text from the audio file. Please try another file or contact us for assistance.')
    logger.error(f"Audio error {e}")
    return redirect(url_for('extract'))

def handle_youtube_error(e) -> 'Response':
    event_tracker(current_user.id, 'extract_start', 'fail', 'youtubeerror')
    flash('We were unable to extract the text from the link. A small minority of youtube videos do not allow text extraction. Please try another link or contact us for assistance.')
    logger.error(f"Youtube error {e}")
    return redirect(url_for('extract'))

def handle_file_not_found_error(e) -> 'Response':
    flash("File not found. Please try again.")
    event_tracker(current_user.id, 'extract_start', 'fail', 'filenotfound')
    logger.error(f"File not found {e}")
    return redirect(url_for('extract'))

def handle_unknown_error(e) -> 'Response':
    logger.error(e)
    event_tracker(current_user.id, 'extract_start', 'fail', 'unknown')
    flash('Something went wrong. This error has been logged and we are now investigating the cause.  Please try again or contact us for assistance')
    return redirect('/extract')
