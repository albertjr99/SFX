from app import app, db, Usuario
from werkzeug.security import generate_password_hash

analistas = [
    # Presencial
    {"nome": "Lucas",  "email": "lucas@stc.com",  "modalidade": "presencial"},
    {"nome": "Albert", "email": "albert@stc.com", "modalidade": "presencial"},
    {"nome": "Eric",   "email": "eric@stc.com",   "modalidade": "presencial"},
    {"nome": "Ana",    "email": "ana@stc.com",    "modalidade": "presencial"},

    # Teletrabalho
    {"nome": "Almino", "email": "almino@stc.com", "modalidade": "teletrabalho"},
]

with app.app_context():
    for a in analistas:
        usuario = Usuario(
            nome=a["nome"],
            email=a["email"],
            senha=generate_password_hash("123456"),
            tipo="analista",
            modalidade=a["modalidade"]
        )
        db.session.add(usuario)

    db.session.commit()
    print("✅ Analistas cadastrados com sucesso!")
