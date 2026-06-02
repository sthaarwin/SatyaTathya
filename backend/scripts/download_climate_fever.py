import argparse
import json
import os

from datasets import load_dataset


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = {
    0: "SUPPORT",
    1: "CONTRADICT",
    2: "INDETERMINATE",
    "supports": "SUPPORT",
    "refutes": "CONTRADICT",
    "not enough info": "INDETERMINATE",
}


def normalize_label(label) -> str:
    if isinstance(label, int):
        return LABELS.get(label, str(label))
    return LABELS.get(str(label).strip().lower(), str(label).strip().upper())


def export_split(dataset, split: str, output_dir: str) -> int:
    path = os.path.join(output_dir, f"{split}.jsonl")
    count = 0
    with open(path, "w") as output_file:
        for row in dataset[split]:
            record = {
                "claim_id": row.get("claim_id"),
                "claim": row.get("claim", ""),
                "evidence": row.get("evidence", ""),
                "label": normalize_label(row.get("label")),
                "category": row.get("category", ""),
            }
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Download Climate-FEVER fixed into backend/data for local experiments.")
    parser.add_argument("--dataset", default="rexarski/climate_fever_fixed")
    parser.add_argument("--output-dir", default=os.path.join(BACKEND_DIR, "data", "climate_fever"))
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    dataset = load_dataset(args.dataset)

    metadata = {
        "dataset": args.dataset,
        "splits": {},
        "labels": ["SUPPORT", "CONTRADICT", "INDETERMINATE"],
    }
    for split in dataset:
        metadata["splits"][split] = export_split(dataset, split, args.output_dir)

    metadata_path = os.path.join(args.output_dir, "metadata.json")
    with open(metadata_path, "w") as metadata_file:
        json.dump(metadata, metadata_file, indent=2)

    print(f"Saved Climate-FEVER data to {args.output_dir}")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
