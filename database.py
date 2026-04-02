import os
import sys
import secrets
import sqlite3
 
from flask import g

# Caminho do executável e do database
BASE_DIR = os.path.dirname(
    sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
)

DB_PATH = os.path.join(BASE_DIR, 'dados.db')


# Função para gerar chave secreta
def get_secret_key():
    """
    Gera uma chave aleatória na primeira execução e reutiliza nas seguintes.
    Fica armazenada no banco, não no código-fonte.
    """
    db = sqlite3.connect(DB_PATH)
    db.execute("CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT)")
    row = db.execute("SELECT valor FROM config WHERE chave='secret_key'").fetchone()
    if row:
        key = row[0]
    else:
        key = secrets.token_hex(32)
        db.execute("INSERT INTO config(chave,valor) VALUES('secret_key',?)", (key,))
        db.commit()
    db.close()
    return key


# -------- BANCO DE DADOS ------------------------------------------------------------------

# Conexão por request
def get_db():
    """Retorna a conexão SQLite do request atual (cria se não existir)."""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


def _close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()


def init_app(app):
    """Registra o teardown de conexão no app Flask."""
    app.teardown_appcontext(_close_db)


# Database
def init_db():
    """Cria as tabelas caso ainda não existam. Chamado no startup."""
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS config (
            chave TEXT PRIMARY KEY,
            valor TEXT
        );
        CREATE TABLE IF NOT EXISTS produtos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo        TEXT,
            codigo_barras TEXT,
            nome          TEXT NOT NULL,
            preco         REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS vendas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            data        TEXT NOT NULL,
            hora        TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            pagamento   TEXT NOT NULL DEFAULT 'Dinheiro',
            subtotal    REAL NOT NULL DEFAULT 0,
            desconto    REAL NOT NULL DEFAULT 0,
            total       REAL NOT NULL DEFAULT 0,
            registrado  INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS itens_venda (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id    INTEGER NOT NULL REFERENCES vendas(id),
            codigo      TEXT,
            nome        TEXT NOT NULL,
            preco_unit  REAL NOT NULL,
            quantidade  INTEGER NOT NULL,
            subtotal    REAL NOT NULL
        );
    """)
    db.commit()
    db.close()


# Configurações

def get_config(chave, padrao=''):
    row = get_db().execute("SELECT valor FROM config WHERE chave=?", (chave,)).fetchone()
    return row['valor'] if row else padrao


def set_config(chave, valor):
    get_db().execute("INSERT OR REPLACE INTO config(chave,valor) VALUES(?,?)", (chave, valor))
    get_db().commit()