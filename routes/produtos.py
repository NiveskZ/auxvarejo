import csv
import io
 
from flask import Blueprint, request, jsonify
 
from database import get_db
from utils import fmt_brl, parse_float, limpar_codigo
 
bp = Blueprint('produtos', __name__)


# ---- Importando Produtos -----------------------------------------------

@bp.route('/importar', methods=['POST'])
def importar():
    arquivo = request.files.get('arquivo')
    if not arquivo or arquivo.filename == '':
        return jsonify({'ok': False, 'msg': 'Nenhum arquivo enviado'}), 400
    
    nome_arquivo = arquivo.filename.lower()
    col_cod = request.form.get('col_codigo', 'cod').strip()
    col_nome = request.form.get('col_nome', 'produto').strip()
    col_preco = request.form.get('col_preco', 'pv').strip()
    col_barras = request.form.get('col_barras', 'codigo de barras').strip()
    separador = request.form.get('separador', ',')
    if separador == '\\t':
        separador = '\t'
    
        try:
            rows    = []
            headers = []
    
            # ── XLS ────────────────────────────────────────────────────────────
            # Muitos ERPs exportam arquivos .xls que são na verdade TSV ou CSV
            # renomeados. Tentamos xlrd primeiro; se falhar, lemos como texto.
            if nome_arquivo.endswith('.xls'):
                conteudo_bytes = arquivo.read()
                try:
                    import xlrd
                    wb   = xlrd.open_workbook(file_contents=conteudo_bytes)
                    ws   = wb.sheet_by_index(0)
                    rows = [ws.row_values(r) for r in range(ws.nrows)]
                except Exception:
                    # Arquivo .xls falso — ERP exportou texto com extensão errada.
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
    
                    try:
                        dialeto       = csv.Sniffer().sniff(texto[:4096], delimiters='\t,;|')
                        sep_detectado = dialeto.delimiter
                    except csv.Error:
                        sep_detectado = '\t'
    
                    reader = csv.reader(io.StringIO(texto), delimiter=sep_detectado)
                    rows   = list(reader)
    
            # ── XLSX ───────────────────────────────────────────────────────────
            elif nome_arquivo.endswith('.xlsx'):
                try:
                    import openpyxl
                except ImportError:
                    return jsonify({'ok': False,
                        'msg': 'Biblioteca openpyxl não encontrada. Contate o suporte.'}), 400
    
                wb   = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
                ws   = wb.active
                rows = list(ws.iter_rows(values_only=True))
    
            # ── CSV / TXT ──────────────────────────────────────────────────────
            elif nome_arquivo.endswith(('.csv', '.txt')):
                conteudo = arquivo.read().decode('utf-8-sig', errors='replace')
                reader   = csv.reader(io.StringIO(conteudo), delimiter=separador)
                rows     = list(reader)
    
            else:
                return jsonify({'ok': False,
                    'msg': 'Formato não suportado. Use XLS, XLSX ou CSV.'}), 400
    
            if len(rows) < 2:
                return jsonify({'ok': False, 'msg': 'Arquivo vazio ou sem dados'}), 400
    
            # Normaliza cabeçalhos: minúsculo, sem espaços extras
            headers = [str(h).strip().lower() if h is not None else '' for h in rows[0]]
    
            def get_idx(col):
                """Aceita nome de coluna (ex: 'produto') ou índice numérico (ex: '5')."""
                try:
                    return int(col)
                except ValueError:
                    pass
                try:
                    return headers.index(col.lower().strip())
                except ValueError:
                    return -1
    
            i_cod    = get_idx(col_cod)
            i_nome   = get_idx(col_nome)
            i_preco  = get_idx(col_preco)
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
                if not any(row):
                    continue
    
                nome_val  = str(row[i_nome]).strip() if i_nome < len(row) and row[i_nome] is not None else ''
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
    
            # Substitui todos os produtos (mantém histórico de vendas intacto)
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
                'ok':                 True,
                'total':              len(produtos),
                'preview':            preview,
                'headers_detectados': headers,
            })
 
        except Exception as e:
            return jsonify({'ok': False, 'msg': f'Erro ao processar arquivo: {str(e)}'}), 500
        

# Buscar produtos

@bp.route('/buscar')
def buscar():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
 
    like = f'%{q}%'
    # Prioridade: código exato (0) > código de barras exato (1) > parcial (2)
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
 
 
@bp.route('/produtos/preview')
def produtos_preview():
    db    = get_db()
    total = db.execute("SELECT COUNT(*) as c FROM produtos").fetchone()['c']
    rows  = db.execute("SELECT codigo, nome, preco FROM produtos LIMIT 10").fetchall()
    return jsonify({
        'total': total,
        'items': [{'codigo': r['codigo'], 'nome': r['nome'], 'preco': fmt_brl(r['preco'])} for r in rows],
    })
 
 
@bp.route('/produtos/limpar', methods=['POST'])
def limpar_produtos():
    get_db().execute("DELETE FROM produtos")
    get_db().commit()
    return jsonify({'ok': True})
 