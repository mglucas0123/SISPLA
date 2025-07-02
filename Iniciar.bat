@echo off
TITLE Servidor do Sistema de Plantão

ECHO ##################################################
ECHO # INICIANDO PROTOTIPO - SISTEMA DE EXAMES        #
ECHO ##################################################
ECHO.

SET VENV_DIR=venv

REM Verificação Python
python --version > NUL 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO ERRO: Python nao encontrado.
    ECHO Por favor, instale o Python 3 e marque a opcao "Add Python to PATH".
    PAUSE
    EXIT /B 1
)

REM Cria o ambiente virtual
IF NOT EXIST "%VENV_DIR%\" (
    ECHO.
    ECHO Criando ambiente virtual...
    python -m venv %VENV_DIR%
    IF %ERRORLEVEL% NEQ 0 (
        ECHO ERRO: Falha ao criar o ambiente virtual.
        PAUSE
        EXIT /B 1
    )
)

ECHO.
ECHO Ativando ambiente virtual...
CALL "%VENV_DIR%\Scripts\activate.bat"

REM Instalar dependencias
ECHO.
ECHO Instalando dependencias do requirements.txt...
pip install -r requirements.txt
IF %ERRORLEVEL% NEQ 0 (
    ECHO ERRO: Falha ao instalar as dependencias.
    PAUSE
    EXIT /B 1
)

ECHO.
ECHO ====================================================================
ECHO  Servidor iniciado!
ECHO.
ECHO  A aplicacao esta rodando.
ECHO.
ECHO  Pressione CTRL+C nesta janela para parar o servidor.
ECHO ====================================================================
ECHO.

REM Iniciar o servidor de desenvolvimento do Flask
python app.py

PAUSE