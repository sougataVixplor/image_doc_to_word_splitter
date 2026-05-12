import cv2
import numpy as np
import os
import pandas as pd


def word_splitter(image_path, output_dir=None):
    # get file name without extension (cross-platform safe)
    file_name = os.path.splitext(os.path.basename(image_path))[0]

    if output_dir is None:
        output_dir = "."
    out_folder = os.path.join(output_dir, file_name)
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # --- Step 1: Binarize using adaptive thresholding ---
    # More robust than Canny for text — handles varying illumination and
    # preserves small strokes like the dot in Bengali "র".
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=15,
        C=10
    )

    # --- Step 2: Light denoising — remove isolated tiny specks (noise) ---
    # Erode then dilate (opening) kills lone pixels that are too small to be
    # part of any character stroke.
    noise_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, noise_kernel, iterations=1)

    # --- Step 3: Dilate to merge characters into word blobs ---
    # Kernel is wider (horizontal merge) and taller (30px) so that diacritics
    # / dots that sit below or above the base glyph (e.g. the dot in "র") are
    # joined to the main character body before we find contours.
    word_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 8))
    dilated = cv2.dilate(binary, word_kernel, iterations=1)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    os.makedirs(out_folder, exist_ok=True)

    h_img, w_img = img.shape[:2]
    img_area = h_img * w_img

    # Derive a reasonable minimum character height from the image dimensions.
    # Words should be at least ~1 % of image height and at most 95 %.
    min_h = max(10, int(h_img * 0.01))
    min_w = max(10, int(w_img * 0.005))
    min_area = min_h * min_w

    # Collect valid bounding boxes first
    valid_boxes = []

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)

        # --- Noise filters ---

        # 1. Minimum size: both width and height must be reasonable
        if w < min_w or h < min_h:
            continue

        # 2. Minimum area: avoids tiny diagonal line artifacts
        if w * h < min_area:
            continue

        # 3. Aspect-ratio guard: a contour that is extremely wide relative to
        #    its height is likely a horizontal rule / underline, not a word.
        aspect = w / h
        if aspect > 30:
            continue

        # 4. Relative-size guard: a contour covering most of the image is
        #    likely a border or a full-page artefact.
        if (w * h) > 0.8 * img_area:
            continue

        pad = 5
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(w_img, x + w + pad)
        y2 = min(h_img, y + h + pad)

        crop = img[y1:y2, x1:x2]

        if crop.size == 0:
            continue

        # --- Content-quality filters on the crop ---
        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

        # 5. Variance check: a near-uniform (dark or light) patch has very low
        #    std-dev — it's background/shadow noise, not actual text.
        #    Real character strokes produce a spread of pixel intensities.
        std_dev = float(np.std(crop_gray))
        if std_dev < 8.0:
            continue

        # 6. Ink-density check: binarize the crop and measure what fraction of
        #    pixels are "ink" (dark).  Genuine words sit in the 1–60 % range.
        #    Below 1 % -> almost blank; above 60 % -> fully filled artefact.
        _, crop_bin = cv2.threshold(crop_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        ink_ratio = float(np.count_nonzero(crop_bin)) / crop_bin.size
        if ink_ratio < 0.01 or ink_ratio > 0.60:
            continue

        valid_boxes.append((x1, y1, x2, y2, crop))

    # --- Step 4: Sort boxes in reading order (top-to-bottom, left-to-right) ---
    # Group words into "lines" by clustering on their vertical centre.
    # Words whose centres are within (line_tolerance) pixels of each other
    # are considered to be on the same line, then sorted left-to-right.
    if valid_boxes:
        line_tolerance = max(20, int(h_img * 0.04))

        def reading_order_key(box):
            bx1, by1, bx2, by2, _ = box
            cy = (by1 + by2) // 2          # vertical centre
            # Snap cy to the nearest line band
            band = round(cy / line_tolerance)
            return (band, bx1)            # primary: band (top->bottom), secondary: x (left->right)

        valid_boxes.sort(key=reading_order_key)

    image_list = []
    for i, (x1, y1, x2, y2, crop) in enumerate(valid_boxes):
        fname = f"word_{i:04d}.png"
        cv2.imwrite(os.path.join(out_folder, fname), crop)
        image_list.append(
            {
                "file_name": file_name,
                "image": fname,
                "text": "",
                "score": "",
            }
        )

    print("Saved", len(image_list), "word images")
    df = pd.DataFrame.from_dict(image_list)
    df.to_excel(os.path.join(out_folder, "output.xlsx"))
    return out_folder