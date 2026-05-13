"""
PyTorch Dataset wrapping Stage 05's tokenized Parquet outputs.

Loads a tokenized split lazily by row index. Each item is a dict
{input_ids, attention_mask, labels} ready for the HuggingFace
training Trainer.

The dataset never re-tokenizes — it consumes what Stage 05 produced,
which is the point of having Stage 05 (D58: no padding at tokenize
time means dynamic padding per batch in the training dataloader,
applied via the HF DataCollatorWithPadding).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import Dataset


class TokenizedDataset(Dataset):
    """
    Stage 05 tokenized Parquet → PyTorch Dataset.

    Parameters
    ----------
    parquet_path : Path
        Path to one of the Stage 05 outputs (e.g., train.parquet).

    Notes
    -----
    * The whole Parquet is read once at construction and held in
      memory as a DataFrame. At our scale (max 14,846 rows in train,
      with token lists averaging 291 tokens) this is well under
      500 MB and far cheaper than mmap.
    * Items are returned as dicts of `torch.long` tensors. The HF
      DataCollator handles padding at batch time.
    * `labels` is renamed from Stage 05's `label` column to match
      HuggingFace's expected field name.
    """

    def __init__(self, parquet_path: Path):
        self.path = Path(parquet_path)
        if not self.path.exists():
            raise FileNotFoundError(f"Tokenized split missing: {self.path}")

        self.df = pd.read_parquet(self.path).reset_index(drop=True)
        if len(self.df) == 0:
            raise ValueError(
                f"Tokenized split {self.path.name} is empty. "
                f"Stage 05 should never write empty Parquets."
            )

        # Sanity check on the columns the dataset will use
        required = {"input_ids", "attention_mask", "label"}
        missing = required - set(self.df.columns)
        if missing:
            raise ValueError(
                f"Tokenized split {self.path.name} is missing columns: "
                f"{sorted(missing)}. Re-run Stage 05."
            )

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        row = self.df.iloc[idx]
        # input_ids and attention_mask are stored as Parquet lists;
        # pyarrow gives us numpy arrays back, which torch.as_tensor
        # handles natively.
        return {
            "input_ids": torch.as_tensor(row["input_ids"], dtype=torch.long),
            "attention_mask": torch.as_tensor(
                row["attention_mask"], dtype=torch.long
            ),
            "labels": torch.as_tensor(row["label"], dtype=torch.long),
        }
