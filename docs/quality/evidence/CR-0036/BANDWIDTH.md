# Can a high-bandwidth EC2 instance pull and process ME/NH/VT 3DEP lidar quickly?

Date: 2026-10-05. Research only. No repository file was edited.
Scratch evidence for this report is in `../bw/` (benchmark script, EPT
nodes, price lists) and `../lidar/` (the crawl output `crawl.py` and
the sibling route agent's files, which this report reads but does not change).

**Short answer: partly.** The full three-state job costs about **6–11 h of wall-clock on one
192-vCPU instance in us-west-2**. That is roughly **$12–25 on spot or $70–110 on-demand**,
and a pilot costs **under $1**. However, the job is **CPU-bound, not network-bound**. A
50 Gbps instance (c7a, c7i or c8g .48xlarge) has 5–10x more network than the job can use.
The 200 Gbps c6in/c7gn/m6in tiers buy nothing extra. Run the job in **us-west-2**,
which is the bucket region, not on the us-east-2 host.

Each figure in this report is labelled with how it was established:
- **[verified]**: checked this session against the URL or command given.
- **[measured]**: benchmarked in this sandbox.
- **[estimate]**: arithmetic shown in the report.
- **[unverified]**: neither checked nor measured.

---

## 1. Where the data lives, and transfer costs

### Buckets [verified]

| Bucket | Contents | Region | Requester-pays |
|---|---|---|---|
| `s3://usgs-lidar-public` | Entwine Point Tiles (EPT): one `ept.json` plus `ept-data/*.laz` nodes per project | **us-west-2** | No (anonymous reads work) |
| `s3://usgs-lidar` | Raw 3DEP LAZ 1.4 tiles. "More complete in coverage than the EPT bucket, but it is not a complete 3DEP mirror." | **us-west-2** | **Yes** (needs AWS credentials and `--request-payer requester`) |

- Bucket details: https://registry.opendata.aws/usgs-lidar/ and https://github.com/hobuinc/usgs-lidar
- Region check: `curl -sI https://usgs-lidar-public.s3.amazonaws.com/` returned `x-amz-bucket-region: us-west-2`.
- The same raw tiles are also served over plain HTTP from USGS rockyweb (outside AWS):
  https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/Elevation/LPC/Projects/
  Each project there has a `.vpc` index (STAC-style JSON with a per-tile `pc:count`).
- EPT resources store points in **EPSG:3857**, with no vertical SRS declared [verified: the
  `srs` field of each `ept.json`].
- The raw tiles keep the native project CRS. Example: the VT tile I sampled is
  `NAD83(2011) / Vermont (EPSG:6589) + NAVD88 height – Geoid18` [verified: tile header].
- **Unverified:** whether the requester-pays bucket holds the projects that are missing from
  EPT (ME_WesternMtns_B24, ME_CrownofMaine_B1, ME_Eastern_B1/B2, NH CT-River 2015,
  NY_NHGaps_D24, VT_Statewide_3_A23). I could not list it without credentials.
  Check first with `aws s3 ls s3://usgs-lidar/Projects/ --request-payer requester`; if a project is
  missing, rockyweb is the fallback.

### Transfer and request prices [verified from AWS price lists, 2026-09/10]

- **S3 to EC2 in the same region:** free. https://aws.amazon.com/s3/pricing/ states: "Data
  transferred from an Amazon S3 bucket to any AWS service(s) within the same AWS Region" is
  not charged.
- **us-west-2 → us-east-2:** **$0.02/GB**. The AWSDataTransfer offer file (effective
  2026-06-01) has the SKU "$0.02 per GB - US West (Oregon) data transfer to US East (Ohio)",
  and inbound to Ohio is $0.00.
  https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/index.csv
- **S3 Standard GET:** $0.0004 per 1,000 requests ("$0.004 per 10,000 GET and all other
  requests", AmazonS3 us-west-2 offer file).
- **Requester-pays:** "the requester pays for the data transfer and the request". Inside
  us-west-2 the transfer price is $0, so only GET fees apply.
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/RequesterPaysBuckets.html
- **Cross-region bandwidth cap:** traffic leaving through an internet gateway is limited to
  5 Gbps on instances with fewer than 32 vCPUs, and to 50% of rated bandwidth on larger ones.
  A single flow is capped at 5 Gbps.
  https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-network-bandwidth.html
  A us-east-2 host reading from us-west-2 would hit both caps and about 50–70 ms RTT
  [RTT unverified].
- **NAT gateway:** if the us-east-2 host sits in a private subnet behind a NAT gateway, every
  GB also pays NAT processing, about $0.045/GB [**unverified** this session: my price-list grep
  did not find the SKU]. For 11–13 TB that is roughly $500–600. This is the main hidden cost
  of running in Ohio.

**Running in us-west-2 avoids all of these.** Only the small 30 m output rasters, a few GB,
cross to Ohio, at about $0.10.

### Data volume for ME, NH and VT

**EPT bucket (my enumeration) [verified]**
- I enumerated all 2,287 EPT prefixes and read every `ept.json` whose bounds intersect the
  states.
- The EPT projects whose names are ME/NH/VT hold **1.59 T points**. EPT LAZ nodes average
  **8.24 B/point** (30 VT_Statewide_1 leaf nodes: 17.5 MB for 2.13 M points). That puts
  the EPT copy at roughly **13 TB** [estimate].
- EPT nodes average about 30–70 k points per node (six sampled sub-hierarchies). The whole
  set is therefore about **30–40 M objects** [estimate].

**Newest-wins coverage**

The sibling agent's WESM analysis (`../lidar/newest_points.txt`, `wesm_summary.txt`;
**unverified by me**) clips each state to its newest project:

| State | Area | Points | Of which not in EPT |
|---|---|---|---|
| Maine | 84,572 km² | 761 G | 332 G |
| New Hampshire | 23,963 km² | 205 G | 13 G |
| Vermont | 24,723 km² | 687 G | 210 G |
| **Total** | 133,258 km² | **1,653 G** | **≈555 G (≈1/3)** |

**Whole-tile workload [verified]**

You cannot clip a tile before reading it, so the real workload is every tile that touches a
state. My rockyweb `.vpc` crawl sums the whole projects in the newest-wins set to
**2,143 G points**. This excludes NH_CT_River P2/P3, whose `.vpc` files I did not find.

Planning figures used below:
- Central workload: **P = 2.0 T points**, range 1.65–2.3 T.
- Raw LAZ: about **5.5 B/point**. The full VT tile `USGS_LPC_VT_Statewide_A23_N2555E4795.laz`
  is 450,100,971 B for 81,498,925 points [verified].
- So the raw tiles are about **11 TB** [estimate].
- There are about 85–95 k tiles (sum of `.vpc` feature counts). VT_Statewide_1 averages
  53 M points (about 290 MB) per tile.

**Derived rasters that already exist (for comparison) [sizes unverified]**
- **VT:** statewide 0.7 m nDSM, as COG and image service.
  https://vcgi.vermont.gov/data-and-programs/lidar-program
  Uncompressed float32 would be about 24,900 km² / 0.49 m² × 4 B ≈ 200 GB [estimate].
- **NH:** 2 m nDSM/CHM image service from 8 collections (as of 2020).
  https://granit24a.sr.unh.edu/image/rest/services/ImageServices/nDSM_NH/ImageServer
  About 24 GB uncompressed [estimate].
- **ME:** no statewide CHM product found.
- **New England (all six states):** ORNL DAAC ds 1854 gives **30 m canopy height and cover**
  from 2010–2015 leaf-off lidar. https://doi.org/10.3334/ORNLDAAC/1854
  It is already on a 30 m grid, but it is old and has no understory band.

**Understory return fractions (0.5–5 m) need the point cloud.** No CHM or nDSM contains them.

---

## 2. Instance options

Sources:
- On-demand prices and specs: AWS price-list API, `AmazonEC2/current/{us-west-2,us-east-2}/index.csv`
  (Linux, shared tenancy) [verified].
- Spot prices: https://website.spot.ec2.aws.a2z.com/spot.js, a **snapshot taken 2026-10-05
  that moves hourly**.
- Interruption band: https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json
  (r index 0 = <5%, 1 = 5–10%, 2 = 10–15%, 3 = 15–20%, 4 = >20%).
- Network baseline/burst: https://docs.aws.amazon.com/ec2/latest/instancetypes/co.html#co_network
- EBS figure: the price list's "Dedicated EBS Throughput" in Mbps; divide by 8 for MB/s.

| Type (us-west-2) | vCPU | Network baseline / burst | EBS Mbps | Instance store | On-demand $/h | Spot $/h (2026-10-05) | Interruption band |
|---|---|---|---|---|---|---|---|
| c6in.4xlarge | 16 | 25 / 50 Gbps | up to 25,000 | none | 0.907 | 0.436 | >20% |
| c6in.8xlarge | 32 | 50 | 25,000 | none | 1.814 | 0.901 | >20% |
| c6in.16xlarge | 64 | 100 | 50,000 | none | 3.629 | 1.474 | >20% |
| **c6in.32xlarge** | 128 | **200** | 100,000 | none | 7.258 | 2.539 | >20% |
| c7gn.8xlarge (Graviton3) | 32 | 100 | 20,000 | none | 1.997 | 0.371 | >20% |
| **c7gn.16xlarge** | 64 | **200** | 40,000 | none | 3.994 | 0.639 | <5% |
| c8gn.48xlarge (Graviton4) | 192 | 600 | 120,000 | none | 11.376 | n/a in feed | 5–10% |
| **m6in.32xlarge** | 128 | **200** | 100,000 | none | 8.911 | 1.830 | >20% |
| c6i.16xlarge | 64 | 25 | 20,000 | none | 2.720 | 0.886 | 15–20% |
| c6i.32xlarge | 128 | 50 | 40,000 | none | 5.440 | 1.895 | >20% |
| c7i.4xlarge | 16 | 6.25 / 12.5 | up to 10,000 | none | 0.714 | 0.253 | 5–10% |
| c7i.16xlarge | 64 | 25 | 20,000 | none | 2.856 | 0.715 | 5–10% |
| **c7i.48xlarge** | 192 | 50 | 40,000 | none | 8.568 | 2.208 | 10–15% |
| **c7a.48xlarge** (1 vCPU = 1 physical core) | 192 | 50 | 40,000 | none | 9.853 | **1.703** | 10–15% |
| **c8g.48xlarge** (Graviton4, 1 vCPU = 1 core) | 192 | 50 | 40,000 | none | 7.657 | n/a in feed | <5% |
| c6id.32xlarge | 128 | 50 | 40,000 | 4 × 1900 GB NVMe | 6.451 | 1.646 | >20% |
| c7gd.16xlarge | 64 | 30 | 20,000 | 2 × 1900 GB NVMe | 2.903 | 0.793 | 5–10% |
| r6i.32xlarge | 128 | 50 | 40,000 | none | 8.064 | 3.244 | >20% |
| r6in.32xlarge | 128 | 200 | 100,000 | none | 11.157 | 5.945 | >20% |
| r7i.48xlarge (1.5 TB RAM) | 192 | 50 | 40,000 | none | 12.701 | 1.690 | 5–10% |
| m7i.48xlarge (768 GB RAM) | 192 | 50 | 40,000 | none | 9.677 | 2.482 | <5% |

**us-east-2 (Ohio):**
- On-demand prices are the same as us-west-2, to the cent, for every type above.
- Spot is often higher in Ohio: c7a.48xlarge $3.14, c7i.48xlarge $3.40, c7gn.16xlarge $0.81,
  c6in.32xlarge $2.46.
- Full table: `../bw/` and the extraction printed in this session.

**Burst bandwidth.** Only the 4xlarge and smaller sizes are "up to". They burst for "typically
5 to 60 minutes" on network I/O credits and then fall back to baseline (bandwidth doc above).
For an hours-long job, plan on the **baseline** figure.

---

## 3. Where the real bottleneck is

### Measured per-core rates [measured]

Sandbox: Intel Xeon @ 2.8 GHz (one vCPU), laspy 2.7 with the lazrs backend, 2.13 M points
of VT_Statewide_1 EPT nodes. Script: `../bw/bench.py`.

| Stage | Rate per vCPU |
|---|---|
| LAZ decompression plus scaling of x, y, z, class and return number | **1.1–1.55 M pts/s** (cold / warm) |
| Height above ground (3-NN inverse-distance weighting on class-2 ground, scipy cKDTree) | **0.59 M pts/s** |
| 30 m binning and 0.5–5 m counting (numpy bincount) | 2.8 M pts/s |
| **End to end** | **≈0.5 M pts/s per vCPU** |

Published LASzip figure: 1–3 (some sources say 1–4) M pts/s decode.
https://rapidlasso.de/laszip-lossless-compression-of-lidar-data/

PDAL runs each pipeline single-threaded ("parallelization is up to users of the library"),
and `filters.hag_delaunay` triangulates per point.
https://pdal.io/stages/filters.hag_delaunay.html
Its per-point rate has no published benchmark that I could find [**unverified**]. I expect it
to be slower than my k-NN proxy.

Planning rates per vCPU:

| Case | Rate | When |
|---|---|---|
| Pessimistic | **0.3 M pts/s** | PDAL with hag_delaunay |
| Central | **0.5 M pts/s** | measured proxy |
| Optimistic | **1.0 M pts/s** | lean pipeline that is decode-bound, e.g. `filters.hag_dem` against a 1 m DEM, or c7a/c8g cores, which are faster than this sandbox) |

### Wall-clock for all three states

Inputs:
- Workload: P = 2.0 × 10¹² points.
- Parallel efficiency: η = 0.85 for the tail and stragglers [estimate].
- CPU-hours = P / rate / 3600:
  - 0.3 M pts/s → 2.0e12 / 0.3e6 / 3600 = **1,852 vCPU-h**
  - 0.5 M pts/s → 2.0e12 / 0.5e6 / 3600 = **1,111 vCPU-h**
  - 1.0 M pts/s → 2.0e12 / 1.0e6 / 3600 = **556 vCPU-h**

Wall-clock = vCPU-h / (N × 0.85):

| vCPUs N | 0.3 M/s | **0.5 M/s** | 1.0 M/s |
|---|---|---|---|
| 16 | 1852 / 13.6 = **136 h (5.7 d)** | 1111 / 13.6 = **82 h (3.4 d)** | 556 / 13.6 = **41 h** |
| 64 | 1852 / 54.4 = **34 h** | 1111 / 54.4 = **20 h** | 556 / 54.4 = **10 h** |
| 192 | 1852 / 163 = **11.3 h** | 1111 / 163 = **6.8 h** | 556 / 163 = **3.4 h** |

The workload range of 1.65–2.3 T points moves each cell by −18% to +15%.

### Network that this CPU rate actually consumes

- 192 vCPU × 0.5 M pts/s = 96 M pts/s.
- Raw LAZ: 96 M × 5.5 B = 528 MB/s ≈ **4.2 Gbps**.
- EPT: 96 M × 8.2 B ≈ **6.3 Gbps**.
- At the optimistic 1.0 M pts/s these double, to **8.4–12.6 Gbps**.
- For comparison, a 50 Gbps NIC could pull all 11 TB in 11e12 × 8 / 50e9 ≈ 30 min, and a
  200 Gbps NIC in about 7.5 min. The CPU needs about 7 h for the same data.

**Conclusion: network is not the bottleneck. CPU is.** Paying for c6in, c7gn or m6in at
200 Gbps buys idle NIC capacity.

### The other candidate bottlenecks

**S3 GET rate** [verified]
- S3 supports "at least … 5,500 GET/HEAD requests per second per partitioned Amazon S3
  prefix", and a single instance can reach up to 100 Gb/s.
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html
- Raw LAZ: about 90 k objects of roughly 300 MB each. At 96 M pts/s that is about 2 GET/s.
  Not a concern.
- EPT: about 50 k points per node, so 96 M pts/s needs about **1,900 GET/s**. That is under
  5,500/s per project prefix, but S3 may return 503 SlowDown while it scales.
- At a first-byte latency of 100–200 ms (the same S3 doc), sustaining that rate needs about
  200–400 requests in flight. PDAL `readers.ept` has a `threads` option.
- **EPT works, but raw LAZ is simpler and cheaper per byte** (5.5 vs 8.2 B/pt).
- EPT also lacks about one third of the newest coverage (the 555 G points above), so raw LAZ
  is needed regardless.

**Per-connection throughput** [verified]
- A single flow is capped at 5 Gbps.
- s5cmd reaches about 4.3 GB/s (40 Gbps) with `-dw 16`+ workers; the AWS CLI reaches about
  375 MB/s by default.
  https://www.doit.com/blog/save-time-and-money-on-s3-data-transfers-surpass-aws-cli-performance-by-up-to-80x
- At 0.5–1 GB/s needed, one s5cmd process or about 16–32 concurrent `GetObject` calls is
  enough.

**LAZ decompression** [measured]
- About 25–45% of per-point time in my benchmark (decode at 1.1–1.55 M/s, inside an
  end-to-end 0.5 M/s).
- It parallelises per tile. lazrs also has a multi-threaded per-chunk backend.

**PDAL single-threaded per pipeline**
- Not a problem if you run one pipeline per vCPU with xargs, GNU parallel or a Python
  process pool.
- The real constraint here is **memory**. PDAL's standard (non-stream) mode holds the whole
  tile.
- Dense VT QL1 tiles reach 81 M points [verified].
- At roughly 50–100 B/point in PDAL's in-memory layout [**unverified**], that is 4–8 GB per
  worker. 192 workers would need 0.8–1.5 TB, which is more than the 384 GB of a
  c7a/c7i/c8g.48xlarge.
- Mitigations, any one of which works:
  - Stream mode with `filters.hag_dem` against the project's 1 m DEM, which streams. Whether
    every project has a matching 1 m DEM is [unverified].
  - Chunked numpy/laspy processing as in my benchmark (about 30 B/pt for x, y, z, class and
    return number).
  - Fewer workers on m7i/r7i (768 GB / 1.5 TB).
  - Splitting tiles into 4 sub-tiles with a 20 m buffer.

**Disk**
- Not needed. Hold each tile in RAM (about 300 MB compressed per worker × 192 ≈ 58 GB, which
  fits in tmpfs on a 384 GB host), process it, then discard it.
- EBS (gp3) is only used for the OS and outputs. Instance-store NVMe (c6id/c7gd) is
  unnecessary.

---

## 4. Recommended architecture

1. **Region: us-west-2**, the same region as both buckets. Pass S3 traffic through a free S3
   gateway VPC endpoint so it avoids NAT and the internet gateway [standard AWS practice;
   endpoint pricing not re-checked].
2. **Compute: one c7a.48xlarge or c8g.48xlarge** (192 physical cores, 50 Gbps). Request it
   as a capacity-optimized spot request diversified across c7a, c7i, m7i and c8g .48xlarge,
   with on-demand fallback.
   - c7gn, c6in and m6in are not needed.
   - Graviton (c8g/c7gn) needs arm64 PDAL or laspy/lazrs builds. conda-forge publishes
     linux-aarch64 builds [**unverified** for PDAL's current version]. Pilot before
     committing.
3. **Work list.**
   - Per tile key, from the project `.vpc` files plus WESM newest-wins footprints.
   - Choose raw LAZ from `s3://usgs-lidar` with `--request-payer requester`.
   - Fall back to EPT, then to rockyweb, for projects missing from the raw bucket.
4. **Per tile, process and discard:**
   1. Stream the GET into RAM.
   2. Drop noise (class 7/18) and withheld points.
   3. Compute height above ground: from class-2 ground of the same tile with a buffer, or
      `hag_dem` with the same project's DEM.
   4. Convert units: some older projects are in **US survey feet**, so read the header units
      and convert before applying the 0.5/5 m thresholds.
   5. Transform x, y to **EPSG:5070** with pyproj.
   6. Floor-index each point into the **template lattice**: origin and pixel size read from
      the template raster, never assumed.
   7. Accumulate **integer counts** per cell. Example: n_first, n_all, n_first in each HAG bin
      (0.5–1, 1–2, 2–5, >5 m), max/p95 HAG sums or a histogram, and n_ground.
   8. Write a tiny per-tile sparse `.npz` of (cell_index, counts) to
      `s3://<own-bucket>/out/<project>/<tile>.npz`.
   - Counts are additive, so cells split across tile boundaries merge **exactly** by
     summation. Fractions and heights are derived only at the end.
5. **Checkpoint and resume.**
   - A tile is done when its output object exists, and the queue is all tiles minus those
     outputs. Spot interruption costs at most one in-flight tile per worker, about 2–3 min.
   - Poll IMDS `spot/instance-action` every 5 s; the notice comes two minutes ahead.
     https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-instance-termination-notices.html
   - On notice, stop taking new tiles.
6. **Merge** per-tile counts into one 30 m GeoTIFF per band on the template grid, then copy to
   the us-east-2 host. Size: 133,000 km² / 900 m² ≈ 148 M cells. 8 bands of uint16/float32
   come to about 2–5 GB uncompressed, about $0.10 at $0.02/GB.
7. **Tools.** s5cmd (`-numworkers 32`) or boto3 inside the workers. Use the AWS CLI only with
   `max_concurrent_requests` raised.

### Dollar estimate (us-west-2) [estimate from verified unit prices; spot is a snapshot]

| Item | Arithmetic | Cost |
|---|---|---|
| Compute, central (6.8 h), c7a.48xlarge spot | 6.8 × $1.70 | **≈$12** |
| Compute, central, on-demand | 6.8 × $9.85 | **≈$67** |
| Compute, pessimistic (11.3 h), on-demand | 11.3 × $9.85 | **≈$111** |
| Requester-pays GETs | 90 k × $0.0004/1k | ≈$0.04 |
| S3 → EC2 transfer in-region | free | $0 |
| EPT reads (if used for a third of the data), GETs | public bucket, not requester-pays | $0 to the reader |
| EBS gp3 200 GB for 1 day, plus output S3 | — | <$2 |
| Outputs to us-east-2 | about 5 GB × $0.02 | ≈$0.10 |
| **Total, full job** | allow one full re-run | **≈$25–50 spot; ≈$70–220 on-demand** |

**Pilot:**
- Contents: one tile from each distinct project, about 21 tiles, mainly to exercise CRS,
  units, datum and classification differences. Smaller version: one VT QL1 tile.
- Runtime: one 81 M-point tile ≈ 81e6 / 0.5e6 ≈ 160 s on one vCPU. 21 tiles on a c7i.4xlarge
  (16 vCPU) take about 5–10 min.
- Cost: with 1 h of setup, under $1 on-demand ($0.71/h) and about $0.25 on spot.

### The us-east-2 alternative (for comparison)

Reading 11–13 TB cross-region:
- Requester-pays raw LAZ: about $220–260 at $0.02/GB. EPT's transfer is borne by the bucket
  owner.
- NAT gateway processing if the host is in a private subnet: about $500–600 [unverified].
- The internet-gateway bandwidth caps above also apply.

Even on a free-to-read path, the GPU host's vCPU count sets the runtime: at 16 vCPU, about
3.4 days (table above). **Not recommended.**

---

## 5. Risks

1. **Requester-pays.**
   - In us-west-2 the only charge is GET fees (cents).
   - The risk is running it from us-east-2 or a laptop by mistake: $0.02/GB inter-region, or
     about $0.09/GB to the internet [internet rate unverified], on 11 TB.
   - Guard: an IAM policy or bucket-region check that refuses to run outside us-west-2, and an
     AWS Budgets alarm.
   - Anonymous requests are refused ("anonymous access … is not allowed").
2. **Spot interruptions.**
   - The c7a/c7i.48xlarge band is 10–15%; m7i and c8g.48xlarge are <5%; c6in is >20% (advisor
     snapshot).
   - With per-tile idempotent outputs, the loss is one tile per worker per interruption.
   - Diversify instance types and AZs. Do not use hibernation, which gives no two-minute
     warning.
3. **Mixed CRS and vertical datums.**
   - EPT is in EPSG:3857. Raw tiles are in native state-plane or UTM projections (e.g.
     EPSG:6589 for VT; ME is UTM 19N [ME unverified]), in metres or **US feet**, with
     NAVD88 on Geoid12B or 18.
   - Height above ground is a within-project difference, so the vertical datum cancels, but
     **only if ground and vegetation come from the same project**. Never take HAG against a
     DEM from a different acquisition or datum.
   - Horizontal: transform points, not rasters, straight into EPSG:5070.
4. **Leaf-on vs leaf-off.**
   - From the sibling's WESM table (**unverified by me**), these projects carry leaf-on risk:
     - ME_Eastern_B1/B2_2017
     - ME_CrownofMaine_B1/B2_2018
     - ME_MidCoast_2_2021
     - ME_SouthCoastal_1_2020
     - NH_Umbagog_2016
     - NY_NHGaps_2_D24
   - Together they are about 50% of Maine's newest-wins area.
   - Leaf-on canopy occludes the 0.5–5 m layer, so understory fractions are biased low in a
     way that follows project boundaries.
   - Mitigation: carry `project_id` and `leaf_on` as per-cell bands; consider an older
     leaf-off project where one exists.
5. **Density and quality-level heterogeneity.**
   - QL1 density is about 8+ pts/m² nominal; the sampled VT A23 tile is about 41 pts/m²
     [verified: 81.5 M points over 1.4 × 1.4 km]. QL2 is about 2+ pts/m².
   - Return fractions are less density-sensitive than counts, but low-density cells are noisy.
   - Emit `n_all` per cell and a minimum-count mask.
6. **Ground classification quality.**
   - USGS LPC usually classifies only ground (2), noise (7/18), water (9) and bridge (17/20).
     **Vegetation stays in class 1.** My sample: class 1 = 1.81 M, class 2 = 0.31 M [measured].
   - So "understory" must come from height above ground, not from class codes.
   - Sparse ground under dense conifer, and older ARRA-era projects, may misplace ground.
   - Run QA against the state nDSMs (VT 0.7 m, NH 2 m) and ORNL 1854.
7. **Project seams.**
   - A 30 m cell that straddles two projects must take its points from **one** project (the
     newest-wins footprint), or it mixes datums and seasons.
   - Assign each cell to a project before aggregating, and drop the other project's points in
     that cell.
8. **Registration (repo rules).**
   - BUG-0094 found that every Earth Engine layer was shifted about 21 m north-west. They had
     been requested on a lattice offset half a pixel from the source, and nearest-neighbour
     broke the four-way tie the same way every time
     (`docs/quality/bugs/BUG-0094-ee-downloads-half-pixel-tie-shift.md`).
   - Its preventive action **PA-0049 (extends PA-0007)** is drafted in BUG-0094 §8 and is
     "to be filed at close-out with CR-0034". It is **not yet a row in
     `docs/quality/PREVENTIVE_ACTIONS.md`** (grep 2026-10-05). It requires:
     - (a) resample on the source's own lattice, never on a half-pixel-offset parallel grid;
     - (b) check every new model layer for **content registration** against an independent
       reference (`diagnose_layer_registration.py` against `road_dist`) and record the result.
   - For this pipeline:
     - Aggregate points **directly into template cells**, computing cell index as
       floor((x − x0) / 30) from the template's own transform.
     - **Never** rasterize in EPSG:3857 or native CRS and then `gdalwarp` or reproject.
     - Never compute a fine CHM and resample it.
     - Run `diagnose_layer_registration.py` on each output band before any model reads it.
   - PA-0007 also applies when writing the GeoTIFF: corner vs centre convention.
9. **Coverage gap.**
   - About one third of the newest points are not in EPT. Raw-bucket completeness is
     **unverified**, and rockyweb throughput from AWS is unverified. My sandbox saw only
     0.27 MB/s, but that sandbox is proxy-limited and not representative.
   - Verify in the pilot.
10. **Change control.** Writing these rasters into `data/` and wiring them into the model needs
    a CR under the repo's CLAUDE.md §1. The acceptance check (the registration diagnostic) can
    be committed before approval (CR-0011 A3).

---

## Sources (all fetched or queried 2026-10-05)
- https://registry.opendata.aws/usgs-lidar/ and https://github.com/hobuinc/usgs-lidar
- https://usgs-lidar-public.s3.amazonaws.com/ (listing, `ept.json`, `ept-hierarchy`, `ept-data`)
- https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/Elevation/LPC/Projects/ (`.vpc` point counts, tile header)
- https://aws.amazon.com/s3/pricing/
- https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSDataTransfer/current/index.csv
- https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-west-2/index.csv (and the us-east-2 file)
- https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/us-west-2/index.csv
- https://website.spot.ec2.aws.a2z.com/spot.js and https://spot-bid-advisor.s3.amazonaws.com/spot-advisor-data.json
- https://docs.aws.amazon.com/ec2/latest/instancetypes/co.html
- https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-network-bandwidth.html
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/optimizing-performance.html
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/RequesterPaysBuckets.html
- https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-instance-termination-notices.html
- https://rapidlasso.de/laszip-lossless-compression-of-lidar-data/
- https://pdal.io/stages/filters.hag_delaunay.html
- https://www.doit.com/blog/save-time-and-money-on-s3-data-transfers-surpass-aws-cli-performance-by-up-to-80x
- https://vcgi.vermont.gov/data-and-programs/lidar-program
- https://granit24a.sr.unh.edu/image/rest/services/ImageServices/nDSM_NH/ImageServer
- https://doi.org/10.3334/ORNLDAAC/1854 (https://daac.ornl.gov/cgi-bin/dsviewer.pl?ds_id=1854)
