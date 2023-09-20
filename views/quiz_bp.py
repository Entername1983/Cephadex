
from datetime import datetime
import datetime as dt
from urllib.parse import unquote
import difflib
from io import BytesIO
import requests as req
from urllib.parse import urljoin
import xhtml2pdf.pisa as pisa
import random
import uuid
import logging
from flask import (
    Blueprint, render_template, url_for, make_response,
    flash, redirect, request, jsonify, session
)
from flask_login import login_required, current_user
####from cardcreator import create_image, creator
from bleach import clean

from models.creators.formatters import check_comma_list
from models.helpers.helpers import remove_punctuation
from models.tracking.events import event_tracker
from models.qr_code import create_qr_code
from models.forms.forms import BuildTest, UpdateCardForm

from models.models_ import (
    QuestionResult, Question, Test, TestResult, User, 
    questions, distribution, cards,
    UserSettings, Deck, Card
)

from run.extensions import db
from tools.lists import TEST_NAMES
from config.settings import APP_URL

from models.helpers.log_decorators import log_decorator

logger = logging.getLogger("flask_app")

quiz_bp = Blueprint(
    'quiz_bp', 
    __name__,
    template_folder='templates/quiz_bp',
    static_folder='static'
)

@quiz_bp.route('/update_card', methods=['POST'])
@login_required
@log_decorator
def update_card():
    data = request.get_json()
    form = UpdateCardForm(data=data)
    question_id = data['question-id']
    question = Question.query.filter_by(id=question_id).first_or_404()
    try:
        if data['question'] != '':
            question.question = clean(data['question'])
        if data['answer'] != '':
            question.term = clean(data['answer'])
        if data['answer'] != '':
            question.content = clean(data['answer'])
        if data['points'] != '':
            question.points = data['points']
        # Handle multiple choice options
        if question.q_type == 'mcq':
            if data['boc_2'] != '':
                question.boc_2 = clean(data['boc_2'])
            if data['boc_3'] != '':
                question.boc_3 = clean(data['boc_3'])
            if data['boc_4'] != '':
                question.boc_4 = clean(data['boc_4'])
        db.session.flush()
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Quiz - Error in updating quiz card {e}")
        raise e
    ## TO DO how to handle htis, was it necessary?
    # finally:
    #     return jsonify(success=False, error=str(e))

@quiz_bp.route("/download/<int:quiz_id>")
@login_required
@log_decorator
def download(quiz_id):
    # Get HTML content
    quiz_url = url_for('quiz_print', quiz_id=quiz_id, _external=True)
    response = req.get(quiz_url)
    html_content = response.content

    # Create a pdf buffer
    pdf = BytesIO()

    # Define the link fetcher
    def fetch_resources(uri, rel):
        # Here the base URL should be the URL to the quiz_print page
        return req.get(urljoin(quiz_url, uri)).content

    # Then pass that HTML to CreatePDF
    pisa.CreatePDF(BytesIO(html_content), pdf, link_callback=fetch_resources)

    return make_response(pdf.getvalue(), 200,
                         {
                             'Content-Type': 'quiz_bplication/pdf',
                             'Content-Disposition': 'attachment; filename=output.pdf'
                         })




@quiz_bp.route("/delete_question/<int:quiz_id>/<int:question_id>", methods=["POST", "GET"])
@login_required
@log_decorator
def delete_question(quiz_id, question_id):
    c_quiz_id = quiz_id
    c_question_id = question_id
    question_to_delete = Question.query.get_or_404(c_question_id)
    # Delthe rows in the questions table that reference the question row you want to del
    db.session.execute(questions.delete()
                       .where(questions.c.question_id == c_question_id))
    # Now you can safely delete the row from the question table
    db.session.delete(question_to_delete)
    db.session.commit()
    return redirect(('/quiz_bp/assign_quiz/{quiz_id}'.format(quiz_id=c_quiz_id)))

@quiz_bp.route("/delete_quiz/<int:quiz_id>/", methods = ["POST", "GET"])
@login_required
@log_decorator
def delete_quiz(quiz_id):
    c_quiz_id = quiz_id
    quiz_to_delete = Test.query.get_or_404(c_quiz_id)
    if current_user.id == quiz_to_delete.creator:
        db.session.delete(quiz_to_delete)
        db.session.commit()
    return redirect('/quiz_bp/quiz_overview/')



@quiz_bp.route("/build_quiz/<int:deck_id>", methods=["GET", "POST"])
@log_decorator
def build_quiz(deck_id):
    settings = UserSettings.query.filter_by(user=current_user.id).first()
    event_tracker(current_user.id, "build_quiz", deck_id)
    deck = Deck.query.get_or_404(deck_id)
    creator = current_user
    
    if request.method == "POST":
        form_data = request.form.to_dict()
        quiz_questions = request.form.getlist('selected_cards[]')
        jeopardyMode = form_data.get('jeopardyMode')
        chosen_name = random.choice(TEST_NAMES)
        new_quiz = Test(creator=current_user.id, deck_id=deck.id, name=chosen_name)
        db.session.add(new_quiz)

        for question_id in quiz_questions:
            card = Card.query.get_or_404(question_id)
            add_question_to_quiz(card, new_quiz, jeopardyMode)
            print(question_id)

        db.session.commit()
        return redirect(f'/quiz_bp/assign_quiz/{new_quiz.id}')

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 4
    paginated_cards = (
        db.session.query(Card)
        .join(cards, cards.c.card_id == Card.id)
        .filter(cards.c.deck_id == deck_id)
        .paginate(page, per_page, False)
    )
    return render_template('/quiz_bp/build_quiz.html',
                           title='Quiz Builder', deck=deck, creator=creator, settings=settings,
                paginated_cards=paginated_cards,
 page=page)




def add_question_to_quiz(card, new_quiz, jeopardyMode):
    question = Question()
    print(new_quiz)
    print(question)
    db.session.add(question)
    question.points = 1
    question.content = card.content
    question.term = card.term
    question.prompt_option = card.prompt_option
    # Mapping the card categories to question types
    category_to_q_type = {
        'Mcq': 'mcq',
        'Cloze': 'cloze',
        'Explain': 'explain',
        'Formulas': 'formulas',
        'Discuss': 'discuss',
        'Definitions': 'jeopardy' if jeopardyMode == 'on' else 'definitions',
    }
    question.q_type = category_to_q_type.get(card.category, 'other')
    if card.category == "Mcq":
        question.question = card.term
        question.boc_2 = card.boc_2
        question.boc_3 = card.boc_3
        question.boc_4 = card.boc_4
    elif card.category == "Cloze":
        question.question = card.term
    elif card.category == "Explain":
        question.question = card.term
    elif card.category == "Formulas":
        question.question = card.term
        question.term = card.formula
    elif card.category == "Discuss":
        question.question = card.term
        question.boc_2 = card.boc_2
    elif card.category == "Definitions":
## switching them around so that the quiz gives them a definition and they have to write the word
        if jeopardyMode == "on":
            question.question = card.content
            question.term = card.term
        else:
            question.question = card.term
    else:
        question.question = card.term
    new_quiz.questions.append(question)
        
    print(f"appending question {question.term} to quiz {new_quiz.id}")

## TO DO: rework this so it doesn't throw an exception when it doesn't find a user, bad practice

@quiz_bp.route("/assign_quiz/<int:quiz_id>", methods=["GET", "POST"])
@log_decorator
def assign_quiz(quiz_id):
    settings = UserSettings.query.filter_by(user=current_user.id).first()
    update_card_form = UpdateCardForm(request.form)
    form = BuildTest()
    page = request.args.get('page', 1, type=int)
    per_page = 4
    paginated_questions = (
        db.session.query(Question)
        .join(questions, questions.c.question_id == Question.id)
        .filter(questions.c.test_id == quiz_id)
        .paginate(page, per_page, False)
    )
    print(f"paginated questions {paginated_questions.items}")
    try:
        event_tracker(current_user.id, "assign_quiz", quiz_id)
        quiz = Test.query.get_or_404(quiz_id)
        if request.method == 'POST' and 'name' in request.form:
            update_quiz_properties(quiz, form)
            db.session.commit()
            flash(f'Test: "{quiz.name}" has been updated!', 'success')
        return render_template('/quiz_bp/assign_quiz.html', title='Assign quiz',
                quiz=quiz, form = form, update_card_form = update_card_form, settings = settings,
                paginated_questions = paginated_questions, page = page)
    
    except Exception as e:
        logger.error(f"Quiz - Error assigning quiz {e}")
        raise e        
        ##flash("At this moment you can only assign quizzes to other users.  We are working on allowing you to assign quizzes to non-users")
        # return render_template('/quiz_bp/assign_quiz.html', title='Assign quiz',
        #         quiz=quiz, form = form, update_card_form = update_card_form,
        #         settings = settings)


def update_quiz_properties(quiz, form):
    quiz.name = form.name.data
    quiz.creator = current_user.id
    quiz.due_date = dt.datetime.strptime(request.form['due_date'][:16], '%Y-%m-%dT%H:%M') if request.form['due_date'] else None
    quiz.subject = form.subject.data
    quiz.topic = form.topic.data
    quiz.instructions = form.instructions.data
    quiz.description = form.description.data
    quiz.time_limit = int(form.time_limit.data) if form.time_limit.data else None
    quiz.answer_reveal = form.reveal_answers.data == 'answer-reveal'
    quiz.result_reveal = form.reveal_results.data == 'result-reveal'
    quiz.shuffle = form.shuffle.data == 'shuffle'
    quiz.count_questions()
    quiz.sum_points()




@quiz_bp.route('/shared_quiz_view/<string:share_id>', methods=['GET'])
@log_decorator
def shared_quiz_view(share_id):
    quiz = Test.query.filter_by(share_id=share_id).first_or_404()
    session['shared_quiz_id'] = share_id
    return render_template('/quiz_bp/shared_quiz_view.html', quiz=quiz)

@quiz_bp.route('/generate_link_quiz/<int:quiz_id>', methods=['GET'])
@login_required
@log_decorator
def generate_link_quiz(quiz_id):
    quiz = Test.query.get(quiz_id)
    if quiz.share_id:
        link = f'{APP_URL}/quiz_bp/shared_quiz_view/{quiz.share_id}'
        img_str = create_qr_code(link)
        return jsonify(
            {
                'share_link': f'{APP_URL}/quiz_bp/shared_quiz_view/{quiz.share_id}',
                'qr_code': img_str,
            }
        )
    else:
        share_id = str(uuid.uuid4())
        quiz.share_id = share_id
        db.session.commit()
        link = f'{APP_URL}/quiz_bp/shared_quiz_view/{quiz.share_id}'

        img_str = create_qr_code(link)

        return jsonify(
            {
                'share_link': f'{APP_URL}/quiz_bp/shared_quiz_view/{share_id}',
                'qr_code': img_str,
            }
        )


@quiz_bp.route("/assign/<int:quiz_id>/<string:user_email>/", methods=["GET", "POST"])
@log_decorator
@login_required
def assign(quiz_id, user_email):
    c_quiz_id = quiz_id
    c_user_email = clean(user_email)
    quiz = Test.query.filter_by(id=c_quiz_id).first()
    quiz.count_questions()
    quiz.sum_points()
    not_users = []
    if check_comma_list(c_user_email):
        users_emails = user_email.split(",")
        for email in users_emails:
            email = unquote(email).strip()
            taker = User.query.filter_by(email=email).first()
            if taker is None:
                not_users.append(email)
            else:
                quiz.taker.append(taker)
    else:
        email = unquote(c_user_email)
        taker = User.query.filter_by(email=email).first()
        if taker is None:
            not_users.append(email)


        else:
            quiz.taker.append(taker)
            print(f"taker is {taker.email}")
    db.session.commit()
    if not not_users:
        flash('Quiz assigned!', 'success')
    else:
        flash(f"Could not locate the following users: {not_users}.  Currently you can only assign to other users", "danger")  # noqa: E501
    return redirect('/quiz_bp/assign_quiz/{quiz_id}'.format(quiz_id = c_quiz_id))





@quiz_bp.route("/take_quiz_2/<share_id>/<int:user_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def take_quiz_2(share_id, user_id):
    event_tracker(current_user.id, "take_quiz", share_id)
    quiz = Test.query.filter_by(share_id=share_id).first_or_404()
    quiz_result = TestResult.query.filter_by(quiz_id = quiz.id, taker = user_id).first()

    if request.method == 'POST':
        for question in quiz.questions:
            question_id = question.id
            to_call = f"answer{str(question_id)}"
            answer = request.form.get(to_call, '')
            answer = answer.strip()
            result = QuestionResult(quiz_id = quiz.id,
                                    taker = current_user.id,
                                    question_id = question.id, answer = answer)
            db.session.add(result)
            db.session.commit()
        end_time = request.form.get('end-time')
        end_time = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S.%fZ')
        quiz_result.end_time = end_time
        db.session.commit()
        return redirect('/quiz_bp/quiz_results/{quiz_id}/{user_id}'.format
                        (quiz_id = quiz.id, user_id = user_id))

    else:
        if quiz_result is None:
            start_time = dt.datetime.now(dt.timezone.utc)
            quiz_result = TestResult(quiz_id = quiz.id,
                                    taker = user_id, start_time = start_time,
                                    creator=quiz.creator)
            taker = User.query.get_or_404(user_id)
            db.session.add(quiz_result)
            db.session.commit()
            return render_template('quiz_bp/take_quiz.html',
                            quiz=quiz, taker=taker, start_time = start_time)
        else:
            ## TO DO - RESOLVE THE ISSUE OF NOT BEING ABLE TO REMOVE THE CURRENT USER
            try:
                quiz.taker.remove(current_user)
                db.session.commit()
            except Exception as e:
                logger.error(f"could not remove user from quiz: {e}")
            flash('you have already taken this quiz', 'danger')
            return redirect('/quiz_bp/quiz_overview/')
        
@quiz_bp.route("/take_quiz/<int:quiz_id>/<int:user_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def take_quiz(quiz_id, user_id):
    if user_id != current_user.id:
        flash('You do not have permission to take this quiz', 'danger')
        return redirect('/quiz_bp/quiz_overview/')
    event_tracker(current_user.id, "take_quiz", quiz_id)
    start_time = dt.datetime.now(dt.timezone.utc)
    quiz = Test.query.get_or_404(quiz_id)

    quiz_result = TestResult(test_id = quiz_id,
                            taker = user_id, start_time = start_time,
                            creator=quiz.creator)    
    if request.method == 'POST':
        for question in quiz.questions:
            question_id = question.id
            to_call = f"answer{str(question_id)}"
            answer = request.form.get(to_call, '')
            answer = answer.strip()
            result = QuestionResult(test_id = quiz.id,
                taker = current_user.id, question_id = question.id,
                answer = answer, quiz_result_id = quiz_result.id)
            db.session.add(result)
            db.session.commit()
        end_time = request.form.get('end-time')
        end_time = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S.%fZ')
        quiz_result.end_time = end_time
        db.session.commit()
        return redirect('/quiz_bp/quiz_results/{quiz_id}/{user_id}'.format
                        (quiz_id = quiz_id, user_id = user_id))
    taker = User.query.get_or_404(user_id)
    db.session.add(quiz_result)
    db.session.commit()
    return render_template('quiz_bp/take_quiz.html',
                    quiz=quiz, taker=taker, start_time = start_time)
        ##else:
          ##  quiz.taker.remove(current_user)
         ##   db.session.commit()
           ## flash('you have already taken this quiz', 'danger')
          ##  return redirect('/quiz_overview/')

@quiz_bp.route('/reject_quiz/<int:quiz_id>/<int:user_id>', methods=['DELETE'])
@log_decorator
def reject_quiz(quiz_id, user_id):
    distribution_entry = distribution.delete().where(
        (distribution.c.test_id == quiz_id) & (distribution.c.taker_id == user_id)
    )
    db.session.execute(distribution_entry)
    db.session.commit()
    return jsonify({'message': 'Test deleted successfully'}), 200

# @quiz_bp.route("/quiz_results/<int:quiz_id>/<int:user_id>/", methods=["GET", "POST"])
# @login_required
# @log_decorator
# def quiz_results(quiz_id, user_id): 
#     c_quiz_id = quiz_id
#     c_user_id = user_id      
#     point_counter = 0
#     correct_counter = 0
#     quiz = Test.query.get_or_404(c_quiz_id)
#     creator = quiz.creator
#     taker = User.query.get_or_404(c_user_id)
#     graded_results = []
#     for question in quiz.questions:
#         answer = QuestionResult.query.filter_by(test_id = c_quiz_id,
#                                 taker = c_user_id, question_id = question.id).first()
#         if answer.answer:
#             answer_given = remove_punctuation(answer.answer).lower().strip()
#             if question.q_type == "jeopardy":
#                 answer_expected = remove_punctuation(question.term).lower().strip()
#             else:
#                 answer_expected = remove_punctuation(question.content).lower().strip()
#             matcher = difflib.SequenceMatcher(None, answer_given.lower(),
#                                             answer_expected.lower())
#             if matcher.ratio() > 0.9:
#                 point_counter += question.points
#                 correct_counter += 1
#                 answer.points = int(question.points)
#             else:
#                 answer.points = 0
#         if not answer.points:
#             answer.points = 0
#         graded_results.append({'question': question, 'result': answer})
#     quiz = db.session.query(Test).filter_by(id=c_quiz_id).first()
#     quiz_result = TestResult.query.filter_by(test_id = c_quiz_id,
#                                             taker = c_user_id).first()
#     quiz_result.points = point_counter
#     quiz_result.correct = correct_counter
#     quiz_result.correct = creator
#     taker = current_user
#     if taker in quiz.taker:
#         quiz.taker.remove(taker)
#     db.session.add(quiz_result)
#     db.session.commit()
#     return render_template('quiz_bp/quiz_results.html', quiz=quiz,
#                             taker=taker, results=quiz_result)    


def calculate_points(answer_given, answer_expected):
    answer_given = remove_punctuation(answer_given).lower().strip()
    answer_expected = remove_punctuation(answer_expected).lower().strip()
    matcher = difflib.SequenceMatcher(None, answer_given, answer_expected)
    return matcher.ratio()

def grade_quiz(quiz, taker_id):
    point_counter = 0
    correct_counter = 0
    graded_results = []
    for question in quiz.questions:
        correct = False
        answer = QuestionResult.query.filter_by(
            test_id=quiz.id, taker=taker_id, question_id=question.id
        ).first()
        if answer and answer.answer:
            answer_given = answer.answer
            answer_expected = question.term if question.q_type == "jeopardy" else question.content
            if calculate_points(answer_given, answer_expected) > 0.9:
                point_counter += question.points
                correct_counter += 1
                answer.points = int(question.points)
                correct = True
            else:
                answer.points = 0

        graded_results.append({'question': question, 'result': answer, 'correct': correct})
    return point_counter, correct_counter, graded_results

@quiz_bp.route("/quiz_results/<int:quiz_id>/<int:user_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def quiz_results(quiz_id, user_id):
    page = request.args.get('page', 1, type=int)
    per_page = 5
    quiz = Test.query.get_or_404(quiz_id)
    taker = User.query.get_or_404(user_id)
    point_counter, correct_counter, graded_results = grade_quiz(quiz, taker.id)
    quiz_result = TestResult.query.filter_by(test_id=quiz_id, taker=user_id).first()
    quiz_result.points = point_counter
    quiz_result.correct = correct_counter
    if taker in quiz.taker:
        quiz.taker.remove(taker)
    db.session.commit()
    graded_results_paginations = Pagination(graded_results, page, per_page)

    return render_template('quiz_bp/quiz_results.html', quiz=quiz, quiz_result = quiz_result, taker=taker, results = graded_results_paginations)




@quiz_bp.route("/quiz_results_overview/", methods=["GET", "POST"])
@log_decorator
# sourcery skip: no-loop-in-quizzes
def quiz_results_overview():
    quizzes_created = Test.query.filter_by(creator = current_user.id).all()
    ## results of quizzes taken
    ## results of quizzes given

    quiz_results_taken = TestResult.query.filter_by(taker = current_user.id).all()
    quizzes = []    

    for result in quiz_results_taken:
        quiz = Test.query.filter_by(id=result.test_id).first()
        quizzes.append(quiz)
    ## if the quiz has been deleted and there are are no results for user then delete

    quiz_results_given = TestResult.query.filter_by(creator = current_user.id).all()
    for result in quiz_results_given:
        exist_quiz = Test.query.filter_by (id = result.test_id).first()
        if not exist_quiz:
            if not quiz.taker:
                db.session.delete(quiz)
                db.session.commit()
    return render_template('quiz_bp/quiz_results_overview.html',
                            taken = quiz_results_taken,
                            given = quiz_results_given,
                            created = quizzes_created,quizzes=quizzes)



@quiz_bp.route("/quiz_overview/", methods=["GET", "POST"])
@log_decorator
def quiz_overview():
    page_created = request.args.get('page_created', 1, type=int)
    page_taken = request.args.get('page_taken', 1, type=int)
    page_given = request.args.get('page_given', 1, type=int)
    per_page = 10  # Items per page
    
    quizzes_created_paginated = Test.query.filter_by(creator=current_user.id).paginate(page_created, per_page, False)

    ### quizzes given
    quiz_results_given = TestResult.query.filter_by(creator = current_user.id).all()
    print(quiz_results_given)
    for result in quiz_results_given:
        exist_quiz = Test.query.filter_by (id = result.test_id).first()
        if not exist_quiz:
            if not result.taker:
                print("deleting quiz")
                db.session.delete(result)
                db.session.commit()
    


    quiz_results_taken = TestResult.query.filter_by(taker=current_user.id).all()
    quizzes_taken = []
    for result in quiz_results_taken:
        exist_quiz = Test.query.filter_by(id=result.test_id).first()
        user = User.query.filter_by(id=result.taker).first()
        if not exist_quiz:
            if not result.taker:
                db.session.delete(result)
                db.session.commit()
        else:
            quizzes_taken.append({'result': result,'quiz': exist_quiz, 'user': user})
    taken_paginations = Pagination(quizzes_taken, page_taken, per_page)
    


    quiz_results_given = TestResult.query.filter_by(creator = current_user.id).all()
    quizzes_given = []
    for result in quiz_results_given:
        exist_quiz = Test.query.filter_by(id=result.test_id).first()
        user = User.query.filter_by(id=result.taker).first()
        if not exist_quiz:
            if not result.taker:
                db.session.delete(result)
                db.session.commit()
        else:
            quizzes_given.append({'result': result,'quiz': exist_quiz, 'user': user})
    given_paginations = Pagination(quizzes_given, page_given, per_page)
    


    return render_template(
        'quiz_bp/quiz_overview.html', 
        taken=taken_paginations.items,
        given=given_paginations.items,
        created=quizzes_created_paginated.items,
        created_paginations=quizzes_created_paginated,
        given_paginations=given_paginations,
        taken_paginations=taken_paginations
    )

@quiz_bp.route("/quiz_result_details/<int:quiz_id>/", methods=["GET", "POST"])
@log_decorator
def quiz_result_details(quiz_id):
    page = request.args.get('page', 1, type=int)
    per_page = 10
    results = TestResult.query.filter_by(test_id = quiz_id).all()
    my_students_results = []
    for result in results:
        taker = User.query.filter_by(id = result.taker).first()
        my_students_results.append({'result': result, 'taker': taker})
    quiz = Test.query.filter_by(id = quiz_id).first()
    # Get the list of taker ids from the TestResult objects
    taker_ids = [result.taker for result in results]
    # Filter the User objects by the taker ids
    takers = User.query.filter(User.id.in_(taker_ids)).all()
    my_students_results_paginated = Pagination(my_students_results, page, per_page)

    return render_template('quiz_bp/quiz_result_details.html',
            results = my_students_results_paginated, quiz = quiz,
         page = page, per_page = per_page)

class Pagination:
    def __init__(self, items, page, per_page):
        self.items = items[(page - 1) * per_page: page * per_page]
        self.page = page
        self.per_page = per_page
        self.total = len(items)
        self.pages = self.total // per_page + (1 if self.total % per_page else 0)

    def has_prev(self):
        return self.page > 1

    def has_next(self):
        return self.page < self.pages

    def iter_pages(self):
        return range(1, self.pages + 1)


@quiz_bp.route("/quiz_created/<int:quiz_id>/", methods=["GET", "POST"])
@log_decorator
def quiz_created(quiz_id):
    c_quiz_id = quiz_id
    quiz = Test.query.get_or_404(c_quiz_id)
    if request.method == 'POST' and 'quiz-name' in request.form:
        quiz.name= clean(request.form['quiz-name'])
        quiz.creator = current_user.id
        due_date = request.form.get('due-date')
        if due_date:
            due_date = dt.datetime.strptime((due_date),'%Y-%m-%dT%H:%M')
            quiz.due_date = due_date
        quiz.subject = clean(request.form['subject'])
        quiz.topic = clean(request.form['topic'])
        quiz.instructions = clean(request.form['instructions'])
        quiz.description = clean(request.form['description'])
        if time_limit := request.form.get('time-limit', False):
            quiz.time_limit = time_limit
        answer_reveal = request.form.get('answer-reveal', False)
        result_reveal = request.form.get('result-reveal', False)
        shuffle = request.form.get('shuffle', False)
        if answer_reveal == 'answer-reveal':
            quiz.answer_reveal = True
        if result_reveal == 'result-reveal':
            quiz.result_reveal = True
        if shuffle == 'shuffle':
            quiz.shuffle = True
        quiz.count_questions()
        quiz.sum_points()
        db.session.commit()
    return render_template('quiz_bp/quiz_created.html', quiz=quiz)
   
@quiz_bp.route("/quiz_result/<int:result_id>/", methods=["GET", "POST"])
@log_decorator
def quiz_result(result_id):
    result = TestResult.query.filter_by(id = result_id, taker = current_user.id).first()
    quiz = Test.query.filter_by(id = result.test_id).first()
    return render_template('quiz_bp/quiz_result.html', result=result, quiz=quiz)

@quiz_bp.route("/quiz_answers/<int:result_id>/", methods=["GET", "POST"])
@log_decorator
def quiz_answers(result_id):#
    result = TestResult.query.filter_by(id=result_id).first()
    if result.creator != current_user.id:
            flash('you are not allowed to view this page', 'danger')
            return redirect('/quiz_bp/quiz_overview/')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    students_results = []
    question_results = QuestionResult.query.filter_by(quiz_result_id = result.id).all()
    for results in question_results:
        question = Question.query.filter_by(id = results.question_id).first()
        students_results.append({'question': question, 'result': results})
    paginated_students_results = Pagination(students_results, page, per_page)            
    quiz = Test.query.filter_by(id = result.test_id).first()
    taker = User.query.filter_by(id = result.taker).first()
    
    if request.method == "POST":
        for question_result in question_results:
            question_points_id = 'points' + str(question_result.id)
            points_entered = int(request.form.get(question_points_id))
            question_result.points = int(points_entered)
            for question in quiz.questions:
                if question_result.points == question.points:
                    question_result.correct = True
        result.sum_points()        
        db.session.commit()
        
    return render_template('quiz_bp/quiz_answers.html',
                            results=paginated_students_results, result = result,
                            question_results=question_results, quiz=quiz, taker=taker)
    
@quiz_bp.route("/answer_key/<int:quiz_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def quiz_print(quiz_id):
    c_quiz_id = quiz_id
    quiz = Test.query.filter_by(id = c_quiz_id).first()
    return render_template('quiz_bp/answer_key.html', quiz=quiz)

@quiz_bp.route("/quiz_print/<int:quiz_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def answer_key(quiz_id):
    c_quiz_id = quiz_id
    quiz = Test.query.filter_by(id = c_quiz_id).first()
    return render_template('quiz_bp/quiz_print.html', quiz=quiz)