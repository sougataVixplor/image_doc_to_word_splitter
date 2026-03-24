# 📄 Image & PDF Word Splitter

A modern, Streamlit-based application designed to automatically split scanned documents—both images and PDFs—into individual word crops using OpenCV contour detection.

This app features a clean, interactive UI for processing single images or multi-page PDFs, and seamlessly packages the output crops alongside tracking metadata (Excel) into ZIP files for easy downloading.

---

## 🚀 Key Features

- **Multi-Format Uploads:** Accepts `PDF`, `PNG`, `JPG`, `JPEG`, `TIFF`, and `BMP` files.
- **PDF Handling:** Automatically extracts and converts multi-page PDFs into high-quality images (300 DPI) using `PyMuPDF`.
- **Intelligent Splitting:** Employs OpenCV blurring, canny edge detection, and dilation to isolate and extract text blocks and individual words reliably.
- **Session Based Cleanup:** Automatically dynamically wipes previously processed files and memory when new files are uploaded, keeping your system clutter-free.
- **Instant Packaging:** Generates downloadable `.zip` archives containing your word crops and an organized `.xlsx` mapping document per page processed.

---

## 🛠️ Installation & Setup

Follow these simple steps to get the application running locally:

**1. Install Requirements**  
Ensure you have Python installed, then install the necessary dependencies:
```bash
pip install -r requirements.txt
```

**2. Open Command Prompt / Terminal**  
Navigate to the root folder of this project where the files are saved.

**3. Run the Application**  
Launch the Streamlit server using the following command:
```bash
streamlit run streamlit_app.py
```

**4. Usage**  
- Access the local Streamlit URL provided in the terminal (usually `http://localhost:8501`).
- Upload any supported image or PDF file through the web UI.
- Allow the automated processing to complete.
- Download the bundled `.zip` outputs containing your cropped words and Excel data!

---

## 📦 Dependencies

The application relies on these primary libraries (see `requirements.txt`):
- `streamlit` (UI & Web App)
- `PyMuPDF` (PDF parsing and reading)
- `Pillow` (Image memory handling)
- `opencv-python-headless` (Computer Vision for text bounding)
- `numpy`, `pandas`, `openpyxl` (Data and Excel handling)
