

import logging
import logging.handlers
import logging.config
import datetime as dt
import random
from flask import g, redirect, render_template, request, session
from flask import url_for, send_file, jsonify
from flask_login import login_required, current_user
from models.models_ import (
    Job, JobNotification, UsageRecord, User
)
from models.forms.forms import TryOut, FeedbackForm
from models.send_email import send_email
from flask_wtf.csrf import generate_csrf
from factory import create_app
from run.extensions import db, login_manager, socketio

app = create_app()
app.config['EXPLAIN_TEMPLATE_LOADING'] = True

logger = logging.getLogger('flask_app')  # Logs to 'app.log'

@app.before_request
def redirect_to_https():
    """Redirect HTTP to HTTPS"""
    if not app.debug and request.headers.get('X-Forwarded-Proto', 'http') == 'http':
        url = request.url.replace('http://', 'https://', 1)
        return redirect(url, code=301)

@app.context_processor
def inject_csrf_token():
    """Inject CSRF token into templates"""
    return dict(csrf_token=generate_csrf())

@login_manager.user_loader
def load_user(user_id):
    """Load user from database"""
    return User.query.get(int(user_id))

logger.debug("app started")

@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade" ## ONLY FOR http AND LOCALHOST, FOR GOOGLE AUTH
    return response    

@app.before_request
def before_request():
    """Addressing bug with import anki and feedback form"""
    g.feedback_form = None if request.path == '/import_anki' else FeedbackForm()

@app.route('/robots.txt')
def robots():
    """For indexing"""
    return send_file('static/robots.txt')

@app.route('/sitemap.xml')
def sitemap():
    """For indexing"""
    return send_file('static/sitemap.xml')

@app.route("/", methods=["GET", "POST"])
def index():
    """Home page"""
    form = TryOut()
    if not current_user.is_authenticated: # type: ignore
        return render_template('index.html', form=form)
    cache_buster = random.randint(1, 999999)
    return redirect(url_for("deck_bp.viewdecks")+'?v=' + str(cache_buster))

@app.route('/testing1', methods = ['GET', 'POST'])
def testing1():
    """test page"""
    return render_template('testing1.html')
        
@app.route('/update_sidebar_state', methods=['POST'])
def update_sidebar_state():
    """Toggle side bar state"""
    is_collapsed = request.form.get('sidebar-collapsed') == 'true'
    session['sidebar-collapsed'] = is_collapsed
    return '', 204  # return 204 No Content response

@app.route("/landingpage", methods = ["GET", "POST"])
def landingpage():
    """ landing page, deprecated"""
    return render_template("landingpage.html", title="Landing Page")


def notify(user_id):
## find unnotified jobs  
    if jobs := find_unnotified_jobs(user_id):
        print("unnotified jobs", jobs)
## send notification
        for job in jobs:
            if current_user.contacted_email is True: # type: ignore
                send_email(current_user.email, current_user.first_name,'deck_ready')
          ## mark job as notified
            job.notified = True
            db.session.commit()
    return True

def find_unnotified_jobs(user_id):
    return JobNotification.query.filter_by(user_id=user_id,complete=True, notified=False).all()

## Look through Job Notification, find items that are not completed for each user
def find_non_complete_job_notifs(user_id):
    return JobNotification.query.filter_by(user_id=user_id, complete=False).all()
## If not complete 

## Look through jobs for that notification and check if jobs are completed
def find_jobs_by_slug(slug):
    return Job.query.filter_by(slug=slug).order_by(Job.id.asc()).all()

def check_jobs_complete(jobs):
    counter = 0
    for job in jobs:
        if job.state == "completed":
            counter = counter + 1
    return counter == len(jobs)

def job_error_checker(slug):
    print(slug)
    error_ratio = check_for_errors(slug)
    print("error ratio", error_ratio)
    if error_ratio > 0:
        print("Recognized error")
        job_notification = JobNotification.query.filter_by(slug=slug).first()
        credit = current_user.remaining_credit() * 341 + job_notification.cost + 3410
        new_usage_record = UsageRecord(user_id=job_notification.user_id,
            date=dt.datetime.now(dt.timezone.utc), operation_type="credit",
            operation_details="credit for job error", operation_count=0,
            remaining_count = credit, status="active", time_period="month",
            limit_count = credit)
        db.session.add(new_usage_record)
        db.session.commit()
        return True
    else:
        return False


def check_for_errors(slug):
    jobs = find_jobs_by_slug(slug)
    print(f"jobs {jobs}, slug {slug}")
    error_count = 0
    for job in jobs:
        if job.error_type == "error":
            error_count = error_count + 1
            job.error_type = "error_returned"
            
            print("error found")
        db.session.commit()
    return error_count / len(jobs)

## if not wait
## if they are completed check if need to be reassembled and turned into a file
## if not change each jobs result to 1
## if so reassemble and turn into file
## after assembling into a file change job result to 1
## if all jobs are complete and have result of 1, then change notification to complete

##def file_assembler(user_id):
  ##  print("entered file assembler route")
 ##   job_finisher(user_id)
  ##  notify(user_id)
  ##  return jsonify({"success": True})

@app.route("/query", methods=["POST"])
@login_required
def query():
    progress = 0
    job_id = request.form["id"]
    # Now we can ask database about the state of that request
    data = Job.query.filter_by(slug=job_id).first()
    num_completed = Job.query.filter_by(slug=job_id, state="completed").count()
    num_total = Job.query.filter_by(slug=job_id).count()
    slug = JobNotification.query.filter_by(slug=job_id).first()

    if num_total != 0:
        progress = int(num_completed/num_total*95)
           
    if data is None:
        return jsonify({"state": None, "progress": None, "result": None})
    return jsonify(
        {
            "state": data.state,
            "progress": progress,
            "result": slug.state,
        }
    )


@app.route("/notification_complete", methods=["POST"])
@login_required
def notification_complete():
    logger.debug("entered notification")
    print("entered notification")
    slug_id= request.form["id"]
    slug = JobNotification.query.filter_by(slug=slug_id).first()
    print("state is", slug.state)
    if job_error_checker(slug.slug):
            print("entered error checker")
            session.pop('slug', None)
            db.session.commit()
            return jsonify("error")
    if slug.state == 'ready':
        print("job notification complete is true")

        send_email(current_user.email, current_user.first_name,'deck_ready')

        session.pop('slug', None)
        slug.state = 'notified'
        db.session.commit()
        return jsonify("success")
 




if __name__ == "__main__":
    app.run(debug=True)
    socketio.run(app)

else:
    # For Alembic
    ## from run.extensions import db
    db.init_app(app)


##objgraph.show_growth()

##@app.after_request
##def analyze_memory(response):
  ##  objgraph.show_most_common_types(limit=10)
  ##  objgraph.show_growth()

   ## return response

    """
def assemble_file(total_jobs):
    print("entered assemble file route")
    try:
        deck = Deck.query.get_or_404(total_jobs[0].deck_id)
        task_type = total_jobs[0].task_type
        full_text = ""
        for job in total_jobs:
            full_text += job.processed_content
        if task_type == "Turn2notes":
            chosen_name = f"{random.choice(NOTES_FILE_NAMES)} {task_type}"
        elif task_type == "Transcribe":
            chosen_name = f"{random.choice(TRANSCRIPTION_FILE_NAMES)} {task_type}"
        elif task_type == "Summarize":
            chosen_name = f"{random.choice(SUMMARY_FILE_NAMES)} {task_type}"
        else:
            chosen_name = f"{random.choice(SOURCE_FILE_NAMES)} {task_type}"
        rand_int = random.randint(1, 99)
        name = f"{chosen_name}_{rand_int}"
        existing_file = DeckFiles.query.filter_by(file_name=name).first()
        print(f"File already exists {existing_file}")
        if not existing_file:
            print("no existing file, creating one")

            name = chosen_name
            file_storage = DeckFiles(file_name=name, text_string=full_text,
                                    create_type = task_type,
                                    time_created = dt.datetime.now(dt.timezone.utc))
            db.session.add(file_storage)
            deck.deck_files.append(file_storage)
            db.session.commit()
    except Exception as e:
        logger.debug("error assembling file %s", e)
        raise e
"""


"""
def job_finisher(user_id):
    if not (incomplete_jobs_notifs := find_non_complete_job_notifs(user_id)):
        return
    print("incomplete jobs notifs", incomplete_jobs_notifs)
    for incomplete_job_notif in incomplete_jobs_notifs:
        jobs = find_jobs_by_slug(incomplete_job_notif.slug)
        print(jobs)
        if check_jobs_complete(jobs):
            print("jobs complete")
            assembly_jobs = []
            audio_transcript = []
            for job in jobs:
                print(job)
                if job.task_type == "audio" and job.save_source is True:
                    audio_transcript.append(job)
                if job.task_type in ["Turn2notes", "Transcribe", "Summarize"]:
                    assembly_jobs.append(job)
                job.result = 1
            if assembly_jobs:
                assemble_file(assembly_jobs)
            if audio_transcript:
                assemble_file(audio_transcript)
            db.session.commit()
            incomplete_job_notif.complete = True
            db.session.commit()
"""


"""
if form.validate_on_submit():
    
    logger.debug("form validated")
    text = clean(form.select_text.data)
    prompt_options = {
        'main_opt': clean(form.prompt.data) or None,
        'trans_opt': clean(form.languages.data) or None,
        'lang_opt': None,
        'detail_lvl_opt': "long",
        'min_opt':  None,
        'max_opt':  None,
        'images_opt':  None,
        'save_text_opt':  None,
        'subject_opt':  None,
        'custom_term':  clean(form.custom_term.data) or None,
        'custom_content': clean(form.custom_content.data) or None,
    }
    logger.debug(prompt_options)
    
    response = creator(text, prompt_options)
    terms = response[0]
    for item in terms:
        logger.debug(item['A'])
        logger.debug(item['B'])
    event_tracker(None, "tryout", json.dumps(prompt_options), json.dumps(terms))
    return render_template('index.html', form = form,
                            terms = terms, option = prompt_options['main_opt'])
"""
"""
@app.route('/generate_img/<int:deck_id>', methods=['GET', 'POST'])
@login_required
def generate_img(deck_id):
    c_deck_id = deck_id
    event_tracker(current_user.id, "generate_img", c_deck_id)
    deck = Deck.query.get(c_deck_id)
    if(current_user.id != deck.user_id):
         return apology('Deck not assigned to user', 403)
    if deck is None:
        return apology('Deck not found', 404)
    for card in deck.cards:
        try:
            card.img = create_image(card.term)
            db.session.commit()
        except:
            pass
    return redirect(("/currentdeck/{deck}").format(deck=deck_id))
"""       
"""
def is_valid_audio(file_storage):
    try:
        # Attempt to load audio file
        audio = AudioSegment.from_file(file_storage, format=file_storage.filename.split('.')[-1])
        logging.info("Valid audio file")
        return True
    except Exception as e:
        logging.info("Invalid audio file %s", e)
        return False

"""