from app import app, db, Usuario
from werkzeug.security import generate_password_hash

usuarios = [
    {"nome": "Caio", "email": "caio@stc.com", "tipo": "subgerente"},
    {"nome": "Daniella", "email": "daniella@stc.com", "tipo": "gerente"},
    {"nome": "Anapaula", "email": "anapaula@stc.com", "tipo": "diretora"},
    {"nome": "Kethlen", "email": "kethlen@stc.com", "tipo": "estagiaria"},
    {"nome": "Anna Clara", "email": "annaclara@stc.com", "tipo": "estagiaria"}
]

with app.app_context():
    for u in usuarios:
        existente = Usuario.query.filter_by(email=u["email"]).first()
        if not existente:
            novo = Usuario(
                nome=u["nome"],
                email=u["email"],
                senha=generate_password_hash("123"),
                tipo=u["tipo"],
                modalidade=''
            )
            db.session.add(novo)
    db.session.commit()

print("✅ Usuários administrativos criados com sucesso.")

