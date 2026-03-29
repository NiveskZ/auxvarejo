# AuxVarejo — Sistema Auxiliar de Vendas

Sistema local para consulta de preços e registro de vendas offline.
Desenvolvido em Python + Flask + SQLite.

---

## Instalação (fazer só uma vez)

1. Ter o Python instalado (python.org — versão 3.8 ou superior)
2. Executar **INSTALAR.bat** (instala Flask e openpyxl)
3. Pronto.

---

## Como usar no dia a dia

1. Executar **RODAR.bat**
2. O navegador abre automaticamente em http://localhost:5000
3. **Não fechar a janela preta** enquanto estiver usando
4. Para encerrar: feche a janela preta do terminal

---

## Onde ficam os dados

Arquivo `dados.db` na mesma pasta do sistema.
Este arquivo contém TODOS os dados: produtos e histórico de vendas.

**Backup:** copie o arquivo `dados.db` para outro lugar.
**Restaurar:** substitua o `dados.db` pelo backup.

---

## Importar produtos

Aceita XLS, XLSX e CSV.
Exporte o relatório do sistema principal e importe pela aba "Importar".

Se as colunas tiverem nomes diferentes, configure os nomes na tela de importação.
Exemplo: se a coluna se chama "descricao" em vez de "nome", troque o campo.

Os cabeçalhos detectados aparecem após a importação — use isso para ajustar.

---

## Exportar vendas para o sistema principal

Aba "Histórico" → botão "Exportar CSV"
O CSV exportado contém: id_venda, data, hora, timestamp, pagamento,
codigo_produto, nome_produto, preco_unitario, quantidade, subtotal_item,
desconto_venda, total_venda.

---

## Manutenção do código

Estrutura de arquivos:
```
app.py              ← lógica do servidor (Python)
templates/
  index.html        ← interface visual (HTML + JS mínimo)
dados.db            ← banco de dados SQLite (gerado automaticamente)
requirements.txt    ← dependências Python
INSTALAR.bat        ← instalação
RODAR.bat           ← iniciar o sistema
```

Para modificar a interface: editar `templates/index.html`
Para modificar regras de negócio: editar `app.py`
Para ver os dados diretamente: abrir `dados.db` com DB Browser for SQLite (gratuito)

---

## Gerar executável .exe (opcional)

Se quiser distribuir sem precisar ter Python instalado:

```
pip install pyinstaller
pyinstaller --onefile --add-data "templates;templates" app.py
```

O .exe ficará em `dist/app.exe`. Copiar junto com a pasta `templates/`.

---

## Problemas comuns

**"python não é reconhecido"**
→ Python não está no PATH. Reinstale marcando "Add to PATH" na instalação.

**Porta 5000 em uso**
→ Mude `port=5000` para `port=5001` no final do `app.py`.

**Arquivo XLS não importa**
→ Execute `pip install openpyxl` manualmente e tente novamente.
