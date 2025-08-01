$venvPath = ".\venv"

if (-Not (Test-Path $venvPath)) {
    Write-Host "Criando ambiente virtual..."
    python -m venv $venvPath
} else {
    Write-Host "Ambiente virtual já existe."
}

Write-Host "Ativando ambiente virtual..."
$activateScript = "$venvPath\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    . $activateScript
} else {
    Write-Error "Script de ativação não encontrado!"
    exit 1
}

Write-Host "Atualizando pip..."
pip install --upgrade pip

Write-Host "Instalando dependências..."
pip install -r requirements.txt

Write-Host "Iniciando o app Python..."
python main.py
