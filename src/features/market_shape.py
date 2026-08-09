"""
Market Shape layer — Layer 5 of the semantic pipeline (roadmap Phase 5).

"Shapes classify." This module assigns every bar a recurring-structure identity built on the
Market Context (Layer 4). The spec is configs/formulas/market_shapes.yaml — declarative only,
loaded strictly, never eval'd.

TWO-TIER IDENTITY (see the YAML header for the full rationale)
  fine   — content-addressed: "MS-" + sha256[:16] of the context PROJECTED onto the declared
           structure dimensions. Total, deterministic, zero fitted parameters: two bars share a
           fine id iff their projected semantic descriptions are identical. (IC-003B killed
           FITTED shape libraries — unstable k*; exact discrete recurrence is the opposite
           construction and is what the Layer-4 result licenses: 3,871 XAUUSD bars collapsed to
           731 recurring contexts.)
  coarse — the YAML's ordered first-match predicates give matched bars a human name + family;
           unmatched bars keep the fine id with name=None. Not a fallback: an explicit identity.

CONTRACT (no defaults, no fallbacks — same discipline as Layers 2/4)
  - The spec is validated at LOAD: unknown feature, undeclared state name, feature outside the
    projection, unknown projection dimension, or duplicate shape name all RAISE. A typo is a
    load error, never a silently-dead predicate.
  - X_ markers in projected dimensions propagate: the bar cannot match any named shape (an X_
    state equals no declared state) and the markers surface on the result.
Shadow-only: nothing on the decision spine imports this module.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from features.feature_states import X_PREFIX
from features.market_context import MarketContext, MarketContextBuilder

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHAPES_PATH = _REPO_ROOT / "configs" / "formulas" / "market_shapes.yaml"

SHAPE_ID_PREFIX = "MS-"


@dataclass(frozen=True)
class ShapeSpec:
    """One declared named shape (validated predicate)."""
    name: str
    family: str
    when: dict[str, tuple[str, ...]]   # feature -> allowed state names (AND across, OR within)
    description: str


@dataclass(frozen=True)
class MarketShape:
    """One bar's shape identity."""
    shape_id: str                       # fine identity: MS-<hash of projected context>
    name: str | None                    # coarse label from first matching predicate, or None
    family: str | None
    projected_signature: str            # the exact string the shape_id hashes
    x_markers: tuple[str, ...]          # projected-dimension X_ states (domain drift)

    @property
    def matched(self) -> bool:
        return self.name is not None

    @property
    def label(self) -> str:
        """Human handle: the name when matched, else the explicit UNNAMED fine id."""
        return self.name if self.name is not None else f"UNNAMED({self.shape_id})"


class MarketShapeClassifier:
    """Projects Market Contexts to shape identities per the declarative spec."""

    def __init__(self, builder: MarketContextBuilder | None = None,
                 spec_path: Path | None = None):
        self._builder = builder if builder is not None else MarketContextBuilder()
        path = spec_path if spec_path is not None else _SHAPES_PATH
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"market shapes spec {path} did not parse to a mapping")

        # ── projection: known, non-empty, populated dimensions only ──────────
        projection = raw.get("projection")
        if not projection or not isinstance(projection, list):
            raise ValueError("market_shapes.yaml: `projection` must be a non-empty list")
        unknown_dims = [d for d in projection if d not in self._builder.dimensions]
        if unknown_dims:
            raise ValueError(
                f"market_shapes.yaml: projection names unknown/unpopulated dimensions "
                f"{unknown_dims} (known: {list(self._builder.dimensions)})"
            )
        self._projection: tuple[str, ...] = tuple(projection)

        # Features whose category is inside the projection — the only legal predicate targets.
        enc = self._builder._encoder  # same package; the builder owns the encoder
        projected_features = {
            f for dim in self._projection for f in self._builder.features_of(dim)
            if enc.spec(f).vector_index is not None
        }

        # ── shapes: strict validation, order = precedence ────────────────────
        shapes: list[ShapeSpec] = []
        seen: set[str] = set()
        for entry in (raw.get("shapes") or []):
            name = entry.get("name")
            if not name or name in seen:
                raise ValueError(f"market_shapes.yaml: missing/duplicate shape name {name!r}")
            seen.add(name)
            when_raw = entry.get("when")
            if not when_raw:
                raise ValueError(f"market_shapes.yaml: shape {name!r} has an empty `when`")
            when: dict[str, tuple[str, ...]] = {}
            for feat, allowed in when_raw.items():
                if feat not in projected_features:
                    raise ValueError(
                        f"market_shapes.yaml: shape {name!r} references {feat!r}, which is not a "
                        f"vector-bound stateful feature inside the projection {self._projection}"
                    )
                declared = set(enc.spec(feat).value_to_state.values())
                bad = [s for s in allowed if s not in declared]
                if bad:
                    raise ValueError(
                        f"market_shapes.yaml: shape {name!r}: {feat!r} has no declared state(s) "
                        f"{bad} (declared: {sorted(declared)})"
                    )
                when[feat] = tuple(allowed)
            shapes.append(ShapeSpec(
                name=str(name),
                family=str(entry.get("family") or name),
                when=when,
                description=str(entry.get("description") or ""),
            ))
        if not shapes:
            raise ValueError("market_shapes.yaml: no shapes declared")
        self._shapes: tuple[ShapeSpec, ...] = tuple(shapes)

    # ── introspection ────────────────────────────────────────────────────────

    @property
    def projection(self) -> tuple[str, ...]:
        return self._projection

    @property
    def shapes(self) -> tuple[ShapeSpec, ...]:
        """Declared named shapes, in precedence order."""
        return self._shapes

    # ── classification ───────────────────────────────────────────────────────

    def classify_context(self, ctx: MarketContext) -> MarketShape:
        """Assign the shape identity for one bar's Market Context."""
        # Project: only the declared structure dimensions participate in identity.
        projected: dict[str, str] = {}
        parts: list[str] = []
        x_markers: list[str] = []
        for dim in self._projection:
            feats = ctx.dimensions.get(dim)
            if feats is None:
                raise ValueError(
                    f"classify_context(): context is missing projected dimension {dim!r} — "
                    "build it from the full canonical input first"
                )
            parts.append(f"{dim}[" + ",".join(f"{f}={s}" for f, s in feats.items()) + "]")
            for f, s in feats.items():
                projected[f] = s
                if s.startswith(X_PREFIX):
                    x_markers.append(f"{f}={s}")

        projected_signature = "|".join(parts)
        shape_id = SHAPE_ID_PREFIX + hashlib.sha256(
            projected_signature.encode()
        ).hexdigest()[:16]

        # First-match naming. An X_ state equals no declared state, so drifted bars
        # can only resolve UNNAMED — drift never silently wears a shape name.
        name = family = None
        for spec in self._shapes:
            if all(projected[f] in allowed for f, allowed in spec.when.items()):
                name, family = spec.name, spec.family
                break

        return MarketShape(
            shape_id=shape_id,
            name=name,
            family=family,
            projected_signature=projected_signature,
            x_markers=tuple(x_markers),
        )

    def classify_vector(self, vector: Sequence[float]) -> MarketShape:
        """Canonical 39-dim vector -> MarketShape."""
        return self.classify_context(self._builder.build_from_vector(vector))

    def survey(self, vectors: Sequence[Sequence[float]]) -> dict[str, dict[str, int]]:
        """Corpus summary: occurrence counts by label, family, and fine shape_id."""
        by_label: dict[str, int] = {}
        by_family: dict[str, int] = {}
        by_id: dict[str, int] = {}
        for v in vectors:
            s = self.classify_vector(v)
            by_label[s.label] = by_label.get(s.label, 0) + 1
            fam = s.family if s.family is not None else "UNNAMED"
            by_family[fam] = by_family.get(fam, 0) + 1
            by_id[s.shape_id] = by_id.get(s.shape_id, 0) + 1
        return {"by_label": by_label, "by_family": by_family, "by_shape_id": by_id}
