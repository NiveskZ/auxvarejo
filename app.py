import os
import sys
import csv
import io
import sqlite3
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, send_file, g

# ── CONFIG ─────────────────────────────────────────────────────────────────
# Quando rodando como .exe (PyInstaller --onefile), os arquivos empacotados
# ficam em sys._MEIPASS. Esta função encontra o caminho correto nos dois casos.
def resource_path(relative):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)

# O banco de dados sempre fica ao lado do .exe (ou do app.py), nunca no temp.
# Assim os dados não se perdem quando o .exe fecha.
BASE_DIR = os.path.dirname(
    sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__)
)
DB_PATH = os.path.join(BASE_DIR, 'dados.db')

def get_secret_key():
    """
    Gera uma chave aleatória na primeira vez e reutiliza nas seguintes.
    Fica armazenada no banco, não no código.
    """
    db = sqlite3.connect(DB_PATH)
    db.execute("CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT)")
    row = db.execute("SELECT valor FROM config WHERE chave='secret_key'").fetchone()
    if row:
        key = row[0]
    else:
        import secrets
        key = secrets.token_hex(32)
        db.execute("INSERT INTO config(chave,valor) VALUES('secret_key',?)", (key,))
        db.commit()
    db.close()
    return key

app = Flask(__name__, template_folder=resource_path('templates'))
app.secret_key = get_secret_key()


# ── BANCO DE DADOS ─────────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS config (
            chave TEXT PRIMARY KEY,
            valor TEXT
        );
        CREATE TABLE IF NOT EXISTS produtos (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo  TEXT,
            codigo_barras  TEXT,         
            nome    TEXT NOT NULL,
            preco   REAL NOT NULL DEFAULT 0
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


# ── HELPERS ────────────────────────────────────────────────────────────────
def get_config(chave, padrao=''):
    row = get_db().execute("SELECT valor FROM config WHERE chave=?", (chave,)).fetchone()
    return row['valor'] if row else padrao

def set_config(chave, valor):
    get_db().execute("INSERT OR REPLACE INTO config(chave,valor) VALUES(?,?)", (chave, valor))
    get_db().commit()

def fmt_brl(valor):
    # Formata float para "R$ 1.234,56"
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def parse_float(s):
    """Converte string para float aceitando tanto 1.234,56 quanto 1,234.56"""
    if not s:
        return 0.0
    s = str(s).strip().replace(' ', '')
    # Remove símbolo de moeda se houver
    s = s.replace('R$', '').replace('$', '').strip()
    if ',' in s and '.' in s:
        # Descobre qual é separador decimal pelo que vem por último
        if s.index(',') > s.index('.'):
            # Formato BR: 1.234,56
            s = s.replace('.', '').replace(',', '.')
        else:
            # Formato US: 1,234.56
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0

def limpar_codigo(val):
    """Remove o .0 que o Excel adiciona em números lidos como float (ex: 4842.0 → 4842)"""
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s


# ── ROTA PRINCIPAL ─────────────────────────────────────────────────────────
@app.route('/')
def index():
    db = get_db()
    total_produtos = db.execute("SELECT COUNT(*) as c FROM produtos").fetchone()['c']
    hoje = date.today().strftime('%d/%m/%Y')
    vendas_hoje = db.execute("SELECT COUNT(*) as c FROM vendas WHERE data=?", (hoje,)).fetchone()['c']
    total_hoje  = db.execute("SELECT COALESCE(SUM(total),0) as t FROM vendas WHERE data=?", (hoje,)).fetchone()['t']
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


# ── IMPORTAR PRODUTOS ──────────────────────────────────────────────────────
@app.route('/importar', methods=['POST'])
def importar():
    arquivo = request.files.get('arquivo')
    if not arquivo or arquivo.filename == '':
        return jsonify({'ok': False, 'msg': 'Nenhum arquivo enviado'}), 400

    nome_arquivo = arquivo.filename.lower()
    col_cod   = request.form.get('col_codigo', 'cod').strip()
    col_nome  = request.form.get('col_nome',   'produto').strip()
    col_preco = request.form.get('col_preco',  'pv').strip()
    col_barras = request.form.get('col_barras',  'codigo de barras').strip()
    separador = request.form.get('separador',  ',')
    if separador == '\\t':
        separador = '\t'

    try:
        rows = []
        headers = []

        # ── XLS ────────────────────────────────────────────────────────────
        # Muitos ERPs exportam arquivos .xls que são na verdade TSV ou CSV
        # renomeados. Tentamos xlrd primeiro; se falhar, lemos como texto.
        if nome_arquivo.endswith('.xls'):
            conteudo_bytes = arquivo.read()
            try:
                import xlrd
                wb = xlrd.open_workbook(file_contents=conteudo_bytes)
                ws = wb.sheet_by_index(0)
                rows = [ws.row_values(r) for r in range(ws.nrows)]
            except Exception:
                # Arquivo .xls falso — ERP exportou texto com extensão errada.
                # Tenta decodificar e detectar o separador automaticamente.
                texto = None
                for enc in ('utf-8-sig', 'latin-1', 'cp1252'):
                    try:
                        texto = conteudo_bytes.decode(enc)
                        break
                    except Exception:
                        continue

                if not texto:
                    return jsonify({'ok': False,
                        'msg': 'Não foi possível ler o arquivo. Tente exportar como CSV.'}), 400

                # csv.Sniffer detecta o separador automaticamente
                try:
                    dialeto = csv.Sniffer().sniff(texto[:4096], delimiters='\t,;|')
                    sep_detectado = dialeto.delimiter
                except csv.Error:
                    # Sniffer falhou — assume tab, que é o mais comum em ERPs
                    sep_detectado = '\t'

                reader = csv.reader(io.StringIO(texto), delimiter=sep_detectado)
                rows = list(reader)

        # ── XLSX (Excel moderno, formato XML/zip) ──────────────────────────
        elif nome_arquivo.endswith('.xlsx'):
            try:
                import openpyxl
            except ImportError:
                return jsonify({'ok': False,
                    'msg': 'Biblioteca openpyxl não encontrada. Contate o suporte.'}), 400

            wb = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))

        # ── CSV / TXT ──────────────────────────────────────────────────────
        elif nome_arquivo.endswith(('.csv', '.txt')):
            conteudo = arquivo.read().decode('utf-8-sig', errors='replace')
            reader = csv.reader(io.StringIO(conteudo), delimiter=separador)
            rows = list(reader)

        else:
            return jsonify({'ok': False,
                'msg': 'Formato não suportado. Use XLS, XLSX ou CSV.'}), 400

        if len(rows) < 2:
            return jsonify({'ok': False, 'msg': 'Arquivo vazio ou sem dados'}), 400

        # Normaliza cabeçalhos: minúsculo, sem espaços extras
        headers = [str(h).strip().lower() if h is not None else '' for h in rows[0]]

        def get_idx(col):
            """Aceita nome de coluna (ex: 'produto') ou índice numérico (ex: '5')"""
            try:
                return int(col)
            except ValueError:
                pass
            try:
                return headers.index(col.lower().strip())
            except ValueError:
                return -1

        i_cod   = get_idx(col_cod)
        i_nome  = get_idx(col_nome)
        i_preco = get_idx(col_preco)
        i_barras = get_idx(col_barras)

        if i_nome < 0:
            return jsonify({'ok': False,
                'msg': f'Coluna de nome "{col_nome}" não encontrada. '
                       f'Cabeçalhos detectados: {", ".join(headers)}'}), 400
        if i_preco < 0:
            return jsonify({'ok': False,
                'msg': f'Coluna de preço "{col_preco}" não encontrada. '
                       f'Cabeçalhos detectados: {", ".join(headers)}'}), 400

        produtos = []
        for row in rows[1:]:
            # Garante que a linha tem células suficientes
            if not any(row):
                continue

            nome_val = str(row[i_nome]).strip() if i_nome < len(row) and row[i_nome] is not None else ''
            if not nome_val or nome_val.lower() in ('none', 'nan', ''):
                continue

            preco_raw = str(row[i_preco]) if i_preco < len(row) and row[i_preco] is not None else '0'
            preco_val = parse_float(preco_raw)

            codigo_val = ''
            if i_cod >= 0 and i_cod < len(row) and row[i_cod] is not None:
                codigo_val = limpar_codigo(row[i_cod])

            barras_val = ''
            if i_barras >= 0 and i_barras < len(row) and row[i_barras] is not None:
                barras_val = limpar_codigo(row[i_barras])

            produtos.append((codigo_val, barras_val, nome_val, preco_val))

        if not produtos:
            return jsonify({'ok': False,
                'msg': 'Nenhum produto válido encontrado no arquivo'}), 400

        # Substitui todos os produtos no banco (mantém histórico de vendas intacto)
        db = get_db()
        db.execute("DELETE FROM produtos")
        db.executemany(
            "INSERT INTO produtos(codigo, codigo_barras, nome, preco) VALUES (?, ?, ?, ?)",
            produtos
        )
        db.commit()

        preview = [
            {'codigo': p[0], 'codigo_barras': p[1], 'nome': p[2], 'preco': fmt_brl(p[3])}
            for p in produtos[:10]
        ]
        return jsonify({
            'ok': True,
            'total': len(produtos),
            'preview': preview,
            'headers_detectados': headers,
        })

    except Exception as e:
        return jsonify({'ok': False, 'msg': f'Erro ao processar arquivo: {str(e)}'}), 500


# ── BUSCAR PRODUTOS ────────────────────────────────────────────────────────
@app.route('/buscar')
def buscar():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    like = f'%{q}%'
    # Prioridade de ordenação:
    #   0 = match exato de código interno  (ex: digitar "10" → gelo)
    #   1 = match exato de código de barras
    #   2 = qualquer outro match (nome, código parcial)
    rows = get_db().execute(
        """SELECT id, codigo, codigo_barras, nome, preco FROM produtos
           WHERE nome LIKE ? OR codigo LIKE ? OR codigo_barras LIKE ?
           ORDER BY
             CASE
               WHEN LOWER(codigo)        = LOWER(?) THEN 0
               WHEN LOWER(codigo_barras) = LOWER(?) THEN 1
               ELSE 2
             END,
             nome
           LIMIT 12""",
        (like, like, like, q, q)
    ).fetchall()
    return jsonify([{
        'id':            r['id'],
        'codigo':        r['codigo'],
        'codigo_barras': r['codigo_barras'],
        'nome':          r['nome'],
        'preco':         r['preco'],
        'preco_fmt':     fmt_brl(r['preco']),
    } for r in rows])

@app.route('/produtos/preview')
def produtos_preview():
    db = get_db()
    total = db.execute("SELECT COUNT(*) as c FROM produtos").fetchone()['c']
    rows  = db.execute("SELECT codigo, nome, preco FROM produtos LIMIT 10").fetchall()
    return jsonify({
        'total': total,
        'items': [{'codigo': r['codigo'], 'nome': r['nome'], 'preco': fmt_brl(r['preco'])} for r in rows],
    })

@app.route('/produtos/limpar', methods=['POST'])
def limpar_produtos():
    get_db().execute("DELETE FROM produtos")
    get_db().commit()
    return jsonify({'ok': True})


# ── REGISTRAR VENDA ────────────────────────────────────────────────────────
@app.route('/venda', methods=['POST'])
def registrar_venda():
    data = request.get_json()
    if not data or not data.get('itens'):
        return jsonify({'ok': False, 'msg': 'Carrinho vazio'}), 400

    now       = datetime.now()
    pagamento = data.get('pagamento', 'Dinheiro')
    subtotal  = float(data.get('subtotal', 0))
    desconto  = float(data.get('desconto', 0))
    total     = float(data.get('total', 0))

    db = get_db()
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

    v     = db.execute("SELECT * FROM vendas WHERE id=?", (venda_id,)).fetchone()
    itens = db.execute("SELECT * FROM itens_venda WHERE venda_id=?", (venda_id,)).fetchall()

    return jsonify({
        'ok': True,
        'venda': {
            'id':         v['id'],
            'data':       v['data'],
            'hora':       v['hora'],
            'pagamento':  v['pagamento'],
            'subtotal':   fmt_brl(v['subtotal']),
            'desconto':   fmt_brl(v['desconto']),
            'total':      fmt_brl(v['total']),
            'tem_desconto': v['desconto'] > 0,
            'itens': [{
                'nome':      i['nome'],
                'codigo':    i['codigo'],
                'preco_unit': fmt_brl(i['preco_unit']),
                'quantidade': i['quantidade'],
                'subtotal':  fmt_brl(i['subtotal']),
            } for i in itens],
        }
    })


# ── HISTÓRICO DE VENDAS ────────────────────────────────────────────────────
@app.route('/historico')
def historico():
    db = get_db()
    filtro_data = request.args.get('data', '').strip()
    filtro_pag  = request.args.get('pagamento', '').strip()

    filtro_hora  = request.args.get('hora', '').strip()
    filtro_reg   = request.args.get('registrado', '').strip()

    sql    = "SELECT * FROM vendas WHERE 1=1"
    params = []
    if filtro_data:
        sql += " AND data=?"
        params.append(filtro_data)
    if filtro_hora:
        sql += " AND hora LIKE ?"
        params.append(filtro_hora + '%')
    if filtro_pag:
        sql += " AND pagamento=?"
        params.append(filtro_pag)
    if filtro_reg == 'nao':
        sql += " AND registrado=0"
    elif filtro_reg == 'sim':
        sql += " AND registrado=1"
    sql += " ORDER BY id DESC LIMIT 200"

    vendas = db.execute(sql, params).fetchall()
    resultado = []
    for v in vendas:
        itens = db.execute("SELECT * FROM itens_venda WHERE venda_id=?", (v['id'],)).fetchall()
        resultado.append({
            'id':          v['id'],
            'data':        v['data'],
            'hora':        v['hora'],
            'pagamento':   v['pagamento'],
            'subtotal':    fmt_brl(v['subtotal']),
            'desconto':    fmt_brl(v['desconto']),
            'total':       fmt_brl(v['total']),
            'tem_desconto': v['desconto'] > 0,
            'registrado':  bool(v['registrado']),
            'itens': [{
                'nome':      i['nome'],
                'codigo':    i['codigo'],
                'quantidade': i['quantidade'],
                'preco_unit': fmt_brl(i['preco_unit']),
                'subtotal':  fmt_brl(i['subtotal']),
            } for i in itens],
        })
    return jsonify(resultado)

@app.route('/venda/<int:venda_id>')
def get_venda(venda_id):
    db = get_db()
    v = db.execute("SELECT * FROM vendas WHERE id=?", (venda_id,)).fetchone()
    if not v:
        return jsonify({'ok': False}), 404
    itens = db.execute("SELECT * FROM itens_venda WHERE venda_id=?", (venda_id,)).fetchall()
    return jsonify({
        'ok': True,
        'venda': {
            'id':          v['id'],
            'data':        v['data'],
            'hora':        v['hora'],
            'pagamento':   v['pagamento'],
            'subtotal':    fmt_brl(v['subtotal']),
            'desconto':    fmt_brl(v['desconto']),
            'total':       fmt_brl(v['total']),
            'tem_desconto': v['desconto'] > 0,
            'itens': [{
                'nome':      i['nome'],
                'codigo':    i['codigo'],
                'quantidade': i['quantidade'],
                'preco_unit': fmt_brl(i['preco_unit']),
                'subtotal':  fmt_brl(i['subtotal']),
            } for i in itens],
        }
    })

@app.route('/venda/<int:venda_id>/registrado', methods=['POST'])
def marcar_registrado(venda_id):
    data = request.get_json()
    valor = 1 if data.get('registrado') else 0
    get_db().execute("UPDATE vendas SET registrado=? WHERE id=?", (valor, venda_id))
    get_db().commit()
    return jsonify({'ok': True})

@app.route('/exportar/relatorio')
def exportar_relatorio():
    """Exporta relatório TXT separado por venda, para lançamento manual no sistema."""
    db = get_db()
    filtro_data = request.args.get('data', '').strip()
    filtro_reg  = request.args.get('registrado', '').strip()

    sql = (
        "SELECT v.id, v.data, v.hora, v.pagamento, v.subtotal, v.desconto, v.total, v.registrado, "
        "       i.codigo as i_cod, i.codigo_barras as i_bar, i.nome as i_nome, "
        "       i.preco_unit, i.quantidade, i.subtotal as i_sub "
        "FROM vendas v JOIN itens_venda i ON i.venda_id = v.id"
    )
    params = []
    conditions = []
    if filtro_data:
        conditions.append("v.data=?"); params.append(filtro_data)
    if filtro_reg == 'nao':
        conditions.append("v.registrado=0")
    elif filtro_reg == 'sim':
        conditions.append("v.registrado=1")
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY v.id, i.id"

    rows = db.execute(sql, params).fetchall()

    # Agrupa por venda
    from collections import OrderedDict
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

    conteudo = ''.join(linhas)
    nome_arq = f"relatorio_{filtro_data or date.today().strftime('%Y-%m-%d')}.txt"
    return send_file(
        io.BytesIO(conteudo.encode('utf-8')),
        mimetype='text/plain',
        as_attachment=True,
        download_name=nome_arq,
    )

@app.route('/historico/limpar', methods=['POST'])
def limpar_historico():
    db = get_db()
    db.execute("DELETE FROM itens_venda")
    db.execute("DELETE FROM vendas")
    db.commit()
    return jsonify({'ok': True})


# ── EXPORTAR CSV ───────────────────────────────────────────────────────────
@app.route('/exportar/csv')
def exportar_csv():
    db = get_db()
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

    rows = db.execute(sql, params).fetchall()

    output = io.StringIO()
    w = csv.writer(output)
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


# ── CONFIG ─────────────────────────────────────────────────────────────────
@app.route('/config', methods=['POST'])
def salvar_config():
    data = request.get_json()
    for chave, valor in data.items():
        set_config(chave, str(valor))
    return jsonify({'ok': True})

@app.route('/config/verificar-senha', methods=['POST'])
def verificar_senha():
    data = request.get_json()
    senha_correta = get_config('senha', '')
    if not senha_correta:
        return jsonify({'ok': True, 'liberado': True})
    return jsonify({'ok': True, 'liberado': data.get('senha') == senha_correta})


# ── MODELO CSV ─────────────────────────────────────────────────────────────
@app.route('/modelo.csv')
def modelo_csv():
    conteudo = 'cod,produto,pv\n001,Arroz 5kg,22.90\n002,Feijão 1kg,8.50\n003,Óleo 900ml,7.99\n'
    return send_file(
        io.BytesIO(conteudo.encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='modelo_produtos.csv',
    )


# ── ENCERRAR ──────────────────────────────────────────────────────────────
@app.route('/encerrar', methods=['POST'])
def encerrar():
    """Encerra o servidor Flask — útil no Windows para não ficar rodando em background."""
    import threading
    def _stop():
        import time; time.sleep(0.5)
        import os; os._exit(0)
    threading.Thread(target=_stop, daemon=True).start()
    return jsonify({'ok': True})


# ── MAIN ───────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    import webbrowser
    import threading
    import time

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
