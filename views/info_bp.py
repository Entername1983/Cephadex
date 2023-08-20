import logging
from flask import Blueprint, render_template

logger = logging.getLogger("flask_app")

info_bp = Blueprint(
    'info_bp', 
    __name__,
    template_folder='templates/info_bp',
    static_folder='static'
)

@info_bp.route("/legal", methods = ["GET", "POST"])
def legal():
    return render_template('/info_bp/legal.html', title='Legal')

@info_bp.route('/pricing', methods=['GET', 'POST'])
def pricing():
    return render_template('/info_bp/pricing.html')

@info_bp.route("/terms_and_conditions")
def terms_and_conditions():
    return render_template("/info_bp/terms_and_conditions.html", title="Terms and Conditions")

@info_bp.route("/documentation/", methods=['GET', 'POST'])
def documentation():
    return render_template('/info_bp/documentation.html')

@info_bp.route("/news/", methods=['GET', 'POST'])
def news():
    return render_template('/info_bp/news.html')


@info_bp.route("/about/", methods=['GET', 'POST'])
def about():
    return render_template('/info_bp/about.html')

##@info_bp.route("/team", methods=['GET', 'POST'])
##def team():
    ##return render_template('team.html')