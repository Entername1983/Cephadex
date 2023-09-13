
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
    questions, distribution, 
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

@quiz_bp.route("/download/<int:test_id>")
@login_required
@log_decorator
def download(test_id):
    # Get HTML content
    test_url = url_for('test_print', test_id=test_id, _external=True)
    response = req.get(test_url)
    html_content = response.content

    # Create a pdf buffer
    pdf = BytesIO()

    # Define the link fetcher
    def fetch_resources(uri, rel):
        # Here the base URL should be the URL to the test_print page
        return req.get(urljoin(test_url, uri)).content

    # Then pass that HTML to CreatePDF
    pisa.CreatePDF(BytesIO(html_content), pdf, link_callback=fetch_resources)

    return make_response(pdf.getvalue(), 200,
                         {
                             'Content-Type': 'quiz_bplication/pdf',
                             'Content-Disposition': 'attachment; filename=output.pdf'
                         })




@quiz_bp.route("/delete_question/<int:test_id>/<int:question_id>", methods=["POST", "GET"])
@login_required
@log_decorator
def delete_question(test_id, question_id):
    c_test_id = test_id
    c_question_id = question_id
    question_to_delete = Question.query.get_or_404(c_question_id)
    # Delthe rows in the questions table that reference the question row you want to del
    db.session.execute(questions.delete()
                       .where(questions.c.question_id == c_question_id))
    # Now you can safely delete the row from the question table
    db.session.delete(question_to_delete)
    db.session.commit()
    return redirect(('/quiz_bp/assign_test/{test_id}'.format(test_id=c_test_id)))

@quiz_bp.route("/delete_test/<int:test_id>/", methods = ["POST", "GET"])
@login_required
@log_decorator
def delete_test(test_id):
    c_test_id = test_id
    test_to_delete = Test.query.get_or_404(c_test_id)
    if current_user.id == test_to_delete.creator:
        db.session.delete(test_to_delete)
        db.session.commit()
    return redirect('/quiz_bp/test_results_overview/')

@quiz_bp.route("/build_test/<int:deck_id>", methods=["GET", "POST"])
@log_decorator
def build_test(deck_id):
    settings = UserSettings.query.filter_by(user=current_user.id).first()
    c_deck_id = deck_id
    event_tracker(current_user.id, "build_test", c_deck_id)
    deck = Deck.query.get_or_404(c_deck_id)
    creator = current_user
    if request.method == "POST":
        form_data = request.form.to_dict()
        test_questions = request.form.getlist('selected_cards[]')
        name = f"{deck.name} Test " + datetime.now().strftime("%Y-%m-%d %H:%M")
        chosen_name = random.choice(TEST_NAMES)

        name = chosen_name
        new_test = Test(creator=current_user.id, deck_id = deck.id)
        db.session.add(new_test)
        new_test.name = name
        jeopardyMode = form_data.get('jeopardyMode')
        for question in test_questions:
            card = Card.query.get_or_404(question)
            question = Question()
            db.session.add(question)
            question.points = int(1)
            question.content = card.content
            question.term = card.term
            question.prompt_option = card.prompt_option
            if card.category == "Mcq":
                question.question = card.term
                question.boc_2 = card.boc_2
                question.boc_3 = card.boc_3
                question.boc_4 = card.boc_4
                question.q_type = "mcq"
            elif card.category == "Cloze":
                question.question = card.term
                question.q_type = "cloze"
            elif card.category == "Explain":
                question.question = card.term
                question.q_type = "explain"
            elif card.category == "Formulas":
                question.question = card.term
                question.term = card.formula
                question.q_type = "formulas"
            elif card.category == "Discuss":
                question.question = card.term
                question.q_type = "discuss"
                question.boc_2 = card.boc_2
            elif card.category == "Definitions":
## switching them around so that the test gives them a definition and they have to write the word
                if jeopardyMode == "on":
                    question.question = card.content
                    question.term = card.term
                    question.q_type = "jeopardy"
                else:
                    question.question = card.term
                    question.q_type = "definitions"
            else:
                question.question = card.term
                question.q_type = "other"
            db.session.add(question)
            new_test.questions.append(question)

        db.session.commit()
        return redirect('/quiz_bp/assign_test/{test.id}'.format(test=new_test))
    return render_template('/quiz_bp/build_test.html',
                title='Test Builder', deck=deck, creator=creator, settings = settings)

## TO DO: rework this so it doesn't throw an exception when it doesn't find a user, bad practice
@quiz_bp.route("/assign_test/<int:test_id>", methods=["GET", "POST"])
@log_decorator
def assign_test(test_id):
    settings = UserSettings.query.filter_by(user=current_user.id).first()
    c_test_id = test_id
    update_card_form = UpdateCardForm(request.form)
    form = BuildTest()
    try:
        event_tracker(current_user.id, "assign_test", c_test_id)
    
        test = Test.query.get_or_404(c_test_id)
        if request.method == 'POST' and 'name' in request.form:
            test.name = form.name.data
            test.creator = current_user.id
            due_date = request.form['due_date']
            if due_date:
                due_date = dt.datetime.strptime(due_date[:16],'%Y-%m-%dT%H:%M')
                test.due_date = due_date
            test.subject = form.subject.data
            test.topic = form.topic.data
            test.instructions = form.instructions.data
            test.description = form.description.data
            time_limit = form.time_limit.data
            if time_limit != '' and time_limit is not None:
                time_limit = int(time_limit)
                test.time_limit = time_limit
            
            answer_reveal = form.reveal_answers.data
            result_reveal = form.reveal_results.data
            shuffle = form.shuffle.data
            if answer_reveal == 'answer-reveal':
                test.answer_reveal = True
            if result_reveal == 'result-reveal':
                test.result_reveal = True
            if shuffle == 'shuffle':
                test.shuffle = True
            test.count_questions()
            test.sum_points()
            db.session.commit()
            flash(f'Test: "{test.name}" has been updated!', 'success')
        return render_template('/quiz_bp/assign_test.html', title='Assign test',
                            test=test, form = form, update_card_form = update_card_form, settings = settings)
    except Exception as e:
        logger.error(f"Quiz - Error assigning quiz {e}")
        raise e        
        ##flash("At this moment you can only assign tests to other users.  We are working on allowing you to assign tests to non-users")
        # return render_template('/quiz_bp/assign_test.html', title='Assign test',
        #         test=test, form = form, update_card_form = update_card_form,
        #         settings = settings)


@quiz_bp.route('/shared_test_view/<string:share_id>', methods=['GET'])
@log_decorator
def shared_test_view(share_id):
    test = Test.query.filter_by(share_id=share_id).first_or_404()
    session['shared_test_id'] = share_id
    return render_template('/quiz_bp/shared_test_view.html', test=test)

@quiz_bp.route('/generate_link_test/<int:test_id>', methods=['GET'])
@login_required
@log_decorator
def generate_link_test(test_id):
    test = Test.query.get(test_id)
    if test.share_id:
        link = f'{APP_URL}/quiz_bp/shared_test_view/{test.share_id}'
        img_str = create_qr_code(link)
        return jsonify(
            {
                'share_link': f'{APP_URL}/quiz_bp/shared_test_view/{test.share_id}',
                'qr_code': img_str,
            }
        )
    else:
        share_id = str(uuid.uuid4())
        test.share_id = share_id
        db.session.commit()
        link = f'{APP_URL}/quiz_bp/shared_test_view/{test.share_id}'

        img_str = create_qr_code(link)

        return jsonify(
            {
                'share_link': f'{APP_URL}/quiz_bp/shared_test_view/{share_id}',
                'qr_code': img_str,
            }
        )


@quiz_bp.route("/assign/<int:test_id>/<string:user_email>/", methods=["GET", "POST"])
@log_decorator
@login_required
def assign(test_id, user_email):
    c_test_id = test_id
    c_user_email = clean(user_email)
    test = Test.query.filter_by(id=c_test_id).first()
    test.count_questions()
    test.sum_points()
    not_users = []
    if check_comma_list(c_user_email):
        users_emails = user_email.split(",")
        for email in users_emails:
            email = unquote(email).strip()
            taker = User.query.filter_by(email=email).first()
            if taker is None:
                not_users.append(email)
            else:
                test.taker.append(taker)
    else:
        email = unquote(c_user_email)
        taker = User.query.filter_by(email=email).first()
        if taker is None:
            not_users.append(email)

        else:
            test.taker.append(taker)
    db.session.commit()
    if not not_users:
        flash('Test assigned!', 'success')
    else:
        flash(f"Could not locate the following users: {not_users}.  Currently you can only assign to other users", "danger")  # noqa: E501
    return redirect('/quiz_bp/assign_test/{test_id}'.format(test_id = c_test_id))





@quiz_bp.route("/take_test_2/<share_id>/<int:user_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def take_test_2(share_id, user_id):
    event_tracker(current_user.id, "take_test", share_id)
    test = Test.query.filter_by(share_id=share_id).first_or_404()
    test_result = TestResult.query.filter_by(test_id = test.id, taker = user_id).first()

    if request.method == 'POST':
        for question in test.questions:
            question_id = question.id
            to_call = f"answer{str(question_id)}"
            answer = request.form.get(to_call, '')
            answer = answer.strip()
            result = QuestionResult(test_id = test.id,
                                    taker = current_user.id,
                                    question_id = question.id, answer = answer)
            db.session.add(result)
            db.session.commit()
        end_time = request.form.get('end-time')
        end_time = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S.%fZ')
        test_result.end_time = end_time
        db.session.commit()
        return redirect('/quiz_bp/test_results/{test_id}/{user_id}'.format
                        (test_id = test.id, user_id = user_id))

    else:
        if test_result is None:
            start_time = dt.datetime.now(dt.timezone.utc)
            test_result = TestResult(test_id = test.id,
                                    taker = user_id, start_time = start_time,
                                    creator=test.creator)
            taker = User.query.get_or_404(user_id)
            db.session.add(test_result)
            db.session.commit()
            return render_template('quiz_bp/take_test.html',
                            test=test, taker=taker, start_time = start_time)
        else:
            ## TO DO - RESOLVE THE ISSUE OF NOT BEING ABLE TO REMOVE THE CURRENT USER
            try:
                test.taker.remove(current_user)
                db.session.commit()
            except Exception as e:
                logger.error(f"could not remove user from test: {e}")
            flash('you have already taken this test', 'danger')
            return redirect('/quiz_bp/test_results_overview/')
        
@quiz_bp.route("/take_test/<int:test_id>/<int:user_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def take_test(test_id, user_id):
    c_test_id = test_id
    c_user_id = user_id
    event_tracker(current_user.id, "take_test", c_test_id)
    test_result = TestResult.query.filter_by(test_id = test_id, taker = c_user_id).first()  # noqa: E501
    test = Test.query.get_or_404(test_id)
    if request.method == 'POST':
        for question in test.questions:
            question_id = question.id
            to_call = f"answer{str(question_id)}"
            answer = request.form.get(to_call, '')
            answer = answer.strip()
            result = QuestionResult(test_id = test.id,
                                    taker = current_user.id,
                                    question_id = question.id, answer = answer)
            db.session.add(result)
            db.session.commit()
        end_time = request.form.get('end-time')
        end_time = datetime.strptime(end_time, '%Y-%m-%dT%H:%M:%S.%fZ')
        test_result.end_time = end_time
        db.session.commit()
        return redirect('/quiz_bp/test_results/{test_id}/{user_id}'.format
                        (test_id = c_test_id, user_id = c_user_id))



    start_time = dt.datetime.now(dt.timezone.utc)
    test_result = TestResult(test_id = test_id,
                            taker = c_user_id, start_time = start_time,
                            creator=test.creator)
    taker = User.query.get_or_404(user_id)
    db.session.add(test_result)
    db.session.commit()
    return render_template('quiz_bp/take_test.html',
                    test=test, taker=taker, start_time = start_time)
        ##else:
          ##  test.taker.remove(current_user)
         ##   db.session.commit()
           ## flash('you have already taken this test', 'danger')
          ##  return redirect('/test_results_overview/')

@quiz_bp.route('/reject_test/<int:test_id>/<int:user_id>', methods=['DELETE'])
@log_decorator
def reject_test(test_id, user_id):
    distribution_entry = distribution.delete().where(
        (distribution.c.test_id == test_id) & (distribution.c.taker_id == user_id)
    )
    db.session.execute(distribution_entry)
    db.session.commit()
    return jsonify({'message': 'Test deleted successfully'}), 200

@quiz_bp.route("/test_results/<int:test_id>/<int:user_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def test_results(test_id, user_id): 
    c_test_id = test_id
    c_user_id = user_id      
    point_counter = 0
    correct_counter = 0
    test = Test.query.get_or_404(c_test_id)
    creator = test.creator
    taker = User.query.get_or_404(c_user_id)
    for question in test.questions:
        answer = QuestionResult.query.filter_by(test_id = c_test_id,
                                taker = c_user_id, question_id = question.id).first()
        if answer.answer:
            answer_given = remove_punctuation(answer.answer).lower().strip()
            if question.q_type == "jeopardy":
                answer_expected = remove_punctuation(question.term).lower().strip()
            elif question.q_type == "cloze":
                answer_expected = remove_punctuation(question.content).lower().strip()
            elif question.q_type == "mcq":
                answer_expected = remove_punctuation(question.content).lower().strip()
            else:
                answer_expected = remove_punctuation(question.content).lower().strip()
            matcher = difflib.SequenceMatcher(None, answer_given.lower(),
                                            answer_expected.lower())
            if matcher.ratio() > 0.9:
                point_counter += question.points
                correct_counter += 1
                answer.points = int(question.points)
            else:
                answer.points = 0
        if not answer.points:
            answer.points = 0
    test = db.session.query(Test).filter_by(id=c_test_id).first()
    test_result = TestResult.query.filter_by(test_id = c_test_id,
                                            taker = c_user_id).first()
    test_result.points = point_counter
    test_result.correct = correct_counter
    test_result.correct = creator
    taker = current_user
    if taker in test.taker:
        test.taker.remove(taker)
    db.session.add(test_result)
    db.session.commit()
    return render_template('quiz_bp/test_results.html', test=test,
                            taker=taker, results=test_result)    

@quiz_bp.route("/test_results_overview/", methods=["GET", "POST"])
@log_decorator
# sourcery skip: no-loop-in-tests
def test_results_overview():
    tests_created = Test.query.filter_by(creator = current_user.id).all()
    ## results of tests taken
    test_results_taken = TestResult.query.filter_by(taker = current_user.id).all()
    ## results of tests given
    test_results_given = TestResult.query.filter_by(creator = current_user.id).all()
    tests = []
    for result in test_results_taken:
        test = Test.query.filter_by(id=result.test_id).first()
        tests.append(test)
    ## if the test has been deleted and there are are no results for user then delete
    for test in test_results_given:
        exist_test = Test.query.filter_by (id = test.test_id).first()
        if not exist_test:
            if not test.taker:
                db.session.delete(test)
                db.session.commit()
    return render_template('quiz_bp/test_results_overview.html',
                            taken = test_results_taken,
                            given = test_results_given,
                            created = tests_created,tests=tests)

@quiz_bp.route("/test_result_details/<int:test_id>/", methods=["GET", "POST"])
@log_decorator
def test_result_details(test_id):
    c_test_id = test_id
    results = TestResult.query.filter_by(test_id = c_test_id).all()
    test = Test.query.filter_by(id = c_test_id).first()
    # Get the list of taker ids from the TestResult objects
    taker_ids = [result.taker for result in results]
    # Filter the User objects by the taker ids
    
    takers = User.query.filter(User.id.in_(taker_ids)).all()
    return render_template('quiz_bp/test_result_details.html',
                        results = results, test = test, takers = takers)

@quiz_bp.route("/test_created/<int:test_id>/", methods=["GET", "POST"])
@log_decorator
def test_created(test_id):
    c_test_id = test_id
    test = Test.query.get_or_404(c_test_id)
    if request.method == 'POST' and 'test-name' in request.form:
        test.name= clean(request.form['test-name'])
        test.creator = current_user.id
        due_date = request.form.get('due-date')
        if due_date:
            due_date = dt.datetime.strptime((due_date),'%Y-%m-%dT%H:%M')
            test.due_date = due_date
        test.subject = clean(request.form['subject'])
        test.topic = clean(request.form['topic'])
        test.instructions = clean(request.form['instructions'])
        test.description = clean(request.form['description'])
        if time_limit := request.form.get('time-limit', False):
            test.time_limit = time_limit
        answer_reveal = request.form.get('answer-reveal', False)
        result_reveal = request.form.get('result-reveal', False)
        shuffle = request.form.get('shuffle', False)
        if answer_reveal == 'answer-reveal':
            test.answer_reveal = True
        if result_reveal == 'result-reveal':
            test.result_reveal = True
        if shuffle == 'shuffle':
            test.shuffle = True
        test.count_questions()
        test.sum_points()
        db.session.commit()
    return render_template('quiz_bp/test_created.html', test=test)
   
@quiz_bp.route("/test_result/<int:result_id>/", methods=["GET", "POST"])
@log_decorator
def test_result(result_id):
    c_result_id = result_id
    result = TestResult.query.filter_by(id = c_result_id, taker = current_user.id).first()
    test = Test.query.filter_by(id = result.test_id).first()
    return render_template('quiz_bp/test_result.html', result=result, test=test)

@quiz_bp.route("/test_answers/<int:test_id>/<int:taker_id>/", methods=["GET", "POST"])
@log_decorator
def test_answers(test_id, taker_id):#
    c_test_id = test_id
    c_taker_id = taker_id
    test = Test.query.filter_by(id = c_test_id).first()
    result = TestResult.query.filter_by(test_id = c_test_id, taker = c_taker_id).first()
    question_results = (
                QuestionResult.query
                .filter_by(test_id = test.id, taker=c_taker_id).all()
    )
    result.sum_points()   
    taker = User.query.filter_by(id = c_taker_id).first()
    if result.creator != current_user.id:
        flash('you are not allowed to view this page', 'danger')
        return redirect('/quiz_bp/test_results_overview/')
    else:
        if request.method == "POST":
            for question_result in question_results:
                question_points_id = 'points' + str(question_result.id)
                points_entered = int(request.form.get(question_points_id))
                question_result.points = int(points_entered)
                for question in test.questions:
                    if question_result.points == question.points:
                        question_result.correct = True
            result.sum_points()        
            db.session.commit()
        return render_template('quiz_bp/test_answers.html',
                                result=result,
                                question_results=question_results, test=test, taker=taker)
    
@quiz_bp.route("/answer_key/<int:test_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def test_print(test_id):
    c_test_id = test_id
    test = Test.query.filter_by(id = c_test_id).first()
    return render_template('quiz_bp/answer_key.html', test=test)

@quiz_bp.route("/test_print/<int:test_id>/", methods=["GET", "POST"])
@login_required
@log_decorator
def answer_key(test_id):
    c_test_id = test_id
    test = Test.query.filter_by(id = c_test_id).first()
    return render_template('quiz_bp/test_print.html', test=test)