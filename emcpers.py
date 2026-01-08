# streamlit_app.py
import json
import re
import requests
import streamlit as st
from typing import Dict, List, Any, Optional

# =========================
# CONFIG
# =========================
API_URL = "https://dify.b3med.ru/v1/workflows/run"
APP_RISK_KEY = "app-MZnEAgjZvHs4zO7RM5nohC6Y"
APP_KR_KEY   = "app-IQSYqOjP3Yp2uqTTYPepw6sn"
USER_ID = "streamlit-ui"
# =========================
# AUTH
# =========================
ACCESS_CODES = {
    "emc2026"
}

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
def login_gate():
    st.markdown("## 🔒 Доступ ограничен")
    st.markdown("Введите код доступа для продолжения")

    code = st.text_input(
        "Код доступа",
        type="password",
        placeholder="Введите код"
    )

    if st.button("Войти"):
        if code in ACCESS_CODES:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Неверный код доступа")


st.set_page_config(page_title="Система рекомендаций", layout="wide")
if not st.session_state.authenticated:
    login_gate()
    st.stop()


# =========================
# UI STYLE (ЕДИНЫЙ)
# =========================
CSS = """
<style>
.block-card {
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px;
  padding: 14px;
  background: rgba(255,255,255,0.03);
  margin-bottom: 12px;
}
.risk-badge {
  display: inline-block;
  padding: 6px 12px;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.25);
  font-weight: 600;
  margin: 14px 0 10px 0;
}

.service-title {
  font-weight: 700;
  font-size: 1.05rem;
}
.pill {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.78rem;
  margin-right: 6px;
  border: 1px solid rgba(255,255,255,0.12);
}
.pill-blue  { background: rgba(56,189,248,.14); }
.pill-lilac {
  background: rgba(168, 85, 247, 0.16);
  border-color: rgba(168, 85, 247, 0.28);
}
.pill-gray  { background: rgba(148,163,184,.12); }
.pill-white { background: rgba(255,255,255,.10); }
.small-muted { opacity:.85; font-size:.92rem; }
.tooltip-i { margin-left:6px; cursor:help; }
hr.soft { border:none; height:1px; background:rgba(255,255,255,.08); margin:14px 0; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

def pill(text, kind):
    return f"<span class='pill pill-{kind}'>{text}</span>"

# =========================
# API
# =========================
def dify_run(api_key, inputs):
    r = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "inputs": inputs,
            "response_mode": "blocking",
            "user": USER_ID,
        },
        timeout=180,
        verify=False,
    )
    r.raise_for_status()
    return r.json()["data"]["outputs"]

# =========================
# TEXT NORMALIZATION
# =========================
def normalize(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("**", "")
            .replace("🟢", "")
            .replace("\r", "")
            .strip()
    )

# =========================
# PARSING (риски / общие)
# =========================
SYSTEM_RE = re.compile(r"Система:\s*(.+)")
STUDY_RE  = re.compile(r"Вид исследования:\s*(.+)")
SERVICE_RE = re.compile(r"Услуга:\s*(.+)")
GOAL_RE   = re.compile(r"Цель:\s*(.+)")
FREQ_RE   = re.compile(r"Частота в год:\s*(\d+)")
NMU_CODE_RE = re.compile(r"Код НМУ:\s*([A-ZА-Я0-9.\-]+)")
NMU_NAME_RE = re.compile(r"Название по НМУ:\s*(.+)")
RISK_RE = re.compile(r"Риск:\s*(.+)")

def parse_systems(text: str) -> Dict[str, List[Dict[str, Any]]]:
    text = normalize(text)
    lines = text.split("\n")

    systems: Dict[str, List[Dict[str, Any]]] = {}
    current_system = None
    current_study = None
    current_service = None
    current_risk = None

    for line in lines:
        if m := SYSTEM_RE.search(line):
            current_system = m.group(1).strip()
            systems.setdefault(current_system, [])
            current_service = None
            continue

        if m := STUDY_RE.search(line):
            current_study = m.group(1).strip()
            continue
        if m := RISK_RE.search(line):
            current_risk = m.group(1).strip()
            continue


        if m := SERVICE_RE.search(line):
            current_service = {
                "service": m.group(1).strip(),
                "study": current_study,
                "goal": "",
                "freq": None,
                "nmu_code": None,
                "nmu_name": None,
                "risk": current_risk,
            }

            systems[current_system].append(current_service)
            continue

        if not current_service:
            continue

        if m := GOAL_RE.search(line):
            current_service["goal"] = m.group(1).strip()
        if m := FREQ_RE.search(line):
            current_service["freq"] = int(m.group(1))
        if m := NMU_CODE_RE.search(line):
            current_service["nmu_code"] = m.group(1)
        if m := NMU_NAME_RE.search(line):
            current_service["nmu_name"] = m.group(1)

    return systems

def freq_label(n):
    if not n:
        return ""
    return "1 раз в год" if n == 1 else f"{n} раза в год"

# =========================
# RENDERERS (ЕДИНЫЙ СТИЛЬ)
# =========================
def render_cards(title: str, systems: Dict[str, List[Dict[str, Any]]], show_risk_headers: bool = False):

    st.markdown(f"## {title}")
    if not systems:
        st.info("Нет данных")
        return

    for system, services in systems.items():
        with st.expander(system, expanded=False):
            last_risk = None

            for s in services:
                tags = []
                if s.get("study"):
                    tags.append(pill(s["study"], "blue"))
                if s.get("freq"):
                    tags.append(pill(freq_label(s["freq"]), "lilac"))
                if s.get("nmu_code"):
                    tags.append(pill(f"НМУ {s['nmu_code']}", "gray"))

                tooltip = ""
                if s.get("nmu_name"):
                    tooltip = f"<span class='tooltip-i' title='{s['nmu_name']}'>ℹ️</span>"
                if show_risk_headers:
                    risk_name = s.get("risk")
                    if risk_name and risk_name != last_risk:
                        st.markdown(
                            f"<div class='risk-badge'>{risk_name}</div>",
                            unsafe_allow_html=True
                        )
                        last_risk = risk_name


                st.markdown(
                    f"""
                    <div class="block-card">
                    <div class="service-title">{s['service']}{tooltip}</div>
                    <div class="small-muted" style="margin-top:6px;">
                        {s.get('goal','')}
                    </div>
                    <div style="margin-top:10px;">
                        {" ".join(tags)}
                    </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


def render_kr_as_cards(kr_payload: Dict[str, Any]):
    """
    kr_payload ожидается в формате:
    {
      "diagnoses": [
        {
          "name": "Название диагноза",
          "recommendations": [
            {
              "name": "...",
              "code": "...",
              "study_type": "лабораторное | инструментальное | функциональное | консультация",
              "comment": "..."
            }
          ]
        }
      ]
    }
    """

    st.markdown("## Клинические рекомендации")

    if not kr_payload:
        st.info("Нет рекомендаций по КР")
        return

    diagnoses = kr_payload.get("diagnoses", [])
    if not diagnoses:
        st.info("Нет диагнозов в клинических рекомендациях")
        return

    with st.expander("Клинические рекомендации", expanded=True):

        for diag in diagnoses:
            diag_name = diag.get("name")
            recs = diag.get("recommendations", [])

            # ===== ПЛАШКА ДИАГНОЗА =====
            if diag_name:
                st.markdown(
                    f"""
                    <div style="
                        display:inline-block;
                        padding:6px 14px;
                        border-radius:12px;
                        background: rgba(239, 68, 68, 0.12);
                        border: 1px solid rgba(239, 68, 68, 0.25);
                        font-weight: 600;
                        margin: 12px 0 14px 0;
                    ">
                        Диагноз: {diag_name}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            if not recs:
                st.caption("Нет рекомендаций для данного диагноза")
                continue

            # ===== УСЛУГИ ПО ДИАГНОЗУ =====
            for it in recs:
                tags = []

                # вид исследования
                study_type = it.get("study_type")
                if study_type:
                    tags.append(pill(study_type, "blue"))

                # код НМУ
                if it.get("code"):
                    tags.append(pill(f"НМУ {it['code']}", "gray"))

                st.markdown(
                    f"""
                    <div class="block-card">
                      <div class="service-title">{it.get("name","")}</div>
                      <div class="small-muted" style="margin-top:6px;">
                        {it.get("comment","")}
                      </div>
                      <div style="margin-top:10px;">
                        {" ".join(tags)}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.sidebar.markdown(
        """
        <div style="
            background: white;
            margin: -32px -8px 16px -8px;
            padding: 14px 0;
            border-radius: 16px;
            display: flex;
            justify-content: center;
            align-items: center;
        ">
            <img src="https://avatars.mds.yandex.net/get-tycoon/15128173/2a000001940cb7e88d4e048caa0497c94d9b/priority-headline-logo-square"
                width="110"
                style="border-radius:12px;">
        </div>
        """,
        unsafe_allow_html=True
    )





    st.markdown("## Ввод данных о пациенте")
    sex = st.selectbox("Пол", ["Мужской", "Женский"])
    age = st.selectbox("Возраст", ["0-4","5-11","12-17","18-24","25-39","40-49","50-64","65-74","75+"])
    risk_text = st.text_area("Риски / жалобы")
    mkb = st.text_input("Введите коды МКБ-10 через запятую")
    run = st.button("Сформировать рекомендации")

# =========================
# MAIN
# =========================
st.title("Система рекомендаций для врача")

if run:
    with st.spinner("Получаем рекомендации…"):

        kr_payload = None
        if mkb.strip():
            out2 = dify_run(APP_KR_KEY, {"MKB": mkb})
            kr_payload = json.loads(out2.get("result", "{}"))

        out1 = dify_run(
            APP_RISK_KEY,
            {"sex": sex, "age": age, "risk": risk_text}
        )

    # --- Клинические рекомендации
    if kr_payload:
        render_kr_as_cards(kr_payload)

    # --- Риски
    render_cards(
        "Рекомендации по рискам",
        parse_systems(out1.get("result2", "")),
        show_risk_headers=True
    )

    # --- Общие рекомендации
    render_cards(
        "Общие рекомендации по здоровью",
        parse_systems(out1.get("result1", "")),
        show_risk_headers=False
    )

else:
    st.markdown(
    """
    <style>
    .desktop-only { display: block; }
    .mobile-only { display: none; }

    @media (max-width: 768px) {
        .desktop-only { display: none; }
        .mobile-only { display: block; }
    }
    </style>

    <div class="desktop-only">
        <div class="stAlert stAlert-info">
            Заполните данные слева и нажмите кнопку.
        </div>
    </div>

    <div class="mobile-only">
        <div class="stAlert stAlert-info">
            Заполните данные сверху и нажмите кнопку.
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


