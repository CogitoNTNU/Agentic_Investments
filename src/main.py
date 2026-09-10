import re
import string
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


def main():
    text = "The cat sits on the mat. The dog barks."

    # tokenize each sentence SEPARATELY, keep them as separate lists
    sentences = [tokenize(s) for s in split_sentences(text)]
    print("sentences (tokenized separately):", sentences)

    # build ONE global vocab/frequency table across all sentences combined
    flat_tokens = [tok for sent in sentences for tok in sent]
    word2idx, idx2word, freqs = frequency(flat_tokens)
    print("word2idx:", word2idx)

    # convert each sentence's words to ids, still keeping sentence structure
    id_sentences = [[word2idx[w] for w in sent] for sent in sentences]
    print("id_sentences:", id_sentences)

    keep_prob = subsample_probs(freqs)
    print("keep_prob:", keep_prob)

    pairs = generate_pairs(id_sentences, keep_prob, max_window=4)
    print("pairs (as ids):", pairs)

    w_in, w_out = init_embeddings(vocab_size=len(word2idx), dim=5)

    # --- test Step 8/9/10: one full forward -> backward -> update step ---
    neg_probs = negative_sampling(freqs)
    center, context = word2idx["cat"], word2idx["mat"]
    negatives = np.random.default_rng(0).choice(len(word2idx), size=5, p=neg_probs)

    pos_score, neg_score, loss = forward_pass(center, context, negatives, w_in, w_out)
    print(f"\ncenter={idx2word[center]!r}  context={idx2word[context]!r}")
    print("negatives:", [idx2word[n] for n in negatives])
    print("pos_score:", pos_score)
    print("neg_score:", neg_score)
    print("loss:", loss)

    grad_u_o, grad_u_ni, grad_v_c = gradient(center, context, negatives, pos_score, neg_score, w_in, w_out)
    w_in, w_out = update_params(center, context, negatives, grad_v_c, grad_u_o, grad_u_ni, w_in, w_out, lr=0.1)
    _, _, new_loss = forward_pass(center, context, negatives, w_in, w_out)
    print("loss after one update step:", new_loss, " (should be lower than", loss, ")")

    # --- test Step 11: learning rate schedule ---
    print("\nlearning rate decay (lr=0.05, epochs=200):")
    for epoch in [0, 1, 50, 100, 150, 199]:
        print(f"  epoch {epoch:>3}: cur_lr = {current_lr(epoch, 200, 0.05):.5f}")


if __name__ == "__main__":
    main()