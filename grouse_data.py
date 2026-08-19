"""
grouse_data.py

Central data-access layer for the grouse habitat pipeline. All file
naming conventions live in PATH_TEMPLATES (single source of truth);
everything else is discovered from disk, loaded lazily, and cached.

This module is I/O only - no analysis logic. Scripts import it instead
of constructing paths themselves:

    from grouse_data import GrouseData

    data = GrouseData()                    # discovers regions on disk
    me = data["ME"]

    me.positives("train")                  # train_positives_ME.csv
    me.positives("val")                    # val_positives_ME.csv
    me.evaluated                           # evaluated_sightings_ME.csv
    me.envelope_metrics                    # envelope_metrics_ME.csv
    me.block_assignments                   # block_assignments_ME.csv
    me.raster_path("sclass", 2024)         # exact year, must exist
    me.raster_path("sclass", 2025)         # -> nearest available (2024)
    me.raster_years("sclass")              # [2022, 2023, 2024]
    me.sightings(2019)                     # raw me_sightings_2019.csv
    data.evt_crosswalk()                   # newest LF*_EVT.csv as maps

Adding a new file type = one PATH_TEMPLATES entry (+ optionally a
convenience property). Adding a raster feature = drop the .tif in
landfire_data/ - discovery picks it up with no code change.
"""
import os
import re
import glob
from dataclasses import dataclass

import pandas as pd
import rasterio


# ==========================================
# CONFIG
# ==========================================
@dataclass(frozen=True)
class DataConfig:
    """Directory layout. Override any of these at construction:
    GrouseData(DataConfig(base_dir='/some/where'))."""
    base_dir: str = "."
    raster_dir: str = "data/landfire"
    attribute_dir: str = "data/landfire/attribute_tables"
    map_data_dir: str = "data/maps/map_data"

    def resolve(self, rel):
        return os.path.join(self.base_dir, rel)


# Every filename convention in the project, in one place. {region} is the
# two-letter state code, {year} a 4-digit year, {feature} a raster feature
# key (evt/evh/evc/sclass/fdist/ch/cc), {state_lower} the lowercase
# state code used by the raw sighting CSVs.
PATH_TEMPLATES = {
    "raster":            "{raster_dir}/{region}_{year}_{feature}.tif",
    "raster_meta_dir":   "{raster_dir}/{region}_{year}_{feature}_meta",
    "attribute_table":   "{attribute_dir}/LF{year}_{product}.csv",
    "sightings":         "data/sightings/{state_lower}_sightings_{year}.csv",
    "evaluated":         "data/pipeline/evaluated_sightings_{region}.csv",
    "envelope_metrics":  "data/pipeline/envelope_metrics_{region}.csv",
    "nonveg_flagged":    "data/pipeline/nonveg_flagged_{region}.csv",
    "thinned":           "data/pipeline/thinned_positives_{region}.csv",
    "train_positives":   "data/pipeline/train_positives_{region}.csv",
    "val_positives":     "data/pipeline/val_positives_{region}.csv",
    "negatives":         "data/negatives/negatives_{region}.csv",
    "train_negatives":   "data/negatives/train_negatives_{region}.csv",
    "val_negatives":     "data/negatives/val_negatives_{region}.csv",
    "gbif_candidates":   "data/negatives/gbif_negatives_{region}.csv",
    "block_assignments": "data/pipeline/block_assignments_{region}.csv",
    "bin_tuning":        "data/pipeline/bin_tuning_{region}.csv",
    "diagnostic_map":    "data/maps/grouse_diagnostic_map_{region}.png",
}

RASTER_FEATURES = ["evt", "evh", "evc", "sclass", "fdist", "ch", "cc"]


class MissingDataError(FileNotFoundError):
    """A requested file doesn't exist, with the resolved path in the
    message so the fix is obvious."""


# ==========================================
# PER-REGION ACCESSOR
# ==========================================
class RegionData:
    """Lazy, cached access to every per-region artifact. Instantiate via
    GrouseData rather than directly so discovery stays consistent."""

    def __init__(self, region, config=None):
        self.region = region.upper()
        self.config = config or DataConfig()
        self._cache = {}
        self._raster_validity_cache = {}

    # ---- path machinery -------------------------------------------------
    def path(self, kind, must_exist=True, **kw):
        """Resolve a PATH_TEMPLATES entry for this region. Raises
        MissingDataError (with the full path) when must_exist and the
        file is absent - callers never silently work on a wrong path."""
        template = PATH_TEMPLATES[kind]
        fields = dict(
            region=self.region,
            state_lower=self.region.lower(),
            raster_dir=self.config.raster_dir,
            attribute_dir=self.config.attribute_dir,
            **kw,
        )
        rel = template.format(**fields)
        full = self.config.resolve(rel)
        if must_exist and not os.path.exists(full):
            raise MissingDataError(
                f"[{self.region}] no '{kind}' file at {full}")
        return full

    def _load_csv(self, kind, **kw):
        key = (kind, tuple(sorted(kw.items())))
        if key not in self._cache:
            self._cache[key] = pd.read_csv(self.path(kind, **kw))
        return self._cache[key]

    def clear_cache(self):
        self._cache.clear()

    # ---- rasters ---------------------------------------------------------
    def raster_years(self, feature):
        """Years on disk for a feature, discovered by scanning - never
        declared. New downloads appear automatically."""
        pattern = re.compile(rf"^{self.region}_(\d{{4}})_{feature}\.tif$")
        found = []
        for p in glob.glob(self.config.resolve(
                f"{self.config.raster_dir}/{self.region}_*_{feature}.tif")):
            m = pattern.match(os.path.basename(p))
            if m:
                found.append(int(m.group(1)))
        return sorted(set(found))

    def _is_valid_raster(self, path, min_valid_frac=0.01):
        """True if the file opens as a raster and has real content (not
        effectively all-nodata). Catches the failure mode download.py's
        content check normally prevents at download time (a job that
        'succeeds' but returns an empty raster - e.g. LANDFIRE hasn't
        released that vintage for this region yet) in case a bad file
        ever reaches disk through some other path. Cached per path since
        opening a full raster isn't free."""
        if path in self._raster_validity_cache:
            return self._raster_validity_cache[path]
        try:
            with rasterio.open(path) as src:
                data = src.read(1)
                if src.nodata is None:
                    valid = True
                else:
                    frac = (data != src.nodata).sum() / data.size if data.size else 0.0
                    valid = frac >= min_valid_frac
        except Exception:
            valid = False
        self._raster_validity_cache[path] = valid
        return valid

    def raster_path(self, feature, year, nearest=True, validate=True):
        """Path to a feature raster. With nearest=True (default), a year
        with no raster resolves to the closest available year (ties ->
        earlier year) - matches analyze_grouse.py's sighting-extraction
        fallback (appropriate when the goal is land cover close to a
        specific historical date).

        With validate=True (default), the resolved file's CONTENT is
        checked, not just its existence - a present-but-empty raster
        (see _is_valid_raster) is treated as unavailable and this falls
        back to the MOST RECENT valid year overall, regardless of numeric
        distance to the requested year. This is the "just use the most
        recent instead of a missing/broken dataset" behavior - use
        latest_raster_path() instead if you always want current
        conditions regardless of any specific year."""
        years = self.raster_years(feature)
        if not years:
            raise MissingDataError(
                f"[{self.region}] no rasters on disk for feature "
                f"'{feature}' under {self.config.resolve(self.config.raster_dir)}")
        year = int(year)
        if year not in years:
            if not nearest:
                raise MissingDataError(
                    f"[{self.region}] no {feature} raster for {year}; "
                    f"available: {years}")
            year = min(years, key=lambda y: (abs(y - year), y))

        path = self.path("raster", feature=feature, year=year)
        if not validate or self._is_valid_raster(path):
            return path

        # Resolved file exists but is invalid - fall back to the most
        # recent valid year among everything else on disk.
        for candidate_year in sorted(years, reverse=True):
            if candidate_year == year:
                continue
            candidate_path = self.path("raster", feature=feature,
                                       year=candidate_year)
            if self._is_valid_raster(candidate_path):
                return candidate_path
        raise MissingDataError(
            f"[{self.region}] every {feature} raster on disk ({years}) "
            f"failed content validation - all appear empty/corrupted.")

    def latest_raster_path(self, feature, validate=True):
        """The most recent raster for a feature, full stop - no target
        year involved. Use this when you want current conditions (e.g.
        building a present-day feature matrix) rather than land cover
        matched to a specific historical date. With validate=True, skips
        any year that fails content validation in favor of the next
        most recent valid one."""
        years = self.raster_years(feature)
        if not years:
            raise MissingDataError(
                f"[{self.region}] no rasters on disk for feature "
                f"'{feature}' under {self.config.resolve(self.config.raster_dir)}")
        for year in sorted(years, reverse=True):
            path = self.path("raster", feature=feature, year=year)
            if not validate or self._is_valid_raster(path):
                return path
        raise MissingDataError(
            f"[{self.region}] every {feature} raster on disk ({years}) "
            f"failed content validation - all appear empty/corrupted.")

    def available_features(self):
        return [f for f in RASTER_FEATURES if self.raster_years(f)]

    # ---- tabular artifacts ----------------------------------------------
    @property
    def evaluated(self):
        return self._load_csv("evaluated")

    @property
    def envelope_metrics(self):
        return self._load_csv("envelope_metrics")

    @property
    def nonveg_flagged(self):
        return self._load_csv("nonveg_flagged")

    @property
    def thinned(self):
        return self._load_csv("thinned")

    @property
    def block_assignments(self):
        return self._load_csv("block_assignments")

    def positives(self, split="all"):
        """Thinned positive training data. split: 'train', 'val', or
        'all' (the full thinned file, which carries a 'split' column)."""
        if split == "train":
            return self._load_csv("train_positives")
        if split == "val":
            return self._load_csv("val_positives")
        if split == "all":
            return self.thinned
        raise ValueError(f"split must be 'train', 'val', or 'all', got {split!r}")

    def negatives(self, split="all"):
        """Generated negative data (generate_negatives.py output; carries
        label=0, weight, envelope_id, block_id, split columns).
        split: 'train', 'val', or 'all'."""
        if split == "train":
            return self._load_csv("train_negatives")
        if split == "val":
            return self._load_csv("val_negatives")
        if split == "all":
            return self._load_csv("negatives")
        raise ValueError(f"split must be 'train', 'val', or 'all', got {split!r}")

    def training_frame(self, split, feature_columns=None):
        """Positives + negatives for one split, concatenated with a
        'label' column (1/0), restricted to columns BOTH sides share.

        feature_columns=None discovers the usable feature set dynamically:
        the intersection of both frames' columns with RASTER_FEATURES
        (plus evt_phys if present on both). This is what lets model input
        geometry follow the data instead of being hardcoded - add or
        remove a feature upstream and every consumer of this method
        adapts automatically.

        Returns (df, feature_columns). df includes the features, 'label',
        and - when present - 'weight', 'block_id', 'split' passthrough
        columns for weighted losses and leakage audits."""
        pos = self.positives(split).copy()
        neg = self.negatives(split).copy()
        pos['label'] = 1
        if 'label' not in neg.columns:
            neg['label'] = 0

        if feature_columns is None:
            shared = set(pos.columns) & set(neg.columns)
            feature_columns = [f for f in RASTER_FEATURES if f in shared]
            if 'evt_phys' in shared:
                feature_columns.append('evt_phys')
        missing_pos = [c for c in feature_columns if c not in pos.columns]
        missing_neg = [c for c in feature_columns if c not in neg.columns]
        if missing_pos or missing_neg:
            raise MissingDataError(
                f"[{self.region}] feature columns missing - positives lack "
                f"{missing_pos}, negatives lack {missing_neg}. Re-run the "
                f"upstream pipeline (analyze_grouse.py / "
                f"generate_negatives.py) so both carry the same features.")

        passthrough = [c for c in ("weight", "block_id", "split")
                       if c in pos.columns or c in neg.columns]
        keep = feature_columns + ['label'] + passthrough
        combined = pd.concat(
            [pos[[c for c in keep if c in pos.columns]],
             neg[[c for c in keep if c in neg.columns]]],
            ignore_index=True)
        if 'weight' in combined.columns:
            combined['weight'] = combined['weight'].fillna(1.0)
        return combined, feature_columns

    def sightings(self, year):
        """Raw sighting CSV for one year (pre-pipeline input data)."""
        return self._load_csv("sightings", year=year)

    def sighting_years(self):
        pattern = re.compile(
            rf"^{self.region.lower()}_sightings_(\d{{4}})\.csv$")
        found = []
        for p in glob.glob(self.config.resolve(
                f"{self.region.lower()}_sightings_*.csv")):
            m = pattern.match(os.path.basename(p))
            if m:
                found.append(int(m.group(1)))
        return sorted(found)

    def __repr__(self):
        feats = ", ".join(self.available_features()) or "none"
        return f"RegionData({self.region}: rasters=[{feats}])"


# ==========================================
# TOP-LEVEL CONTAINER
# ==========================================
class GrouseData:
    """Discovers regions from what's actually on disk and hands out
    RegionData accessors. Dict-style: data['ME']; iterable over regions."""

    def __init__(self, config=None):
        self.config = config or DataConfig()
        self._regions = {}

    def discover_regions(self):
        """Regions inferred from raster filenames ({REGION}_{year}_...)."""
        pattern = re.compile(r"^([A-Z]{2})_\d{4}_[a-z]+\.tif$")
        found = set()
        for p in glob.glob(self.config.resolve(f"{self.config.raster_dir}/*.tif")):
            m = pattern.match(os.path.basename(p))
            if m:
                found.add(m.group(1))
        return sorted(found)

    def __getitem__(self, region):
        region = region.upper()
        if region not in self._regions:
            self._regions[region] = RegionData(region, self.config)
        return self._regions[region]

    def __iter__(self):
        for r in self.discover_regions():
            yield self[r]

    def evt_crosswalk(self):
        """VALUE -> (EVT_PHYS, EVT_GP_N) maps from the newest EVT
        attribute table on disk, or None if absent. Same semantics as
        analyze_grouse.load_evt_crosswalk."""
        files = sorted(glob.glob(self.config.resolve(
            f"{self.config.attribute_dir}/LF*_EVT.csv")))
        if not files:
            return None
        tbl = pd.read_csv(files[-1])
        tbl.columns = [c.upper().strip() for c in tbl.columns]
        if "VALUE" not in tbl.columns or "EVT_PHYS" not in tbl.columns:
            return None
        group_col = "EVT_GP_N" if "EVT_GP_N" in tbl.columns else "EVT_PHYS"
        return {
            "phys": dict(zip(tbl["VALUE"].astype(int), tbl["EVT_PHYS"].astype(str))),
            "group": dict(zip(tbl["VALUE"].astype(int), tbl[group_col].astype(str))),
            "source": os.path.basename(files[-1]),
        }

    def __repr__(self):
        return f"GrouseData(regions={self.discover_regions()})"

