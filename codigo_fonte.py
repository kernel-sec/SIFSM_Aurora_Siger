"""
SIFSM - Sistema Integrado de Futuro Sustentável em Marte (Aurora Siger)
Arquivo principal. Execute:  python codigo_fonte.py          (menu interativo)
                             python codigo_fonte.py --demo   (demonstração automática)
Dependências: numpy, matplotlib (gráficos opcionais). sqlite3 já vem com o Python.
"""
import csv, heapq, os, sqlite3, sys, time, unicodedata
from collections import deque

import numpy as np

try:                                    
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

PASTA = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PASTA, "aurora_siger.db")
IMG = os.path.join(PASTA, "graficos_ou_imagens")
os.makedirs(IMG, exist_ok=True)


# ============================================================================
# 1. BANCO DE DADOS (SQLite = banco equivalente ao Oracle) + CRUD
# ============================================================================
def conectar():
    """Cria o banco a partir de script_banco.sql + CSV na primeira execução."""
    novo = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if novo:
        with open(os.path.join(PASTA, "script_banco.sql"), encoding="utf-8") as f:
            conn.executescript(f.read())
        with open(os.path.join(PASTA, "dados_aurora_siger.csv"), encoding="utf-8") as f:
            for r in csv.DictReader(f):
                conn.execute(
                    """INSERT INTO leituras (ciclo,id_modulo,codigo_sensor,ocupantes,temperatura_c,
                       umidade_pct,luminosidade_lux,consumo_kwh,status_sensor)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (r["ciclo"], r["id_modulo"], r["codigo_sensor"], r["ocupantes"], r["temperatura_c"],
                     r["umidade_pct"], r["luminosidade_lux"], r["consumo_kwh"], r["status_sensor"]))
        conn.commit()
    return conn


CAMPOS = ["ciclo", "id_modulo", "codigo_sensor", "ocupantes", "temperatura_c",
          "umidade_pct", "luminosidade_lux", "consumo_kwh", "status_sensor"]


def validar_leitura(d):
    """Valida entrada; lança ValueError com mensagem clara (entrada inválida)."""
    try:
        d["ciclo"] = int(d["ciclo"]); d["ocupantes"] = int(d["ocupantes"])
        for k in ("temperatura_c", "umidade_pct", "luminosidade_lux", "consumo_kwh"):
            d[k] = float(d[k])
    except (ValueError, KeyError, TypeError):
        raise ValueError("Campo numérico inválido ou ausente.")
    if d["ciclo"] < 0 or d["ocupantes"] < 0 or d["consumo_kwh"] < 0 or d["luminosidade_lux"] < 0:
        raise ValueError("ciclo, ocupantes, consumo e luminosidade não podem ser negativos.")
    if not 0 <= d["umidade_pct"] <= 100:
        raise ValueError("Umidade deve estar entre 0 e 100 %.")
    if d.get("status_sensor") not in ("OK", "INVALIDO"):
        raise ValueError("status_sensor deve ser OK ou INVALIDO.")
    return d


def criar_leitura(conn, d):
    """CREATE. Demonstra try / except / else / finally."""
    cur = conn.cursor()
    try:
        d = validar_leitura(dict(d))
        cur.execute(f"INSERT INTO leituras ({','.join(CAMPOS)}) VALUES ({','.join('?'*len(CAMPOS))})",
                    [d[c] for c in CAMPOS])
    except sqlite3.IntegrityError as e:           # módulo/sensor inexistente etc
        conn.rollback()
        raise ValueError(f"Violação de integridade no banco: {e}")
    except ValueError:
        conn.rollback()
        raise
    else:                                         # só confirma se nada deu errado
        conn.commit()
        return cur.lastrowid
    finally:                                      # sempre executa
        cur.close()


def listar_leituras(conn, id_modulo=None, limite=10):
    """READ."""
    sql, args = "SELECT * FROM leituras", []
    if id_modulo:
        sql += " WHERE id_modulo = ?"; args.append(id_modulo)
    sql += " ORDER BY id_leitura DESC LIMIT ?"; args.append(limite)
    return conn.execute(sql, args).fetchall()


def obter_leitura(conn, id_leitura):
    r = conn.execute("SELECT * FROM leituras WHERE id_leitura=?", (id_leitura,)).fetchone()
    if r is None:
        raise ValueError(f"Leitura {id_leitura} não encontrada.")
    return dict(r)


def atualizar_leitura(conn, id_leitura, novos):
    """UPDATE. Retorna o registro antigo (para a pilha de desfazer)."""
    antigo = obter_leitura(conn, id_leitura)
    d = {**antigo, **novos}
    try:
        validar_leitura(d)
        conn.execute(f"UPDATE leituras SET {','.join(c+'=?' for c in CAMPOS)} WHERE id_leitura=?",
                     [d[c] for c in CAMPOS] + [id_leitura])
    except (ValueError, sqlite3.IntegrityError) as e:
        conn.rollback(); raise ValueError(str(e))
    else:
        conn.commit()
    return antigo


def excluir_leitura(conn, id_leitura):
    """DELETE. Retorna o registro excluído (para desfazer)."""
    antigo = obter_leitura(conn, id_leitura)
    conn.execute("DELETE FROM leituras WHERE id_leitura=?", (id_leitura,))
    conn.commit()
    return antigo


def restaurar_leitura(conn, reg):
    conn.execute(f"INSERT INTO leituras (id_leitura,{','.join(CAMPOS)}) VALUES (?,{','.join('?'*len(CAMPOS))})",
                 [reg["id_leitura"]] + [reg[c] for c in CAMPOS])
    conn.commit()


# ============================================================================
# 2. ESTRUTURAS DE DADOS
# ============================================================================
class HistoricoAcoes:
    """PILHA (LIFO): última ação feita é a primeira a ser desfeita."""
    def __init__(self): self._p = []
    def push(self, item): self._p.append(item)
    def pop(self): return self._p.pop() if self._p else None
    def __len__(self): return len(self._p)


class FilaChamados:
    """FILA (FIFO): chamados de manutenção são atendidos na ordem de chegada."""
    def __init__(self): self._f = deque()
    def enfileirar(self, c): self._f.append(c)
    def atender(self): return self._f.popleft() if self._f else None
    def __len__(self): return len(self._f)
    def lista(self): return list(self._f)


class AlertasPrioritarios:
    """FILA DE PRIORIDADE (heap): alerta de menor número (mais grave) sai primeiro."""
    def __init__(self): self._h = []; self._n = 0
    def inserir(self, nivel, msg):
        heapq.heappush(self._h, (nivel, self._n, msg)); self._n += 1
    def remover(self): return heapq.heappop(self._h) if self._h else None
    def __len__(self): return len(self._h)


def construir_tabela_hash(conn):
    """TABELA HASH (dict): busca O(1) por código de sensor."""
    return {r["codigo_sensor"]: dict(r) for r in conn.execute(
        "SELECT s.codigo_sensor, s.id_modulo, m.nome, m.critico FROM sensores s "
        "JOIN modulos m ON m.id_modulo = s.id_modulo")}


# GRAFO dirigido de dependências: A -> B significa "B depende de A"
GRAFO_DEPENDENCIAS = {
    "M01": ["M02", "M03", "M04", "M05", "M06"],   # Energia alimenta todos
    "M05": ["M04", "M06"],                          # Comunicação apoia lab e médico
    "M03": ["M02"],                                 # Agricultura abastece habitação
    "M02": [], "M04": [], "M06": []}


def modulos_afetados(origem):
    """Busca em largura (BFS): quais módulos são afetados se 'origem' falhar."""
    visitados, fila = set(), deque([origem])
    while fila:
        atual = fila.popleft()
        for viz in GRAFO_DEPENDENCIAS.get(atual, []):
            if viz not in visitados:
                visitados.add(viz); fila.append(viz)
    return sorted(visitados)


# ============================================================================
# 3. REGRAS BOOLEANAS (software) + tabela verdade do circuito
# ============================================================================
LIMITE_CONSUMO = 1.3    # consumo é "alto" se > 130 % da potência nominal do módulo
LIMITE_LUZ = 200        # lux: abaixo disso é "baixa luminosidade"
LIMITE_UMIDADE = 40     # %: abaixo disso é "umidade baixa"


def avaliar_regras(leitura, modulo):
    """Aplica as regras booleanas a uma leitura. Retorna dict de booleanos."""
    consumo_alto = leitura["consumo_kwh"] > LIMITE_CONSUMO * modulo["potencia_nominal_kw"]
    critico = bool(modulo["critico"])
    sensor_invalido = leitura["status_sensor"] == "INVALIDO"
    presenca = leitura["ocupantes"] > 0
    baixa_luz = leitura["luminosidade_lux"] < LIMITE_LUZ
    agricola_ativo = modulo["tipo"] == "agricultura" and bool(modulo["ativo"])
    umidade_baixa = leitura["umidade_pct"] < LIMITE_UMIDADE
    return {
        "R1_alerta_consumo": consumo_alto and critico,                 # A AND B
        "R2_ligar_iluminacao": presenca and baixa_luz,                 # P AND L
        "R3_liberar_irrigacao": agricola_ativo and umidade_baixa,      # G AND U
        "R4_bloquear_operacao": sensor_invalido,                       # falha de sensor
    }


def tabela_verdade_circuito():
    """Circuito: LED = (A AND B) OR M   (A=consumo alto, B=módulo crítico, M=manutenção pendente)"""
    linhas = []
    for a in (0, 1):
        for b in (0, 1):
            for m in (0, 1):
                linhas.append((a, b, m, int((a and b) or m)))
    return linhas


def mostrar_tabela_verdade():
    print("\nExpressão booleana:  LED_ALERTA = (A · B) + M")
    print("A = consumo alto | B = módulo crítico | M = manutenção pendente")
    print(" A B M | LED")
    for a, b, m, s in tabela_verdade_circuito():
        print(f" {a} {b} {m} |  {s}")
    print("Circuito: ver graficos_ou_imagens/circuito_logico.png (porta AND -> porta OR -> LED).")


# ============================================================================
# 4. SIMULAÇÃO COMPUTACIONAL + MATEMÁTICA (integração, média, convolução)
# ============================================================================
SOL_H = 24.65  # duração de um sol marciano em horas
_trapz = getattr(np, "trapezoid", None) or np.trapz


def consumos_do_banco(conn):
    """Consumo médio (kW) por módulo calculado via SQL, ignorando sensores inválidos."""
    rows = conn.execute(
        """SELECT m.id_modulo, m.critico, AVG(l.consumo_kwh) AS media
           FROM modulos m JOIN leituras l ON l.id_modulo = m.id_modulo
           WHERE l.status_sensor = 'OK' GROUP BY m.id_modulo""").fetchall()
    total = sum(r["media"] for r in rows)
    critico = sum(r["media"] for r in rows if r["critico"])
    return total, critico


def simular_soc(carga_total, carga_critica, p_pico=200.0, cap_kwh=900.0, soc0=80.0,
                horas=74.0, dt=0.25, tempestade=None, load_shedding=False, soc_corte=30.0):
    """Estado de carga da bateria:  dSoC/dt = (P_ger - P_carga) / Capacidade.
    Integração numérica pelo método de Euler. P_ger(t)=Pico*max(0,sin(2πt/SOL))."""
    t = np.arange(0, horas + dt, dt)
    ger = p_pico * np.maximum(0, np.sin(2 * np.pi * t / SOL_H))
    if tempestade:                                    # (início_h, fim_h, fator)
        i, f, fator = tempestade
        ger = np.where((t >= i) & (t <= f), ger * fator, ger)
    soc = np.zeros_like(t); soc[0] = soc0
    carga = np.zeros_like(t); desperdicio = 0.0
    for k in range(len(t) - 1):
        carga[k] = carga_critica if (load_shedding and soc[k] < soc_corte) else carga_total
        novo = soc[k] + (ger[k] - carga[k]) * dt / cap_kwh * 100
        if novo > 100:
            desperdicio += (novo - 100) / 100 * cap_kwh; novo = 100
        soc[k + 1] = max(0.0, novo)
    carga[-1] = carga[-2]
    return {"t": t, "ger": ger, "carga": carga, "soc": soc, "desperdicio_kwh": desperdicio}


def executar_simulacao(conn, salvar=True, verbose=True):
    total, critico = consumos_do_banco(conn)
    cen = {
        "A: Normal": simular_soc(total, critico),
        "B: Tempestade de poeira": simular_soc(total, critico, tempestade=(24, 45, 0.45)),
        "C: Tempestade + corte de cargas": simular_soc(total, critico, tempestade=(24, 45, 0.45),
                                                       load_shedding=True)}
    # --- Integração numérica x analítica (área sob a curva) ---
    n = simular_soc(total, critico, horas=SOL_H, dt=0.01)
    e_num = _trapz(n["ger"], n["t"])
    e_ana = 200.0 * SOL_H / np.pi          # ∫0^(T/2) P·sin(2πt/T) dt = P·T/π
    media_consumo = _trapz(cen["A: Normal"]["carga"], cen["A: Normal"]["t"]) / 74.0  # média de função
    res = {"carga_total": total, "carga_critica": critico, "e_num": e_num, "e_ana": e_ana,
           "media_consumo": media_consumo,
           "soc_min": {k: float(v["soc"].min()) for k, v in cen.items()},
           "desperdicio": {k: v["desperdicio_kwh"] for k, v in cen.items()}}
    # --- Convolução: filtro de média móvel no sinal de temperatura de um sensor ---
    sinal = np.array([r["temperatura_c"] for r in conn.execute(
        "SELECT temperatura_c FROM leituras WHERE id_modulo='M02' AND status_sensor='OK' ORDER BY ciclo")])
    kernel = np.ones(5) / 5
    suave = np.convolve(sinal, kernel, mode="same")
    res["desvio_antes"], res["desvio_depois"] = float(sinal[2:-2].std()), float(suave[2:-2].std())
    if verbose:
        print(f"\nCarga total média (do banco): {total:.1f} kW | carga crítica: {critico:.1f} kW")
        print(f"Energia gerada em 1 sol  -> numérica (trapézio): {e_num:.1f} kWh | analítica P·T/π: {e_ana:.1f} kWh "
              f"| erro {abs(e_num-e_ana)/e_ana*100:.4f} %")
        print(f"Média da função consumo em 74 h (média de função = ∫f/(b-a)): {media_consumo:.1f} kW")
        for k in cen:
            print(f"  {k:34s} SoC mínimo = {res['soc_min'][k]:5.1f} %  | energia desperdiçada (bateria cheia) = {res['desperdicio'][k]:7.1f} kWh")
        print(f"Convolução (média móvel 5): desvio-padrão da temperatura {res['desvio_antes']:.2f} -> {res['desvio_depois']:.2f} °C")
        print("Limitações: carga constante, geração senoidal ideal, sem degradação da bateria nem temperatura.")
    if salvar and plt:
        fig, ax = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
        for k, v in cen.items():
            ax[0].plot(v["t"], v["soc"], label=k)
        ax[0].axhline(30, ls="--", c="gray", lw=0.8); ax[0].set_ylabel("Estado de carga (%)")
        ax[0].set_title("Simulação do SoC da bateria - Aurora Siger"); ax[0].legend()
        v = cen["B: Tempestade de poeira"]
        ax[1].plot(v["t"], v["ger"], label="Geração solar (tempestade)")
        ax[1].plot(v["t"], v["carga"], label="Carga da colônia")
        ax[1].set_xlabel("Tempo (h)"); ax[1].set_ylabel("Potência (kW)"); ax[1].legend()
        fig.tight_layout(); fig.savefig(os.path.join(IMG, "simulacao_soc.png"), dpi=110); plt.close(fig)
        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.plot(sinal, "o-", alpha=0.5, label="Sinal bruto"); ax.plot(suave, lw=2, label="Após convolução (média móvel)")
        ax.set_title("Convolução aplicada ao sensor de temperatura (M02)"); ax.set_xlabel("Ciclo"); ax.set_ylabel("°C")
        ax.legend(); fig.tight_layout(); fig.savefig(os.path.join(IMG, "convolucao_sensor.png"), dpi=110); plt.close(fig)
    return res


# ============================================================================
# 5. MODELO LINEAR (regressão simples e múltipla com NumPy)
# ============================================================================
def ajustar_ols(X, y):
    """Mínimos quadrados ordinários com intercepto. Retorna coeficientes [b0, b1, ...]."""
    A = np.column_stack([np.ones(len(X)), X])
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return coef


def metricas(y, yhat, p):
    n = len(y); ss_res = float(((y - yhat) ** 2).sum()); ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot
    return {"R2": r2, "R2_aj": 1 - (1 - r2) * (n - 1) / (n - p - 1),
            "RMSE": (ss_res / n) ** 0.5, "MAE": float(np.abs(y - yhat).mean())}


def dados_para_modelo(conn):
    """Usa só leituras com sensor OK (limpeza de dados)."""
    rows = conn.execute("""SELECT l.consumo_kwh, l.ocupantes, l.temperatura_c, m.potencia_nominal_kw
        FROM leituras l JOIN modulos m ON m.id_modulo=l.id_modulo
        JOIN (SELECT id_modulo, AVG(consumo_kwh) mm FROM leituras GROUP BY id_modulo) a ON a.id_modulo=l.id_modulo
        WHERE l.status_sensor='OK' AND l.consumo_kwh < 1.6*a.mm""").fetchall()
    # (descarta sensores inválidos e picos anômalos > 1,6x a média do módulo, que distorceriam a regressão)
    a = np.array([[r["consumo_kwh"], r["ocupantes"], r["temperatura_c"], r["potencia_nominal_kw"]] for r in rows])
    return a


def executar_modelo(conn, salvar=True, verbose=True):
    d = dados_para_modelo(conn)
    y, ocup, temp, pot = d[:, 0], d[:, 1], d[:, 2], d[:, 3]
    corr = np.corrcoef(d.T)                       # análise exploratória: correlações
    rng = np.random.default_rng(7); idx = rng.permutation(len(y)); k = int(0.8 * len(y))
    tr, te = idx[:k], idx[k:]
    X_simples = ocup.reshape(-1, 1)   # melhor preditor isolado (maior correlação)
    X_mult = np.column_stack([pot, ocup, temp])
    b_s = ajustar_ols(X_simples[tr], y[tr]); b_m = ajustar_ols(X_mult[tr], y[tr])
    pred_s = np.column_stack([np.ones(len(te)), X_simples[te]]) @ b_s
    pred_m = np.column_stack([np.ones(len(te)), X_mult[te]]) @ b_m
    m_s, m_m = metricas(y[te], pred_s, 1), metricas(y[te], pred_m, 3)
    # multicolinearidade: VIF de cada preditor (regride o preditor nos outros)
    vif = []
    for j in range(3):
        outros = np.delete(X_mult, j, axis=1); bj = ajustar_ols(outros, X_mult[:, j])
        yh = np.column_stack([np.ones(len(outros)), outros]) @ bj
        vif.append(1 / (1 - metricas(X_mult[:, j], yh, 2)["R2"]))
    res = {"n": len(y), "corr": corr, "b_simples": b_s, "b_mult": b_m, "m_simples": m_s,
           "m_mult": m_m, "vif": vif}
    if verbose:
        print(f"\nAmostra limpa: {len(y)} leituras (treino {len(tr)} / teste {len(te)})")
        print("Correlação com consumo -> potência nominal: %.2f | ocupantes: %.2f | temperatura: %.2f"
              % (corr[0, 3], corr[0, 1], corr[0, 2]))
        print(f"Regressão SIMPLES  consumo = {b_s[0]:.2f} + {b_s[1]:.3f}·ocupantes  | "
              f"R²={m_s['R2']:.3f} RMSE={m_s['RMSE']:.2f} MAE={m_s['MAE']:.2f} (teste)")
        print(f"Regressão MÚLTIPLA consumo = {b_m[0]:.2f} + {b_m[1]:.3f}·potência + {b_m[2]:.3f}·ocupantes "
              f"+ ({b_m[3]:.3f})·temperatura")
        print(f"                   R²={m_m['R2']:.3f} R²aj={m_m['R2_aj']:.3f} RMSE={m_m['RMSE']:.2f} MAE={m_m['MAE']:.2f} (teste)")
        print(f"Interpretação: +1 ocupante => +{b_m[2]:.2f} kWh; +1 °C => {b_m[3]:+.2f} kWh (aquecimento menor); "
              f"+1 kW de potência nominal => +{b_m[1]:.2f} kWh.")
        print("VIF (multicolinearidade; <5 é aceitável): potência %.2f | ocupantes %.2f | temperatura %.2f" % tuple(vif))
        print("Limitações: dados simulados, 120 pontos, relação assumida linear, sem efeito de hora do dia.")
    if salvar and plt:
        fig, ax = plt.subplots(figsize=(5.5, 5))
        ax.scatter(y[te], pred_m); lim = [y.min(), y.max()]; ax.plot(lim, lim, "r--")
        ax.set_xlabel("Consumo real (kWh)"); ax.set_ylabel("Consumo previsto (kWh)")
        ax.set_title(f"Regressão múltipla - teste (R²={m_m['R2']:.2f})")
        fig.tight_layout(); fig.savefig(os.path.join(IMG, "regressao_real_vs_previsto.png"), dpi=110); plt.close(fig)
    return res


def prever_consumo(modelo, potencia, ocupantes, temperatura):
    b = modelo["b_mult"]
    return float(b[0] + b[1] * potencia + b[2] * ocupantes + b[3] * temperatura)


# ============================================================================
# 6. SISTEMA MULTIAGENTE (simulado, determinístico - sem LLM externo)
# ============================================================================
def _norm(txt):
    return "".join(c for c in unicodedata.normalize("NFD", txt.lower()) if unicodedata.category(c) != "Mn")


BASE_CONHECIMENTO = [  # RAG simulado: documentos do próprio sistema
    ("Procedimento energia", ["energia", "bateria", "consumo", "solar", "tempestade"],
     "Em tempestade de poeira, reduzir cargas não críticas (laboratório e comunicação) quando SoC < 30 %."),
    ("Procedimento ambiental", ["temperatura", "umidade", "luminosidade", "ambiente", "irrigacao"],
     "Manter habitação entre 18 e 26 °C; irrigação só com módulo agrícola ativo e umidade < 40 %."),
    ("Procedimento manutencao", ["manutencao", "falha", "sensor", "reparo", "chamado"],
     "Sensor INVALIDO bloqueia a operação automática e gera chamado de manutenção."),
    ("Politica de dados", ["privacidade", "tripulacao", "dados", "lgpd"],
     "Dados da tripulação são minimizados e agregados; decisões críticas exigem validação humana."),
]
PALAVRAS_PROIBIDAS = ["desligar suporte de vida", "desativar alarme", "apagar tudo", "ignorar seguranca",
                      "abrir eclusa", "desligar oxigenio"]
ESPECIALIDADES = {"dados": ["prev", "regressao", "media", "indicador", "dados", "historico"],
                  "energia": ["consumo", "energia", "bateria", "solar", "kwh", "carga"],
                  "ambiental": ["temperatura", "umidade", "luz", "luminosidade", "irrigacao", "ambiente"],
                  "manutencao": ["manutencao", "falha", "sensor", "defeito", "reparo", "chamado"],
                  }


class SistemaMultiagente:
    def __init__(self, conn, modelo):
        self.conn, self.modelo = conn, modelo
        self.sessao = []          # sessão: histórico da conversa
        self.contexto = {}        # último módulo mencionado
        self.trace = []           # tracing: cada passo executado

    def _t(self, passo): self.trace.append(passo)

    # ---- guardrails ----
    def guardrail(self, texto):
        t = _norm(texto)
        for p in PALAVRAS_PROIBIDAS:
            if p in t:
                return f"BLOQUEADO pelo guardrail (ação insegura: '{p}'). Encaminhado para a tripulação humana."
        if not any(w in t for ws in ESPECIALIDADES.values() for w in ws) and "m0" not in t:
            return "FORA DO ESCOPO: só respondo sobre energia, ambiente, manutenção e dados da colônia."
        return None

    # ---- ferramentas determinísticas ----
    def ferramenta_consumo(self, id_modulo):
        r = self.conn.execute("SELECT AVG(consumo_kwh) m, MAX(consumo_kwh) mx FROM leituras "
                              "WHERE id_modulo=? AND status_sensor='OK'", (id_modulo,)).fetchone()
        return r["m"], r["mx"]

    def ferramenta_alertas(self):
        return self.conn.execute("SELECT COUNT(*) FROM leituras WHERE status_sensor='INVALIDO'").fetchone()[0]

    def rag(self, texto):
        palavras = set(_norm(texto).split())
        melhor = max(BASE_CONHECIMENTO, key=lambda d: len(palavras & set(d[1])))
        return melhor if palavras & set(melhor[1]) else None

    # ---- agentes ----
    def triador(self, texto):
        t = _norm(texto); pont = {k: sum(w in t for w in ws) for k, ws in ESPECIALIDADES.items()}
        alvo = max(pont, key=pont.get); self._t(f"Triador: pontuação {pont} -> handoff para agente '{alvo}'")
        return alvo

    def agente(self, nome, texto):
        mod = next((m.upper() for m in (w.strip("?!.,;:") for w in _norm(texto).split()) if m.startswith("m0") and len(m) == 3),
                   self.contexto.get("modulo", "M01"))
        self.contexto["modulo"] = mod
        if nome == "energia":
            m, mx = self.ferramenta_consumo(mod); self._t(f"Agente energia: ferramenta_consumo({mod})")
            resp = f"Consumo médio de {mod}: {m:.2f} kWh (pico {mx:.2f})."
        elif nome == "manutencao":
            n = self.ferramenta_alertas(); self._t("Agente manutenção: ferramenta_alertas()")
            resp = f"Há {n} leituras com sensor inválido aguardando manutenção."
        elif nome == "dados":
            p = self.conn.execute("SELECT potencia_nominal_kw FROM modulos WHERE id_modulo=?", (mod,)).fetchone()[0]
            prev = prever_consumo(self.modelo, p, 3, 22); self._t(f"Agente dados: modelo linear({mod}, 3 ocupantes, 22 °C)")
            resp = f"Previsão do consumo de {mod} com 3 ocupantes a 22 °C: {prev:.2f} kWh."
        else:
            resp = "Agente ambiental: consultando regras de temperatura/umidade/luz."; self._t("Agente ambiental: RAG")
        doc = self.rag(texto)
        if doc:
            self._t(f"RAG: documento '{doc[0]}'"); resp += f" [Base: {doc[0]}] {doc[2]}"
        return resp + " (Recomendação - requer validação humana.)"

    def perguntar(self, texto):
        self.trace = [f"Entrada: {texto!r}"]
        bloqueio = self.guardrail(texto)
        if bloqueio:
            self._t("Guardrail ativado"); resposta = bloqueio
        else:
            resposta = self.agente(self.triador(texto), texto)
        self.sessao.append((texto, resposta))
        return resposta


# ============================================================================
# 7. ARQUITETURA COMPUTACIONAL
# ============================================================================
def benchmark_vetorizacao(n=300_000):
    """Mostra o ganho de processar dados em bloco (SIMD/vetorização) vs. laço Python."""
    x = np.random.default_rng(1).random(n)
    t0 = time.perf_counter(); s = 0.0
    for v in x: s += v * v
    t_loop = time.perf_counter() - t0
    t0 = time.perf_counter(); s2 = float(np.dot(x, x)); t_np = time.perf_counter() - t0
    return t_loop, t_np


def explicar_arquitetura():
    t_loop, t_np = benchmark_vetorizacao()
    print(f"""
ARQUITETURA COMPUTACIONAL APLICADA AO SIFSM
- CPU: menus, CRUD, regras booleanas, agentes (poucos dados, muita lógica de controle).
- GPU/NPU (conceitual): simulação com milhares de cenários e inferência de IA (paralelismo de dados);
  NPU/TPU consomem menos energia por inferência - importante em uma colônia com energia limitada.
- Computação heterogênea: cada tarefa na unidade mais eficiente; sensores/regras simples ficam em
  microcontrolador (Arduino) de baixíssimo consumo.
- Hierarquia de memória: leituras recentes em RAM/cache (dict, deque); histórico longo no banco (disco).
  O gargalo costuma ser mover dados (largura de banda), não calcular: por isso agregamos no banco (AVG via SQL).
- Chiplets/grandes sistemas de IA: citados conceitualmente (modularidade e eficiência energética).
Medição real neste computador (soma de quadrados de 300 mil números):
   laço Python = {t_loop*1000:.1f} ms | NumPy vetorizado = {t_np*1000:.2f} ms  -> {t_loop/max(t_np,1e-9):.0f}x mais rápido
   (menos tempo ativo de CPU = menos energia = mais sustentabilidade).""")


# ============================================================================
# 8. REFLEXÃO SOCIOAMBIENTAL (conectada ao sistema)
# ============================================================================
def reflexao_socioambiental():
    print("""
IMPACTO SUSTENTÁVEL, SOCIAL E DIGITAL DO SIFSM
1) Uso responsável de recursos: o banco + regra R1 + simulação do SoC mostram, antes de agir,
   quando o consumo ameaça a bateria; o corte de cargas não críticas evita colapso do módulo crítico.
2) Simulação reduz desperdício: o cenário "tempestade" testa a decisão no computador, não na colônia.
3) Cidadania digital: o campo 'ocupantes' é dado sobre pessoas; guardamos só contagem agregada,
   sem identidade, e o guardrail impede respostas fora do escopo (privacidade e transparência).
4) Economia dos dados: se dados da tripulação fossem vendidos/usados para vigilância, haveria risco
   de discriminação e perda de autonomia; por isso minimização + validação humana.
5) Impacto ambiental da IA/data centers: preferimos regras determinísticas e modelo linear leve
   (milissegundos, baixo consumo) a modelos gigantes; usar IA pesada só quando necessário.
6) Inovação com benefícios e riscos: toda recomendação do sistema é sugestão; a decisão final é humana.""")


# ============================================================================
# 9. ANÁLISE INTEGRADA: "Analisar sustentabilidade da colônia"
# ============================================================================
def analisar_sustentabilidade(conn):
    print("\n========== ANÁLISE DE SUSTENTABILIDADE DA COLÔNIA ==========")
    mods = {r["id_modulo"]: dict(r) for r in conn.execute("SELECT * FROM modulos")}
    alertas = AlertasPrioritarios(); ctr = {"R1": 0, "R4": 0, "R2": 0, "R3": 0}
    for l in conn.execute("SELECT * FROM leituras ORDER BY ciclo"):                 # 1) banco
        r = avaliar_regras(dict(l), mods[l["id_modulo"]])                            # 2) regras booleanas
        if r["R1_alerta_consumo"]:
            alertas.inserir(1, f"[CRÍTICO] {l['id_modulo']} ciclo {l['ciclo']}: consumo {l['consumo_kwh']:.1f} kWh"); ctr["R1"] += 1
        if r["R4_bloquear_operacao"]:
            alertas.inserir(2, f"[BLOQUEIO] {l['id_modulo']} ciclo {l['ciclo']}: sensor inválido"); ctr["R4"] += 1
        ctr["R2"] += r["R2_ligar_iluminacao"]; ctr["R3"] += r["R3_liberar_irrigacao"]
    print(f"Regras disparadas -> R1 alerta consumo: {ctr['R1']} | R4 bloqueio: {ctr['R4']} | "
          f"R2 iluminação: {ctr['R2']} | R3 irrigação: {ctr['R3']}")
    print("Alertas por prioridade (heap, 5 primeiros):")                             # 3) estrutura de dados
    for _ in range(min(5, len(alertas))):
        print("  ", alertas.remover()[2])
    sim = executar_simulacao(conn, verbose=False)                                    # 4) simulação
    modelo = executar_modelo(conn, verbose=False)                                    # 5) regressão
    prev = prever_consumo(modelo, 10, 4, 20)
    print(f"Simulação: SoC mínimo normal {sim['soc_min']['A: Normal']:.0f} % | tempestade {sim['soc_min']['B: Tempestade de poeira']:.0f} % "
          f"| com corte de cargas {sim['soc_min']['C: Tempestade + corte de cargas']:.0f} %")
    print(f"Modelo linear: previsão para módulo de 10 kW, 4 ocupantes, 20 °C = {prev:.2f} kWh (R² teste {modelo['m_mult']['R2']:.2f})")
    print("Impacto de falha de Energia (grafo/BFS):", ", ".join(modulos_afetados("M01")))
    print("\nRECOMENDAÇÃO TÉCNICA:")
    risco = sim["soc_min"]["B: Tempestade de poeira"] < 20
    if risco:
        print(" - Sem ação, a bateria chega a nível perigoso em tempestade: adotar corte automático de cargas não críticas.")
    print(f" - Agendar manutenção de {ctr['R4']} leituras de sensor inválido e investigar {ctr['R1']} picos de consumo.")
    if sim["soc_min"]["C: Tempestade + corte de cargas"] < 15:
        print(" - Mesmo com corte de cargas a margem é pequena: avaliar ampliar o armazenamento ou a geração.")
    print(" - Validação humana obrigatória; dados de tripulação apenas agregados (privacidade).")
    print("LIMITAÇÕES: dados simulados, modelo linear simples, simulação com carga constante e geração ideal.")


# ============================================================================
# 10. INTERFACE (MENU)
# ============================================================================
def _ler(msg, padrao=None):
    v = input(msg).strip()
    return v if v else padrao


def ui_cadastrar(conn, hist):
    try:
        d = {c: _ler(f"{c}: ") for c in CAMPOS}
        novo_id = criar_leitura(conn, d)
    except ValueError as e:
        print(f"[ERRO] {e}")
    else:
        hist.push(("INSERT", novo_id)); print(f"[OK] Leitura cadastrada com id {novo_id}.")
    finally:
        print("(operação de cadastro finalizada)")


def ui_listar(conn):
    mod = _ler("Filtrar por módulo (ENTER = todos): ")
    print(f"{'id':>4} {'ciclo':>5} {'mód':>4} {'ocup':>4} {'temp':>6} {'umid':>6} {'lux':>7} {'kWh':>6} status")
    for r in listar_leituras(conn, mod.upper() if mod else None, 15):
        print(f"{r['id_leitura']:>4} {r['ciclo']:>5} {r['id_modulo']:>4} {r['ocupantes']:>4} {r['temperatura_c']:>6} "
              f"{r['umidade_pct']:>6} {r['luminosidade_lux']:>7} {r['consumo_kwh']:>6} {r['status_sensor']}")


def ui_alterar(conn, hist):
    try:
        i = int(_ler("id da leitura: ")); campo = _ler("campo a alterar: ")
        if campo not in CAMPOS: raise ValueError("Campo inexistente.")
        antigo = atualizar_leitura(conn, i, {campo: _ler("novo valor: ")})
    except (ValueError, TypeError) as e:
        print(f"[ERRO] {e}")
    else:
        hist.push(("UPDATE", antigo)); print("[OK] Leitura alterada.")


def ui_excluir(conn, hist):
    try:
        antigo = excluir_leitura(conn, int(_ler("id da leitura: ")))
    except (ValueError, TypeError) as e:
        print(f"[ERRO] {e}")
    else:
        hist.push(("DELETE", antigo)); print("[OK] Leitura excluída (pode desfazer na opção 5).")


def desfazer(conn, hist):
    a = hist.pop()
    if a is None:
        print("Nada para desfazer."); return
    if a[0] == "INSERT": excluir_leitura(conn, a[1]); print(f"Desfeito: cadastro {a[1]} removido.")
    elif a[0] == "DELETE": restaurar_leitura(conn, a[1]); print(f"Desfeito: leitura {a[1]['id_leitura']} restaurada.")
    elif a[0] == "UPDATE": atualizar_leitura(conn, a[1]["id_leitura"], a[1]); print("Desfeito: alteração revertida.")


def ui_regras(conn):
    mods = {r["id_modulo"]: dict(r) for r in conn.execute("SELECT * FROM modulos")}
    l = conn.execute("SELECT * FROM leituras WHERE consumo_kwh > 1.3*(SELECT potencia_nominal_kw FROM modulos "
                     "WHERE id_modulo=leituras.id_modulo) ORDER BY consumo_kwh DESC LIMIT 1").fetchone()
    if l:
        print(f"Leitura exemplo (id {l['id_leitura']}, {l['id_modulo']}, {l['consumo_kwh']} kWh):")
        for k, v in avaliar_regras(dict(l), mods[l["id_modulo"]]).items(): print(f"  {k}: {v}")
    mostrar_tabela_verdade()


def ui_fila(conn, fila):
    if len(fila) == 0:
        for m, d, p in [("M01", "Inversor com ruído", 2), ("M03", "Bomba de irrigação lenta", 3), ("M06", "Calibrar sensor", 1)]:
            fila.enfileirar({"modulo": m, "descricao": d, "prioridade": p}); conn.execute(
                "INSERT INTO chamados (id_modulo,descricao,prioridade) VALUES (?,?,?)", (m, d, p))
        conn.commit(); print("3 chamados de exemplo enfileirados.")
    print("Fila atual (ordem de chegada):", [c["modulo"] + ":" + c["descricao"] for c in fila.lista()])
    c = fila.atender(); print("Atendendo (FIFO):", c)


def ui_buscar_hash(tabela):
    cod = (_ler("Código do sensor (ex.: SNS-M03): ") or "").upper()
    print(tabela.get(cod, "Sensor não encontrado."))


def menu(conn):
    hist, fila, tabela = HistoricoAcoes(), FilaChamados(), construir_tabela_hash(conn)
    modelo = executar_modelo(conn, salvar=False, verbose=False); sma = SistemaMultiagente(conn, modelo)
    opcoes = {
        "1": ("Cadastrar leitura (CREATE)", lambda: ui_cadastrar(conn, hist)),
        "2": ("Listar leituras (READ)", lambda: ui_listar(conn)),
        "3": ("Alterar leitura (UPDATE)", lambda: ui_alterar(conn, hist)),
        "4": ("Excluir leitura (DELETE)", lambda: ui_excluir(conn, hist)),
        "5": ("Desfazer última ação (pilha)", lambda: desfazer(conn, hist)),
        "6": ("Buscar sensor por código (tabela hash)", lambda: ui_buscar_hash(tabela)),
        "7": ("Regras booleanas e circuito lógico", lambda: ui_regras(conn)),
        "8": ("Fila de chamados de manutenção", lambda: ui_fila(conn, fila)),
        "9": ("Grafo: impacto da falha de um módulo", lambda: print("Afetados:", modulos_afetados((_ler("Módulo (ex.: M01): ") or "M01").upper()))),
        "10": ("Simulação computacional (SoC)", lambda: executar_simulacao(conn)),
        "11": ("Modelo linear (regressão)", lambda: executar_modelo(conn)),
        "12": ("Assistente multiagente", lambda: print(sma.perguntar(_ler("Pergunta: ")), "\nTRACE:", *sma.trace, sep="\n  ")),
        "13": ("Arquitetura computacional", explicar_arquitetura),
        "14": ("Reflexão socioambiental", reflexao_socioambiental),
        "15": ("ANALISAR SUSTENTABILIDADE DA COLÔNIA", lambda: analisar_sustentabilidade(conn)),
    }
    while True:
        print("\n=== SIFSM - Aurora Siger ===")
        for k, (nome, _) in opcoes.items(): print(f"{k:>2}. {nome}")
        print(" 0. Sair")
        esc = input("Escolha: ").strip()
        if esc == "0": print("Encerrando. Até logo!"); break
        if esc in opcoes: opcoes[esc][1]()
        else: print("[ERRO] Opção inválida.")


# ============================================================================
# 11. DEMONSTRAÇÃO AUTOMÁTICA (python codigo_fonte.py --demo)
# ============================================================================
def demo(conn):
    print("##### DEMO SIFSM #####")
    hist = HistoricoAcoes()
    print("\n--- CRUD ---")
    nova = dict(ciclo=20, id_modulo="M02", codigo_sensor="SNS-M02", ocupantes=4, temperatura_c=21.5,
                umidade_pct=47, luminosidade_lux=150, consumo_kwh=7.9, status_sensor="OK")
    i = criar_leitura(conn, nova); hist.push(("INSERT", i)); print("CREATE -> id", i)
    print("READ   ->", dict(obter_leitura(conn, i)))
    antigo = atualizar_leitura(conn, i, {"consumo_kwh": 8.4}); hist.push(("UPDATE", antigo))
    print("UPDATE -> consumo agora", obter_leitura(conn, i)["consumo_kwh"])
    print("Tratamento de erros:")
    for ruim in ({**nova, "umidade_pct": 150}, {**nova, "ocupantes": "abc"}, {**nova, "id_modulo": "M99"}):
        try: criar_leitura(conn, ruim)
        except ValueError as e: print("  [ERRO capturado]", e)
    reg = excluir_leitura(conn, i); hist.push(("DELETE", reg)); print("DELETE -> removida; pilha tem", len(hist), "ações")
    desfazer(conn, hist); print("Desfazer (pilha) -> restaurada:", obter_leitura(conn, i)["id_leitura"] == i)
    excluir_leitura(conn, i)
    print("\n--- Tabela hash ---", construir_tabela_hash(conn)["SNS-M03"])
    print("--- Fila ---"); f = FilaChamados()
    for m in ("M01", "M03", "M06"): f.enfileirar(m)
    print("Atendendo:", f.atender(), "| restam", len(f))
    print("--- Grafo --- falha M01 afeta:", modulos_afetados("M01"), "| falha M05 afeta:", modulos_afetados("M05"))
    print("\n--- Regras booleanas ---"); ui_regras(conn)
    print("\n--- Simulação ---"); executar_simulacao(conn)
    print("\n--- Modelo linear ---"); modelo = executar_modelo(conn)
    print("\n--- Multiagente ---")
    sma = SistemaMultiagente(conn, modelo)
    for q in ("Qual o consumo de energia do M03?", "Preveja o consumo do M02", "Existe sensor com falha?",
              "Por favor desligar suporte de vida do M06", "Qual a receita de bolo?"):
        print("Q:", q); print("R:", sma.perguntar(q)); print("   trace:", " | ".join(sma.trace[1:]))
    print("\n--- Arquitetura ---"); explicar_arquitetura()
    print("\n--- Reflexão ---"); reflexao_socioambiental()
    analisar_sustentabilidade(conn)


if __name__ == "__main__":
    conexao = conectar()
    try:
        demo(conexao) if "--demo" in sys.argv else menu(conexao)
    finally:
        conexao.close()
