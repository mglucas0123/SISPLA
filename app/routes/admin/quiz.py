from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import db, Course, Quiz, Question, QuestionType, AnswerOption, QuizAttachment, UserQuizAttempt
from .utils import admin_required, handle_database_error
import os
import logging
import json

logger = logging.getLogger(__name__)

quiz_bp = Blueprint('quiz', __name__, url_prefix='/quiz')

# ==========================================
# ROTAS DE GESTÃO DE QUIZ
# ==========================================

@quiz_bp.route('/manage/<int:course_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_quiz(course_id):
    """Gerenciar quiz do curso"""
    course = Course.query.get_or_404(course_id)
    
    if request.method == "POST":
        return _create_or_update_quiz(course)
    
    quiz = Quiz.query.filter_by(course_id=course_id).first()
    questions = Question.query.filter_by(quiz_id=quiz.id).all() if quiz else []
    
    return render_template(
        "training/manage_quiz.html", 
        course=course, 
        quiz=quiz, 
        questions=questions
    )

@handle_database_error("gerenciar quiz")
def _create_or_update_quiz(course):
    """Criar ou atualizar quiz"""
    quiz_title = request.form.get("quiz_title", "").strip()
    support_text = request.form.get("support_text", "").strip()
    questions_data = request.form.get("questions_data", "")
    
    if not quiz_title:
        flash("Título do quiz é obrigatório.", "warning")
        return redirect(url_for("admin.quiz.manage_quiz", course_id=course.id))
    
    quiz = Quiz.query.filter_by(course_id=course.id).first()
    
    if quiz:
        quiz.title = quiz_title
        quiz.support_text = support_text
        action = "atualizado"
    else:
        quiz = Quiz(
            title=quiz_title,
            support_text=support_text,
            course_id=course.id
        )
        db.session.add(quiz)
        action = "criado"
    
    db.session.flush()  # Para obter o ID do quiz
    
    # Processar questões se enviadas
    if questions_data:
        try:
            questions_list = json.loads(questions_data)
            
            # Remover questões existentes que não estão na nova lista
            existing_questions = Question.query.filter_by(quiz_id=quiz.id).all()
            existing_ids = [str(q.id) for q in existing_questions]
            new_ids = [str(q['id']) for q in questions_list if not str(q['id']).startswith('new_')]
            
            for existing_q in existing_questions:
                if str(existing_q.id) not in new_ids:
                    db.session.delete(existing_q)
            
            # Processar cada questão
            for q_data in questions_list:
                question_id = str(q_data['id'])
                question_text = q_data['text']
                question_type = QuestionType[q_data['question_type']]
                
                if question_id.startswith('new_'):
                    # Nova questão
                    new_question = Question(
                        quiz_id=quiz.id,
                        text=question_text,
                        question_type=question_type
                    )
                    db.session.add(new_question)
                    db.session.flush()
                    question = new_question
                else:
                    # Questão existente
                    question = Question.query.get(int(question_id))
                    if question:
                        question.text = question_text
                        question.question_type = question_type
                        # Remover opções antigas
                        for option in question.options:
                            db.session.delete(option)
                
                # Adicionar novas opções
                if question:
                    for opt_data in q_data.get('options', []):
                        option = AnswerOption(
                            question_id=question.id,
                            text=opt_data['text'],
                            is_correct=opt_data['is_correct']
                        )
                        db.session.add(option)
                        
        except json.JSONDecodeError:
            flash("Erro ao processar dados das questões.", "danger")
            return redirect(url_for("admin.quiz.manage_quiz", course_id=course.id))
    
    db.session.commit()
    
    logger.info(f"Quiz {action} por {current_user.username} para curso: {course.title}")
    flash(f"Quiz {action} com sucesso!", "success")
    return redirect(url_for("admin.quiz.manage_quiz", course_id=course.id))

@quiz_bp.route('/<int:quiz_id>/questions/create', methods=['POST'])
@login_required
@admin_required
@handle_database_error("criar questão")
def create_question(quiz_id):
    """Criar nova questão"""
    quiz = Quiz.query.get_or_404(quiz_id)
    
    question_text = request.form.get('question_text', '').strip()
    question_type = request.form.get('question_type', 'MULTIPLE_CHOICE')
    
    if not question_text:
        flash('Texto da questão é obrigatório.', 'warning')
        return redirect(url_for('admin.quiz.manage_quiz', course_id=quiz.course_id))
    
    new_question = Question(
        quiz_id=quiz.id,
        text=question_text,
        question_type=QuestionType[question_type]
    )
    db.session.add(new_question)
    db.session.flush()
    
    if question_type == 'MULTIPLE_CHOICE':
        options_data = request.form.getlist('options')
        correct_option = request.form.get('correct_option', type=int)
        
        for i, option_text in enumerate(options_data):
            if option_text.strip():
                is_correct = (i == correct_option)
                option = AnswerOption(
                    question_id=new_question.id,
                    text=option_text.strip(),
                    is_correct=is_correct
                )
                db.session.add(option)
    
    db.session.commit()
    
    logger.info(f"Questão criada por {current_user.username} no quiz: {quiz.title}")
    flash('Questão criada com sucesso!', 'success')
    return redirect(url_for('admin.quiz.manage_quiz', course_id=quiz.course_id))

@quiz_bp.route('/questions/<int:question_id>/edit', methods=['POST'])
@login_required
@admin_required
@handle_database_error("editar questão")
def edit_question(question_id):
    """Editar questão existente"""
    question = Question.query.get_or_404(question_id)
    
    question.text = request.form.get('question_text', '').strip()
    
    if not question.text:
        flash('Texto da questão é obrigatório.', 'warning')
        return redirect(url_for('admin.quiz.manage_quiz', course_id=question.quiz.course_id))
    
    if question.question_type == QuestionType.MULTIPLE_CHOICE:
        for option in question.options:
            db.session.delete(option)
        
        options_data = request.form.getlist('options')
        correct_option = request.form.get('correct_option', type=int)
        
        for i, option_text in enumerate(options_data):
            if option_text.strip():
                is_correct = (i == correct_option)
                option = AnswerOption(
                    question_id=question.id,
                    text=option_text.strip(),
                    is_correct=is_correct
                )
                db.session.add(option)
    
    db.session.commit()
    
    logger.info(f"Questão editada por {current_user.username}: {question.text[:50]}...")
    flash('Questão atualizada com sucesso!', 'success')
    return redirect(url_for('admin.quiz.manage_quiz', course_id=question.quiz.course_id))

@quiz_bp.route('/questions/<int:question_id>/delete', methods=['POST'])
@login_required
@admin_required
@handle_database_error("deletar questão")
def delete_question(question_id):
    """Deletar questão"""
    question = Question.query.get_or_404(question_id)
    course_id = question.quiz.course_id
    
    db.session.delete(question)
    db.session.commit()
    
    logger.info(f"Questão deletada por {current_user.username}")
    flash('Questão removida com sucesso!', 'success')
    return redirect(url_for('admin.quiz.manage_quiz', course_id=course_id))

@quiz_bp.route('/<int:quiz_id>/upload-attachment', methods=['POST'])
@login_required
@admin_required
def upload_quiz_attachment(quiz_id):
    """Upload de anexo para quiz"""
    quiz = Quiz.query.get_or_404(quiz_id)
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo enviado.'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nome de arquivo vazio.'}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join('quiz_attachments', filename)
        
        upload_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'quiz_attachments')
        os.makedirs(upload_folder, exist_ok=True)
        
        file.save(os.path.join(upload_folder, filename))
        
        attachment = QuizAttachment(
            filename=filename,
            filepath=filepath,
            quiz_id=quiz.id
        )
        db.session.add(attachment)
        db.session.commit()
        
        logger.info(f"Anexo adicionado por {current_user.username} ao quiz: {quiz.title}")
        
        attachment_data = {
            'id': attachment.id,
            'filename': attachment.filename,
            'url': url_for('training.download_attachment', attachment_id=attachment.id)
        }
        return jsonify({'success': True, 'attachment': attachment_data})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro no upload de anexo: {str(e)}")
        return jsonify({'success': False, 'message': 'Erro interno no servidor.'}), 500

@quiz_bp.route('/attachment/<int:attachment_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_quiz_attachment(attachment_id):
    """Deletar anexo do quiz"""
    attachment = QuizAttachment.query.get_or_404(attachment_id)
    
    try:
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], attachment.filepath)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        db.session.delete(attachment)
        db.session.commit()
        
        logger.info(f"Anexo removido por {current_user.username} do quiz: {attachment.quiz.title}")
        return jsonify({'success': True, 'message': 'Anexo removido com sucesso!'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao remover anexo: {str(e)}")
        return jsonify({'success': False, 'message': 'Erro interno ao remover anexo.'}), 500

@quiz_bp.route('/<int:quiz_id>/attempts')
@login_required
@admin_required
def view_quiz_attempts(quiz_id):
    """Ver tentativas do quiz"""
    quiz = Quiz.query.get_or_404(quiz_id)
    attempts = UserQuizAttempt.query.filter_by(quiz_id=quiz_id).order_by(UserQuizAttempt.submitted_at.desc()).all()
    
    return render_template('training/quiz_attempts.html', quiz=quiz, attempts=attempts)

@quiz_bp.route('/<int:quiz_id>/reset-attempts', methods=['POST'])
@login_required
@admin_required
@handle_database_error("resetar tentativas")
def reset_quiz_attempts(quiz_id):
    """Resetar todas as tentativas do quiz"""
    quiz = Quiz.query.get_or_404(quiz_id)
    
    UserQuizAttempt.query.filter_by(quiz_id=quiz_id).delete()
    db.session.commit()
    
    logger.info(f"Tentativas do quiz resetadas por {current_user.username}: {quiz.title}")
    flash('Todas as tentativas do quiz foram resetadas.', 'success')
    return redirect(url_for('admin.quiz.view_quiz_attempts', quiz_id=quiz_id))
