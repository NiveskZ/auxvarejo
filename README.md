# AuxVarejo — Sistema Auxiliar de Vendas

Sistema local para consulta de preços e registro de vendas offline.
Desenvolvido em Python + Flask + SQLite.

---

## Instalação no Windows (fazer só uma vez)

1. Instalar Python em python.org — marcar **"Add Python to PATH"** durante a instalação
2. Executar **INSTALAR.bat**
3. Pronto.

## Uso no dia a dia (Windows)

1. Executar **RODAR.bat**
2. O navegador abre automaticamente em http://localhost:5000
3. **Não fechar a janela preta** enquanto estiver usando
4. Para encerrar: feche a janela preta

## Onde ficam os dados

Arquivo **`dados.db`** na mesma pasta do sistema.
Contém TODOS os dados: produtos e histórico de vendas.

- **Backup:** copie o `dados.db` para outro lugar
- **Restaurar:** substitua o `dados.db` pelo backup

Os dados **não são perdidos** ao fechar o navegador ou reiniciar o computador.

---

## Importar produtos do sistema principal

Aceita **.xls**, **.xlsx** e **.csv**.

Colunas padrão configuradas para o relatório do Frenty/NFE Sistemas:
| Campo        | Coluna no XLS |
|--------------|---------------|
| Código       | `cod`         |
| Nome         | `produto`     |
| Preço        | `pv`          |

Se o arquivo tiver nomes diferentes, ajuste na tela de importação.
O sistema mostra os cabeçalhos detectados após importar — use isso para ajustar.

A importação **substitui apenas os produtos**. O histórico de vendas é mantido.

---

## Exportar vendas para o sistema principal

Aba **Histórico** → botão **Exportar CSV**

Colunas exportadas:
`id_venda, data, hora, timestamp_iso, pagamento, codigo_produto, nome_produto,
preco_unitario, quantidade, subtotal_item, desconto_venda, total_venda`

---

## Estrutura do projeto

```
app.py                        ← servidor Python (lógica e banco de dados)
templates/
  index.html                  ← interface visual (HTML + JS)
dados.db                      ← banco SQLite (criado automaticamente)
requirements.txt              ← dependências Python
.github/workflows/build.yml   ← geração automática do .exe via GitHub Actions
INSTALAR.bat                  ← instala dependências (Windows)
RODAR.bat                     ← inicia o sistema (Windows)
rodar.sh                      ← inicia o sistema (Linux/Mac)
```

**Para modificar regras de negócio** (preços, cálculos, banco): editar `app.py`
**Para modificar a interface** (botões, layout, textos): editar `templates/index.html`

Para ver os dados diretamente sem código: usar **DB Browser for SQLite** (gratuito)

---

## Gerar o .exe (GitHub Actions)

O repositório já está configurado. Qualquer `git push` gera um novo `.exe` automaticamente.

```bash
git add .
git commit -m "descrição da mudança"
git push
gh run watch        # acompanha o build
```

O `.exe` fica disponível em:
`https://github.com/SEU_USUARIO/auxvarejo/releases/latest/download/AuxVarejo.exe`

---

## Problemas comuns

**"python não é reconhecido"**
→ Reinstale o Python marcando "Add Python to PATH"

**Porta 5000 em uso**
→ Mude `port=5000` para `port=5001`, ou alguma outra disponível no final do `app.py`

**Colunas não encontradas ao importar**
→ O sistema mostra quais cabeçalhos detectou. Copie o nome exato para o campo correspondente na tela de importação.

## Licença

Este projeto está licenciado sob a GNU Affero General Public License v3.0 (AGPL-3.0).  
Consulte o arquivo [LICENSE](./LICENSE) para mais detalhes.
