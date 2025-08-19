import os
from flask import Blueprint, current_app, json, jsonify, redirect, render_template, request, send_from_directory, flash, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from app.models import AnswerOption, QuestionType, Quiz, QuizAttachment, UserQuizAttempt, db, Course, UserCourseProgress
from datetime import datetime
from werkzeug.utils import secure_filename

training_bp = Blueprint('training', __name__, template_folder='../templates')

@training_bp.route('/course/<int:course_id>/progress', methods=['POST'])
@login_required
def save_progress(course_id):
    data = request.get_json()
    current_time = float(data.get('timestamp', 0))
    finished = data.get('finished', False)

    progress = UserCourseProgress.query.filter_by(
        user_id=current_user.id,
        course_id=course_id
    ).first_or_404()

    if current_time > (progress.last_watched_timestamp + 15) and progress.last_watched_timestamp > 0:
        return jsonify({'success': False, 'error': 'Avanco de vídeo detectado.'}), 400
    
    progress.last_watched_timestamp = max(progress.last_watched_timestamp, current_time)
    course = Course.query.get_or_404(course_id)
    just_completed = False

    is_quizless = not course.quiz or not course.quiz.questions

    if finished and is_quizless and progress.completed_at is None:
        progress.completed_at = datetime.utcnow()
        just_completed = True
        flash(f'Parabéns! Você concluiu o treinamento "{course.title}"!', 'success')

    db.session.commit()
    
    return jsonify({
        'success': True, 
        'last_timestamp': progress.last_watched_timestamp,
        'completed': just_completed 
    })

@training_bp.route('/courses')
@login_required
def course_list_page():
    all_active_courses = Course.query.filter_by(is_active=True).order_by(Course.title).all()
    
    user_progress_map = {p.course_id: p for p in UserCourseProgress.query.filter_by(user_id=current_user.id).all()}
    
    user_attempts_map = {}
    if db.session.query(UserQuizAttempt.id).count() > 0:
        subquery = db.session.query(
            UserQuizAttempt.quiz_id,
            func.max(UserQuizAttempt.score).label('max_score')
        ).filter_by(user_id=current_user.id).group_by(UserQuizAttempt.quiz_id).subquery()
        
        best_attempts = db.session.query(UserQuizAttempt).join(
            subquery,
            db.and_(
                UserQuizAttempt.quiz_id == subquery.c.quiz_id,
                UserQuizAttempt.score == subquery.c.max_score
            )
        ).all()
        user_attempts_map = {attempt.quiz.course_id: attempt for attempt in best_attempts if attempt.quiz}

    courses_completed = []
    courses_in_progress = []
    courses_available = []

    for course in all_active_courses:
        progress = user_progress_map.get(course.id)
        attempt = user_attempts_map.get(course.id)

        if progress and progress.completed_at:
            courses_completed.append((course, attempt))
        elif progress:
            percent_complete = 0
            if course.duration_seconds > 0:
                percent_complete = round((progress.last_watched_timestamp / course.duration_seconds) * 100)
            courses_in_progress.append((course, min(percent_complete, 99)))
        else:
            courses_available.append(course)
            
    return render_template(
        'training/course_list.html',
        completed=courses_completed,
        in_progress=courses_in_progress,
        available=courses_available
    )
    
@training_bp.route("/course/<int:course_id>/player")
@login_required
def course_player_page(course_id):
    course = Course.query.get_or_404(course_id)
    
    if not course.is_active and 'ADMIN' not in current_user.profile:
        flash("Este curso não está disponível no momento.", "warning")
        return redirect(url_for('main.panel'))

    progress = UserCourseProgress.query.filter_by(
        user_id=current_user.id,
        course_id=course_id
    ).first()

    if not progress:
        progress = UserCourseProgress(
            user_id=current_user.id,
            course_id=course_id,
            last_watched_timestamp=0
            )
        db.session.add(progress)
        db.session.commit()

    is_completed = progress.completed_at is not None
    user_attempt = None
    
    if is_completed and course.quiz:
        user_attempt = UserQuizAttempt.query.filter_by(
            user_id=current_user.id,
            quiz_id=course.quiz.id
        ).order_by(UserQuizAttempt.submitted_at.desc()).first()
        
        if user_attempt and isinstance(user_attempt.answers, str):
            user_attempt.answers_dict = json.loads(user_attempt.answers)
        else:
             user_attempt.answers_dict = {}

    return render_template(
        "training/course_player.html", 
        course=course, 
        quiz=course.quiz,
        is_completed=is_completed,
        user_attempt=user_attempt
    )
    
@training_bp.route("/quiz/submit/<int:quiz_id>", methods=['POST'])
@login_required
def submit_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    questions = quiz.questions

    user_answers_data = {}
    correct_answers_count = 0
    total_questions = len(questions)

    for question in questions:
        user_submitted_value = request.form.get(f'question_{question.id}')
        is_correct = False

        if not user_submitted_value:
            user_answers_data[str(question.id)] = {'answer': None, 'is_correct': False}
            continue

        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            try:
                user_answer_id = int(user_submitted_value)
                correct_option = AnswerOption.query.filter_by(question_id=question.id, is_correct=True).first()
                
                if correct_option and correct_option.id == user_answer_id:
                    correct_answers_count += 1
                    is_correct = True
                
                user_answers_data[str(question.id)] = {'answer': user_answer_id, 'is_correct': is_correct}
            except (ValueError, TypeError):
                user_answers_data[str(question.id)] = {'answer': user_submitted_value, 'is_correct': False}

        elif question.question_type == QuestionType.TEXT_INPUT:
            correct_answer = question.options.first()
            
            if correct_answer and user_submitted_value.strip().lower() == correct_answer.text.strip().lower():
                correct_answers_count += 1
                is_correct = True
            
            user_answers_data[str(question.id)] = {'answer': user_submitted_value, 'is_correct': is_correct}

    score = (correct_answers_count / total_questions) * 100 if total_questions > 0 else 0

    new_attempt = UserQuizAttempt(
        user_id=current_user.id,
        quiz_id=quiz_id,
        score=score,
        answers=json.dumps(user_answers_data)
    )
    db.session.add(new_attempt)

    progress = UserCourseProgress.query.filter_by(
        user_id=current_user.id,
        course_id=quiz.course_id
    ).first()
    
    if progress and progress.completed_at is None:
        progress.completed_at = datetime.utcnow()
        flash(f'Parabéns! Você concluiu o treinamento "{quiz.course.title}"!', 'info')

    db.session.commit()
    
    flash(f"Avaliação enviada! Sua pontuação foi: {score:.2f}%", "success")
    return redirect(url_for('training.course_list_page'))

@training_bp.route('/course/<int:course_id>/video')
@login_required
def serve_video(course_id):
    course = Course.query.get_or_404(course_id)
    
    course_folder_name = secure_filename(course.title)
    video_folder_path = os.path.join(current_app.root_path, 'uploads', 'courses', course_folder_name)
    
    return send_from_directory(video_folder_path, course.video_filename)

@training_bp.route('/course/<int:course_id>/image')
@login_required
def serve_course_image(course_id):
    course = Course.query.get_or_404(course_id)
    if not course.image_filename:
        return redirect(url_for('static', filename='course_images/default_course.png'))

    course_folder_name = secure_filename(course.title)
    course_folder_path = os.path.join(current_app.root_path, 'uploads', 'courses', course_folder_name)
    
    return send_from_directory(course_folder_path, course.image_filename)
    
@training_bp.route('/quiz/attachments/<int:attachment_id>')
@login_required
def download_attachment(attachment_id):
    attachment = QuizAttachment.query.get_or_404(attachment_id)
    return send_from_directory(
        current_app.config['UPLOAD_FOLDER'],
        attachment.filepath,
        as_attachment=True,
        download_name=attachment.filename
    )