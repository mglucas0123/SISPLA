"""
Script para migrar usuários de 'Enfermeiro do Trabalho' para 'ENFERMEIRO'
e remover o cargo antigo
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, User, JobPosition

app = create_app()

with app.app_context():
    # Encontrar os cargos
    cargo_antigo = JobPosition.query.filter_by(name='Enfermeiro do Trabalho').first()
    cargo_novo = JobPosition.query.filter_by(name='ENFERMEIRO').first()
    
    if cargo_antigo and cargo_novo:
        # Migrar usuários
        usuarios = User.query.filter_by(job_position_id=cargo_antigo.id).all()
        print(f'Migrando {len(usuarios)} usuários de "{cargo_antigo.name}" para "{cargo_novo.name}"...')
        
        for user in usuarios:
            print(f'  ✓ {user.name}')
            user.job_position_id = cargo_novo.id
        
        db.session.commit()
        
        # Remover cargo antigo
        db.session.delete(cargo_antigo)
        db.session.commit()
        print(f'\n✓ Cargo "{cargo_antigo.name}" removido com sucesso!')
    else:
        if not cargo_antigo:
            print('Cargo "Enfermeiro do Trabalho" não encontrado')
        if not cargo_novo:
            print('Cargo "ENFERMEIRO" não encontrado')
