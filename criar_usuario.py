from app import app, db, Usuario
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()

    nome = "Aline"
    email = "aline@empresa.com"
    senha = "123456"
    tipo = "analista"  # <-- importante

    if not Usuario.query.filter_by(email=email).first():
        novo_usuario = Usuario(
            nome=nome,
            email=email,
            senha=generate_password_hash(senha),
            tipo=tipo
        )
        db.session.add(novo_usuario)
        db.session.commit()
        print("Usuário analista criado com sucesso!")
    else:
        print("Usuário já existe.")
