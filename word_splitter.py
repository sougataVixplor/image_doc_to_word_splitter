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

    gray = cv2.GaussianBlur(gray,(5,5),0)

    edges = cv2.Canny(gray,50,150)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(20,5))
    dilated = cv2.dilate(edges,kernel,iterations=1)

    contours,_ = cv2.findContours(dilated,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

    os.makedirs(out_folder, exist_ok=True)

    h_img, w_img = img.shape[:2]

    i = 0

    for c in contours:

        x,y,w,h = cv2.boundingRect(c)

        if w>15 and h>15:

            pad = 5

            x1 = max(0, x-pad)
            y1 = max(0, y-pad)
            x2 = min(w_img, x+w+pad)
            y2 = min(h_img, y+h+pad)

            crop = img[y1:y2, x1:x2]

            if crop.size > 0:
                cv2.imwrite(os.path.join(out_folder, f"word_{i}.png"), crop)
                i += 1

    print("Saved",i,"word images")
    images=os.listdir(out_folder)
    image_list=[]
    for f in images:
        image_list.append(
            {
                "file_name":file_name,
                "image":f,
                "text":"",
                "score":""
            }
        )
    df=pd.DataFrame.from_dict(
        image_list
    )
    df.to_excel(
        os.path.join(out_folder, "output.xlsx")
    )
    return out_folder