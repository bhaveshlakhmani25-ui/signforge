# INCLUDE Dataset Inspection Report (All 3 Category Archives)

**Author:** Aakarshi Dwivedi (Data, QA & Evaluation)  
**Date:** 2026-10-31  
**Project:** SIGNFORGE  
**Dataset:** INCLUDE: A Large Scale Dataset for Indian Sign Language Recognition (Zenodo `4010759`)  
**Scope:** Complete "Days and Time" Category (Parts 1, 2, and 3)  

---

## 1. Archives Inventory & Storage Requirements

Zenodo splits the complete "Days and Time" category into three sequential zip archives. All three archives have been downloaded locally and verified:

| Archive Filename | Absolute Path | File Size | Entries | Videos | Status |
|:---|:---|:---:|:---:|:---:|:---:|
| `Days_and_Time_1of3.zip` | `C:\Users\Renu Dwivedi\Desktop\hackathon\dataset\Days_and_Time_1of3.zip` | 1,244,115,203 B (1,186.48 MB) | 121 | 112 | Verified Intact |
| `Days_and_Time_2of3.zip` | `C:\Users\Renu Dwivedi\Desktop\hackathon\dataset\Days_and_Time_2of3.zip` | 1,016,797,379 B (969.69 MB) | 107 | 99 | Verified Intact |
| `Days_and_Time_3of3.zip` | `C:\Users\Renu Dwivedi\Desktop\hackathon\dataset\Days_and_Time_3of3.zip` | 852,955,661 B (813.44 MB) | 94 | 87 | Verified Intact |
| **Total Downloaded** | — | **3,113,868,243 B (~2.90 GB)** | **322** | **298** | **0 corrupt files** |

* **Storage Footprint:**
  - Downloaded ZIP archives: **2.90 GB**
  - Potential full uncompressed video storage (if all 298 videos were extracted): ~3.4 GB
  - Selective extraction policy: We extract **only ~10–20 signs** (3 clips each), consuming less than **500 MB** of local disk space.
* **Format:** QuickTime Movie (`.MOV`), H.264 video codec, 1920×1080 resolution at 25.0 FPS.

---

## 2. Comprehensive Sign & Video Inventory Across All 3 ZIPs

### Archive 1: `Days_and_Time_1of3.zip` (Part 1 of 3 — Signs 66 to 73)
| Sign Index & Folder | Canonical Gloss | Videos Available | Format | Sample Filename |
|:---|:---|:---:|:---:|:---|
| `66. Sunday` | `SUNDAY` | 14 | `.MOV` | `MVI_4591.MOV` |
| `67. Monday` | `MONDAY` | 14 | `.MOV` | `MVI_4595.MOV` |
| `68. Tuesday` | `TUESDAY` | 14 | `.MOV` | `MVI_4599.MOV` |
| `69. Wednesday` | `WEDNESDAY` | 14 | `.MOV` | `MVI_4603.MOV` |
| `70. Thursday` | `THURSDAY` | 14 | `.MOV` | `MVI_4607.MOV` |
| `71. Friday` | `FRIDAY` | 14 | `.MOV` | `MVI_4611.MOV` |
| `72. Saturday` | `SATURDAY` | 14 | `.MOV` | `MVI_4615.MOV` |
| `73. Today` | `TODAY` | 14 | `.MOV` | `MVI_4617.MOV` |
| **Subtotal Part 1** | **8 signs** | **112 videos** | — | — |

### Archive 2: `Days_and_Time_2of3.zip` (Part 2 of 3 — Signs 74 to 80)
| Sign Index & Folder | Canonical Gloss | Videos Available | Format | Sample Filename |
|:---|:---|:---:|:---:|:---|
| `74. Tomorrow` | `TOMORROW` | 14 | `.MOV` | `MVI_4619.MOV` |
| `75. Yesterday` | `YESTERDAY` | 14 | `.MOV` | `MVI_4623.MOV` |
| `76. Week` | `WEEK` | 14 | `.MOV` | `MVI_4627.MOV` |
| `77. Month` | `MONTH` | 14 | `.MOV` | `MVI_4631.MOV` |
| `78. Year` | `YEAR` | 15 | `.MOV` | `MVI_4635.MOV` |
| `79. Hour` | `HOUR` | 14 | `.MOV` | `MVI_4639.MOV` |
| `80. Minute` | `MINUTE` | 14 | `.MOV` | `MVI_4643.MOV` |
| **Subtotal Part 2** | **7 signs** | **99 videos** | — | — |

### Archive 3: `Days_and_Time_3of3.zip` (Part 3 of 3 — Signs 81 to 86)
| Sign Index & Folder | Canonical Gloss | Videos Available | Format | Sample Filename |
|:---|:---|:---:|:---:|:---|
| `81. Second` | `SECOND` | 15 | `.MOV` | `MVI_5056.MOV` |
| `82. Morning` | `MORNING` | 14 | `.MOV` | `MVI_4651.MOV` |
| `83. Afternoon` | `AFTERNOON` | 14 | `.MOV` | `MVI_4655.MOV` |
| `84. Evening` | `EVENING` | 14 | `.MOV` | `MVI_4659.MOV` |
| `85. Night` | `NIGHT` | 15 | `.MOV` | `MVI_4663.MOV` |
| `86. Time` | `TIME` | 15 | `.MOV` | `MVI_4667.MOV` |
| **Subtotal Part 3** | **6 signs** | **87 videos** | — | — |

---

## 3. Overlap & Duplicate Analysis Across ZIP Archives

We cross-referenced every single video filename across all three archives:
* **Duplicate Video Filenames:** **0 duplicates detected**. Each video filename is unique across the entire dataset (e.g. `MVI_4591.MOV` through `MVI_5058.MOV`).
* **Overlapping Glosses:** **0 overlapping signs**. The three archives partition signs 66 to 86 into mutually exclusive, strictly sequential ranges:
  - Part 1: Days of the week (`Sunday` .. `Saturday`) + `Today` (Signs 66–73)
  - Part 2: Calendar & relative periods (`Tomorrow`, `Yesterday`, `Week`, `Month`, `Year`, `Hour`, `Minute`) (Signs 74–80)
  - Part 3: Times of day (`Second`, `Morning`, `Afternoon`, `Evening`, `Night`, `Time`) (Signs 81–86)

---

## 4. Subset Selection for SIGNFORGE (10–20 Signs Limit)

To comply with the rule to *"Select only 10–20 signs for the initial SIGNFORGE experiment"* and avoid extracting all 298 videos:

### Selected Subset: **15 Signs** (45 video clips total, 3 clips per sign)
1. From Part 1:
   - `TODAY` (3 clips)
   - `SUNDAY` (3 clips)
2. From Part 2:
   - `TOMORROW` (3 clips)
   - `YESTERDAY` (3 clips)
   - `WEEK` (3 clips)
   - `MONTH` (3 clips)
   - `YEAR` (3 clips)
   - `HOUR` (3 clips)
   - `MINUTE` (3 clips)
3. From Part 3:
   - `SECOND` (3 clips)
   - `MORNING` (3 clips)
   - `AFTERNOON` (3 clips)
   - `EVENING` (3 clips)
   - `NIGHT` (3 clips)
   - `TIME` (3 clips)

This selection spans all 3 downloaded archives while staying inside the 10–20 signs constraint.
