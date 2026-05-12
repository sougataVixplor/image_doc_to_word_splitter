"""
streamlit_app.py — Bengali Handwritten Word Splitter
Two-mode app: Developer (manage DB) + User (split & map words)
"""

import io
import os
import shutil
import tempfile
import uuid
import zipfile

import pandas as pd
import streamlit as st
from PIL import Image

from db import (
    VALID_CLASSES,
    delete_text,
    extract_words,
    get_all_texts,
    get_text_by_serial,
    insert_text,
    peek_next_serial,
    update_text,
)
from word_splitter import word_splitter

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Bengali Word Splitter",
    page_icon="🔡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d0d1a 0%, #1a1a2e 100%) !important;
    border-right: 1px solid #2a2a4a;
}
[data-testid="stSidebar"] * { color: #c8c8e8 !important; }
[data-testid="stSidebar"] h2 { color: #e94560 !important; font-size:1.2rem !important; }

section[data-testid="stMain"] { background: #0a0a18; color: #e0e0f0; }

h1 { color: #e94560 !important; letter-spacing:-0.5px; }
h2, h3 { color: #89d4f5 !important; }

.stButton > button {
    border-radius: 8px; font-weight: 600;
    transition: all 0.2s ease;
}
.stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(233,69,96,0.3); }

.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {
    background: #12122a !important;
    border: 1px solid #2a2a5a !important;
    color: #e0e0f0 !important;
    border-radius: 8px !important;
}

.word-tag {
    display: inline-block;
    background: #1e3a5f;
    color: #89d4f5;
    border-radius: 16px;
    padding: 3px 10px;
    margin: 2px 2px;
    font-size: 0.82rem;
    font-weight: 600;
}
.serial-badge {
    background: #16213e;
    border: 1px solid #e94560;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 0.9rem;
    color: #e94560;
    font-weight: bold;
}
.step-header {
    background: linear-gradient(90deg, #1e3a5f, #12122a);
    border-left: 4px solid #e94560;
    padding: 10px 16px;
    border-radius: 0 8px 8px 0;
    margin: 12px 0 8px 0;
}
.map-row-wrap {
    background: #0f0f23;
    border: 1px solid #2a2a5a;
    border-radius: 8px;
    padding: 6px 10px;
    margin-bottom: 4px;
}
.stDownloadButton > button {
    background: linear-gradient(135deg, #0f3460, #16213e) !important;
    color: #89d4f5 !important;
    border: 1px solid #0f3460 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    width: 100%;
}
.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #e94560, #c23152) !important;
    color: white !important;
    transform: translateY(-1px);
}
div[data-testid="stExpander"] {
    background: #0f0f23;
    border: 1px solid #2a2a5a;
    border-radius: 10px;
}
.stAlert { border-radius: 8px !important; }
.stSuccess { background: #0d2b1e !important; border-color: #2ecc71 !important; }
.stInfo { background: #0d1b2b !important; border-color: #3498db !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Session state initialisation ──────────────────────────────────────────────
_DEFAULTS: dict = {
    "mode": "User",
    "mapping": [],
    "current_serial": None,
    "last_uploaded_name": None,
    "workspace_dir": None,
    "edit_serial": None,
    "split_done": False,
    "dev_msg": ("", ""),   # (level, text)  level = success|error|info
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

ss = st.session_state

if ss.workspace_dir is None or not os.path.exists(ss.workspace_dir):
    ss.workspace_dir = tempfile.mkdtemp(prefix=f"bws_{uuid.uuid4().hex[:8]}_")


# ── Helper functions ──────────────────────────────────────────────────────────
def make_excel_bytes(mapping: list[dict]) -> bytes:
    rows = [
        {"serial_no": i + 1, "image_file": r["img_name"], "digital_word": r["digital_word"]}
        for i, r in enumerate(mapping)
    ]
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Mapping")
    buf.seek(0)
    return buf.read()


def make_zip_bytes(mapping: list[dict]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in mapping:
            if row["img_bytes"]:
                zf.writestr(row["img_name"], row["img_bytes"])
    buf.seek(0)
    return buf.read()


def word_tags_html(words: list[str]) -> str:
    return " ".join(f'<span class="word-tag">{w}</span>' for w in words)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔡 বাংলা Word Splitter")
    st.markdown("---")
    mode_choice = st.radio(
        "Mode",
        ["🛠️ Developer", "👤 User"],
        index=0 if ss.mode == "Developer" else 1,
        key="mode_radio",
    )
    ss.mode = "Developer" if "Dev" in mode_choice else "User"

    if ss.mode == "User":
        st.markdown("---")
        st.markdown("### 📋 Select Text")
        cls_filter = st.selectbox("Filter by Class", ["ALL"] + VALID_CLASSES, key="u_cls")
        texts = get_all_texts(cls_filter if cls_filter != "ALL" else None)

        if texts:
            labels = [f"#{t['serial']} — {t['paragraph'][:38]}…" for t in texts]
            serials = [t["serial"] for t in texts]
            sel_idx = st.selectbox(
                "Text Entry",
                range(len(labels)),
                format_func=lambda i: labels[i],
                key="u_text_idx",
            )
            chosen_serial = serials[sel_idx]
            if chosen_serial != ss.current_serial:
                ss.current_serial = chosen_serial
                ss.mapping = []
                ss.split_done = False
                ss.last_uploaded_name = None
        else:
            st.info("No entries found for this class.")
            ss.current_serial = None

        st.markdown("---")
        st.caption("Upload a handwritten image in the main panel →")

# ══════════════════════════════════════════════════════════════════════════════
# DEVELOPER MODE
# ══════════════════════════════════════════════════════════════════════════════
if ss.mode == "Developer":
    st.title("🛠️ Developer Panel")
    st.caption("Manage the Bengali text database used for handwritten word labelling.")

    # Show any pending flash message
    if ss.dev_msg[1]:
        lvl, msg = ss.dev_msg
        if lvl == "success":
            st.success(msg)
        elif lvl == "error":
            st.error(msg)
        else:
            st.info(msg)
        ss.dev_msg = ("", "")

    # ── Add / Edit form ───────────────────────────────────────────────────────
    is_editing = ss.edit_serial is not None
    edit_doc = get_text_by_serial(ss.edit_serial) if is_editing else None

    form_title = (
        f"✏️ Editing Entry #{ss.edit_serial}"
        if is_editing
        else f"➕ Add New Entry  (next serial: **#{peek_next_serial()}**)"
    )

    with st.expander(form_title, expanded=True):
        with st.form("dev_form", clear_on_submit=not is_editing):
            col_para, col_cls = st.columns([3, 1])

            with col_para:
                paragraph_val = edit_doc["paragraph"] if edit_doc else ""
                paragraph = st.text_area(
                    "Bengali Paragraph Text",
                    value=paragraph_val,
                    height=150,
                    placeholder="বাংলা অনুচ্ছেদ লিখুন...",
                )

            with col_cls:
                cls_default = VALID_CLASSES.index(edit_doc["class"]) if edit_doc else 0
                cls_choice = st.selectbox("Text Class", VALID_CLASSES, index=cls_default)
                st.markdown("**Word count preview:**")
                if paragraph_val:
                    st.info(f"{len(extract_words(paragraph_val))} words")

            btn_col1, btn_col2 = st.columns(2)
            save_btn = btn_col1.form_submit_button(
                "🔄 Update" if is_editing else "💾 Save",
                use_container_width=True,
                type="primary",
            )
            cancel_btn = btn_col2.form_submit_button("✖ Cancel", use_container_width=True)

            if save_btn:
                if not paragraph.strip():
                    ss.dev_msg = ("error", "Paragraph cannot be empty.")
                elif is_editing:
                    update_text(ss.edit_serial, paragraph.strip(), cls_choice)
                    ss.dev_msg = ("success", f"✅ Entry #{ss.edit_serial} updated!")
                    ss.edit_serial = None
                else:
                    doc = insert_text(cls_choice, paragraph.strip())
                    ss.dev_msg = ("success", f"✅ Entry #{doc['serial']} added — {len(doc['words'])} words stored.")
                st.rerun()

            if cancel_btn:
                ss.edit_serial = None
                st.rerun()

    # ── Records table ─────────────────────────────────────────────────────────
    st.markdown("---")
    col_title, col_filter = st.columns([3, 1])
    col_title.markdown("### 📚 All Entries")
    dev_filter = col_filter.selectbox(
        "Filter", ["ALL"] + VALID_CLASSES, key="dev_cls_filter", label_visibility="collapsed"
    )
    records = get_all_texts(dev_filter if dev_filter != "ALL" else None)

    if not records:
        st.info("No records yet. Use the form above to add Bengali text entries.")
    else:
        st.caption(f"Showing {len(records)} entr{'y' if len(records)==1 else 'ies'}")
        for rec in records:
            with st.container():
                st.markdown('<div class="map-row-wrap">', unsafe_allow_html=True)
                c1, c2, c3, c4, c5, c6 = st.columns([0.7, 1.3, 4.5, 1.3, 0.8, 0.8])
                c1.markdown(
                    f'<span class="serial-badge">#{rec["serial"]}</span>',
                    unsafe_allow_html=True,
                )
                c2.markdown(f"**{rec['class']}**")
                c3.write(rec["paragraph"][:100] + ("…" if len(rec["paragraph"]) > 100 else ""))
                c4.caption(f"🔤 {rec['word_count']} words")

                if c5.button("✏️ Edit", key=f"edit_{rec['serial']}", use_container_width=True):
                    ss.edit_serial = rec["serial"]
                    st.rerun()

                if c6.button("🗑️ Del", key=f"del_{rec['serial']}", use_container_width=True):
                    delete_text(rec["serial"])
                    ss.dev_msg = ("success", f"🗑️ Entry #{rec['serial']} deleted.")
                    st.rerun()

                with st.expander(f"📝 Words for #{rec['serial']}"):
                    st.markdown(word_tags_html(rec["words"]), unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# USER MODE
# ══════════════════════════════════════════════════════════════════════════════
else:
    st.title("👤 Bengali Word Mapper")

    if not ss.current_serial:
        st.info("👈 Select a class and text entry from the sidebar to get started.")
        st.stop()

    text_doc = get_text_by_serial(ss.current_serial)
    if text_doc is None:
        st.error("Selected text not found. Please pick another entry.")
        st.stop()

    # ── Step 1: Text preview ──────────────────────────────────────────────────
    st.markdown('<div class="step-header"><h3 style="margin:0">📖 Step 1 — Selected Text</h3></div>', unsafe_allow_html=True)
    with st.container():
        m1, m2 = st.columns([3, 1])
        m1.markdown(f"**Paragraph #{text_doc['serial']}** &nbsp;`{text_doc['class']}`", unsafe_allow_html=True)
        m2.caption(f"🔤 {text_doc['word_count']} words")
        st.info(text_doc["paragraph"])
        st.markdown(word_tags_html(text_doc["words"]), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Step 2: Upload & Split ────────────────────────────────────────────────
    st.markdown('<div class="step-header"><h3 style="margin:0">📤 Step 2 — Upload Handwritten Image</h3></div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "Upload your handwritten Bengali paragraph image",
        type=["png", "jpg", "jpeg", "tiff", "bmp"],
        key="user_upload",
    )

    if uploaded is not None and uploaded.name != ss.last_uploaded_name:
        ss.last_uploaded_name = uploaded.name
        ss.mapping = []
        ss.split_done = False

        img_save_path = os.path.join(ss.workspace_dir, uploaded.name)
        with open(img_save_path, "wb") as f:
            f.write(uploaded.getbuffer())

        with st.spinner("🔍 Detecting and splitting words into images…"):
            out_folder = word_splitter(img_save_path, output_dir=ss.workspace_dir)

        word_files = sorted(
            ff for ff in os.listdir(out_folder)
            if ff.endswith(".png") and ff.startswith("word_")
        )

        digital_words = text_doc["words"]
        new_mapping = []

        for i, wf in enumerate(word_files):
            with open(os.path.join(out_folder, wf), "rb") as f:
                img_bytes = f.read()
            new_mapping.append({
                "img_name": wf,
                "img_bytes": img_bytes,
                "digital_word": digital_words[i] if i < len(digital_words) else "",
            })

        # Append unmatched digital words as empty image rows
        for j in range(len(word_files), len(digital_words)):
            new_mapping.append({
                "img_name": f"no_image_{j:04d}.png",
                "img_bytes": b"",
                "digital_word": digital_words[j],
            })

        ss.mapping = new_mapping
        ss.split_done = True
        st.rerun()

    if uploaded is not None:
        col_img, col_stat = st.columns([3, 1])
        col_img.image(uploaded, caption="Uploaded image", use_container_width=True)
        if ss.split_done:
            col_stat.success(f"✅ {len(ss.mapping)} word segments mapped")
        else:
            col_stat.info("Processing…")

    # ── Step 3: Mapping Table ─────────────────────────────────────────────────
    if ss.mapping:
        st.markdown('<div class="step-header"><h3 style="margin:0">🗺️ Step 3 — Mapping Table</h3></div>', unsafe_allow_html=True)
        st.caption("Edit the digital word per image, reorder rows, delete noise, or upload a replacement image.")

        # Column headers
        h = st.columns([0.5, 2.2, 2.2, 0.7, 0.6, 0.6, 1.5])
        for col, lbl in zip(h, ["#", "Word Image", "Digital Word", "Delete", "↑", "↓", "Replace Image"]):
            col.markdown(f"**{lbl}**")
        st.divider()

        to_delete = []
        for i, row in enumerate(ss.mapping):
            c = st.columns([0.5, 2.2, 2.2, 0.7, 0.6, 0.6, 1.5])
            c[0].markdown(f"**{i+1}**")

            if row["img_bytes"]:
                try:
                    c[1].image(row["img_bytes"], width=130)
                except Exception:
                    c[1].caption("⚠️ image error")
            else:
                c[1].caption("_(no image)_")

            new_word = c[2].text_input(
                "word", value=row["digital_word"],
                key=f"wrd_{i}", label_visibility="collapsed"
            )
            ss.mapping[i]["digital_word"] = new_word

            if c[3].button("🗑️", key=f"d_{i}", help="Delete this row"):
                to_delete.append(i)

            if i > 0 and c[4].button("⬆", key=f"u_{i}", help="Move up"):
                ss.mapping[i - 1], ss.mapping[i] = ss.mapping[i], ss.mapping[i - 1]
                st.rerun()

            if i < len(ss.mapping) - 1 and c[5].button("⬇", key=f"dn_{i}", help="Move down"):
                ss.mapping[i + 1], ss.mapping[i] = ss.mapping[i], ss.mapping[i + 1]
                st.rerun()

            rep = c[6].file_uploader(
                "rep", type=["png", "jpg", "jpeg", "bmp"],
                key=f"rep_{i}", label_visibility="collapsed"
            )
            if rep is not None:
                ss.mapping[i]["img_bytes"] = rep.read()
                ss.mapping[i]["img_name"] = rep.name
                st.rerun()

        for idx in sorted(to_delete, reverse=True):
            ss.mapping.pop(idx)
        if to_delete:
            st.rerun()

        # ── Manual add ────────────────────────────────────────────────────────
        st.markdown("---")
        with st.expander("➕ Add Manual Word Image"):
            a1, a2, a3 = st.columns([2, 2, 1])
            manual_img = a1.file_uploader(
                "Word image file", type=["png", "jpg", "jpeg", "bmp"],
                key="add_img", label_visibility="visible"
            )
            manual_word = a2.text_input("Digital word", key="add_word", placeholder="বাংলা শব্দ")
            a3.markdown("<br>", unsafe_allow_html=True)
            if a3.button("➕ Add", use_container_width=True, type="primary") and manual_img:
                ss.mapping.append({
                    "img_name": manual_img.name,
                    "img_bytes": manual_img.read(),
                    "digital_word": manual_word,
                })
                st.rerun()

        # ── Step 4: Export ────────────────────────────────────────────────────
        st.markdown('<div class="step-header"><h3 style="margin:0">💾 Step 4 — Export</h3></div>', unsafe_allow_html=True)
        st.caption(f"{len(ss.mapping)} mapped pairs ready for download.")

        e1, e2 = st.columns(2)
        e1.download_button(
            label="📊 Download Excel Mapping",
            data=make_excel_bytes(ss.mapping),
            file_name=f"mapping_serial_{ss.current_serial}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        e2.download_button(
            label="📦 Download Word Images (ZIP)",
            data=make_zip_bytes(ss.mapping),
            file_name=f"words_serial_{ss.current_serial}.zip",
            mime="application/zip",
            use_container_width=True,
        )
