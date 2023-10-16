import logging
from flask import Blueprint, render_template
from models.models_ import BlogPost
from flask import jsonify

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


@info_bp.route("/faq/", methods=['GET', 'POST'])
def faq():
    return render_template('/info_bp/faq.html')

##@info_bp.route("/team", methods=['GET', 'POST'])
##def team():
    ##return render_template('team.html')



@info_bp.route('/blog', methods=['GET'])
@info_bp.route('/blog/<slug>', methods=['GET'])
def blog(slug=None):
    if slug:
        return render_template('/info_bp/blog.html', slug=slug)
    else:

        return render_template('/info_bp/blog.html')

def get_post_by_slug(slug):
    post = BlogPost.query.filter_by(slug=slug).first()
    return post

@info_bp.route('/api_0/blog/<slug>', methods=['GET'])
def blog_post_api(slug):
    if slug == "latest" or slug == "blog":
        post = get_latest_post()
    else:
        post = get_post_by_slug(slug)
    if post:
        return post.to_json(), 200
    else:
        return jsonify({"error": "Post not found"}), 404
    
@info_bp.route('/api_0/blog/fetch_list_all_posts', methods=['GET'])
def fetch_list_all_posts():
    post_titles_and_slugs = []
    blog_posts = BlogPost.query.order_by(BlogPost.time_created.desc()).all()
    for post in blog_posts:
        post_titles_and_slugs.append({'title': post.title, 'slug': post.slug, 'summary': post.summary})
    return jsonify(post_titles_and_slugs), 200

def get_latest_post():
    post = BlogPost.query.order_by(BlogPost.time_created.desc()).first()
    return post