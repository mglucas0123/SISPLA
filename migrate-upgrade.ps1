$env:PYTHONPATH = "."
$env:FLASK_APP = "main:create_app"
flask migrate-upgrade