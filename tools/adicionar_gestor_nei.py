"""
Script para adicionar Nei Alves Barbosa Junior como gestor adicional
de todos os colaboradores que têm Lucineia Oliveira da Silva como gestora.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, User, user_managers
from datetime import datetime, timezone
from sqlalchemy import text

app = create_app()

def normalizar_nome(nome):
    """Remove acentos e converte para minúsculas para comparação"""
    import unicodedata
    nfd = unicodedata.normalize('NFD', nome)
    return ''.join([c for c in nfd if not unicodedata.combining(c)]).lower()

def adicionar_gestor_nei(auto_confirm=False):
    """Adiciona Nei como gestor adicional da equipe da Lucineia"""
    
    with app.app_context():
        print("=" * 80)
        print("SCRIPT: Adicionar Nei Alves Barbosa Junior como gestor adicional")
        print("=" * 80)
        print()
        
        # 1. Buscar a Lucineia
        print("1. Buscando gestora Lucineia Oliveira da Silva...")
        lucineia = User.query.filter(
            User.name.ilike('%Lucineia%Oliveira%Silva%')
        ).first()
        
        if not lucineia:
            print("❌ ERRO: Gestora Lucineia Oliveira da Silva não encontrada!")
            return
        
        print(f"✓ Lucineia encontrada: {lucineia.name} (ID: {lucineia.id})")
        print()
        
        # 2. Buscar o Nei
        print("2. Buscando gestor Nei Alves Barbosa Junior...")
        nei = User.query.filter(
            User.name.ilike('%Nei%Alves%Barbosa%')
        ).first()
        
        if not nei:
            print("❌ ERRO: Gestor Nei Alves Barbosa Junior não encontrado!")
            return
        
        print(f"✓ Nei encontrado: {nei.name} (ID: {nei.id})")
        print()
        
        # 3. Buscar todos os colaboradores da Lucineia
        print("3. Buscando colaboradores da Lucineia...")
        query = text("""
            SELECT DISTINCT employee_id 
            FROM user_managers 
            WHERE manager_id = :manager_id
        """)
        
        result = db.session.execute(query, {'manager_id': lucineia.id})
        employee_ids = [row[0] for row in result]
        
        if not employee_ids:
            print(f"⚠️  Nenhum colaborador encontrado para a gestora {lucineia.name}")
            return
        
        colaboradores = User.query.filter(User.id.in_(employee_ids)).all()
        print(f"✓ Encontrados {len(colaboradores)} colaboradores da Lucineia")
        print()
        
        # 4. Listar colaboradores que serão atualizados
        print("4. Colaboradores que terão o Nei adicionado como gestor:")
        print("-" * 80)
        for i, colaborador in enumerate(colaboradores, 1):
            print(f"{i:3}. {colaborador.name:<50} (ID: {colaborador.id})")
        print("-" * 80)
        print()
        
        # 5. Confirmar ação
        if not auto_confirm:
            resposta = input("Deseja adicionar o Nei como gestor adicional destes colaboradores? (s/n): ")
            if resposta.lower() != 's':
                print("❌ Operação cancelada pelo usuário.")
                return
        else:
            print("✓ Modo automático ativado. Prosseguindo com a operação...")
        
        print()
        print("5. Adicionando Nei como gestor adicional...")
        print()
        
        # 6. Adicionar Nei como gestor (se ainda não for)
        adicionados = 0
        ja_existentes = 0
        erros = 0
        
        for colaborador in colaboradores:
            try:
                # Verificar se Nei já é gestor deste colaborador
                check_query = text("""
                    SELECT COUNT(*) 
                    FROM user_managers 
                    WHERE employee_id = :employee_id 
                    AND manager_id = :manager_id
                """)
                
                result = db.session.execute(check_query, {
                    'employee_id': colaborador.id,
                    'manager_id': nei.id
                })
                count = result.scalar()
                
                if count > 0:
                    print(f"  ⊙ {colaborador.name:<50} - Nei já é gestor")
                    ja_existentes += 1
                else:
                    # Adicionar Nei como gestor
                    insert_query = text("""
                        INSERT INTO user_managers 
                        (employee_id, manager_id, assigned_at, assigned_by_id)
                        VALUES 
                        (:employee_id, :manager_id, :assigned_at, :assigned_by_id)
                    """)
                    
                    db.session.execute(insert_query, {
                        'employee_id': colaborador.id,
                        'manager_id': nei.id,
                        'assigned_at': datetime.now(timezone.utc),
                        'assigned_by_id': None  # Script automático
                    })
                    
                    print(f"  ✓ {colaborador.name:<50} - Nei adicionado como gestor")
                    adicionados += 1
                    
            except Exception as e:
                print(f"  ❌ {colaborador.name:<50} - ERRO: {str(e)}")
                erros += 1
        
        # 7. Commit das alterações
        if adicionados > 0:
            try:
                db.session.commit()
                print()
                print("=" * 80)
                print("✓ OPERAÇÃO CONCLUÍDA COM SUCESSO!")
                print("=" * 80)
                print(f"  • Colaboradores atualizados: {adicionados}")
                print(f"  • Já existentes: {ja_existentes}")
                print(f"  • Erros: {erros}")
                print(f"  • Total de colaboradores: {len(colaboradores)}")
                print()
                print(f"Agora {nei.name} é gestor adicional de {adicionados} colaboradores,")
                print(f"juntamente com {lucineia.name}.")
                print("=" * 80)
            except Exception as e:
                db.session.rollback()
                print()
                print("=" * 80)
                print(f"❌ ERRO ao salvar alterações: {str(e)}")
                print("=" * 80)
        else:
            print()
            print("=" * 80)
            print("ℹ️  NENHUMA ALTERAÇÃO NECESSÁRIA")
            print("=" * 80)
            print(f"  • Todos os colaboradores já têm {nei.name} como gestor")
            print("=" * 80)

if __name__ == "__main__":
    import sys
    # Verificar se foi passado o argumento --confirm para confirmação automática
    auto_confirm = '--confirm' in sys.argv or '-y' in sys.argv
    adicionar_gestor_nei(auto_confirm=auto_confirm)
