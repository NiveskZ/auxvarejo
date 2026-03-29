
# Adicione esta rota ao app.py, antes do bloco if __name__ == '__main__':

@app.route('/historico/limpar', methods=['POST'])
def limpar_historico():
    db = get_db()
    db.execute("DELETE FROM itens_venda")
    db.execute("DELETE FROM vendas")
    db.commit()
    return jsonify({'ok': True})
