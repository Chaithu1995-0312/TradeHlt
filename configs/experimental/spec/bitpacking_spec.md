# Bit‑Packing Specification

## Encoding
- Weight values: +1 → 1, -1 → 0
- Input values: +1 → 1, -1 → 0
- Packed into 64‑bit integers (uint64_t) per layer.

## Dot Product (XNOR + popcount)
uint64_t mask = (1ULL << n_bits) - 1;
uint64_t xnor = ~(w ^ x) & mask;
int matches = __builtin_popcountll(xnor);
int dot = 2 * matches - n_bits;

text

## Layer Forward
1. Input (packed bits) → binary dot product with each weight row → multiply by scale → tanh → output.
2. Output (float) → binarize (>0 → 1, else 0) → pack → next layer.

## Multi‑layer Flow
- First layer input is packed from raw features.
- Subsequent layers pack their float outputs.
