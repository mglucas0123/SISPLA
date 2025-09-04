from app import create_app
from app.utils.rbac_permissions import initialize_rbac

app = create_app()

with app.app_context():
    initialize_rbac()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)