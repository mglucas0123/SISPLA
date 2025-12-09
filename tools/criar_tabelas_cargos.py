"""
Script para criar as tabelas de cargos e gestores diretamente no banco de produção
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db
from sqlalchemy import text
from datetime import datetime, timezone

app = create_app()

def main():
    with app.app_context():
        print("=" * 60)
        print("CRIANDO TABELAS DE CARGOS E GESTORES")
        print("=" * 60)
        
        conn = db.engine.connect()
        
        # 1. Criar tabela job_positions se não existir
        print("\n1. Verificando tabela job_positions...")
        try:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='job_positions'"))
            if not result.fetchone():
                print("   Criando tabela job_positions...")
                conn.execute(text("""
                    CREATE TABLE job_positions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(100) UNIQUE NOT NULL,
                        sector VARCHAR(100),
                        is_active BOOLEAN DEFAULT 1 NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.commit()
                print("   ✓ Tabela job_positions criada!")
            else:
                print("   ✓ Tabela job_positions já existe")
        except Exception as e:
            print(f"   ⚠ Erro: {e}")
        
        # 2. Adicionar colunas faltantes na tabela users
        print("\n2. Verificando colunas em users...")
        try:
            result = conn.execute(text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result.fetchall()]
            
            colunas_faltantes = {
                'job_position_id': 'INTEGER REFERENCES job_positions(id)',
                'totp_secret': 'VARCHAR(32)',
            }
            
            for coluna, tipo in colunas_faltantes.items():
                if coluna not in columns:
                    print(f"   Adicionando coluna {coluna}...")
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {coluna} {tipo}"))
                    conn.commit()
                    print(f"   ✓ Coluna {coluna} adicionada!")
                else:
                    print(f"   ✓ Coluna {coluna} já existe")
        except Exception as e:
            print(f"   ⚠ Erro: {e}")
        
        # 3. Criar tabela user_managers se não existir
        print("\n3. Verificando tabela user_managers...")
        try:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_managers'"))
            if not result.fetchone():
                print("   Criando tabela user_managers...")
                conn.execute(text("""
                    CREATE TABLE user_managers (
                        user_id INTEGER NOT NULL,
                        manager_id INTEGER NOT NULL,
                        PRIMARY KEY (user_id, manager_id),
                        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                        FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE
                    )
                """))
                conn.commit()
                print("   ✓ Tabela user_managers criada!")
            else:
                print("   ✓ Tabela user_managers já existe")
        except Exception as e:
            print(f"   ⚠ Erro: {e}")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("Estrutura do banco atualizada!")
        print("=" * 60)

if __name__ == "__main__":
    main()
