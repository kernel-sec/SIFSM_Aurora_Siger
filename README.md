# SIFSM – Sistema Integrado de Futuro Sustentável em Marte (Aurora Siger)

Protótipo em Python: banco de dados + CRUD, regras booleanas e circuito lógico, estruturas de dados, simulação de bateria, regressão linear, agentes de IA simulados e análise de arquitetura.

## Arquivos
| Arquivo | Função |
|---|---|
| `codigo_fonte.py` | **arquivo principal** (menu + demo) |
| `script_banco.sql` | criação das tabelas e dados iniciais (SQLite) |
| `dados_aurora_siger.csv` | base simulada (120 leituras) carregada no banco |
| `gerar_dados.py` | gera o CSV (semente fixa) |
| `gerar_circuito.py` | gera a imagem do circuito |
| `graficos_ou_imagens/` | circuito, gráficos de simulação e regressão, evidência de execução |
| `tinkercad_instrucoes.txt` | montagem e código Arduino do circuito |
| `relatorio_tecnico.md` | relatório técnico |

> A simulação está dentro de `codigo_fonte.py` (seção 4), por isso não há arquivo separado.

## Dependências
Python 3.9+ com `numpy` e `matplotlib` (`pip install numpy matplotlib`). `sqlite3` já vem com o Python. Sem Oracle: usamos SQLite, banco equivalente permitido; no `script_banco.sql` há as notas para converter para Oracle.

## Como executar
```
python codigo_fonte.py          # menu interativo (opções 0 a 15)
python codigo_fonte.py --demo   # demonstração automática de tudo
```
Na primeira execução o arquivo `aurora_siger.db` é criado a partir do `script_banco.sql` e do CSV. Para recomeçar, apague o `.db`.

## Menu
1 Cadastrar · 2 Listar · 3 Alterar · 4 Excluir · 5 Desfazer (pilha) · 6 Buscar sensor (hash) · 7 Regras e circuito · 8 Fila de chamados · 9 Grafo de dependências · 10 Simulação · 11 Modelo linear · 12 Assistente multiagente · 13 Arquitetura · 14 Reflexão socioambiental · **15 Analisar sustentabilidade da colônia** (fluxo integrado).
