

import eventlet
eventlet.monkey_patch()

import logging
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
from config.settings import DEBUG
from run.bp_register import register_blueprints


logger = logging.getLogger("flask_app")

app = create_app()
##app.config['EXPLAIN_TEMPLATE_LOADING'] = True
login_manager.login_view = 'user_bp.login'


@app.before_request
def redirect_to_https():
    """Redirect HTTP to HTTPS"""
    x_forwarded_proto = request.headers.get('X-Forwarded-Proto')
    if x_forwarded_proto:
        if not app.debug and x_forwarded_proto == 'http':
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
    g.feedback_form = None if request.path == '/deck_bp/import_anki' else FeedbackForm()

###  REGISTERING BLUEPRINTS AFTER REQUESTS
register_blueprints(app)

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
    return redirect(url_for("deck_bp.view_decks")+'?v=' + str(cache_buster))

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
## send notification
        for job in jobs:
            if current_user.contacted_email is True: # type: ignore
                send_email(current_user.email, current_user.first_name,'deck_ready')
          ## mark job as notified
            job.notified = True
            db.session.commit()
    return True

def find_unnotified_jobs(user_id: int) -> list[JobNotification]:
    return JobNotification.query.filter_by(user_id=user_id,complete=True, notified=False).all()

## Look through Job Notification, find items that are not completed for each user
def find_non_complete_job_notifs(user_id: int) -> list[JobNotification]:
    return JobNotification.query.filter_by(user_id=user_id, complete=False).all()
## If not complete 

## Look through jobs for that notification and check if jobs are completed
def find_jobs_by_slug(slug: str):
    return Job.query.filter_by(slug=slug).order_by(Job.id.asc()).all()

def check_jobs_complete(jobs: list[Job]) -> bool:
    counter = 0
    for job in jobs:
        if job.state == "completed":
            counter = counter + 1
    return counter == len(jobs)

def job_error_checker(slug: str) -> bool:
    error_ratio = check_for_errors(slug)
    if error_ratio > 0:
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


def check_for_errors(slug: str) -> float:
    jobs = find_jobs_by_slug(slug)
    error_count = 0
    for job in jobs:
        if job.error_type == "error":
            error_count = error_count + 1
            job.error_type = "error_returned"
        db.session.commit()
    return error_count / len(jobs)


@app.route("/query", methods=["POST"])
@login_required
def query():
    progress = 0
    job_id = request.form["id"]
    data = Job.query.filter_by(slug=job_id).first()
    num_completed = Job.query.filter_by(slug=job_id).filter(Job.state.in_(["completed", "failed"])).count()
    num_total = Job.query.filter_by(slug=job_id).count()
    slug = JobNotification.query.filter_by(slug=job_id).first()
    if num_total != 0:
        progress = int(num_completed/num_total*95)
    if data is None:
        return jsonify({"state": None, "progress": None, "result": None})
    else:
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
    slug_id= request.form["id"]
    slug = JobNotification.query.filter_by(slug=slug_id).first()
    if job_error_checker(slug.slug):
            session.pop('slug', None)
            db.session.commit()
            return jsonify("error")
    if slug.state == 'ready':
        session.pop('slug', None)
        slug.state = 'notified'
        db.session.commit()
        try:
            send_email(current_user.email, current_user.first_name,'deck_ready')
        except Exception as e:
            logger.error("error sending email", e)
        session.pop('slug', None)

        return jsonify("success")
 

if __name__ == "__main__":
    app.run(debug=DEBUG)
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
