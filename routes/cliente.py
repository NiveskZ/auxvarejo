from flask import Blueprint, jsonify, request, render_template
 
bp = Blueprint('cliente', __name__)
 
# Estado do carrinho compartilhado com a tela do cliente via polling.
# Mantido em memória, não precisa persistir.
_estado_cliente = {
    'itens':       [],
    'total':       'R$ 0,00',
    'subtotal':    'R$ 0,00',
    'desconto':    'R$ 0,00',
    'tem_desconto': False,
    'finalizado':  False,
    'nome_loja':   '',
}
 
 
@bp.route('/cliente')
def tela_cliente():
    """Tela voltada para o cliente numa segunda janela/aba."""
    return render_template('cliente.html')
 
 
@bp.route('/estado-carrinho', methods=['GET'])
def get_estado_carrinho():
    return jsonify(_estado_cliente)
 
 
@bp.route('/estado-carrinho', methods=['POST'])
def set_estado_carrinho():
    global _estado_cliente
    _estado_cliente.update(request.get_json())
    return jsonify({'ok': True})
 