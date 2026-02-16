import pandas as pd
import numpy as np

# ================= CONFIG =================
INPUT_CSV = "data.csv"
OUTPUT_CSV = "data_for_faiss.csv"

# Your app constants (must match retrieval_service_impl.py)
CODE_COL = "primary_svc_cd"
TYPE_COL = "servc_type"
DESC_COL = "Consumer-Friendly Description"
TITLE_COL = "Consumer-Friendly Title"
CLAIM_COL = "total_claim_count"

# ==========================================

def main():
    df = pd.read_csv(INPUT_CSV)

    print(f"Loaded rows: {len(df)}")

    # --------------------------------------------------
    # 1️⃣ SERVICE CODE COLUMN
    # --------------------------------------------------
    if "Resolved Service Code" in df.columns:
        df[CODE_COL] = (
            df["Resolved Service Code"]
            .astype(str)
            .str.extract(r"(\d{5})")  # extract CPT
        )

    if CODE_COL not in df.columns:
        raise ValueError("❌ Could not create primary_svc_cd column")

    df = df[df[CODE_COL].notna()]

    # --------------------------------------------------
    # 2️⃣ SERVICE TYPE
    # --------------------------------------------------
    df[TYPE_COL] = "CPT"

    # --------------------------------------------------
    # 3️⃣ DESCRIPTION (MOST IMPORTANT)
    # --------------------------------------------------
    if "Ground Truth" in df.columns:
        df[DESC_COL] = df["Ground Truth"].fillna("")
    else:
        df[DESC_COL] = df["User Input"].fillna("")

    df[DESC_COL] = df[DESC_COL].astype(str)

    # --------------------------------------------------
    # 4️⃣ TITLE (SHORT VERSION)
    # --------------------------------------------------
    df[TITLE_COL] = (
        df[DESC_COL]
        .str.slice(0, 80)
        .str.replace("\n", " ")
    )

    # --------------------------------------------------
    # 5️⃣ CLAIM VOLUME (OPTION-2 LOGIC)
    # --------------------------------------------------
    # Frequency of service code in dataset
    claim_volume_map = df[CODE_COL].value_counts().to_dict()
    df[CLAIM_COL] = df[CODE_COL].map(claim_volume_map)

    # Optional smoothing (prevents dominance of single code)
    df[CLAIM_COL] = np.log1p(df[CLAIM_COL]) * 100
    df[CLAIM_COL] = df[CLAIM_COL].astype(int)

    # --------------------------------------------------
    # 6️⃣ REMOVE DUPLICATE EMBEDDINGS
    # --------------------------------------------------
    df = df.drop_duplicates(
        subset=[CODE_COL, DESC_COL]
    )

    # --------------------------------------------------
    # 7️⃣ FINAL CLEANUP
    # --------------------------------------------------
    final_cols = [
        CODE_COL,
        TYPE_COL,
        TITLE_COL,
        DESC_COL,
        CLAIM_COL
    ]

    df_final = df[final_cols].reset_index(drop=True)

    print("Final columns:")
    print(df_final.columns.tolist())
    print("Final rows:", len(df_final))

    df_final.to_csv(OUTPUT_CSV, index=False)
    print(f"\n✅ Clean FAISS-ready file saved as: {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
