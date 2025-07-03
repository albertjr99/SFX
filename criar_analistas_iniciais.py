from app import app, db, Usuario
from werkzeug.security import generate_password_hash

analistas = [
    # Presencial
    {"nome": "Shirlene", "email": "shirlene@stc.com", "modalidade": "presencial"},
    {"nome": "Aline", "email": "aline@stc.com", "modalidade": "presencial"},
    {"nome": "Mariana", "email": "mariana@stc.com", "modalidade": "presencial"},
    {"nome": "Ana Lucia", "email": "analucia@stc.com", "modalidade": "presencial"},
    {"nome": "Caroline", "email": "caroline@stc.com", "modalidade": "presencial"},
    {"nome": "Flávia", "email": "flavia@stc.com", "modalidade": "presencial"},

    # Teletrabalho
    {"nome": "Antonio Henrique", "email": "antonio@stc.com", "modalidade": "teletrabalho"},
    {"nome": "Fabriciano", "email": "fabriciano@stc.com", "modalidade": "teletrabalho"},
    {"nome": "Talmom", "email": "talmom@stc.com", "modalidade": "teletrabalho"},
    {"nome": "Cristina", "email": "cristina@stc.com", "modalidade": "teletrabalho"},
    {"nome": "Alexandre", "email": "alexandre@stc.com", "modalidade": "teletrabalho"},
    {"nome": "Gileade", "email": "gileade@stc.com", "modalidade": "teletrabalho"},
    {"nome": "Silvana", "email": "silvana@stc.com", "modalidade": "teletrabalho"},
    {"nome": "Soraya", "email": "soraya@stc.com", "modalidade": "teletrabalho"},
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

