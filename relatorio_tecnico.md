# Relatório Técnico – SIFSM (Sistema Integrado de Futuro Sustentável em Marte)

**Projeto:** Aurora Siger | **Equipe:** Henrique Dourado Peterli | **Ano:** 2026

## 1. Contexto da solução
A colônia Aurora Siger depende de energia limitada (solar + bateria) e precisa decidir rápido sob risco (tempestades de poeira, falha de sensores). O SIFSM é um protótipo em Python que reúne **banco de dados, regras lógicas, estruturas de dados, simulação, regressão linear, agentes de IA simulados e análise de arquitetura** em um único fluxo, com foco em **consumo de energia**. Há um menu de terminal (opções 0–15) e um modo `--demo` automático.

## 2. Dados e banco de dados
- Banco: **SQLite** (banco equivalente ao Oracle; o `script_banco.sql` traz notas de conversão).
- Tabelas: `modulos` (6 módulos), `sensores`, `leituras` (120 registros), `alertas`, `chamados`.
- Campos de `leituras`: ciclo, id_modulo, codigo_sensor, ocupantes, temperatura_c, umidade_pct, luminosidade_lux, consumo_kwh, status_sensor.
- Base simulada em `dados_aurora_siger.csv`, gerada por `gerar_dados.py` (semente fixa). Contém 4 sensores inválidos e 3 picos de consumo propositais para testar regras e limpeza.
- **CRUD** (opções 1–4) com restrições `CHECK`, `FOREIGN KEY` e validação em Python.
- **Tratamento de erros:** `try/except/else/finally` em `criar_leitura` (rollback em erro, commit só no `else`, fechamento do cursor no `finally`). Erros tratados: umidade fora de 0–100, texto no lugar de número, módulo inexistente (violação de chave estrangeira), id inexistente.

## 3. Regras booleanas e circuito lógico
| Regra | Expressão | Uso |
|---|---|---|
| R1 | consumo_alto **AND** módulo_crítico | alerta de consumo |
| R2 | presença **AND** baixa_luminosidade | acionar iluminação |
| R3 | módulo_agrícola_ativo **AND** umidade_baixa | liberar irrigação |
| R4 | sensor_inválido | bloquear operação automática |

Limiares: consumo alto > 130 % da potência nominal; luz baixa < 200 lux; umidade baixa < 40 %.
**Circuito:** `LED_ALERTA = (A · B) + M` (A = consumo alto, B = módulo crítico, M = manutenção pendente): porta AND seguida de porta OR (`graficos_ou_imagens/circuito_logico.png`, com tabela verdade de 8 linhas). O mesmo circuito pode ser montado em Arduino/Tinkercad (`tinkercad_instrucoes.txt`), com a mesma lógica do Python. Resultado na base: R1 disparou 9 vezes, R4 4, R2 63, R3 1.

## 4. Estruturas de dados (e por quê)
| Estrutura | Onde | Justificativa |
|---|---|---|
| Pilha | histórico de ações / desfazer CRUD | a última ação é a primeira a desfazer (LIFO) |
| Fila | chamados de manutenção | atendimento por ordem de chegada (FIFO) |
| Fila de prioridade (heap) | alertas | o mais grave sai primeiro, custo O(log n) |
| Tabela hash (dict) | busca de sensor por código | acesso O(1) |
| Grafo + BFS | dependências entre módulos | descobre o que falha em cascata (falha de Energia afeta 5 módulos) |

## 5. Simulação computacional e matemática
Modelo da bateria: `dSoC/dt = (P_ger − P_carga)/Capacidade`, resolvido por integração numérica (Euler, dt = 0,25 h) durante 74 h (3 sóis). Geração: `P_ger(t) = 200·max(0, sin(2πt/24,65))` kW. Bateria de 900 kWh, SoC inicial 80 %. A carga (43,2 kW total; 31,0 kW crítica) vem **do banco** (média por SQL).
- **Integração numérica × analítica:** energia gerada em 1 sol = 1569,3 kWh (regra do trapézio) = 1569,3 kWh (analítico P·T/π); erro ≈ 0.
- **Média de função:** consumo médio em 74 h = ∫f dt/(b−a) = 43,2 kW.
- **Convolução:** média móvel de 5 pontos no sensor de temperatura reduziu o desvio-padrão de 2,25 para 0,93 °C.
- **Cenários:** (A) normal: SoC mínimo 36,8 %; (B) tempestade de poeira (geração ×0,45 de 24 h a 45 h): SoC chega a 0 %; (C) tempestade + corte de cargas não críticas quando SoC < 30 %: SoC mínimo 6,7 %.
- **Limitações:** carga constante, geração senoidal ideal, sem degradação da bateria, sem efeito de temperatura, parâmetros assumidos.

## 6. Modelo linear
Alvo: `consumo_kwh`. Limpeza: remove sensores inválidos e picos > 1,6× a média do módulo (113 leituras restantes; 90 treino / 23 teste).
- **Exploratória:** correlação com consumo: ocupantes 0,81; potência nominal 0,46; temperatura −0,36.
- **Simples:** `consumo = 4,50 + 0,842·ocupantes` → R² = 0,645; RMSE = 1,14; MAE = 1,00 (teste).
- **Múltipla:** `consumo = 4,15 + 0,474·potência + 0,824·ocupantes − 0,160·temperatura` → R² = 0,974; R² ajustado = 0,970; RMSE = 0,31; MAE = 0,25 (teste).
- **Interpretação:** +1 ocupante ≈ +0,82 kWh; +1 °C ≈ −0,16 kWh; +1 kW de potência nominal ≈ +0,47 kWh.
- **Multicolinearidade:** VIF ≈ 1,0 para os três preditores (sem problema).
- **Limitações:** dados simulados (o bom ajuste é esperado, pois os dados foram gerados com relação linear), poucos pontos, sem variável de hora do dia.

## 7. IA: sistema multiagente (simulado, sem LLM externo)
Triador classifica o pedido e faz **handoff** para agentes de energia, ambiental, manutenção ou dados. **Ferramentas determinísticas:** consumo por módulo (SQL), contagem de sensores inválidos, previsão pelo modelo linear. **RAG simulado:** busca por palavras-chave em 4 documentos internos. **Sessão:** histórico e último módulo mencionado. **Tracing:** cada passo é registrado e exibido. **Guardrails:** bloqueio de ações inseguras (ex.: "desligar suporte de vida") e de perguntas fora do escopo. Toda resposta é **recomendação com validação humana**. Limite: o triador usa palavras-chave, não entende contexto como um LLM.

## 8. Arquitetura computacional
CPU para controle (CRUD, regras, agentes); GPU/NPU/TPU (conceitual) para simulação em larga escala e inferência de IA com menor energia por operação; microcontrolador para regras simples de sensores. Computação heterogênea: cada tarefa na unidade mais eficiente. Hierarquia de memória: dados recentes em RAM (`dict`, `deque`), histórico no banco; agregamos no banco (`AVG` em SQL) para reduzir movimentação de dados, que costuma ser o gargalo. Medição real: laço Python ≈ 24,6 ms × NumPy vetorizado ≈ 0,20 ms (~120×; varia por máquina): menos CPU ativa = menos energia. Chiplets e grandes sistemas de IA são citados apenas de forma conceitual.

## 9. Sustentabilidade, cidadania digital e impacto socioambiental
1. **Uso responsável de recursos:** R1 + simulação detectam o risco antes do esgotamento da bateria; corte de cargas protege módulos críticos.
2. **Simulação evita desperdício:** a tempestade é testada no computador, não na colônia.
3. **Cidadania digital e privacidade:** só a contagem de ocupantes é guardada (dado agregado, sem identidade); guardrails e rastreabilidade dão transparência.
4. **Economia dos dados:** uso indevido de dados da tripulação (vigilância, discriminação) é um risco; adotamos minimização e validação humana.
5. **Impacto ambiental de IA e data centers:** preferimos regras determinísticas e regressão leve a modelos gigantes.
6. **Inovação com benefícios e riscos:** toda decisão sugerida pelo sistema exige aprovação humana.

## 10. Limitações e melhorias
Dados simulados; SQLite no lugar de Oracle; agentes sem LLM; simulação simplificada. Melhorias: sensores reais (Arduino), API de agentes com LLM real, dashboard, mais variáveis e validação cruzada, otimização do corte de cargas.
