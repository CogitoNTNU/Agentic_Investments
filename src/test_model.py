"""Interactive REPL for testing trained word embeddings.

Usage (from project root):
    python src/test_model.py
    python src/test_model.py --topn 10
    python src/test_model.py --vocab vocab --weights w_in.npy
"""
import argparse
import string
import sys

import numpy as np

sys.path.insert(0, "src")
from main import load_vocab, most_similar

MASK = "___"


def analogy(a, b, c, word2idx, idx2word, w_in, topn=5):
    """Words closest to b - a + c  (e.g. king - man + woman ≈ queen)."""
    Wn = w_in / np.linalg.norm(w_in, axis=1, keepdims=True)
    target = Wn[word2idx[b]] - Wn[word2idx[a]] + Wn[word2idx[c]]
    target /= np.linalg.norm(target) + 1e-10
    sims = Wn @ target
    exclude = {word2idx[a], word2idx[b], word2idx[c]}
    order = np.argsort(-sims)
    return [(idx2word[i], float(sims[i])) for i in order if i not in exclude][:topn]


def predict_mask(sentence, word2idx, idx2word, w_in, w_out, topn=5, max_window=4):
    """Predict the word at the ___ position from surrounding context.

    Uses the inverse of skip-gram scoring: average the w_out (context)
    embeddings of nearby words, then rank every word by how well its
    w_in (center) embedding matches that average.
    """
    # Tokenize, preserving MASK position
    tokens = []
    for raw in sentence.lower().split():
        clean = raw.translate(str.maketrans("", "", string.punctuation))
        if raw == MASK:
            tokens.append(None)          # None marks the mask position
        elif clean:
            tokens.append(clean)

    if None not in tokens:
        return None, []

    mask_pos = tokens.index(None)
    start = max(0, mask_pos - max_window)
    end   = min(len(tokens), mask_pos + max_window + 1)

    context = [t for i, t in enumerate(tokens[start:end], start)
               if i != mask_pos and t is not None and t in word2idx]

    if not context:
        return context, []

    # Average w_out of context words → the "signal" the center word should match
    ctx_avg = np.mean([w_out[word2idx[w]] for w in context], axis=0)

    # Score every word by how its w_in aligns with that context signal
    scores  = w_in @ ctx_avg
    exclude = {word2idx[w] for w in context}
    order   = np.argsort(-scores)
    results = [(idx2word[i], float(scores[i])) for i in order if i not in exclude][:topn]
    return context, results


def main():
    parser = argparse.ArgumentParser(description="Test word embedding model interactively")
    parser.add_argument("--vocab",   default="vocab",    help="Vocab file prefix (default: vocab)")
    parser.add_argument("--weights", default="w_in.npy", help="w_in weights file (default: w_in.npy)")
    parser.add_argument("--wout",    default="w_out.npy", help="w_out weights file (default: w_out.npy)")
    parser.add_argument("--topn",    default=5, type=int, help="How many results to show (default: 5)")
    args = parser.parse_args()

    print(f"Loading vocab from {args.vocab}_*.npy ...")
    word2idx, idx2word = load_vocab(args.vocab)
    print(f"Loading weights ...")
    w_in  = np.load(args.weights, allow_pickle=True)
    w_out = np.load(args.wout,    allow_pickle=True)
    print(f"Ready — {len(word2idx):,} words, embedding dim {w_in.shape[1]}\n")

    print("Commands:")
    print(f"  <word>                     — nearest neighbours")
    print(f"  <a> : <b> :: <c>           — analogy  (b − a + c)")
    print(f"  sentence with {MASK}        — predict the missing word")
    print(f"  quit / exit / Ctrl-D       — exit\n")

    while True:
        try:
            line = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue
        if line.lower() in ("quit", "exit"):
            break

        # ── masked-word prediction ───────────────────────────────────────────
        if MASK in line.split():
            context, results = predict_mask(line, word2idx, idx2word, w_in, w_out, topn=args.topn)
            if context is None:
                print(f"  Use {MASK} to mark the missing word")
            elif not results:
                print("  None of the surrounding words are in the vocabulary")
            else:
                print(f"  Context used: {context}")
                print(f"  Predictions for '{MASK}':")
                for word, score in results:
                    print(f"    {word:<20} {score:.4f}")
            continue

        # ── analogy: a : b :: c ──────────────────────────────────────────────
        if "::" in line:
            try:
                left, c = line.split("::")
                a, b = left.split(":")
                a, b, c = a.strip(), b.strip(), c.strip()
                missing = [w for w in (a, b, c) if w not in word2idx]
                if missing:
                    print(f"  Unknown: {missing}")
                    continue
                results = analogy(a, b, c, word2idx, idx2word, w_in, topn=args.topn)
                print(f"  {a} : {b} :: {c} : ?")
                for word, score in results:
                    print(f"    {word:<20} {score:.4f}")
            except Exception as e:
                print(f"  Error: {e}")
            continue

        # ── simple similarity ────────────────────────────────────────────────
        word = line.lower()
        if word not in word2idx:
            print(f"  '{word}' not in vocabulary")
            continue
        results = most_similar(word, word2idx, idx2word, w_in, topn=args.topn)
        for neighbour, score in results:
            print(f"  {neighbour:<20} {score:.4f}")


if __name__ == "__main__":
    main()
