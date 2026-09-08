import re
import string
import numpy as np
from itertools import combinations



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


def subsample_probs(freqs, threshold=1e-3):
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

        center = int(len(surviving)/2)
        m = rng.integers(1, max_window+1)
        start = max(0, center-m)
        end = min(len(surviving), center+m)

        pairs.append(list(combinations(surviving[start:end], 2)))

    return pairs


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


if __name__ == "__main__":
    main()