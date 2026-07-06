O seu código original continha vários blocos desconexos, variáveis indefinidas (`email` e `senha` vazios, `tempo_total`, `tma`), funções cortadas pela metade (como a parte do Ranking e a exibição final), além de um trecho solto de HTML e problemas na indentação do loop da busca.

Eu juntei todas as pontas, corrigi a estrutura das funções, unifiquei o cálculo de KPIs/TMA dentro da função `calcular_kpi`, criei a lógica para o `ranking` baseado na fila/técnico e arrumei a interface do Streamlit para exibir tudo de forma organizada.

Aqui está o código completo e corrigido:

```python
import time
from datetime import datetime, time as datetime_time
import requests
import streamlit as st
from bs4 import BeautifulSoup

print("🔥 Iniciando aplicação...")

# ===== CONFIG =====
login_url = "https://pabx.evence.com.br/login"
cdr_url = "https://pabx.evence.com.br/cdr/pesquisar"

# Adicione suas credenciais aqui
email = "seu_email@exemplo.com"
senha = "sua_senha"


# =========================================================
# SESSÃO REUTILIZÁVEL (evita múltiplos logins)
# =========================================================
@st.cache_resource
def get_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    return session


# =========================================================
# LOGIN NO PABX (TIMEOUT 120)
# =========================================================
def login_pabx():
    session = get_session()

    r = session.get(login_url, timeout=120)
    soup = BeautifulSoup(r.text, "html.parser")

    csrf_input = soup.find("input", {"name": "_token"})
    csrf_token = csrf_input["value"] if csrf_input else ""

    payload = {"login": email, "senha": senha, "_token": csrf_token}

    response = session.post(login_url, data=payload, timeout=120)

    if response.url != login_url:
        return session
    else:
        raise Exception("Erro no login")


# =========================================================
# RETRY (EVITA TIMEOUT QUEBRAR EXECUÇÃO)
# =========================================================
def request_com_retry(session, url, params, headers, tentativas=4):
    """Faz retry automático em caso de timeout ou falha de rede."""
    for i in range(tentativas):
        try:
            return session.get(url, params=params, headers=headers, timeout=120)
        except requests.exceptions.Timeout:
            if i == tentativas - 1:
                raise
            time.sleep(2)


# =========================================================
# BUSCA CDR (SEM CACHE PARA NÃO QUEBRAR UI)
# =========================================================
def buscar_cdr(data_inicio, data_fim, progress_ui=None):
    session = login_pabx()

    data_inicio_dt = datetime.strptime(data_inicio, "%Y-%m-%d")
    data_fim_dt = datetime.strptime(data_fim, "%Y-%m-%d")

    if data_inicio_dt > data_fim_dt:
        data_inicio_dt, data_fim_dt = data_fim_dt, data_inicio_dt

    data_inicio_str = data_inicio_dt.strftime("%d-%m-%Y")
    data_fim_str = data_fim_dt.strftime("%d-%m-%Y")

    payload = {
        "ramal_origem": "",
        "numero_origem": "",
        "ramal_destino": "",
        "numero_destino": "",
        "did": "",
        "status_chamada": "",
        "centrocusto_id": "",
        "tipo_chamada": "IN",
        "gravacao": "",
        "discador": "0",
        "data_inicial": data_inicio_str,
        "data_final": data_fim_str,
    }

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://pabx.evence.com.br/cdr",
    }

    dados = []
    pagina = 1

    if progress_ui:
        progress_bar = progress_ui.progress(0)
        status_text = st.empty()
    else:
        progress_bar = None
        status_text = None

    total_estimado = 70

    while True:
        payload["page"] = pagina

        if status_text:
            status_text.text(f"📄 Processando página {pagina}")

        r = request_com_retry(session, cdr_url, payload, headers)
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("table tbody tr")

        if not rows:
            break

        for row in rows:
            cols = row.find_all("td")
            if len(cols) >= 8:
                data_hora = cols[0].get_text(strip=True)
                fila = cols[4].get_text(strip=True)
                duracao = cols[5].get_text(strip=True)
                status = cols[6].get_text(strip=True)
                tipo = cols[7].get_text(strip=True)

                try:
                    dt = datetime.strptime(data_hora, "%d-%m-%Y %H:%M:%S")
                except:
                    continue

                hora = dt.time()

                try:
                    h, m, s = duracao.split(":")
                    segundos = int(h) * 3600 + int(m) * 60 + int(s)
                except:
                    segundos = 0

                dados.append(
                    {
                        "data": dt,
                        "hora": hora,
                        "fila": fila,
                        "duracao": duracao,
                        "segundos": segundos,
                        "status": status,
                        "tipo": tipo,
                    }
                )

        if progress_bar:
            progresso = min(pagina / total_estimado, 1.0)
            progress_bar.progress(progresso)

        pagina += 1
        time.sleep(0.3)

    if progress_ui:
        progress_ui.empty()
        if status_text:
            status_text.empty()

    return dados


# =========================================================
# KPI E RESOLUÇÃO DOS CÁLCULOS DE TEMPO
# =========================================================
def calcular_kpi(dados):
    total_atendidas = 0
    total_manha = 0
    total_tarde = 0
    tempo_total = 0

    inicio_manha = datetime_time(8, 15, 0)
    fim_manha = datetime_time(13, 0, 0)
    inicio_tarde = datetime_time(13, 0, 0)
    fim_tarde = datetime_time(21, 0, 0)

    for d in dados:
        if d["status"].lower() != "atendida":
            continue
        if d["tipo"].lower() != "entrada":
            continue

        total_atendidas += 1
        tempo_total += d["segundos"]
        hora = d["hora"]

        if inicio_manha <= hora < fim_manha:
            total_manha += 1
        elif inicio_tarde <= hora <= fim_tarde:
            total_tarde += 1

    # Cálculos extras baseados nos blocos soltos do seu código
    tempo_total_horas = tempo_total / 3600
    horas_fmt = int(tempo_total // 3600)
    minutos_fmt = int((tempo_total % 3600) // 60)
    tempo_formatado = f"{horas_fmt:02d}:{minutos_fmt:02d}"

    tma = (tempo_total / total_atendidas) if total_atendidas > 0 else 0
    tma_seg_total = int(round(tma))
    tma_minutos = tma_seg_total // 60
    tma_segundos = tma_seg_total % 60
    tma_formatado = f"{tma_minutos:02d}:{tma_segundos:02d}"

    alertas = []
    if tma > 300:  # Exemplo: Alerta se TMA for maior que 5 minutos
        alertas.append("⚠️ O Tempo Médio de Atendimento (TMA) está acima do esperado!")

    return {
        "total": total_atendidas,
        "manha": total_manha,
        "tarde": total_tarde,
        "tempo_total": round(tempo_total_horas, 2),
        "tempo_total_formatado": tempo_formatado,
        "tma": round(tma / 60, 2),
        "tma_formatado": tma_formatado,
        "alertas": alertas,
    }


# =========================================================
# RANKING POR FILA / TÉCNICO
# =========================================================
def gerar_ranking(dados):
    tecnicos_dados = {}

    for d in dados:
        if d["status"].lower() != "atendida" or d["tipo"].lower() != "entrada":
            continue

        tecnico = d["fila"] if d["fila"] else "Não Identificado"

        if tecnico not in tecnicos_dados:
            tecnicos_dados[tecnico] = {"chamadas": 0, "segundos": 0}

        tecnicos_dados[tecnico]["chamadas"] += 1
        tecnicos_dados[tecnico]["segundos"] += d["segundos"]

    resultado = []
    for tecnico, info in tecnicos_dados.items():
        tma = info["segundos"] / info["chamadas"] if info["chamadas"] > 0 else 0
        tma_seg_total = int(round(tma))
        tma_minutos = tma_seg_total // 60
        tma_segundos = tma_seg_total % 60
        tma_formatado = f"{tma_minutos:02d}:{tma_segundos:02d}"

        resultado.append(
            {
                "tecnico": tecnico,
                "chamadas": info["chamadas"],
                "tma": round(tma / 60, 2),
                "tma_formatado": tma_formatado,
            }
        )

    resultado.sort(key=lambda x: x["chamadas"], reverse=True)
    return resultado


# =========================================================
# INTERFACE STREAMLIT
# =========================================================
st.title("📊 Dashboard de ligações - Helpdesk")

with st.form("form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        data_inicio = st.date_input("Data início")

    with col2:
        data_fim = st.date_input("Data fim")

    with col3:
        st.empty()

    submit = st.form_submit_button("🔍 Consultar")


# =========================================================
# EXECUÇÃO
# =========================================================
if submit:
    try:
        if not data_inicio or not data_fim:
            st.error("Preencha as datas")
        else:
            progress_ui = st.empty()

            dados = buscar_cdr(str(data_inicio), str(data_fim), progress_ui)

            if not dados:
                st.error("Nenhum dado encontrado")
            else:
                resultado = calcular_kpi(dados)
                ranking = gerar_ranking(dados)

                # Exibição dos Cards de Métrica
                m1, m2, m3 = st.columns(3)
                m1.metric("📞 Total Atendidas", resultado["total"])
                m2.metric("🌞 Manhã (08:15 às 13:00)", resultado["manha"])
                m3.metric("🌙 Tarde (13:00 às 21:00)", resultado["tarde"])

                st.markdown("---")

                # Métricas de Tempo Adicionais
                m4, m5 = st.columns(2)
                m4.metric("⏳ Tempo Total Conversado", resultado["tempo_total_formatado"])
                m5.metric("⏱️ TMA Formatado", resultado["tma_formatado"])

                # Exibição de Alertas se houverem
                if resultado["alertas"]:
                    st.write("")
                    for alerta in resultado["alertas"]:
                        st.markdown(
                            f"""
                            <div style="background-color:#F7D7DA;padding:15px;border-radius:10px;border:1px solid #f5c2c7;color:#842029;margin-bottom:10px;">
                                {alerta}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                # Construção e Exibição da Tabela de Ranking
                st.subheader("🏆 Ranking de Atendimento")
                ranking_formatado = [
                    {
                        "Técnico/Fila": r["tecnico"],
                        "Chamadas": r["chamadas"],
                        "TMA (mm:ss)": r["tma_formatado"],
                    }
                    for r in ranking
                ]

                st.table(ranking_formatado)

    except Exception as e:
        st.error(f"Ocorreu um erro: {e}")

```
