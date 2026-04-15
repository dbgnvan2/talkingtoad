# Functional Specification: Image Intelligence & Optimization Engine (Python)

## 1. Objective
To build a Python-based utility that automatically identifies, resizes, compresses, and converts web images into next-gen formats (WebP) to improve PageSpeed Insights scores and Core Web Vitals while maintaining a lean server environment.

## 2. Tech Stack Requirements
* **Language:** Python 3.10+
* **Primary Library:** `Pillow` (PIL Fork) for image processing.
* **Support Libraries:** `os`, `pathlib` for file management; `ImageOps` for advanced cropping.
* **Input:** Local directory path, single image file, or server-side media path.
* **Output:** Optimized `-small.webp` file + Local record + Server cleanup.

## 3. Threshold Detection Logic
To maximize efficiency, the engine only processes files meeting the following "Inclusion Criteria":
* **Size Trigger:** Files > 150KB.
* **Dimension Trigger:** Images with a width > 1920px (Desktop Max).
* **Format Target:** Convert all `JPEG`, `PNG`, and `BMP` to `WebP`.

## 4. The Transformation Pipeline
1. **Initialize:** Load image and convert to `RGBA` to preserve transparency.
2. **Standardize:** Apply proportional resizing or hard cropping (see Section 8).
3. **Optimize:** Save as WebP using `quality=80` and `method=6` (Smart Compression).
4. **Rename:** Append the suffix `-small` to the final filename.

## 5. Feature Requirements: Operations
* **Task 1 (Single):** Optimize one specific file path.
* **Task 2 (Bulk):** Recursively crawl folders, identifying all unoptimized assets.
* **Task 3 (Transparency):** Explicit handling of PNG transparency to prevent "black box" artifacts during WebP conversion.

## 6. Failure Modes & Guardrails
| Potential Failure | Mitigation Logic |
| :--- | :--- |
| **Negative Compression** | If the WebP is larger than the original, discard it and keep the original. |
| **Upscaling** | If target dimensions > current dimensions, skip resizing to prevent pixelation. |
| **Corruption** | Use `try/except` with `PIL.UnidentifiedImageError` to skip non-image files. |

## 7. Implementation Instructions for Agent
* **Step 1:** Use `LANCZOS` resampling for all downscaling (highest quality).
* **Step 2:** Create a class `ImageOptimizer` with modular methods for scalability.
* **Step 3:** Implement a logging system to track `% size reduction` per file.

## 8. Custom Dimension Controls
The engine must support user-defined pixel dimensions:
* **Mode: Scale (Proportional):** Uses `img.thumbnail` to fit the image inside a bounding box without distortion.
* **Mode: Crop (Fixed):** Uses `ImageOps.fit` to center and trim the image to exact dimensions (e.g., 500x500 square).

## 9. Server-Side Cleanup Protocol
* **The "Delete-Original" Rule:** Once the `-small.webp` is verified, the heavy original (e.g., the 3MB .jpg) MUST be deleted from the production server path to free up space.
* **Verification:** Deletion only triggers if `new_file_size > 0`.

## 10. Dual-Destination Saving
The final `-small.webp` file must be saved in two locations simultaneously:
1. **Production Path (Server):** The live directory for the web page link.
2. **Archive Path (Local):** A designated local folder (e.g., `C:/Users/Dave/Optimized_Images/`) for permanent safety and records.
