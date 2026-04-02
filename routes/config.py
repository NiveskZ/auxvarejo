import io
import threading
 
from flask import Blueprint, request, jsonify, send_file
 
from database import DB_PATH, get_config, set_config
 
bp = Blueprint('config', __name__)
 
 
# ── CONFIGURAÇÕES ──────────────────────────────────────────────────────────
 
@bp.route('/config', methods=['POST'])
def salvar_config():
    data = request.get_json()
    for chave, valor in data.items():
        set_config(chave, str(valor))
    return jsonify({'ok': True})
 
 
@bp.route('/config/verificar-senha', methods=['POST'])
def verificar_senha():
    data          = request.get_json()
    senha_correta = get_config('senha', '')
    if not senha_correta:
        return jsonify({'ok': True, 'liberado': True})
    return jsonify({'ok': True, 'liberado': data.get('senha') == senha_correta})
 
 
# ── MODELO CSV ─────────────────────────────────────────────────────────────
 
@bp.route('/modelo.csv')
def modelo_csv():
    conteudo = 'cod,produto,pv\n001,Arroz 5kg,22.90\n002,Feijão 1kg,8.50\n003,Óleo 900ml,7.99\n'
    return send_file(
        io.BytesIO(conteudo.encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='modelo_produtos.csv',
    )
 
 
# ── BACKUP ─────────────────────────────────────────────────────────────────
 
@bp.route('/backup')
def backup():
    """Download direto do banco de dados para backup manual."""
    from datetime import date
    nome = f"backup_auxvarejo_{date.today().strftime('%Y-%m-%d')}.db"
    return send_file(DB_PATH, as_attachment=True, download_name=nome)
 
 
# ── ENCERRAR ───────────────────────────────────────────────────────────────
 
@bp.route('/encerrar', methods=['POST'])
def encerrar():
    """Encerra o processo Flask — útil no Windows para não ficar rodando em background."""
    def _stop():
        import time
        import os
        time.sleep(0.5)
        os._exit(0)
 
    threading.Thread(target=_stop, daemon=True).start()
    return jsonify({'ok': True})
 