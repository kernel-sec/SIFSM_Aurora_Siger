"""Gera graficos_ou_imagens/circuito_logico.png: LED = (A AND B) OR M + tabela verdade."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle

fig, ax = plt.subplots(figsize=(11, 5)); ax.set_xlim(0, 11); ax.set_ylim(0, 5); ax.axis("off")

def fio(xs, ys):
    ax.plot(xs, ys, "k", lw=2, solid_capstyle="round")

def porta(x, y, rot):                       # símbolo IEC: retângulo com & ou ≥1
    ax.add_patch(Rectangle((x, y), 1.4, 1.2, fill=False, lw=2))
    ax.text(x + 0.7, y + 0.6, rot, ha="center", va="center", fontsize=16, weight="bold")

# Entradas
ax.text(0.1, 3.95, "A (consumo alto)", fontsize=10, va="center")
ax.text(0.1, 3.05, "B (módulo crítico)", fontsize=10, va="center")
ax.text(0.1, 1.00, "M (manutenção pendente)", fontsize=10, va="center")
fio([2.2, 3.0], [3.95, 3.95]); fio([3.0, 3.0], [3.95, 3.80])   # A -> AND (entrada de cima)
fio([2.2, 3.0], [3.05, 3.05]); fio([3.0, 3.0], [3.05, 3.20])   # B -> AND (entrada de baixo)
porta(3.0, 3.0, "&"); ax.text(3.7, 4.35, "AND", ha="center")
# AND -> OR
fio([4.4, 5.0, 5.0, 5.6], [3.6, 3.6, 2.9, 2.9])
# M -> OR
fio([2.9, 5.0, 5.0, 5.6], [1.0, 1.0, 2.3, 2.3])
porta(5.6, 2.1, "≥1"); ax.text(6.3, 3.5, "OR", ha="center")
# OR -> LED
fio([7.0, 7.8], [2.7, 2.7]); ax.add_patch(Circle((8.1, 2.7), 0.3, color="red", alpha=0.85))
ax.text(8.1, 2.1, "LED alerta", ha="center")
ax.set_title("Circuito lógico: LED_ALERTA = (A · B) + M", fontsize=13)
linhas = ["A B M | LED"] + [f"{a} {b} {m} |  {int((a and b) or m)}" for a in (0, 1) for b in (0, 1) for m in (0, 1)]
ax.text(9.2, 4.6, "\n".join(linhas), family="monospace", va="top", fontsize=10)
fig.tight_layout(); fig.savefig("graficos_ou_imagens/circuito_logico.png", dpi=120)
