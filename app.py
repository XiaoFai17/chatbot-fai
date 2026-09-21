"""
Fai - Gaming Companion Chatbot
Streamlit app terhubung ke Groq API dengan fitur:
- Trial chat gratis (1x pakai API key milik developer, selanjutnya user wajib input API key sendiri)
- Streaming response
- Conversation history (simpan ke JSON & muat ulang)
- Kontrol parameter temperature
- Error handling supaya tidak crash
"""

import json
from datetime import datetime

import streamlit as st
from groq import Groq

# =========================================================
# KONFIGURASI DASAR
# =========================================================

st.set_page_config(page_title="Fai - Gaming Companion", layout="centered")

SYSTEM_PROMPT = """Kamu adalah Fai, AI gaming companion yang membantu pengguna menentukan game yang cocok untuk dimainkan.

Kepribadianmu:
- Ramah, santai, dan antusias soal game
- Ngobrol seperti teman, bukan seperti asisten formal
- Pakai bahasa Indonesia yang natural dan kasual
- Boleh sesekali pakai emoji yang relevan, tapi jangan berlebihan

Tugasmu:
- Bantu pengguna menemukan game yang cocok berdasarkan kondisi dan preferensi mereka
- Pertimbangkan faktor seperti: mood, waktu bermain, genre favorit, platform, single/multiplayer, santai vs kompetitif
- Ingat preferensi yang sudah disebutkan pengguna dalam percakapan ini
- Berikan rekomendasi beserta alasan singkat mengapa game itu cocok untuk mereka
- Jika info pengguna belum cukup, tanya secara natural — jangan seperti mengisi formulir
- Boleh rekomendasikan beberapa game sekaligus dengan variasi pilihan

Yang tidak boleh dilakukan:
- Jangan pura-pura punya database game realtime atau akses internet
- Jika tidak yakin soal detail game tertentu, sampaikan dengan jujur
- Jangan keluar dari peran sebagai gaming companion
- Jangan terlalu formal atau kaku
"""

GREETING = (
    "Halo, gue Fai, temen ngobrol kamu buat nyari game yang pas dimainkan. "
    "Cerita dong, sekarang lagi mood apa? Capek dan pengen santai, lagi semangat "
    "cari tantangan, punya waktu berapa lama, atau ada genre favorit tertentu?"
)

MODEL_NAME = "openai/gpt-oss-120b"

# =========================================================
# STYLING
# =========================================================

st.markdown(
    """
    <style>
    .fai-header {
        text-align: center;
        padding: 0.75rem 0 1.25rem 0;
    }
    .fai-header h1 {
        font-size: 1.8rem;
        margin-bottom: 0.1rem;
        background: linear-gradient(90deg, #8b5cf6, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .fai-header p {
        color: #9ca3af;
        font-size: 0.9rem;
        margin: 0;
    }
    /* Bubble chat: background gelap konsisten + teks dipaksa terang supaya
       selalu kebaca, apapun tema browser/OS pengguna */
    [data-testid="stChatMessage"] {
        border-radius: 14px;
        padding: 0.7rem 1rem;
        background-color: #1a1b23;
        border: 1px solid #2a2b36;
        margin-bottom: 0.5rem;
    }
    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] li,
    [data-testid="stChatMessage"] span,
    [data-testid="stChatMessage"] strong {
        color: #e8e9ed !important;
    }
    [data-testid="stChatMessage"] code {
        color: #f0abfc !important;
        background-color: #26272f !important;
    }
    .stChatInput textarea {
        border-radius: 12px !important;
    }
    div[data-testid="stSidebarUserContent"] hr { margin: 0.6rem 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# SESSION STATE
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
if "trial_used" not in st.session_state:
    st.session_state.trial_used = False
if "user_api_key" not in st.session_state:
    st.session_state.user_api_key = ""
if "last_loaded_file" not in st.session_state:
    st.session_state.last_loaded_file = None


def reset_chat():
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]


def get_trial_key():
    """Ambil API key trial milik developer dari secrets, kalau ada."""
    try:
        return st.secrets["GROQ_API_KEY"]
    except Exception:
        return None


def resolve_api_key():
    """
    Tentukan API key mana yang dipakai untuk request berikutnya.
    Return (api_key, source) dengan source: 'own', 'trial', atau None kalau tidak ada.
    """
    if st.session_state.user_api_key:
        return st.session_state.user_api_key, "own"
    if not st.session_state.trial_used:
        trial_key = get_trial_key()
        if trial_key:
            return trial_key, "trial"
    return None, None


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:
    st.markdown("### Fai — Gaming Companion")
    st.caption("Chatbot rekomendasi game, ditenagai Groq API")

    st.divider()

    trial_available = get_trial_key() is not None

    if st.session_state.user_api_key:
        st.success("Pakai API key kamu sendiri")
    elif st.session_state.trial_used:
        st.warning("Jatah trial gratis sudah dipakai. Masukkan API key kamu di bawah untuk lanjut chat.")
    elif trial_available:
        st.info("Kamu punya 1x chat gratis (trial). Setelah itu, masukkan API key Groq kamu sendiri.")
    else:
        st.warning("Trial belum dikonfigurasi. Masukkan API key Groq kamu untuk mulai chat.")

    with st.expander(
        "Groq API Key kamu",
        expanded=st.session_state.trial_used and not st.session_state.user_api_key,
    ):
        st.markdown(
            "Belum punya? Buat gratis di [console.groq.com/keys](https://console.groq.com/keys)"
        )
        key_input = st.text_input(
            "API Key", type="password", value=st.session_state.user_api_key
        )
        if st.button("Simpan Key", use_container_width=True):
            if key_input.strip():
                st.session_state.user_api_key = key_input.strip()
                st.success("Tersimpan. Lanjut ngobrol yuk.")
                st.rerun()
            else:
                st.error("Key masih kosong.")

    st.divider()

    temperature = st.slider("Temperature (kreativitas jawaban)", 0.0, 1.5, 0.7, 0.1)

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Chat Baru", use_container_width=True):
            reset_chat()
            st.rerun()
    with col2:
        history_for_download = [
            m for m in st.session_state.messages if m["role"] != "system"
        ]
        st.download_button(
            "Simpan",
            data=json.dumps(history_for_download, ensure_ascii=False, indent=2),
            file_name=f"riwayat_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
            disabled=len(history_for_download) == 0,
        )

    uploaded = st.file_uploader("Muat riwayat chat (.json)", type=["json"])
    if uploaded is not None:
        # Identifikasi file lewat nama + ukuran, supaya file yang sama tidak
        # diproses ulang terus-menerus tiap kali halaman rerun (file_uploader
        # tetap menyimpan file di session state selama belum diganti/dihapus).
        file_id = f"{uploaded.name}-{uploaded.size}"
        if file_id != st.session_state.last_loaded_file:
            try:
                loaded = json.load(uploaded)
                if isinstance(loaded, list):
                    st.session_state.messages = [
                        {"role": "system", "content": SYSTEM_PROMPT}
                    ] + loaded
                    st.session_state.last_loaded_file = file_id
                    st.success("Riwayat berhasil dimuat.")
                    st.rerun()
                else:
                    st.error("Format file tidak sesuai (harus berupa list pesan).")
            except Exception:
                st.error("Gagal membaca file JSON.")

    st.divider()

    n_user = sum(1 for m in st.session_state.messages if m["role"] == "user")
    n_assistant = sum(1 for m in st.session_state.messages if m["role"] == "assistant")
    st.caption(f"{n_user} pesan kamu, {n_assistant} balasan Fai")

# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div class="fai-header">
        <h1>Fai</h1>
        <p>Ngobrol bareng Fai buat nemuin game yang pas buat kamu mainkan</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# RENDER RIWAYAT CHAT
# =========================================================

for msg in st.session_state.messages:
    if msg["role"] == "system":
        continue
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Sapaan awal statis (tidak makan jatah trial karena tidak call API)
if len(st.session_state.messages) == 1:
    with st.chat_message("assistant"):
        st.markdown(GREETING)

# =========================================================
# INPUT & LOGIKA CHAT
# =========================================================

prompt = st.chat_input("Ceritain kondisi kamu sekarang, Fai bakal carikan game yang pas...")

if prompt:
    api_key, key_source = resolve_api_key()

    if api_key is None:
        st.error(
            "Trial gratis kamu sudah habis. Masukkan Groq API key kamu sendiri "
            "di sidebar untuk lanjut ngobrol sama Fai."
        )
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""
        error_occurred = False
        try:
            client = Groq(api_key=api_key)
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=st.session_state.messages,
                temperature=temperature,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                full_response += delta
                placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)

        except Exception as e:
            error_occurred = True
            err_text = str(e).lower()
            if "401" in err_text or "invalid_api_key" in err_text or "authentication" in err_text:
                placeholder.error("API key tidak valid. Cek kembali key kamu di sidebar.")
            elif "429" in err_text or "rate_limit" in err_text:
                placeholder.error("Kena rate limit. Coba tunggu sebentar lalu kirim ulang pesan kamu.")
            elif "timeout" in err_text:
                placeholder.error("Koneksi ke Groq API timeout. Coba lagi.")
            else:
                placeholder.error(f"Terjadi error saat menghubungi Groq API: {e}")

    if error_occurred:
        # buang pesan user supaya history tidak rusak
        st.session_state.messages.pop()
        st.stop()

    st.session_state.messages.append({"role": "assistant", "content": full_response})

    if key_source == "trial":
        st.session_state.trial_used = True
        st.rerun()