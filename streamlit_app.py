import streamlit as st
import os
import shutil
import fitz  # PyMuPDF
from PIL import Image
import io
import zipfile
import uuid
import tempfile
from word_splitter import word_splitter

st.set_page_config(page_title="Word Splitter", page_icon="✂️", layout="centered")

def cleanup():
    """Clean all previous data when new file uploads."""
    # Remove tracked generated folders
    if "generated_folders" in st.session_state:
        for folder in st.session_state.generated_folders:
            if os.path.exists(folder):
                shutil.rmtree(folder)
        st.session_state.generated_folders = []

    # Clean the current session's workspace directory
    workspace_dir = st.session_state.get("workspace_dir")
    if workspace_dir and os.path.exists(workspace_dir):
        for filename in os.listdir(workspace_dir):
            file_path = os.path.join(workspace_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                pass

# Initialize session state
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "workspace_dir" not in st.session_state:
    st.session_state.workspace_dir = tempfile.mkdtemp(prefix=f"workspace_{st.session_state.session_id}_")

if "generated_folders" not in st.session_state:
    st.session_state.generated_folders = []

if "download_data" not in st.session_state:
    st.session_state.download_data = []

st.title("📄 Image & PDF Word Splitter")
st.markdown("Upload a PDF or an image to split it into individual words. All data is cleaned up automatically on new upload.")

uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg", "tiff", "bmp"])

if uploaded_file is not None:
    # Check if a new file is uploaded
    if st.session_state.get("last_uploaded") != uploaded_file.name:
        cleanup()
        st.session_state.last_uploaded = uploaded_file.name
        st.session_state.download_data = []
        
        file_ext = uploaded_file.name.split(".")[-1].lower()
        
        with st.spinner("Processing file..."):
            if file_ext == "pdf":
                # Handle PDF
                st.info("PDF detected. Converting pages to images...")
                pdf_bytes = uploaded_file.read()
                doc = fitz.open("pdf", pdf_bytes)
                
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    pix = page.get_pixmap(dpi=300) # Use higher dpi for better quality
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # Save temporary image
                    base_name = f"{uploaded_file.name.replace('.pdf', '')}_page_{page_num+1}"
                    img_path = os.path.join(st.session_state.workspace_dir, f"{base_name}.png")
                    img.save(img_path)
                    
                    # Process with word_splitter
                    folder_name = word_splitter(img_path, output_dir=st.session_state.workspace_dir)
                    if folder_name not in st.session_state.generated_folders:
                        st.session_state.generated_folders.append(folder_name)
                        
                st.success(f"Processed {len(doc)} pages from PDF!")
                
            else:
                # Handle Image
                st.info("Image detected. Processing...")
                img_path = os.path.join(st.session_state.workspace_dir, uploaded_file.name)
                with open(img_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                    
                folder_name = word_splitter(img_path, output_dir=st.session_state.workspace_dir)
                if folder_name not in st.session_state.generated_folders:
                    st.session_state.generated_folders.append(folder_name)
                    
                st.success("Image processing complete!")
                
            # Prepare multiple ZIP file downloads (also single zip if 1 folder)
            for folder in st.session_state.generated_folders:
                if os.path.exists(folder):
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for root, dirs, files in os.walk(folder):
                            for file in files:
                                file_path = os.path.join(root, file)
                                zip_file.write(file_path, os.path.relpath(file_path, folder))
                    zip_buffer.seek(0)
                    folder_base_name = os.path.basename(folder)
                    st.session_state.download_data.append((f"{folder_base_name}.zip", zip_buffer.getvalue()))
                    
if st.session_state.get("download_data"):
    st.markdown("### 📥 Download Results")
    st.markdown("Download the extracted word images and Excel output below.")
    
    for name, data in st.session_state.download_data:
        st.download_button(
            label=f"Download {name}",
            data=data,
            file_name=name,
            mime="application/zip",
            key=f"download_{name}" # ensure unique key for multiple buttons
        )
