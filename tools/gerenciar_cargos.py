"""
Script para gerenciar cargos do sistema
- Cria os cargos que estão na planilha mas não existem no sistema
- Remove cargos que não estão na planilha
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, User, JobPosition
from datetime import datetime, timezone

app = create_app()

# Lista de cargos que devem existir no sistema (extraídos da planilha)
CARGOS_PLANILHA = [
    "Gerente Administrativo",
    "Gerente Operacional",
    "Gerente Assistencial",
    "Coordenador de Enfermagem",
    "Coordenador de Suprimentos",
    "Coordenador de Humanização",
    "Enfermeiro",
    "Enfermeiro da Qualidade",
    "Técnico de Enfermagem",
    "Técnico de Imobilização Ortopédica",
    "Técnico de Segurança do Trabalho Júnior",
    "Técnico de Refrigeração",
    "Instrumentador Cirúrgico",
    "Fisioterapeuta",
    "Farmacêutico",
    "Bioquímico",
    "Biomédico",
    "Dentista",
    "Psicólogo",
    "Assistente Social",
    "Assistente Administrativo",
    "Auxiliar Administrativo",
    "Auxiliar de Almoxarifado",
    "Auxiliar de Farmácia",
    "Auxiliar de Laboratório",
    "Auxiliar de Faturamento",
    "Auxiliar de Higienização",
    "Auxiliar de Lavanderia",
    "Analista Administrativo Pleno",
    "Analista de T.I. Pleno",
    "Analista de RH Júnior",
    "Líder de Laboratório",
    "Encarregado de Manutenção",
    "Maqueiro",
    "Jardineiro",
    "Ajudante de Manutenção",
    "Oficial Eletricista",
    "Aprendiz",
]

def normalizar_cargo(nome):
    """Normaliza nome do cargo para comparação"""
    import unicodedata
    if not nome:
        return ""
    nome = unicodedata.normalize('NFKD', nome)
    nome = ''.join(c for c in nome if not unicodedata.combining(c))
    return ' '.join(nome.upper().split())

def main():
    with app.app_context():
        print("=" * 60)
        print("GERENCIAMENTO DE CARGOS DO SISTEMA")
        print("=" * 60)
        
        # Buscar todos os cargos existentes
        cargos_existentes = JobPosition.query.all()
        print(f"Total de cargos no sistema: {len(cargos_existentes)}")
        print(f"Total de cargos na planilha: {len(CARGOS_PLANILHA)}")
        print("=" * 60)
        
        # Normalizar nomes dos cargos da planilha
        cargos_planilha_norm = {normalizar_cargo(c): c for c in CARGOS_PLANILHA}
        
        # Criar dict de cargos existentes
        cargos_existentes_dict = {}
        for cargo in cargos_existentes:
            nome_norm = normalizar_cargo(cargo.name)
            cargos_existentes_dict[nome_norm] = cargo
        
        # 1. CRIAR CARGOS QUE NÃO EXISTEM
        print("\n📝 CRIANDO CARGOS NOVOS:")
        print("-" * 60)
        cargos_criados = 0
        
        for cargo_norm, cargo_original in cargos_planilha_norm.items():
            if cargo_norm not in cargos_existentes_dict:
                novo_cargo = JobPosition(
                    name=cargo_original,
                    is_active=True
                )
                db.session.add(novo_cargo)
                print(f"   ✓ Criado: {cargo_original}")
                cargos_criados += 1
        
        if cargos_criados == 0:
            print("   Nenhum cargo novo para criar.")
        
        db.session.commit()
        
        # 2. IDENTIFICAR CARGOS PARA REMOVER
        print("\n🗑️  CARGOS A SEREM REMOVIDOS (não estão na planilha):")
        print("-" * 60)
        
        cargos_para_remover = []
        cargos_em_uso = []
        
        for cargo_norm, cargo in cargos_existentes_dict.items():
            if cargo_norm not in cargos_planilha_norm:
                # Verificar se o cargo está em uso
                usuarios_com_cargo = User.query.filter_by(job_position_id=cargo.id).count()
                
                if usuarios_com_cargo > 0:
                    cargos_em_uso.append((cargo, usuarios_com_cargo))
                    print(f"   ⚠️  {cargo.name} - EM USO por {usuarios_com_cargo} usuário(s)")
                else:
                    cargos_para_remover.append(cargo)
                    print(f"   ✓ {cargo.name} - pode ser removido")
        
        # 3. REMOVER CARGOS NÃO UTILIZADOS
        print("\n🗑️  REMOVENDO CARGOS NÃO UTILIZADOS:")
        print("-" * 60)
        cargos_removidos = 0
        
        for cargo in cargos_para_remover:
            db.session.delete(cargo)
            print(f"   ✓ Removido: {cargo.name}")
            cargos_removidos += 1
        
        if cargos_removidos == 0:
            print("   Nenhum cargo para remover.")
        
        db.session.commit()
        
        # 4. RELATÓRIO FINAL
        print("\n" + "=" * 60)
        print("RELATÓRIO FINAL")
        print("=" * 60)
        print(f"Cargos criados: {cargos_criados}")
        print(f"Cargos removidos: {cargos_removidos}")
        
        if cargos_em_uso:
            print(f"\n⚠️  {len(cargos_em_uso)} cargos NÃO foram removidos por estarem em uso:")
            for cargo, qtd in cargos_em_uso:
                print(f"   - {cargo.name} ({qtd} usuário(s))")
            print("\n   Para removê-los, primeiro atualize os usuários para outro cargo.")
        
        # Mostrar cargos finais
        cargos_finais = JobPosition.query.order_by(JobPosition.name).all()
        print(f"\n📋 LISTA FINAL DE CARGOS ({len(cargos_finais)}):")
        print("-" * 60)
        for cargo in cargos_finais:
            usuarios = User.query.filter_by(job_position_id=cargo.id).count()
            status = f"({usuarios} usuários)" if usuarios > 0 else "(sem usuários)"
            print(f"   • {cargo.name} {status}")
        
        print("\n" + "=" * 60)
        print("Gerenciamento de cargos concluído!")
        print("=" * 60)

if __name__ == "__main__":
    main()
