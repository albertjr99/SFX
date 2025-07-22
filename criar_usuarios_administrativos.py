from app import app, db, Usuario
from werkzeug.security import generate_password_hash

usuarios = [
    {"nome": "Doris", "email": "doris@stc.com", "tipo": "subgerente"},
    {"nome": "Daniella", "email": "daniella@stc.com", "tipo": "gerente"},
    {"nome": "Anapaula", "email": "anapaula@stc.com", "tipo": "diretora"},
    {"nome": "Gabriela", "email": "gabriela@stc.com", "tipo": "estagiaria"},
    {"nome": "Andressa", "email": "andressa@stc.com", "tipo": "estagiaria"}
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

