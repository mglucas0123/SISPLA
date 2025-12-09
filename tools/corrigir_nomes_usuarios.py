"""
Script para CORRIGIR nomes de usuários no sistema
baseado nas discrepâncias encontradas entre a planilha Excel e o sistema.

⚠️ ATENÇÃO: Este script irá MODIFICAR os nomes dos usuários no banco de dados!
Execute apenas após revisar as correções sugeridas.

Para executar: python tools/corrigir_nomes_usuarios.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, User
from datetime import datetime

app = create_app()

# ============================================================================
# CORRECOES A SEREM APLICADAS
# Formato: (user_id, nome_atual_sistema, nome_correto_excel)
# 
# Identificadas pelo script comparar_nomes_similares.py em 05/12/2025
# REVISADO com base na planilha Excel original
# ============================================================================
CORRECOES = [
    # ============================================================================
    # ANALISE FINAL: OS NOMES NO SISTEMA ESTAO CORRETOS!
    # ============================================================================
    # Apos revisar a planilha Excel original, verificou-se que:
    # - Os nomes no sistema correspondem aos nomes da planilha
    # - LUANA OLIVEIRA SILVA e uma pessoa DIFERENTE de Lucineia Oliveira da Silva
    # - LUANA OLIVEIRA SILVA (Aux. Higienizacao) NAO esta cadastrada no sistema
    #   e precisa ser CADASTRADA, nao corrigida
    #
    # COLABORADORES QUE PRECISAM SER CADASTRADOS NO SISTEMA:
    # (nao estao no sistema e precisam ser adicionados)
    # - LUANA OLIVEIRA SILVA (Aux. Higienizacao)
    # - LEANDRO SILVA (Tec. Imobilizacao Ort)
    # - JOAO LAZARO DA SILVA SANTOS (Aux. Lavanderia)
    # - IONICA FERREIRA (Tec. Enfermagem)
    # - CAMILA SANTA ROSA (Aux. Administrativo)
    # - ELAINE BORGES DA SILVA OLIVEIRA (Aux. Higienizacao)
    # - ROSINEI FERREIRA BARBOSA (Aux. Higienizacao)
    # - E varios outros...
    #
    # Para ver a lista completa, execute:
    # python tools/comparar_nomes_similares.py
    # ============================================================================
]


def main():
    """Executa as correções de nomes"""
    
    if not CORRECOES:
        print("=" * 70)
        print("CORREÇÃO DE NOMES DE USUÁRIOS")
        print("=" * 70)
        print("\n⚠️  NENHUMA CORREÇÃO DEFINIDA!")
        print("\nPara usar este script:")
        print("1. Execute primeiro: python tools/comparar_nomes_similares.py")
        print("2. Revise o relatório e identifique os nomes a corrigir")
        print("3. Adicione as correções na lista CORRECOES neste arquivo")
        print("4. Execute novamente este script")
        print("\nFormato das correções:")
        print('   (user_id, "Nome Atual", "Nome Correto"),')
        print("=" * 70)
        return
    
    with app.app_context():
        print("=" * 70)
        print("CORREÇÃO DE NOMES DE USUÁRIOS")
        print(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print("=" * 70)
        print(f"\nTotal de correções a aplicar: {len(CORRECOES)}")
        
        # Mostrar o que será alterado
        print("\n" + "-" * 70)
        print("ALTERAÇÕES QUE SERÃO REALIZADAS:")
        print("-" * 70)
        
        usuarios_validos = []
        for user_id, nome_atual, nome_correto in CORRECOES:
            user = User.query.get(user_id)
            if user:
                usuarios_validos.append((user, nome_correto))
                print(f"\n  ID: {user_id}")
                print(f"  Atual:   \"{user.name}\"")
                print(f"  Novo:    \"{nome_correto}\"")
                if user.name != nome_atual:
                    print(f"  ⚠️ AVISO: Nome atual difere do esperado!")
                    print(f"  Esperado: \"{nome_atual}\"")
            else:
                print(f"\n  ❌ ERRO: Usuário ID {user_id} não encontrado!")
        
        if not usuarios_validos:
            print("\n❌ Nenhum usuário válido para corrigir.")
            return
        
        # Confirmação antes de aplicar
        print("\n" + "-" * 70)
        print(f"Serão corrigidos {len(usuarios_validos)} usuário(s).")
        print("-" * 70)
        
        resposta = input("\n⚠️  Deseja aplicar estas correções? (sim/não): ").strip().lower()
        
        if resposta not in ['sim', 's', 'yes', 'y']:
            print("\n❌ Operação cancelada pelo usuário.")
            return
        
        # Aplicar correções
        print("\n" + "=" * 70)
        print("APLICANDO CORREÇÕES...")
        print("=" * 70)
        
        for user, nome_correto in usuarios_validos:
            nome_antigo = user.name
            user.name = nome_correto
            print(f"✓ {nome_antigo} → {nome_correto}")
        
        db.session.commit()
        
        print("\n" + "=" * 70)
        print(f"✅ {len(usuarios_validos)} nome(s) corrigido(s) com sucesso!")
        print("=" * 70)
        
        print("\n📌 Próximo passo: Execute novamente o script de atualização de cargos/gestores")
        print("   python tools/atualizar_cargos_gestores_v2.py")


if __name__ == "__main__":
    main()
