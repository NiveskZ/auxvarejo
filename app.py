import os
import sys
from datetime import date
 
from flask import Flask, render_template
 
from database import get_db, get_config, get_secret_key, init_db, init_app as db_init_app
from utils import fmt_brl
 
from routes.produtos import bp as produtos_bp
from routes.vendas   import bp as vendas_bp
from routes.config   import bp as config_bp
from routes.cliente  import bp as cliente_bp

# ── CONFIG ─────────────────────────────────────────────────────────────────

# Pegando o caminho do executável empacotado
def resource_path(relative):
    """Resolve caminhos tanto no modo script quanto no modo .exe (PyInstaller)."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


# ── FACTORY ────────────────────────────────────────────────────────────────
def create_app(test_config=None):
    """
    Cria e configura a instância do Flask.
 
    Em produção, chamada sem argumentos.
    Em testes, recebe um dict com overrides (ex: SECRET_KEY, TESTING).
    Isso permite criar instâncias isoladas por teste sem compartilhar estado.
    """
    flask_app = Flask(__name__, template_folder=resource_path('templates'))
 
    if test_config:
        flask_app.config.update(test_config)
        flask_app.secret_key = test_config.get('SECRET_KEY', 'dev-test-key')
    else:
        flask_app.secret_key = get_secret_key()
 
    db_init_app(flask_app)
 
    flask_app.register_blueprint(produtos_bp)
    flask_app.register_blueprint(vendas_bp)
    flask_app.register_blueprint(config_bp)
    flask_app.register_blueprint(cliente_bp)
 
    @flask_app.route('/')
    def index():
        db   = get_db()
        hoje = date.today().strftime('%d/%m/%Y')
 
        total_produtos = db.execute("SELECT COUNT(*) as c FROM produtos").fetchone()['c']
        vendas_hoje    = db.execute("SELECT COUNT(*) as c FROM vendas WHERE data=?", (hoje,)).fetchone()['c']
        total_hoje     = db.execute("SELECT COALESCE(SUM(total),0) as t FROM vendas WHERE data=?", (hoje,)).fetchone()['t']
 
        config = {
            'nome_loja': get_config('nome_loja', ''),
            'desc_auto': get_config('desc_auto', '0'),
        }
        return render_template('index.html',
            total_produtos=total_produtos,
            vendas_hoje=vendas_hoje,
            total_hoje=fmt_brl(total_hoje),
            config=config,
        )
 
    return flask_app


# ── INSTÂNCIA GLOBAL ───────────────────────────────────────────────────────
app = create_app()


# ── MAIN ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import time
    import threading
    import webbrowser
 
    init_db()
 
    def abrir_browser():
        time.sleep(1)
        webbrowser.open('http://localhost:5000')
 
    threading.Thread(target=abrir_browser, daemon=True).start()
 
    print("=" * 50)
    print("  AuxVarejo iniciado!")
    print("  Acesse: http://localhost:5000")
    print("  Para encerrar: Ctrl+C ou feche a janela")
    print("=" * 50)
 
    app.run(host='127.0.0.1', port=5000, debug=False)
