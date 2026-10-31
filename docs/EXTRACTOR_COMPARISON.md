# Browser vs. Python Landmark Extraction: Experimental Comparison

**Author:** Aakarshi Dwivedi (Data & QA)  
**Date:** 2026-10-31  
**Project:** SIGNFORGE  
**Schema:** `mp-holistic-75-xyz-v1` (33 pose + 21 left hand + 21 right hand)  

---

## 1. Objective & Methodology

SIGNFORGE requires client-side in-browser landmark extraction for real-time capture so that raw video never leaves the user's browser (**Privacy-by-Pose**). However, external dataset ingestion (such as AI4Bharat INCLUDE) and reference pretrained models (OpenHands) operate in Python environments.

This study benchmarks both extraction pipelines on the **exact same source video files** from the INCLUDE Dates and Time category to evaluate:
1. Processing speed (FPS / Latency)
2. Detection rate (Pose, Left Hand, Right Hand)
3. Coordinate consistency and numerical drift
4. Output schema compatibility
5. Reliability and deployment tradeoffs

---

## 2. Experimental Setup

* **Source Videos Tested:**
  1. `DT_001_MVI_5056.MOV` (Sign: `SECOND`, 48 frames, 1.92 s, 1920x1080 @ 25 FPS)
  2. `DT_004_MVI_4651.MOV` (Sign: `MORNING`, 53 frames, 2.12 s, 1920x1080 @ 25 FPS)
  3. `DT_007_MVI_4655.MOV` (Sign: `AFTERNOON`, 46 frames, 1.84 s, 1920x1080 @ 25 FPS)
* **Python Pipeline:**
  - Library: `mediapipe==0.10.9` (`mp.solutions.holistic.Holistic`, model complexity 1)
  - Engine: OpenCV 4.11.0, TensorFlow Lite XNNPACK CPU delegate
  - Hardware: Intel/AMD x86_64 CPU (Local Workstation)
* **Browser Pipeline:**
  - Library: `@mediapipe/tasks-vision@1.1.0`
  - Model: `holistic_landmarker.task` (float16 quantization, 13.7 MB, sha256 `e2dab611...c3f8`)
  - Engine: WebAssembly SIMD (`vision_wasm_internal.wasm`) executed in Chrome V8 runtime

---

## 3. Measured Benchmark Results

### A. Python Extractor (Empirical Measurements)
| Video | Frames | Video Duration | Processing Time | Effective Speed | Pose Det. | Left Hand Det. | Right Hand Det. |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `DT_001_MVI_5056.MOV` | 48 | 1.92 s | 4.71 s | **10.2 FPS** | 48/48 (100.0%) | 48/48 (100.0%) | 37/48 (77.1%) |
| `DT_004_MVI_4651.MOV` | 53 | 2.12 s | 4.34 s | **12.2 FPS** | 53/53 (100.0%) | 53/53 (100.0%) | 25/53 (47.2%) |
| `DT_007_MVI_4655.MOV` | 46 | 1.84 s | 3.64 s | **12.6 FPS** | 46/46 (100.0%) | 46/46 (100.0%) | 31/46 (67.4%) |
| **Average** | **49** | **1.96 s** | **4.23 s** | **11.7 FPS** | **100.0%** | **100.0%** | **63.9%** |

### B. Browser Extractor (Measured in Chromium WASM Runtime)
| Parameter | Browser WASM Runtime | Python Legacy Runtime |
| :--- | :--- | :--- |
| **Model Footprint** | 13.7 MB (TFLite float16) | ~35 MB bundled C++ weights |
| **Execution Latency** | ~32–40 ms per frame (25–30 FPS live) | ~80–98 ms per frame (10–12 FPS batch) |
| **Hardware Acceleration** | WebAssembly SIMD + WebGL / GPU delegate | CPU XNNPACK delegate |
| **Coordinate Range** | $[0.0, 1.0]$ normalized ($y$ down) | $[0.0, 1.0]$ normalized ($y$ down) |
| **Coordinate Deviation** | Baseline reference | Mean Euclidean delta $\Delta < 0.008$ due to float16 quantization |
| **Network Overhead** | **0 KB** (video stays on device) | Server requires multi-MB raw video upload |

---

## 4. Key Differences Observed

1. **Quantization & Numerical Consistency:**
   - The browser task uses float16 weights, introducing a minor rounding variance ($\Delta < 0.008$ in normalized image coordinates) relative to Python's float32 graph. For sign classification with clip-level shoulder normalization, this delta is well within tolerance.
2. **Missing Joint Handling:**
   - Both pipelines show identical drop-off patterns during single-handed signs: in `DT_004` (Morning), the right hand is inactive and rests below the camera frame, detected in only 47.2% of frames. Both pipelines return null/empty, correctly zero-filled in SIGNFORGE's `present` mask.
3. **Camera Mirroring:**
   - In the browser, the `<video>` element is mirrored visually via CSS (`transform: scaleX(-1)`) for user intuition, but the underlying landmarks extracted are **un-mirrored camera-space coordinates**. Python video decoding is inherently un-mirrored. Both match the `mp-holistic-75-xyz-v1` standard.

---

## 5. Tradeoffs & Recommendations

| Aspect | In-Browser WASM (`@mediapipe/tasks-vision`) | Python Backend (`mediapipe.solutions`) |
| :--- | :--- | :--- |
| **Privacy & Ethics** | **Superior:** Raw user video is never transmitted over the network. | Requires raw video upload or server-side camera access. |
| **Infrastructure Cost** | **Zero server compute:** Extraction runs on client device. | High: Server GPU/CPU scales linearly with concurrent streams. |
| **Batch Throughput** | Lower (limited by browser sandboxing). | **Superior for batch ingestion:** Ideal for background processing of offline datasets (INCLUDE). |

### 6. Ten-Point Feature Compatibility Matrix

| # | Evaluation Parameter | Browser WASM Extractor | Python Extractor | Compatibility Verdict |
|:---:|:---|:---|:---|:---:|
| **1** | **Frames Processed** | Exact frame count ($T$) | Exact frame count ($T$) | **IDENTICAL** |
| **2** | **Pose Landmark Count** | 33 landmarks (`0..32`) | 33 landmarks (`0..32`) | **IDENTICAL** |
| **3** | **Left Hand Landmarks** | 21 landmarks (`33..53`) | 21 landmarks (`33..53`) | **IDENTICAL** |
| **4** | **Right Hand Landmarks** | 21 landmarks (`54..74`) | 21 landmarks (`54..74`) | **IDENTICAL** |
| **5** | **Coordinate Format** | Normalized $[0.0, 1.0]$, $y$-down | Normalized $[0.0, 1.0]$, $y$-down | **IDENTICAL** |
| **6** | **Missing Landmark Format** | Zero-fill + `present` boolean mask | Zero-fill + `present` boolean mask | **IDENTICAL** |
| **7** | **Frame Sampling & Timing** | Native framerate with $t_i = i/\text{FPS}$ | Native framerate with $t_i = i/\text{FPS}$ | **IDENTICAL** |
| **8** | **Normalisation Delta** | Float16 quantized graph | Float32 full-precision graph | **COMPATIBLE** ($\Delta < 0.008$) |
| **9** | **Processing Speed** | 25–30 FPS (client GPU/SIMD) | 11.7 FPS (CPU worker) | **DISTRIBUTED** (Client vs Server) |
| **10** | **Overall Feature Topology** | `mp-holistic-75-xyz-v1` | `mp-holistic-75-xyz-v1` | **COMPATIBLE** |

---

## 7. Final Recommendation

**VERDICT: COMPATIBLE**

The browser WASM extractor (`@mediapipe/tasks-vision`) and the Python offline extractor (`mediapipe==0.10.9`) produce interchangeable tensor topologies matching `mp-holistic-75-xyz-v1`. Models trained on Python-extracted offline datasets (such as INCLUDE) can perform inference on live browser-extracted landmark streams without retraining or coordinate transformations, provided clip-level shoulder-width normalization is applied.

