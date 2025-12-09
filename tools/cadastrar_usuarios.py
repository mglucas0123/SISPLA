"""
Script para cadastrar usuários no sistema a partir de uma lista de nomes
- Nome normalizado (primeira letra maiúscula)
- Username: primeiro.ultimo nome
- Email: nomecompleto@email.com (sem espaços)
- Senha padrão: 12345678
- Profile: user

IMPORTANTE: Só cadastra usuários que NÃO existem no sistema!
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import db, User
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
import unicodedata

app = create_app()

# Lista de nomes dos usuários (copiada da planilha)
NOMES_USUARIOS = """
ADRIANA SILGUEIRO DOS REIS
ANA LUCIA DE ARAUJO
CLAUDIO SANTA ROSA FILHO
CLEIDE TOMAZ DE FREITAS LIMA
CLEONICE RIBEIRO BARBOSA PAULO
FERNANDA FREITAS COELHO
GEOVANA FERREIRA MORAIS
GUILHERME RODRIGUES SANTOS
ISILIDA ALICE SANCHES DOS SANTOS
JUCINEI SILVA MORAIS
JOANA DARC PEREIRA BARBOSA
LEIA FREITAS MARQUES
LORRAN HERNANDES SOUZA
LUZIA QUIRINO DE ALMEIDA
MICHELE PEREIRA DOS SANTOS FIEL
RAFAEL ANDRADE FREITAS FARIA
RAFAELA MARIA SILVA RODRIGUES
RODRIGO SOARES
RYAN DE CHRISTHAN SANCHES SILVA
SOBREIA APARECIDA DA SILVA
LEANDRO SILVA
JOAO LAZARO DA SILVA SANTOS
IONICA FERREIRA
CAMILA SANTA ROSA
ELAINE BORGES DA SILVA OLIVEIRA
ROSINEI FERREIRA BARBOSA
LUANA OLIVEIRA SILVA
APARECIDA ALINE IDENUSA
EVELINE FERREIRA DA SILVA PEREIRA
JESHLAINE VIEIRA LOPES DA SILVA
MANOELINA BENEDITA DE SOUZA
ROSANA APARECIDA ARAUJO SILVA
SUELEN APARECIDA RIBEIRO SANTIAGO BARBOSA
MARIA DE FATIMA FERNANDES SILVA
MARIO HERMES APARECIDO TEIXEIRA
VANESSA LENK REZENDE DE MATOS
VALQUIRIA SANTOS ROCHA
ANA CAROLINE FERNANDES PEREIRA
IZABELLA FREITAS BERALDO
ADRIANA SILVA MARTINS
MICHELE LEITE DA SILVA
MIRIAM CARLA DE SOUZA SANTOS
JULIANA FERREIRA SOLER
LAIRYS LARA FREITAS GARCIA
MARCO TULIO FERREIRA SOUZA
GIOVANNA QUEIROZ BORGES SEVERINO
MARIA AUXILIADORA AMARAL PACHECO
GEOVANNA CATALAO GIOVANI
LUCINEIA DIVINA DE FREITAS
JEAN CARLOS PEREIRA DE SOUZA
ANA GABRIELLA ALMEIDA MARRAS
TALITA CRISTINA FREITAS DA SILVA
ESTEFANE ARAUJO DE FREITAS BERNINI
LESELI GALDINO ARAUJO
JOSIANE SANTOS PESCHIETTI
RENATA SILVA SAMARINO
MARILEIA FARIA DINIZ
MELISSA MELO DA SILVA
ADRIANE GOMES SILVA
CARLOS EDUARDO FONSECA DA SILVA
PEDRO SILVA
""".strip().split('\n')


def normalizar_nome(nome):
    """Normaliza o nome: primeira letra maiúscula de cada palavra"""
    nome = ' '.join(nome.strip().split())
    
    conectivos = {'de', 'da', 'do', 'das', 'dos', 'e'}
    
    partes = nome.lower().split()
    resultado = []
    
    for i, parte in enumerate(partes):
        if i == 0:
            resultado.append(parte.capitalize())
        elif parte in conectivos:
            resultado.append(parte.lower())
        else:
            resultado.append(parte.capitalize())
    
    return ' '.join(resultado)


def remover_acentos(texto):
    """Remove acentos de um texto"""
    nfkd = unicodedata.normalize('NFKD', texto)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def gerar_username(nome):
    """Gera username no formato primeiro.ultimo"""
    partes = nome.lower().split()
    conectivos = {'de', 'da', 'do', 'das', 'dos', 'e'}
    partes_filtradas = [p for p in partes if p not in conectivos]
    
    if len(partes_filtradas) >= 2:
        primeiro = partes_filtradas[0]
        ultimo = partes_filtradas[-1]
        username = f"{primeiro}.{ultimo}"
    else:
        username = partes_filtradas[0] if partes_filtradas else partes[0]
    
    return remover_acentos(username)


def gerar_email(nome):
    """Gera email no formato nomecompleto@email.com (sem espaços)"""
    # Remove espaços e junta o nome todo
    nome_junto = nome.lower().replace(' ', '')
    return f"{remover_acentos(nome_junto)}@email.com"


def listar_preview():
    """Mostra uma prévia dos usuários que serão criados (sem salvar)"""
    with app.app_context():
        usuarios_sistema = User.query.all()
        nomes_existentes = set()
        for u in usuarios_sistema:
            nome_normalizado = ' '.join(u.name.strip().lower().split())
            nomes_existentes.add(nome_normalizado)
        
        novos = []
        existentes = []
        
        for nome_original in NOMES_USUARIOS:
            nome_original = nome_original.strip()
            if not nome_original:
                continue
            
            nome = normalizar_nome(nome_original)
            nome_comparacao = ' '.join(nome.lower().split())
            
            if nome_comparacao in nomes_existentes:
                existentes.append(nome)
            else:
                username = gerar_username(nome)
                email = gerar_email(nome)
                novos.append({'nome': nome, 'username': username, 'email': email})
        
        print(f"\n{'='*80}")
        print("ANALISE DOS USUARIOS")
        print(f"{'='*80}")
        print(f"\nTotal na planilha: {len(NOMES_USUARIOS)}")
        print(f"Ja existentes no sistema: {len(existentes)}")
        print(f"Novos a serem criados: {len(novos)}")
        
        if existentes:
            print(f"\n{'='*60}")
            print("USUARIOS JA EXISTENTES (serao ignorados):")
            print("-" * 60)
            for nome in existentes[:15]:
                print(f"  [OK] {nome}")
            if len(existentes) > 15:
                print(f"  ... e mais {len(existentes) - 15} usuarios")
        
        if novos:
            print(f"\n{'='*80}")
            print("NOVOS USUARIOS A SEREM CRIADOS:")
            print(f"{'='*80}")
            print(f"{'Nome':<40} {'Username':<20} {'Email':<25}")
            print("-" * 80)
            for u in novos:
                print(f"{u['nome']:<40} {u['username']:<20} {u['email']:<25}")
            print("-" * 80)
            print(f"\nSenha padrao para todos: 12345678")
        else:
            print(f"\n{'='*60}")
            print("NENHUM USUARIO NOVO PARA CRIAR!")
            print("Todos os usuarios da planilha ja existem no sistema.")
            print(f"{'='*60}")
        
        return len(novos)


def cadastrar_usuarios():
    """Cadastra apenas os usuários que NÃO existem no sistema"""
    with app.app_context():
        senha_hash = generate_password_hash('12345678')
        
        usuarios_criados = []
        usuarios_existentes = []
        usuarios_erro = []
        
        username_count = {}
        email_count = {}
        
        # Buscar todos os nomes já existentes no sistema
        usuarios_sistema = User.query.all()
        nomes_existentes = set()
        for u in usuarios_sistema:
            nome_normalizado = ' '.join(u.name.strip().lower().split())
            nomes_existentes.add(nome_normalizado)
        
        for nome_original in NOMES_USUARIOS:
            nome_original = nome_original.strip()
            if not nome_original:
                continue
            
            nome = normalizar_nome(nome_original)
            
            # Verifica se o usuário já existe pelo nome
            nome_comparacao = ' '.join(nome.lower().split())
            if nome_comparacao in nomes_existentes:
                usuarios_existentes.append(nome)
                continue
            
            username_base = gerar_username(nome)
            email_base = gerar_email(nome)
            
            # Gerar username único
            username = username_base
            if username in username_count:
                username_count[username] += 1
                username = f"{username_base}{username_count[username]}"
            else:
                username_count[username] = 0
                existente = User.query.filter_by(username=username).first()
                if existente:
                    username_count[username_base] = 1
                    username = f"{username_base}1"
            
            while User.query.filter_by(username=username).first():
                username_count[username_base] = username_count.get(username_base, 0) + 1
                username = f"{username_base}{username_count[username_base]}"
            
            # Gerar email único
            email = email_base
            if email in email_count:
                email_count[email] += 1
                primeiro_nome = email.split('@')[0]
                email = f"{primeiro_nome}{email_count[email]}@email.com"
            else:
                email_count[email] = 0
                existente = User.query.filter_by(email=email).first()
                if existente:
                    email_count[email_base] = 1
                    primeiro_nome = email_base.split('@')[0]
                    email = f"{primeiro_nome}1@email.com"
            
            while User.query.filter_by(email=email).first():
                email_count[email_base] = email_count.get(email_base, 0) + 1
                primeiro_nome = email_base.split('@')[0]
                email = f"{primeiro_nome}{email_count[email_base]}@email.com"
            
            try:
                novo_usuario = User(
                    name=nome,
                    username=username,
                    password=senha_hash,
                    email=email,
                    profile='user',
                    is_active=True,
                    creation_date=datetime.now(timezone.utc)
                )
                
                db.session.add(novo_usuario)
                usuarios_criados.append({
                    'nome': nome,
                    'username': username,
                    'email': email
                })
                
            except Exception as e:
                usuarios_erro.append({
                    'nome': nome,
                    'erro': str(e)
                })
        
        try:
            db.session.commit()
            print(f"\n{'='*60}")
            print(f"CADASTRO DE USUARIOS CONCLUIDO")
            print(f"{'='*60}")
            print(f"\nUsuarios ja existentes (ignorados): {len(usuarios_existentes)}")
            print(f"Usuarios criados: {len(usuarios_criados)}")
            print(f"Usuarios com erro: {len(usuarios_erro)}")
            
            if usuarios_criados:
                print(f"\n{'='*60}")
                print("USUARIOS CRIADOS:")
                print(f"{'='*60}")
                for u in usuarios_criados:
                    print(f"  Nome: {u['nome']}")
                    print(f"  Username: {u['username']}")
                    print(f"  Email: {u['email']}")
                    print(f"  Senha: 12345678")
                    print("-" * 40)
            
            if usuarios_erro:
                print(f"\n{'='*60}")
                print("ERROS:")
                print(f"{'='*60}")
                for u in usuarios_erro:
                    print(f"  Nome: {u['nome']}")
                    print(f"  Erro: {u['erro']}")
                    print("-" * 40)
                    
        except Exception as e:
            db.session.rollback()
            print(f"\nERRO ao salvar no banco de dados: {e}")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("SCRIPT DE CADASTRO DE USUARIOS")
    print("="*60)
    
    qtd_novos = listar_preview()
    
    if qtd_novos > 0:
        print("\n" + "="*60)
        resposta = input(f"\nDeseja cadastrar esses {qtd_novos} novos usuarios? (s/n): ").strip().lower()
        
        if resposta == 's':
            cadastrar_usuarios()
        else:
            print("\nOperacao cancelada.")
    else:
        print("\nNenhuma acao necessaria.")
