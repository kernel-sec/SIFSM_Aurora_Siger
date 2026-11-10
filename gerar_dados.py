"""Gera a base simulada dados_aurora_siger.csv (semente fixa = reprodutível).
Modelo "verdadeiro" usado na simulação dos dados:
consumo = 0.5*potencia_nominal + 0.8*ocupantes + 0.15*(25 - temperatura) + ruído
"""
import csv, math, random
random.seed(42)
MODULOS = {  # id: (potencia_nominal_kw, umidade_media)
    "M01": (6, 45), "M02": (10, 45), "M03": (12, 45),
    "M04": (8, 42), "M05": (5, 40), "M06": (9, 48)}
linhas = []
for mod, (pot, um) in MODULOS.items():
    for ciclo in range(20):                       # 20 ciclos (1 ciclo = 1 hora simulada)
        ocup = random.randint(0, 6)
        temp = round(random.gauss(22, 3), 1)
        umid = round(random.gauss(um, 6), 1)
        lum = round(max(0, 700*math.sin(2*math.pi*ciclo/20) + random.gauss(0, 40)), 1)
        cons = 0.5*pot + 0.8*ocup + 0.15*(25-temp) + random.gauss(0, 0.3)
        status = "OK"
        if (mod, ciclo) in [("M01", 7), ("M06", 12), ("M03", 15)]:
            cons *= 1.9                            # picos de consumo (eventos anômalos)
        if (mod, ciclo) in [("M04", 3), ("M05", 9), ("M02", 14), ("M06", 4)]:
            status, temp = "INVALIDO", -99.0       # falha de sensor simulada
        linhas.append([ciclo, mod, f"SNS-{mod}", ocup, temp, umid, lum, round(cons, 2), status])
with open("dados_aurora_siger.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["ciclo","id_modulo","codigo_sensor","ocupantes","temperatura_c",
                "umidade_pct","luminosidade_lux","consumo_kwh","status_sensor"])
    w.writerows(linhas)
print(len(linhas), "linhas geradas")
