"""
Script para corrigir nomes dos cargos:
- Converter para formato título (primeira letra maiúscula)
- Adicionar acentos corretamente
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, JobPosition

app = create_app()

# Mapeamento de correção dos nomes dos cargos
CORRECAO_CARGOS = {
    "AJUDANTE DE MANUTENÇÃO": "Ajudante de Manutenção",
    "ANALISTA ADMINISTRATIVO PL": "Analista Administrativo Pleno",
    "ANALISTA DE RH JR": "Analista de RH Júnior",
    "ANALISTA DE T.I PL": "Analista de T.I. Pleno",
    "APRENDIZ": "Aprendiz",
    "AUXILIAR DE FARMACIA": "Auxiliar de Farmácia",
    "AUXILIAR DE FATURAMENTO": "Auxiliar de Faturamento",
    "AUXILIAR DE HIGIENIZACAO": "Auxiliar de Higienização",
    "AUXILIAR DE LABORATORIO": "Auxiliar de Laboratório",
    "Assistente Administrativo": "Assistente Administrativo",
    "Assistente Social": "Assistente Social",
    "Auxiliar Administrativo": "Auxiliar Administrativo",
    "Auxiliar de Almoxarifado": "Auxiliar de Almoxarifado",
    "Auxiliar de Lavanderia": "Auxiliar de Lavanderia",
    "BIOMÉDICO": "Biomédico",
    "BIOQUÍMICO": "Bioquímico",
    "COORDENADOR DE HUMANIZACAO": "Coordenador de Humanização",
    "COORDENADOR DE SUPRIMENTOS": "Coordenador de Suprimentos",
    "Coordenador de Enfermagem": "Coordenador de Enfermagem",
    "DENTISTA": "Dentista",
    "ENFERMEIRO": "Enfermeiro",
    "ENFERMEIRO DA QUALIDADE": "Enfermeiro da Qualidade",
    "Encarregado de Manutenção": "Encarregado de Manutenção",
    "FISIOTERAPEUTA": "Fisioterapeuta",
    "Farmacêutico": "Farmacêutico",
    "GERENTE ASSISTENCIAL": "Gerente Assistencial",
    "GERENTE OPERACIONAL": "Gerente Operacional",
    "Gerente Administrativo": "Gerente Administrativo",
    "INSTRUMENTADOR CIRURGICO": "Instrumentador Cirúrgico",
    "Jardineiro": "Jardineiro",
    "LIDER DE LABORATORIO": "Líder de Laboratório",
    "Maqueiro": "Maqueiro",
    "OFICIAL ELÉTRICA": "Oficial Eletricista",
    "PSICÓLOGO": "Psicólogo",
    "TECNICO DE IMOBILIZACAO ORTOPEDICA": "Técnico de Imobilização Ortopédica",
    "TECNICO DE REFRIGERAÇÃO": "Técnico de Refrigeração",
    "TECNICO DE SEGURANCA NO TRABALHO JR": "Técnico de Segurança do Trabalho Júnior",
    "Técnico de Enfermagem": "Técnico de Enfermagem",
}

def main():
    with app.app_context():
        print("=" * 60)
        print("CORRIGINDO NOMES DOS CARGOS")
        print("=" * 60)
        
        cargos = JobPosition.query.all()
        corrigidos = 0
        
        for cargo in cargos:
            if cargo.name in CORRECAO_CARGOS:
                nome_novo = CORRECAO_CARGOS[cargo.name]
                if cargo.name != nome_novo:
                    print(f"   ✓ {cargo.name} → {nome_novo}")
                    cargo.name = nome_novo
                    corrigidos += 1
            else:
                print(f"   ⚠️  Cargo não mapeado: {cargo.name}")
        
        db.session.commit()
        
        print("\n" + "=" * 60)
        print(f"Total de cargos corrigidos: {corrigidos}")
        print("=" * 60)
        
        # Listar cargos finais
        print("\n📋 LISTA FINAL DE CARGOS:")
        print("-" * 60)
        cargos_finais = JobPosition.query.order_by(JobPosition.name).all()
        for cargo in cargos_finais:
            print(f"   • {cargo.name}")
        
        print("\n" + "=" * 60)
        print("Correção concluída!")
        print("=" * 60)

if __name__ == "__main__":
    main()
