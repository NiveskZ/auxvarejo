def fmt_brl(valor):
    """Formata float para 'R$ 1.234,56'."""
    return f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


def parse_float(s):
    """Converte string para float aceitando tanto 1.234,56 quanto 1,234.56."""
    if not s:
        return 0.0
    s = str(s).strip().replace(' ', '')
    s = s.replace('R$', '').replace('$', '').strip()
    if ',' in s and '.' in s:
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
    """Remove o .0 que o Excel adiciona em números lidos como float (ex: 4842.0 → 4842)."""
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    return s
