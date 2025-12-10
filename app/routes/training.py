import os
from flask import Blueprint, current_app, json, jsonify, redirect, render_template, request, send_from_directory, flash, url_for
from flask_login import login_required, current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.models import AnswerOption, QuestionType, Quiz, QuizAttachment, UserQuizAttempt, db, Course, UserCourseProgress, CourseEnrollmentTerm, User
from datetime import datetime
from werkzeug.utils import secure_filename
from app.utils.rbac_permissions import require_permission

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

@training_bp.route('/course/<int:course_id>/enroll', methods=['POST'])
@login_required
def enroll_course(course_id):
    course = Course.query.get_or_404(course_id)

    if not course.is_active:
        return jsonify({'success': False, 'errors': ['Este curso nao esta disponivel no momento.']}), 400

    if request.is_json:
        form_data = request.get_json() or {}
    else:
        form_data = request.form

    full_name = (form_data.get('full_name') or '').strip()
    email = (form_data.get('email') or '').strip()
    phone = (form_data.get('phone') or '').strip()
    department = (form_data.get('department') or '').strip()
    role = (form_data.get('role') or '').strip()
    observations = (form_data.get('observations') or '').strip()
    accepted_terms_raw = form_data.get('accepted_terms')
    accepted_terms = str(accepted_terms_raw).lower() in {'on', '1', 'true', 'yes'}

    errors = []

    if not full_name:
        errors.append('Informe o seu nome completo.')
    if not email:
        errors.append('Informe um e-mail de contato.')
    if not accepted_terms:
        errors.append('E necessario aceitar o termo de inscricao para prosseguir.')

    if errors:
        return jsonify({'success': False, 'errors': errors}), 400

    enrollment_term = CourseEnrollmentTerm.query.filter_by(
        user_id=current_user.id,
        course_id=course_id
    ).first()

    if enrollment_term:
        enrollment_term.full_name = full_name
        enrollment_term.email = email
        enrollment_term.phone = phone or None
        enrollment_term.department = department or None
        enrollment_term.role = role or None
        enrollment_term.observations = observations or None
        enrollment_term.accepted_terms = accepted_terms
        enrollment_term.accepted_at = datetime.utcnow()
    else:
        enrollment_term = CourseEnrollmentTerm(
            user_id=current_user.id,
            course_id=course_id,
            full_name=full_name,
            email=email,
            phone=phone or None,
            department=department or None,
            role=role or None,
            observations=observations or None,
            accepted_terms=accepted_terms,
            accepted_at=datetime.utcnow()
        )
        db.session.add(enrollment_term)

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

    return jsonify({
        'success': True,
        'redirect_url': url_for('training.course_player_page', course_id=course_id)
    })
    
@training_bp.route("/course/<int:course_id>/player")
@login_required
def course_player_page(course_id):
    course = Course.query.get_or_404(course_id)
    
    if not course.is_active:
        flash("Este curso não está disponível no momento.", "warning")
        return redirect(url_for('main.panel'))

    progress = UserCourseProgress.query.filter_by(
        user_id=current_user.id,
        course_id=course_id
    ).first()

    enrollment_term = CourseEnrollmentTerm.query.filter_by(
        user_id=current_user.id,
        course_id=course_id
    ).first()

    if not enrollment_term and not progress:
        flash("Para acessar o conteudo deste curso e necessario preencher o termo de inscricao.", "warning")
        return redirect(url_for('training.course_list_page'))

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
        user_attempt=user_attempt,
        content_type=course.content_type or 'video'
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
            # Get the first option from the list (not a query, so use list indexing)
            correct_answer = question.options[0] if question.options else None
            
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

    if not course.video_filename:
        flash("Arquivo do curso não encontrado.", "error")
        return redirect(request.referrer or url_for('main.panel'))

    course_folder_name = secure_filename(course.title)
    content_folder_path = os.path.join('/app/uploads/courses', course_folder_name)
    os.makedirs(content_folder_path, exist_ok=True)

    content_file_path = os.path.join(content_folder_path, course.video_filename)

    if not os.path.exists(content_folder_path) or not os.path.exists(content_file_path):
        flash("Arquivo do curso não encontrado no servidor.", "error")
        return redirect(request.referrer or url_for('main.panel'))

    return send_from_directory(content_folder_path, course.video_filename)

@training_bp.route('/course/<int:course_id>/image')
@login_required
def serve_course_image(course_id):
    course = Course.query.get_or_404(course_id)
    if not course.image_filename:
        return redirect(url_for('static', filename='course_images/default_course.png'))

    course_folder_name = secure_filename(course.title)

    course_folder_path = os.path.join('/app/uploads/courses', course_folder_name)
    os.makedirs(course_folder_path, exist_ok=True)
    
    image_file_path = os.path.join(course_folder_path, course.image_filename)
    
    if not os.path.exists(course_folder_path) or not os.path.exists(image_file_path):
        return redirect(url_for('static', filename='course_images/default_course.png'))
    
    return send_from_directory(course_folder_path, course.image_filename)
    
@training_bp.route('/quiz/attachments/<int:attachment_id>')
@login_required
def download_attachment(attachment_id):
    attachment = QuizAttachment.query.get_or_404(attachment_id)
    
    upload_folder = current_app.config['UPLOAD_FOLDER']
    full_path = os.path.join(upload_folder, attachment.filepath)
    
    if not os.path.exists(full_path):
        flash("Arquivo não encontrado.", "error")
        return redirect(request.referrer or url_for('main.panel'))
    
    directory = os.path.dirname(full_path)
    filename = os.path.basename(full_path)
    
    return send_from_directory(
        directory,
        filename,
        as_attachment=True,
        download_name=attachment.filename
    )

@training_bp.route('/course/<int:course_id>/certificate')
@login_required
def view_certificate(course_id):
    """Rota para o usuário visualizar seu próprio certificado"""
    course = Course.query.options(joinedload(Course.created_by)).get_or_404(course_id)
    
    # Buscar progresso do usuário atual
    progress = UserCourseProgress.query.filter_by(
        user_id=current_user.id,
        course_id=course_id
    ).first()
    
    # Verificar se o curso foi concluído
    if not progress or not progress.completed_at:
        flash("Você ainda não concluiu este treinamento.", "warning")
        return redirect(url_for('training.course_list_page'))
    
    # Buscar termo de inscrição
    enrollment = CourseEnrollmentTerm.query.filter_by(
        user_id=current_user.id,
        course_id=course_id
    ).first()
    
    # Buscar melhor tentativa do quiz (se houver)
    attempt = None
    if course.quiz:
        attempt = UserQuizAttempt.query.filter_by(
            user_id=current_user.id,
            quiz_id=course.quiz.id
        ).order_by(UserQuizAttempt.score.desc()).first()
    
    return render_template(
        'training/course_certificate.html',
        course=course,
        user=current_user,
        progress=progress,
        enrollment=enrollment,
        attempt=attempt
    )
