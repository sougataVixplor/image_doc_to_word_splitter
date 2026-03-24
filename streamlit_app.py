import streamlit as st
import os
import shutil
import fitz  # PyMuPDF
from PIL import Image
import io
import zipfile
from word_splitter import word_splitter

# Constants
UPLOAD_DIR = "uploaded_files"

st.set_page_config(page_title="Word Splitter", page_icon="✂️", layout="centered")

def cleanup():
    """Clean all previous data when new file uploads."""
    # Remove tracked generated folders
    if "generated_folders" in st.session_state:
        for folder in st.session_state.generated_folders:
            if os.path.exists(folder):
                shutil.rmtree(folder)
        st.session_state.generated_folders = []

    # Clean upload directory
    if os.path.exists(UPLOAD_DIR):
        shutil.rmtree(UPLOAD_DIR)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# Initialize session state
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
                    img_path = os.path.join(UPLOAD_DIR, f"{base_name}.png")
                    img.save(img_path)
                    
                    # Process with word_splitter
                    folder_name = word_splitter(img_path)
                    if folder_name not in st.session_state.generated_folders:
                        st.session_state.generated_folders.append(folder_name)
                        
                st.success(f"Processed {len(doc)} pages from PDF!")
                
            else:
                # Handle Image
                st.info("Image detected. Processing...")
                img_path = os.path.join(UPLOAD_DIR, uploaded_file.name)
                with open(img_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                    
                folder_name = word_splitter(img_path)
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
                    st.session_state.download_data.append((f"{folder}.zip", zip_buffer.getvalue()))
                    
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
