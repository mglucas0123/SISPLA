"""
Script para comparar nomes nao encontrados na planilha com usuarios do sistema
e identificar possiveis correspondencias por similaridade de nomes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, User, JobPosition
from difflib import SequenceMatcher
import unicodedata

app = create_app()

# Importar os dados da planilha do outro script
from atualizar_cargos_gestores_v2 import DADOS_PLANILHA, normalizar_nome, encontrar_usuario_por_nome


def calcular_similaridade(nome1, nome2):
    """Calcula a similaridade entre dois nomes (0 a 1)"""
    return SequenceMatcher(None, nome1, nome2).ratio()


def similaridade_por_partes(nome1, nome2):
    """
    Calcula similaridade considerando partes do nome.
    Retorna tuple: (score, tipo_match)
    """
    partes1 = normalizar_nome(nome1).split()
    partes2 = normalizar_nome(nome2).split()
    
    if not partes1 or not partes2:
        return 0, "nenhum"
    
    # Primeiro nome igual
    primeiro_igual = partes1[0] == partes2[0] if partes1 and partes2 else False
    
    # Ultimo nome igual
    ultimo_igual = partes1[-1] == partes2[-1] if partes1 and partes2 else False
    
    # Contar partes iguais
    partes_comuns = set(partes1) & set(partes2)
    total_partes = len(set(partes1) | set(partes2))
    score_partes = len(partes_comuns) / total_partes if total_partes > 0 else 0
    
    # Calcular score combinado
    score = 0
    tipo = []
    
    if primeiro_igual:
        score += 0.4
        tipo.append("primeiro nome")
    
    if ultimo_igual:
        score += 0.4
        tipo.append("ultimo nome")
    
    score += score_partes * 0.2
    
    # Similaridade geral do texto
    sim_texto = calcular_similaridade(normalizar_nome(nome1), normalizar_nome(nome2))
    
    # Score final: media ponderada
    score_final = score * 0.6 + sim_texto * 0.4
    
    tipo_match = ", ".join(tipo) if tipo else f"similaridade {sim_texto:.0%}"
    
    return score_final, tipo_match


def encontrar_nomes_similares(nome_planilha, usuarios, limite_min=0.4, top_n=3):
    """
    Encontra os N usuarios mais similares ao nome da planilha
    Retorna lista de tuplas: (usuario, score, tipo_match)
    """
    resultados = []
    
    for user in usuarios:
        score, tipo = similaridade_por_partes(nome_planilha, user.name)
        if score >= limite_min:
            resultados.append((user, score, tipo))
    
    # Ordenar por score decrescente
    resultados.sort(key=lambda x: x[1], reverse=True)
    
    return resultados[:top_n]


def main():
    with app.app_context():
        print("=" * 90)
        print("ANALISE DE NOMES NAO ENCONTRADOS - BUSCA POR SIMILARIDADE")
        print("=" * 90)
        
        # Carregar dados
        usuarios = User.query.all()
        cargos = JobPosition.query.all()
        
        # Criar dicionario de cargos por id
        cargos_dict = {c.id: c.name for c in cargos}
        
        print(f"Total de usuarios no sistema: {len(usuarios)}")
        print(f"Total de registros na planilha: {len(DADOS_PLANILHA)}")
        
        # Identificar usuarios sem cargo ou gestor no sistema
        usuarios_sem_cargo = [u for u in usuarios if not u.job_position_id]
        usuarios_sem_gestor = [u for u in usuarios if not u.assigned_managers]
        usuarios_incompletos = [u for u in usuarios if not u.job_position_id or not u.assigned_managers]
        
        print(f"Usuarios sem cargo no sistema: {len(usuarios_sem_cargo)}")
        print(f"Usuarios sem gestor no sistema: {len(usuarios_sem_gestor)}")
        print(f"Usuarios sem cargo OU sem gestor: {len(usuarios_incompletos)}")
        
        # Identificar nomes nao encontrados na planilha
        nao_encontrados = []
        for nome, data, nome_gestor, cargo_planilha in DADOS_PLANILHA:
            usuario = encontrar_usuario_por_nome(nome, usuarios)
            if not usuario:
                nao_encontrados.append((nome, data, nome_gestor, cargo_planilha))
        
        print(f"Colaboradores da planilha nao encontrados no sistema: {len(nao_encontrados)}")
        print("=" * 90)
        
        # Armazenar possiveis correcoes
        possiveis_correcoes = []
        
        print("\n" + "=" * 90)
        print("ANALISE DETALHADA DE NOMES NAO ENCONTRADOS")
        print("=" * 90)
        
        for nome_excel, data, gestor, cargo in nao_encontrados:
            print(f"\n[PLANILHA] {nome_excel}")
            print(f"   Cargo na planilha: {cargo}")
            print(f"   Gestor na planilha: {gestor}")
            print(f"   Data: {data}")
            
            # Buscar usuarios similares (priorizar os sem cargo/gestor)
            similares_incompletos = encontrar_nomes_similares(nome_excel, usuarios_incompletos, limite_min=0.35, top_n=5)
            similares_todos = encontrar_nomes_similares(nome_excel, usuarios, limite_min=0.35, top_n=5)
            
            if similares_incompletos:
                print(f"\n   [?] Possiveis correspondencias (usuarios SEM cargo/gestor):")
                for user, score, tipo in similares_incompletos:
                    cargo_atual = cargos_dict.get(user.job_position_id, "Sem cargo")
                    tem_gestor = "Sim" if user.assigned_managers else "Nao"
                    print(f"      -> {user.name}")
                    print(f"        Score: {score:.0%} | Match: {tipo}")
                    print(f"        Cargo atual: {cargo_atual} | Tem gestor: {tem_gestor}")
                    
                    # Se score > 60%, adicionar como possivel correcao
                    if score >= 0.60:
                        possiveis_correcoes.append({
                            'nome_excel': nome_excel,
                            'nome_sistema': user.name,
                            'user_id': user.id,
                            'score': score,
                            'cargo_planilha': cargo,
                            'gestor_planilha': gestor
                        })
            
            # Mostrar tambem matches de todos os usuarios
            print(f"\n   [*] Correspondencias em TODOS os usuarios:")
            if similares_todos:
                for user, score, tipo in similares_todos[:3]:
                    cargo_atual = cargos_dict.get(user.job_position_id, "Sem cargo")
                    tem_gestor = "Sim" if user.assigned_managers else "Nao"
                    print(f"      -> {user.name}")
                    print(f"        Score: {score:.0%} | Cargo: {cargo_atual} | Gestor: {tem_gestor}")
            else:
                print(f"      (nenhuma correspondencia encontrada)")
        
        # Resumo das possiveis correcoes
        print("\n" + "=" * 90)
        print("RESUMO: POSSIVEIS CORRECOES DE NOMES (Score >= 60%)")
        print("=" * 90)
        
        if possiveis_correcoes:
            print(f"\nEncontradas {len(possiveis_correcoes)} possiveis correcoes:\n")
            for i, corr in enumerate(possiveis_correcoes, 1):
                print(f"{i}. EXCEL: \"{corr['nome_excel']}\"")
                print(f"   SISTEMA: \"{corr['nome_sistema']}\" (ID: {corr['user_id']})")
                print(f"   Score: {corr['score']:.0%}")
                print()
        else:
            print("\nNenhuma correcao automatica identificada com score >= 60%.")
        
        # Gerar relatorio de todos os usuarios incompletos para referencia
        print("\n" + "=" * 90)
        print("LISTA COMPLETA: USUARIOS SEM CARGO OU SEM GESTOR NO SISTEMA")
        print("=" * 90)
        
        for user in sorted(usuarios_incompletos, key=lambda x: x.name):
            cargo_atual = cargos_dict.get(user.job_position_id, "[X] Sem cargo")
            tem_gestor = "[v] Sim" if user.assigned_managers else "[X] Nao"
            print(f"   {user.name}")
            print(f"      Cargo: {cargo_atual} | Gestor: {tem_gestor}")
        
        print("\n" + "=" * 90)
        print("ANALISE CONCLUIDA")
        print("=" * 90)
        
        return possiveis_correcoes


if __name__ == "__main__":
    main()
