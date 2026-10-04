# Labeler brief — marked-bar chart reading

You are labeling candlestick crops. Each image shows a short stretch of
price. One bar is marked by a small tick **outside** the plot, not on the
candle itself. Some images also show two unlabelled horizontal lines.
Answer from what you can see. Do not open any other file in this
repository. Do not search for timestamps, instrument names, or engine
output.

There is no rule card. There is no threshold. If you are unsure, say so
with LOW confidence and still pick an option.

## The four questions

**V1.** At the marked bar, did price spike beyond a prior extreme and then
close back inside?

- Above
- Below
- Neither

**V2.** Is the marked bar a strong directional push away from that spike?

- Up
- Down
- Neither

**V3.** Does the marked bar carry that push further in the same direction?

- Yes
- No

**V4.** Has price come back close to the level it originally broke?

- Yes
- No

For every item also give:

- **confidence:** HIGH / MEDIUM / LOW
- **visible evidence:** one or two sentences about the marked bar's
  body/wick, its relation to the previous candle, and (if lines are
  present) where it sits relative to those lines.

## Output shape

One JSON object per image, filename stem as `item_id`:

```json
{
  "item_id": "item_a3f9c2",
  "v1": "above",
  "v1_confidence": "HIGH",
  "v2": "neither",
  "v2_confidence": "MEDIUM",
  "v3": "no",
  "v3_confidence": "HIGH",
  "v4": "no",
  "v4_confidence": "HIGH",
  "evidence": "long upper wick through the prior high, close back inside the body of the previous bar"
}
```

Allowed values are exactly the option words above, lowercase
(`above` / `below` / `neither` / `up` / `down` / `yes` / `no`).
Confidence is `HIGH` / `MEDIUM` / `LOW`.
