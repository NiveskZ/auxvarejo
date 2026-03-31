# AuxVarejo — Sistema Auxiliar de Vendas

Sistema local para consulta de preços e registro de vendas offline.
Desenvolvido em Python + Flask + SQLite.

> **Licença:** AGPL-3.0 — veja o arquivo [LICENSE](./LICENSE) para mais detalhes.

---

## O que é

AuxVarejo é um sistema auxiliar de ponto de venda (PDV) que roda inteiramente no computador do usuário, sem depender de internet ou de servidores externos. Ele foi desenvolvido para ser usado como backup operacional quando o sistema principal de vendas estiver indisponível.

Funcionalidades principais:

- Importação de catálogo de produtos via XLS, XLSX ou CSV
- Busca por nome, código interno e código de barras (com suporte a leitores)
- Registro de vendas com múltiplas formas de pagamento
- Desconto por valor fixo ou percentual
- Edição de preço unitário diretamente no carrinho
- Cálculo de troco para pagamentos em dinheiro
- Histórico de vendas com filtros por data, hora, pagamento e status
- Exportação de vendas em CSV e relatório TXT formatado por venda
- Marcação de vendas já lançadas no sistema oficial
- Cupom não fiscal com suporte a impressão
- Atalhos de teclado para operação sem mouse

---

## Privacidade e comportamento de rede

**Este software não se conecta à internet e não envia dados a nenhum servidor externo.**

Ao executar o `.exe` ou `app.py`, o programa inicia um servidor HTTP restrito
ao próprio computador, acessível somente em `127.0.0.1:5000` (localhost).
Nenhuma porta é aberta para a rede local ou para a internet.

- Nenhum dado é coletado, transmitido ou armazenado fora do computador local.
- Nenhuma telemetria, analytics, update check ou requisição externa é feita.
- Todos os dados (produtos, vendas, configurações) ficam no arquivo `dados.db`
  na mesma pasta do executável.
- O programa não modifica configurações do sistema operacional, registro do
  Windows ou outros aplicativos.
- O programa pode ser encerrado a qualquer momento pelo botão "Encerrar" na
  interface, ou fechando a janela do terminal.

---

## Instalação no Windows (fazer só uma vez)

1. Instalar Python em python.org — marcar **"Add Python to PATH"** durante a instalação
2. Executar **INSTALAR.bat** (instala Flask, openpyxl e xlrd)
3. Pronto.

### Alternativa sem Python: usar o executável

O arquivo `AuxVarejo.exe` pode ser baixado diretamente na aba
[Releases](../../releases/latest) deste repositório.
Não requer instalação — basta executar o `.exe`.

---

## Uso no dia a dia (Windows)

1. Executar **RODAR.bat** (ou `AuxVarejo.exe`)
2. O navegador abre automaticamente em `http://localhost:5000`
3. **Não fechar a janela preta** enquanto estiver usando o sistema
4. Para encerrar: use o botão **"Encerrar"** na interface, ou feche a janela preta

---

## Testar no Linux / macOS (desenvolvimento)

```bash
pip install flask openpyxl xlrd
python3 app.py
# Acesse: http://localhost:5000
```

---

## Onde ficam os dados

Arquivo **`dados.db`** na mesma pasta do sistema.
Contém TODOS os dados: produtos e histórico de vendas.

- **Backup:** copie o `dados.db` para outro lugar
- **Restaurar:** substitua o `dados.db` pelo backup
- Os dados **não são perdidos** ao fechar o navegador ou reiniciar o computador

---

## Importar produtos

Aceita **.xls**, **.xlsx** e **.csv**.

Colunas padrão para o relatório do Frenty/NFE Sistemas:

| Campo           | Coluna no arquivo |
|-----------------|-------------------|
| Código interno  | `cod`             |
| Código de barras| `codigo de barras`|
| Nome            | `produto`         |
| Preço de venda  | `pv`              |

Se o arquivo usar nomes diferentes, ajuste os campos na aba **Config → Importar Produtos**.
O sistema exibe os cabeçalhos detectados após a importação para facilitar o ajuste.

A importação **substitui apenas os produtos**. O histórico de vendas é mantido.

---

## Exportar vendas

**Aba Histórico → Relatório TXT** — relatório formatado por venda, com código interno,
nome do produto, quantidade, preço unitário e total. Ideal para lançamento manual no sistema principal.

**Aba Histórico → CSV** — planilha completa para análise ou importação em outros sistemas.

Colunas do CSV:
`id_venda, data, hora, timestamp_iso, pagamento, codigo_produto, nome_produto,
preco_unitario, quantidade, subtotal_item, desconto_venda, total_venda`

---

## Atalhos de teclado

| Tecla | Ação |
|-------|------|
| `F1`  | Foca o campo de quantidade |
| `F2`  | Finaliza a venda (ou confirma o modal aberto) |
| `F3`  | Foca o campo de busca de produto |
| `ESC` | Fecha qualquer modal aberto |
| `Enter` no campo de busca | Adiciona produto se código for exato ou resultado único |

---

## Estrutura do projeto

```
app.py                          ← servidor Python (lógica e banco de dados)
templates/
  index.html                    ← interface visual (HTML + JS)
dados.db                        ← banco SQLite (criado automaticamente na primeira execução)
requirements.txt                ← dependências Python
.github/workflows/build.yml     ← geração automática do .exe via GitHub Actions
INSTALAR.bat                    ← instala dependências Python (Windows)
RODAR.bat                       ← inicia o sistema (Windows)
LICENSE                         ← licença AGPL-3.0
```

Para modificar regras de negócio (cálculos, banco, importação): editar `app.py`

Para modificar a interface (layout, textos, botões): editar `templates/index.html`

Para inspecionar os dados sem código: usar **DB Browser for SQLite** (gratuito — sqlitebrowser.org)

---

## Gerar o .exe (GitHub Actions)

O repositório está configurado para gerar um `.exe` Windows automaticamente a cada `git push`.

```bash
git add .
git commit -m "descrição da mudança"
git push
gh run watch        # acompanha o build no terminal
```

O `.exe` fica disponível em:

```
https://github.com/SEU_USUARIO/auxvarejo/releases/latest/download/AuxVarejo.exe
```

---

## Assinatura digital (SignPath Foundation)

O executável é assinado digitalmente via **SignPath Foundation**, que oferece assinatura
gratuita para projetos open source sob licença aprovada pela OSI.

A assinatura garante que o arquivo disponibilizado nas releases é exatamente o arquivo
gerado pelo build público deste repositório, sem modificações.

**Por que o Windows pode exibir aviso mesmo assim:**
A assinatura elimina o aviso de "publisher desconhecido" após o executável acumular
reputação suficiente no SmartScreen. Em distribuições iniciais, um aviso de reputação
ainda pode aparecer — isso é normal para qualquer software novo, independente de assinatura.

---

## Problemas comuns

**"python não é reconhecido"**
→ Reinstale o Python marcando "Add Python to PATH" durante a instalação.

**Porta 5000 em uso**
→ Mude `port=5000` para outra porta disponível (ex: `5001`) no final do `app.py`
e acesse `http://localhost:5001`.

**Colunas não encontradas ao importar**
→ O sistema exibe os cabeçalhos detectados logo abaixo do botão Importar.
Copie o nome exato da coluna para o campo correspondente na tela de importação.

**Arquivo XLS não importa**
→ O arquivo provavelmente é um TSV (texto com tabulação) com extensão `.xls` —
prática comum em ERPs. O sistema detecta isso automaticamente. Se ainda assim
falhar, exporte como CSV do Excel e importe normalmente.

---

## Licença

Este projeto está licenciado sob a **GNU Affero General Public License v3.0 (AGPL-3.0)**.

Isso significa que você pode usar, estudar, modificar e distribuir este software
livremente, desde que versões modificadas também sejam distribuídas sob a mesma licença.
Consulte o arquivo [LICENSE](./LICENSE) para o texto completo.
