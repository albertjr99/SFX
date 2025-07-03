from sqlalchemy import create_engine, MetaData, Table
import pandas as pd

# Caminho para seu banco de dados local
caminho_db = r"C:\Users\albert.junior\Documents\sistema_producao\instance\producao.db"
engine = create_engine(f'sqlite:///{caminho_db}')

# Conexão e leitura das tabelas
with engine.connect() as conn:
    meta = MetaData()
    meta.reflect(bind=engine)

    for tabela in meta.tables.values():
        print(f'\nTabela: {tabela.name}')
        df = pd.read_sql_table(tabela.name, conn)
        print(df.head())
