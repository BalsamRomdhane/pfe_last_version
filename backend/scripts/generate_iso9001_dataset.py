#!/usr/bin/env python3
"""
Generate synthetic ISO 9001 compliance dataset for ML training.

This script creates a balanced dataset of document samples with different
compliance levels (good, medium, bad) based on 10 ISO 9001 rules.
"""

import json
import random
from typing import List, Dict, Any
from pathlib import Path


# Fixed order of ISO 9001 rules (must remain consistent)
RULES = [
    "Identification du document",
    "Version du document",
    "Approbation du document",
    "Lisibilité et format",
    "Contrôle des modifications",
    "Accessibilité",
    "Protection du document",
    "Archivage",
    "Validité du contenu",
    "Signature ou validation officielle"
]


def generate_sample(sample_type: str) -> Dict[str, Any]:
    """
    Generate a single document sample based on compliance type.

    Args:
        sample_type: 'good', 'medium', or 'bad'

    Returns:
        Dictionary with features, score, label, and type
    """
    # Base probabilities for each rule based on document type
    base_probs = {
        'good': 0.95,    # 95% chance of compliance per rule
        'medium': 0.70,  # 70% chance
        'bad': 0.30      # 30% chance
    }

    base_prob = base_probs[sample_type]

    # Add realistic noise: vary probability slightly per sample
    # Good docs: 90-100%, Medium: 60-80%, Bad: 20-40%
    noise_range = {
        'good': (0.90, 1.00),
        'medium': (0.60, 0.80),
        'bad': (0.20, 0.40)
    }

    min_prob, max_prob = noise_range[sample_type]
    actual_prob = random.uniform(min_prob, max_prob)

    # Generate features with some diversity
    features = []
    for i in range(10):
        # Add slight variation per rule (some rules might be harder/easier)
        rule_variation = random.uniform(-0.1, 0.1)  # ±10% variation
        rule_prob = max(0.1, min(0.9, actual_prob + rule_variation))

        # Generate 0 or 1 based on probability
        feature = 1 if random.random() < rule_prob else 0
        features.append(feature)

    # Add realistic imperfections even for good documents
    if sample_type == 'good' and random.random() < 0.3:  # 30% chance
        # Flip 1-2 random rules to 0
        num_to_flip = random.randint(1, 2)
        valid_indices = [i for i, f in enumerate(features) if f == 1]
        if valid_indices:
            to_flip = random.sample(valid_indices, min(num_to_flip, len(valid_indices)))
            for idx in to_flip:
                features[idx] = 0

    # Calculate compliance score
    score = int((sum(features) / len(features)) * 100)

    # Determine label based on score
    label = "approved" if score >= 80 else "rejected"

    return {
        "features": features,
        "score": score,
        "label": label,
        "type": sample_type
    }


def generate_dataset(num_samples: int = 100) -> List[Dict[str, Any]]:
    """
    Generate a balanced dataset with equal distribution of document types.

    Args:
        num_samples: Total number of samples (will be distributed evenly)

    Returns:
        List of sample dictionaries
    """
    if num_samples < 3:
        raise ValueError("Minimum 3 samples required for balanced dataset")

    # Calculate samples per type (as equal as possible)
    samples_per_type = num_samples // 3
    remainder = num_samples % 3

    type_counts = {
        'good': samples_per_type + (1 if remainder > 0 else 0),
        'medium': samples_per_type + (1 if remainder > 1 else 0),
        'bad': samples_per_type
    }

    dataset = []

    # Generate samples for each type
    for sample_type, count in type_counts.items():
        for _ in range(count):
            sample = generate_sample(sample_type)
            dataset.append(sample)

    # Shuffle to avoid ordering bias
    random.shuffle(dataset)

    return dataset


def save_dataset(dataset: List[Dict[str, Any]], filename: str = "iso9001_dataset.json"):
    """
    Save dataset to JSON file.

    Args:
        dataset: List of sample dictionaries
        filename: Output filename
    """
    output_path = Path(__file__).parent / filename

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"✓ Dataset saved to {output_path}")
    print(f"  Total samples: {len(dataset)}")


def analyze_dataset(dataset: List[Dict[str, Any]]):
    """
    Print analysis of the generated dataset.

    Args:
        dataset: List of sample dictionaries
    """
    print("\n" + "="*60)
    print("DATASET ANALYSIS")
    print("="*60)

    total = len(dataset)
    types = {}
    labels = {}

    for sample in dataset:
        sample_type = sample['type']
        label = sample['label']
        score = sample['score']

        types[sample_type] = types.get(sample_type, 0) + 1
        labels[label] = labels.get(label, 0) + 1

    print(f"Total samples: {total}")
    print(f"\nBy type:")
    for t, count in types.items():
        pct = (count / total) * 100
        print(f"  {t.capitalize()}: {count} ({pct:.1f}%)")

    print(f"\nBy label:")
    for l, count in labels.items():
        pct = (count / total) * 100
        print(f"  {l.capitalize()}: {count} ({pct:.1f}%)")

    # Score distribution
    scores = [s['score'] for s in dataset]
    print(f"\nScore range: {min(scores)}% - {max(scores)}%")
    print(f"Average score: {sum(scores)/len(scores):.1f}%")

    print("="*60)


def main():
    """Main function to generate and save the dataset."""
    print("ISO 9001 Compliance Dataset Generator")
    print("="*50)

    # Generate dataset
    num_samples = 100  # Can be adjusted
    print(f"Generating {num_samples} samples...")

    dataset = generate_dataset(num_samples)

    # Analyze and display results
    analyze_dataset(dataset)

    # Save to file
    save_dataset(dataset)

    print("\n✓ Dataset generation complete!")
    print("\nSample entry:")
    print(json.dumps(dataset[0], indent=2))


if __name__ == "__main__":
    # Set random seed for reproducible results (optional)
    # random.seed(42)

    main()