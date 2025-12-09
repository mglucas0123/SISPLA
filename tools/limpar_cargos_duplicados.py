"""
Script para limpar cargos duplicados e manter apenas os corretos
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, User, JobPosition

app = create_app()

# Mapeamento de cargos duplicados para o correto
MIGRAR_CARGOS = {
    "ANALISTA ADMINISTRATIVO PL": "Analista Administrativo Pleno",
    "ANALISTA DE RH JR": "Analista de RH Júnior",
    "ANALISTA DE T.I PL": "Analista de T.I. Pleno",
    "OFICIAL ELÉTRICA": "Oficial Eletricista",
    "TECNICO DE SEGURANCA NO TRABALHO JR": "Técnico de Segurança do Trabalho Júnior",
}

def main():
    with app.app_context():
        print("=" * 60)
        print("LIMPANDO CARGOS DUPLICADOS")
        print("=" * 60)
        
        for cargo_antigo_nome, cargo_novo_nome in MIGRAR_CARGOS.items():
            cargo_antigo = JobPosition.query.filter_by(name=cargo_antigo_nome).first()
            cargo_novo = JobPosition.query.filter_by(name=cargo_novo_nome).first()
            
            if cargo_antigo:
                # Migrar usuários se houver
                usuarios = User.query.filter_by(job_position_id=cargo_antigo.id).all()
                if usuarios and cargo_novo:
                    for user in usuarios:
                        user.job_position_id = cargo_novo.id
                        print(f"  ✓ Migrado: {user.name} → {cargo_novo_nome}")
                
                # Remover cargo antigo
                db.session.delete(cargo_antigo)
                print(f"✓ Removido: {cargo_antigo_nome}")
            else:
                print(f"  - {cargo_antigo_nome} não encontrado")
        
        db.session.commit()
        
        # Listar cargos finais
        print("\n" + "=" * 60)
        print("📋 LISTA FINAL DE CARGOS:")
        print("-" * 60)
        cargos = JobPosition.query.order_by(JobPosition.name).all()
        for cargo in cargos:
            qtd = User.query.filter_by(job_position_id=cargo.id).count()
            status = f"({qtd} usuários)" if qtd > 0 else "(sem usuários)"
            print(f"   • {cargo.name} {status}")
        
        print(f"\nTotal: {len(cargos)} cargos")
        print("=" * 60)

if __name__ == "__main__":
    main()
