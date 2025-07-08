import sqlite3

# Conectar ao banco de dados existente
conn = sqlite3.connect('producao.db')
cursor = conn.cursor()

# Adicionar a coluna 'indice_linha' se ela ainda não existir
try:
    cursor.execute("ALTER TABLE linha_producao ADD COLUMN indice_linha INTEGER DEFAULT 0")
    print("Coluna 'indice_linha' adicionada com sucesso.")
except sqlite3.OperationalError as e:
    print(f"Erro (possivelmente a coluna já existe): {e}")

# Confirmar e fechar
conn.commit()
conn.close()
