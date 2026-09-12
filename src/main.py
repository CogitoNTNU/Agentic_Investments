import os
import re
import string
from multiprocessing import Pool, shared_memory

import numpy as np


def split_sentences(text: str) -> list:
    """Split raw text into sentences BEFORE punctuation is stripped —
    tokenize() removes periods, so this has to run first."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in sentences if s]


def tokenize(text: str) -> list:
    clean_text = text.translate(str.maketrans('', '', string.punctuation))
    tokens = clean_text.lower().split()
    return tokens


def frequency(tokens: list):
    word2idx = {}
    idx2word = {}
    freqs = []

    for word in tokens:
        if word not in word2idx:
            pos = len(freqs)
            word2idx[word] = pos
            idx2word[pos] = word
            freqs.append(1)
        else:
            pos = word2idx[word]
            freqs[pos] += 1

    return word2idx, idx2word, freqs


def subsample_probs(freqs, threshold=1e-2):  # threshold = 1e-3
    freqs = np.array(freqs)
    f = freqs / freqs.sum()
    keep_prob = (np.sqrt(f / threshold) + 1) * (threshold / f)

    return np.clip(keep_prob, 0, 1)


def negative_sampling(freqs: list) -> list:
    freqs = np.array(freqs)
    powered = freqs**(3/4)

    return powered/powered.sum()


def generate_pairs(id_sentences, keep_prob, max_window):
    rng = np.random.default_rng()
    pairs = []

    for sentence in id_sentences:
        surviving = [x for x in sentence if rng.random() < keep_prob[x]]

        for i, center in enumerate(surviving):
            m = rng.integers(1, max_window+1)
            start = max(0, i-m)
            end = min(len(surviving), i+m+1)
            for j in range(start, end):
                if j != i:
                    pairs.append((center, surviving[j]))

    return pairs


def init_embeddings(vocab_size, dim, seed=42):
    rng = np.random.default_rng(seed)
    W_in = (rng.random((vocab_size, dim)) - 0.5) / dim   # small random values
    W_out = np.zeros((vocab_size, dim))                  # zeros is fine here
    return W_in, W_out


def sigmoid(x) -> float:
    return 1 / (1 + np.exp(-x))


def sigmoid_derivative(x) -> float:
    return sigmoid(x) * (1 - sigmoid(x))


def forward_pass(center, context, negatives, w_in, w_out):
    v_c = w_in[center]
    u_o = w_out[context]
    u_ni = w_out[negatives]

    pos_score = sigmoid(np.dot(u_o, v_c))
    neg_score = sigmoid(np.dot(u_ni, v_c))

    # + 1e-10 is a safety to avoid log(0)
    loss = -np.log(pos_score + 1e-10) - np.sum(np.log(1-neg_score + 1e-10))
    return pos_score, neg_score, loss


def gradient(center, context, negatives, pos_score, neg_score, w_in, w_out):
    v_c = w_in[center]
    u_o = w_out[context]
    u_ni = w_out[negatives]

    grad_u_o = (pos_score - 1) * v_c
    grad_u_ni = neg_score[:, None] * v_c[None, :]
    # FIX: added axis=0 -- without it, np.sum collapses (K,D) into a single
    # scalar instead of summing across the K negatives into a (D,) vector.
    grad_v_c = (pos_score - 1) * u_o + np.sum(neg_score[:, None] * u_ni, axis=0)

    return grad_u_o, grad_u_ni, grad_v_c


def update_params(center, context, negatives, grad_v_c, grad_u_o, grad_u_ni, w_in, w_out, lr):
    w_in[center]   -= lr * grad_v_c
    w_out[context] -= lr * grad_u_o
    np.add.at(w_out, negatives, -lr * grad_u_ni)
    return w_in, w_out


def current_lr(epoch, epochs, lr):
    return lr * max(1e-4, 1 - epoch/epochs)


def _train_chunk_mp(args):
    """Hogwild worker: attaches to shared memory and updates w_in/w_out in-place."""
    pairs, neg_table, k, lr, shm_in_name, shm_out_name, shape_in, shape_out, dtype = args
    shm_in  = shared_memory.SharedMemory(name=shm_in_name)
    shm_out = shared_memory.SharedMemory(name=shm_out_name)
    w_in  = np.ndarray(shape_in,  dtype=dtype, buffer=shm_in.buf)
    w_out = np.ndarray(shape_out, dtype=dtype, buffer=shm_out.buf)
    rng = np.random.default_rng()
    n = len(neg_table)
    total_loss = 0.0
    for center, context in pairs:
        negatives = neg_table[rng.integers(0, n, size=k)]
        pos_score, neg_score, loss = forward_pass(center, context, negatives, w_in, w_out)
        grad_u_o, grad_u_ni, grad_v_c = gradient(center, context, negatives, pos_score, neg_score, w_in, w_out)
        update_params(center, context, negatives, grad_v_c, grad_u_o, grad_u_ni, w_in, w_out, lr)
        total_loss += loss
    shm_in.close()
    shm_out.close()
    return total_loss


def train(id_sentences, word2idx, freqs, dim=768, epochs=200, k=5, lr=0.05, max_window=4, seed=42, num_workers=None):
    if num_workers is None:
        num_workers = min(os.cpu_count() or 4, 8)

    rng = np.random.default_rng(seed)
    vocab_size = len(word2idx)

    keep_prob = subsample_probs(freqs)
    neg_probs = negative_sampling(freqs)
    neg_table = rng.choice(vocab_size, size=1_000_000, p=neg_probs)  # build ONCE, not per pair

    w_in, w_out = init_embeddings(vocab_size, dim, seed=seed)

    # Put weight matrices in shared memory so worker processes can update them in-place (Hogwild).
    shm_in  = shared_memory.SharedMemory(create=True, size=w_in.nbytes)
    shm_out = shared_memory.SharedMemory(create=True, size=w_out.nbytes)
    shared_w_in  = np.ndarray(w_in.shape,  dtype=w_in.dtype,  buffer=shm_in.buf)
    shared_w_out = np.ndarray(w_out.shape, dtype=w_out.dtype, buffer=shm_out.buf)
    shared_w_in[:]  = w_in
    shared_w_out[:] = w_out

    print(f"Training with {num_workers} workers ...")
    try:
        with Pool(num_workers) as pool:
            for epoch in range(epochs):
                pairs  = generate_pairs(id_sentences, keep_prob, max_window)
                rng.shuffle(pairs)
                cur_lr = current_lr(epoch, epochs, lr)

                chunk_size = max(1, len(pairs) // num_workers)
                chunks = [pairs[i:i + chunk_size] for i in range(0, len(pairs), chunk_size)]

                args = [
                    (chunk, neg_table, k, cur_lr,
                     shm_in.name, shm_out.name,
                     shared_w_in.shape, shared_w_out.shape, shared_w_in.dtype)
                    for chunk in chunks
                ]
                total_loss = sum(pool.map(_train_chunk_mp, args))

                if pairs:
                    print(f"epoch {epoch:4d}  avg loss {total_loss/len(pairs):.4f}  lr {cur_lr:.4f}  #pairs {len(pairs)}")
    finally:
        result_w_in  = shared_w_in.copy()
        result_w_out = shared_w_out.copy()
        shm_in.close();  shm_in.unlink()
        shm_out.close(); shm_out.unlink()

    return result_w_in, result_w_out

def save_vocab(word2idx, idx2word, prefix="vocab"):
    np.save(f"{prefix}_word2idx.npy", word2idx)
    np.save(f"{prefix}_idx2word.npy", idx2word)


def load_vocab(prefix="vocab"):
    word2idx = np.load(f"{prefix}_word2idx.npy", allow_pickle=True).item()
    idx2word = np.load(f"{prefix}_idx2word.npy", allow_pickle=True).item()
    return word2idx, idx2word


def most_similar(word, word2idx, idx2word, w_in, topn=5):
    Wn = w_in / np.linalg.norm(w_in, axis=1, keepdims=True)   # normalize every row to unit length
    v = Wn[word2idx[word]]
    sims = Wn @ v                                              # cosine similarity to every word at once
    order = np.argsort(-sims)
    return [(idx2word[i], sims[i]) for i in order if idx2word[i] != word][:topn]

def load_gutenberg(path: str) -> str:
    with open(path, encoding="utf-8-sig") as f:  # utf-8-sig strips the BOM
        raw = f.read()
    start = re.search(r'\*{3} START OF (THIS|THE) PROJECT GUTENBERG EBOOK', raw)
    end = re.search(r'\*{3} END OF (THIS|THE) PROJECT GUTENBERG EBOOK', raw)
    if start:
        raw = raw[raw.index("\n", start.start()) + 1:]
        # recalculate end position after slicing
        end = re.search(r'\*{3} END OF (THIS|THE) PROJECT GUTENBERG EBOOK', raw)
    if end:
        raw = raw[:end.start()]
    return raw


def main():
    corpus_path = "data/2600-0.txt"
    print(f"Loading corpus from {corpus_path} ...")
    text = load_gutenberg(corpus_path)

    print("Splitting into sentences ...")
    sentences = [tokenize(s) for s in split_sentences(text)]
    sentences = [s for s in sentences if s]  # drop empty

    flat_tokens = [tok for sent in sentences for tok in sent]
    word2idx, idx2word, freqs = frequency(flat_tokens)
    print(f"Vocab size: {len(word2idx)}  |  Total tokens: {len(flat_tokens)}  |  Sentences: {len(sentences)}")

    save_vocab(word2idx, idx2word)
    id_sentences = [[word2idx[w] for w in sent] for sent in sentences]

    w_in, w_out = train(id_sentences, word2idx, freqs, dim=100, epochs=5, lr=0.025)
    np.save("w_in.npy", w_in)
    np.save("w_out.npy", w_out)
    print("Saved w_in.npy, w_out.npy, vocab_word2idx.npy, vocab_idx2word.npy")

    for probe in ("cock", "grandmother"):
        if probe in word2idx:
            print(f"Most similar to '{probe}':", most_similar(probe, word2idx, idx2word, w_in))

if __name__ == "__main__":
    main()