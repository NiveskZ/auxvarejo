import csv
import io
from collections import OrderedDict
from datetime import datetime, date
 
from flask import Blueprint, request, jsonify, send_file
 
from database import get_db
from utils import fmt_brl
 
bp = Blueprint('vendas', __name__)
 
 
# ---- Registro de Vendas ----------------------------------------------------------------
 
@bp.route('/venda', methods=['POST'])
def registrar_venda():
    data = request.get_json()
    if not data or not data.get('itens'):
        return jsonify({'ok': False, 'msg': 'Carrinho vazio'}), 400
 
    now       = datetime.now()
    pagamento = data.get('pagamento', 'Dinheiro')
    subtotal  = float(data.get('subtotal', 0))
    desconto  = float(data.get('desconto', 0))
    total     = float(data.get('total', 0))
 
    db  = get_db()
    cur = db.execute(
        "INSERT INTO vendas(data, hora, timestamp, pagamento, subtotal, desconto, total) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (now.strftime('%d/%m/%Y'), now.strftime('%H:%M:%S'), now.isoformat(),
         pagamento, subtotal, desconto, total)
    )
    venda_id = cur.lastrowid
 
    for item in data['itens']:
        qty   = int(item['qty'])
        preco = float(item['preco'])
        db.execute(
            "INSERT INTO itens_venda(venda_id, codigo, nome, preco_unit, quantidade, subtotal) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (venda_id, item.get('codigo', ''), item['nome'], preco, qty, preco * qty)
        )
    db.commit()
 
    return jsonify({'ok': True, 'venda': _serializar_venda(venda_id)})
 
 
# Detalhes de uma venda por ID
 
@bp.route('/venda/<int:venda_id>')
def get_venda(venda_id):
    v = get_db().execute("SELECT * FROM vendas WHERE id=?", (venda_id,)).fetchone()
    if not v:
        return jsonify({'ok': False}), 404
    return jsonify({'ok': True, 'venda': _serializar_venda(venda_id)})
 
 
@bp.route('/venda/<int:venda_id>/registrado', methods=['POST'])
def marcar_registrado(venda_id):
    data  = request.get_json()
    valor = 1 if data.get('registrado') else 0
    get_db().execute("UPDATE vendas SET registrado=? WHERE id=?", (valor, venda_id))
    get_db().commit()
    return jsonify({'ok': True})
 
 
# ── HISTÓRICO ──────────────────────────────────────────────────────────────
 
@bp.route('/historico')
def historico():
    db           = get_db()
    filtro_data  = request.args.get('data',       '').strip()
    filtro_pag   = request.args.get('pagamento',  '').strip()
    filtro_hora  = request.args.get('hora',       '').strip()
    filtro_reg   = request.args.get('registrado', '').strip()
 
    sql    = "SELECT * FROM vendas WHERE 1=1"
    params = []
    if filtro_data: sql += " AND data=?";          params.append(filtro_data)
    if filtro_hora: sql += " AND hora LIKE ?";     params.append(filtro_hora + '%')
    if filtro_pag:  sql += " AND pagamento=?";     params.append(filtro_pag)
    if filtro_reg == 'nao': sql += " AND registrado=0"
    elif filtro_reg == 'sim': sql += " AND registrado=1"
    sql += " ORDER BY id DESC LIMIT 200"
 
    vendas    = db.execute(sql, params).fetchall()
    resultado = []
    for v in vendas:
        itens = db.execute("SELECT * FROM itens_venda WHERE venda_id=?", (v['id'],)).fetchall()
        resultado.append({
            'id':           v['id'],
            'data':         v['data'],
            'hora':         v['hora'],
            'pagamento':    v['pagamento'],
            'subtotal':     fmt_brl(v['subtotal']),
            'desconto':     fmt_brl(v['desconto']),
            'total':        fmt_brl(v['total']),
            'tem_desconto': v['desconto'] > 0,
            'registrado':   bool(v['registrado']),
            'itens': [{
                'nome':       i['nome'],
                'codigo':     i['codigo'],
                'quantidade': i['quantidade'],
                'preco_unit': fmt_brl(i['preco_unit']),
                'subtotal':   fmt_brl(i['subtotal']),
            } for i in itens],
        })
    return jsonify(resultado)
 
 
@bp.route('/historico/limpar', methods=['POST'])
def limpar_historico():
    db = get_db()
    db.execute("DELETE FROM itens_venda")
    db.execute("DELETE FROM vendas")
    db.commit()
    return jsonify({'ok': True})
 
 
# ── EXPORTAR CSV ───────────────────────────────────────────────────────────
 
@bp.route('/exportar/csv')
def exportar_csv():
    db          = get_db()
    filtro_data = request.args.get('data', '').strip()
 
    sql = (
        "SELECT v.id, v.data, v.hora, v.timestamp, v.pagamento, v.desconto, v.total, "
        "       i.codigo as i_cod, i.nome as i_nome, i.preco_unit, i.quantidade, i.subtotal as i_sub "
        "FROM vendas v JOIN itens_venda i ON i.venda_id = v.id"
    )
    params = []
    if filtro_data:
        sql += " WHERE v.data=?"
        params.append(filtro_data)
    sql += " ORDER BY v.id, i.id"
 
    rows   = db.execute(sql, params).fetchall()
    output = io.StringIO()
    w      = csv.writer(output)
    w.writerow([
        'id_venda', 'data', 'hora', 'timestamp_iso', 'pagamento',
        'codigo_produto', 'nome_produto', 'preco_unitario', 'quantidade',
        'subtotal_item', 'desconto_venda', 'total_venda',
    ])
    for r in rows:
        w.writerow([
            r['id'], r['data'], r['hora'], r['timestamp'], r['pagamento'],
            r['i_cod'], r['i_nome'], r['preco_unit'], r['quantidade'],
            r['i_sub'], r['desconto'], r['total'],
        ])
 
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f"vendas_{date.today().strftime('%Y-%m-%d')}.csv",
    )
 
 
# ── EXPORTAR RELATÓRIO TXT ─────────────────────────────────────────────────
 
@bp.route('/exportar/relatorio')
def exportar_relatorio():
    """Exporta relatório TXT separado por venda, para lançamento manual no sistema."""
    db          = get_db()
    filtro_data = request.args.get('data',        '').strip()
    filtro_reg  = request.args.get('registrado',  '').strip()
 
    sql = (
        "SELECT v.id, v.data, v.hora, v.pagamento, v.subtotal, v.desconto, v.total, v.registrado, "
        "       i.codigo as i_cod, i.codigo_barras as i_bar, i.nome as i_nome, "
        "       i.preco_unit, i.quantidade, i.subtotal as i_sub "
        "FROM vendas v JOIN itens_venda i ON i.venda_id = v.id"
    )
    params     = []
    conditions = []
    if filtro_data: conditions.append("v.data=?");        params.append(filtro_data)
    if filtro_reg == 'nao': conditions.append("v.registrado=0")
    elif filtro_reg == 'sim': conditions.append("v.registrado=1")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY v.id, i.id"
 
    rows = db.execute(sql, params).fetchall()
 
    # Agrupa por venda
    vendas_map = OrderedDict()
    for r in rows:
        vid = r['id']
        if vid not in vendas_map:
            vendas_map[vid] = {
                'id': r['id'], 'data': r['data'], 'hora': r['hora'],
                'pagamento': r['pagamento'], 'subtotal': r['subtotal'],
                'desconto': r['desconto'], 'total': r['total'],
                'registrado': r['registrado'], 'itens': []
            }
        vendas_map[vid]['itens'].append({
            'codigo': r['i_cod'], 'codigo_barras': r['i_bar'],
            'nome': r['i_nome'], 'preco_unit': r['preco_unit'],
            'quantidade': r['quantidade'], 'subtotal': r['i_sub']
        })
 
    linhas = []
    linhas.append('=' * 60)
    linhas.append('  RELATÓRIO DE VENDAS — AuxVarejo')
    if filtro_data:
        linhas.append(f'  Data: {filtro_data}')
    linhas.append(f'  Gerado em: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}')
    linhas.append('=' * 60)
 
    for v in vendas_map.values():
        status = '[REGISTRADO]' if v['registrado'] else '[PENDENTE]'
        linhas.append('')
        linhas.append(f"VENDA #{v['id']}  {v['data']} {v['hora']}  {status}")
        linhas.append(f"Pagamento: {v['pagamento']}")
        linhas.append('-' * 40)
        for it in v['itens']:
            cod  = it['codigo'] or '-'
            nome = it['nome']
            qtd  = it['quantidade']
            unit = f"R$ {it['preco_unit']:.2f}".replace('.', ',')
            sub  = f"R$ {it['subtotal']:.2f}".replace('.', ',')
            linhas.append(f"  {cod:<8} {nome[:30]:<30} {qtd:>3}x {unit:>9} = {sub:>10}")
        linhas.append('-' * 40)
        if v['desconto'] > 0:
            linhas.append(f"  Subtotal: R$ {v['subtotal']:.2f}".replace('.', ','))
            linhas.append(f"  Desconto: R$ {v['desconto']:.2f}".replace('.', ','))
        linhas.append(f"  TOTAL:    R$ {v['total']:.2f}".replace('.', ','))
 
    linhas.append('')
    linhas.append('=' * 60)
    total_geral = sum(v['total'] for v in vendas_map.values())
    linhas.append(f'  TOTAL GERAL: R$ {total_geral:.2f}'.replace('.', ','))
    linhas.append(f'  VENDAS:      {len(vendas_map)}')
    linhas.append('=' * 60)
 
    conteudo = '\n'.join(linhas)
    nome_arq = f"relatorio_{filtro_data or date.today().strftime('%Y-%m-%d')}.txt"
    return send_file(
        io.BytesIO(conteudo.encode('utf-8')),
        mimetype='text/plain',
        as_attachment=True,
        download_name=nome_arq,
    )
 
 
# ── HELPER INTERNO ─────────────────────────────────────────────────────────
 
def _serializar_venda(venda_id):
    """Retorna dict serializável de uma venda + seus itens."""
    db    = get_db()
    v     = db.execute("SELECT * FROM vendas WHERE id=?", (venda_id,)).fetchone()
    itens = db.execute("SELECT * FROM itens_venda WHERE venda_id=?", (venda_id,)).fetchall()
    return {
        'id':           v['id'],
        'data':         v['data'],
        'hora':         v['hora'],
        'pagamento':    v['pagamento'],
        'subtotal':     fmt_brl(v['subtotal']),
        'desconto':     fmt_brl(v['desconto']),
        'total':        fmt_brl(v['total']),
        'tem_desconto': v['desconto'] > 0,
        'itens': [{
            'nome':       i['nome'],
            'codigo':     i['codigo'],
            'preco_unit': fmt_brl(i['preco_unit']),
            'quantidade': i['quantidade'],
            'subtotal':   fmt_brl(i['subtotal']),
        } for i in itens],
    }
 