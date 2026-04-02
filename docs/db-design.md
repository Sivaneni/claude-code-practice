# Database & Cache Cross-Region Multi-AZ Design

Covers stateful PostgreSQL and Redis Cache running as StatefulSets in Kubernetes,
with gp3 EBS volumes that are AZ-scoped, across multiple Availability Zones and AWS regions.

---

## Table of Contents

- [PostgreSQL](#postgresql)
- [Redis Cache](#redis-cache)
- [Side-by-Side Comparison](#side-by-side-comparison)

---

# PostgreSQL

Stateful PostgreSQL running as a StatefulSet in Kubernetes, with gp3 EBS volumes
that are AZ-scoped, across multiple Availability Zones and AWS regions.

---

## The Core Constraint

```
EBS gp3  →  AZ-scoped  →  cannot cross AZ boundaries
             (volume lives in us-east-1a, pod MUST run in us-east-1a)

Cross-region →  no native EBS replication at all
```

This creates **two separate problems** that need separate solutions:

| Scope | Problem | Can gp3 help? |
|---|---|---|
| Multi-AZ (same region) | Pod scheduling + volume locality | Yes — one gp3 per AZ |
| Cross-region | Data durability + DR / active-active | No — needs a higher layer |

---

## Layer 1 — Multi-AZ Within a Region

### How it works

Each PostgreSQL pod owns **its own gp3 volume in its own AZ**. The StatefulSet
`volumeClaimTemplates` creates one PVC per pod. Setting `volumeBindingMode:
WaitForFirstConsumer` defers provisioning until the pod is scheduled, so the
volume is always created in the same AZ as the pod.

```
us-east-1
├── AZ-a  →  postgres-0  →  PVC-0  →  gp3 (us-east-1a)
├── AZ-b  →  postgres-1  →  PVC-1  →  gp3 (us-east-1b)
└── AZ-c  →  postgres-2  →  PVC-2  →  gp3 (us-east-1c)
```

### StorageClass — gp3 with topology awareness

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: gp3-topology
provisioner: ebs.csi.aws.com
parameters:
  type: gp3
  iops: "3000"
  throughput: "125"
  encrypted: "true"
volumeBindingMode: WaitForFirstConsumer   # critical — defers volume creation to scheduling time
allowVolumeExpansion: true
reclaimPolicy: Retain                     # never auto-delete production data
```

### StatefulSet — force pods across AZs

```yaml
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        app: postgres
```

---

## Layer 2 — Multi-AZ Replication (Database Layer)

gp3 does not replicate data between AZs — **PostgreSQL streaming replication does**.
A PostgreSQL operator manages primary election, failover, and standby synchronisation.

```
                    ┌─────────────────────────────────────┐
                    │             us-east-1                │
                    │                                      │
  ┌──────────────┐  │  ┌──────────┐   WAL stream           │
  │  pgBouncer   │──┼─▶│ Primary  │──────────────┐         │
  │ (conn pool)  │  │  │  AZ-a    │              ▼         │
  └──────────────┘  │  └──────────┘         ┌─────────┐   │
        │           │       │               │ Standby │   │
        │           │  DCS  │ (etcd /       │  AZ-b   │   │
        │           │  ┌────┴────┐          └─────────┘   │
        │           │  │ Patroni │               │         │
        │           │  └─────────┘          ┌─────────┐   │
        └───────────┼── failover promotes   │ Standby │   │
                    │                       │  AZ-c   │   │
                    │                       └─────────┘   │
                    └─────────────────────────────────────┘
```

### Recommended Operators

| Operator | Strengths | When to use |
|---|---|---|
| **CloudNativePG** | Kubernetes-native, CNCF sandbox, built-in backup, clean CRD API | Greenfield — best developer experience |
| **Zalando Postgres Operator** | Battle-tested, Patroni under the hood | Established Kubernetes setups |
| **Crunchy PGO** | Enterprise features, Red Hat backed | Regulated / enterprise environments |
| **Patroni (raw)** | Full control, no operator overhead | When you own the full complexity |

### CloudNativePG — 3-node cluster across 3 AZs

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgres-ha
spec:
  instances: 3

  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: DoNotSchedule

  storage:
    storageClass: gp3-topology
    size: 100Gi

  postgresql:
    parameters:
      synchronous_commit: "on"      # zero data loss within region
      max_wal_senders: "10"
      wal_level: logical            # enables cross-region logical replication

  backup:
    barmanObjectStore:
      destinationPath: s3://your-bucket/postgres-ha
      s3Credentials:
        accessKeyId:
          name: aws-creds
          key: ACCESS_KEY_ID
        secretAccessKey:
          name: aws-creds
          key: SECRET_ACCESS_KEY
      wal:
        compression: brotli
        maxParallel: 8
```

---

## Layer 3 — Cross-Region Design

gp3 volumes have no cross-region capability. Cross-region durability must be handled
at the database replication or managed-service layer. Four patterns address this,
each with different RPO and RTO characteristics.

---

### Pattern A — WAL Archiving to S3 (DR, RPO minutes)

Continuous WAL segments are shipped to an S3 bucket. S3 Cross-Region Replication (CRR)
copies them to a secondary region bucket, from which a warm standby can restore.

```
Region A (primary)
  PostgreSQL
    └── WAL-G / Barman ──▶ s3://bucket-us-east-1
                                    │
                          S3 CRR    │
                                    ▼
Region B (standby)      s3://bucket-us-west-2
  PostgreSQL
    └── WAL restore ◀──────────────┘
        (on-demand or warm standby)
```

| Attribute | Value |
|---|---|
| RPO | Minutes (last WAL archive interval) |
| RTO | 15–60 minutes (spin up cluster + restore WAL) |
| Cost | Low — S3 storage + standby compute only when needed |
| Best for | Pure DR, infrequent planned failover |

---

### Pattern B — PostgreSQL Logical Replication (Active Read Replica, RPO seconds)

The primary publishes all changes via logical decoding. A replica in a second region
subscribes and applies them asynchronously.

```
Region A                                Region B
┌──────────────────┐                   ┌──────────────────┐
│ Primary (writes) │                   │ Replica (reads)  │
│                  │   logical         │                  │
│  Publication:    │── replication ───▶│  Subscription:   │
│  ALL TABLES      │   (async WAL)     │  ALL TABLES      │
└──────────────────┘                   └──────────────────┘
```

| Attribute | Value |
|---|---|
| RPO | Seconds (async replication lag) |
| RTO | Minutes (promote replica, redirect writes) |
| Limitation | DDL changes not replicated automatically; sequences drift |
| Best for | Read scaling + DR, workloads tolerant of seconds of lag |

---

### Pattern C — Distributed PostgreSQL-Compatible Engine (Active-Active, RPO ~0)

Replace vanilla PostgreSQL with a geo-distributed consensus-based engine.
No EBS cross-region replication needed — the database protocol handles it.

```
         ┌─────────────┐
         │  Global LB  │
         └──────┬──────┘
    ┌───────────┼───────────┐
    ▼           ▼           ▼
Region A     Region B    Region C
YugabyteDB  YugabyteDB  YugabyteDB
  node         node        node
    │            │            │
    └────────────┴────────────┘
         Raft consensus
    (synchronous cross-region)
```

| Engine | Consensus | PostgreSQL Compat | Write Latency Penalty |
|---|---|---|---|
| **YugabyteDB** | Raft | High (YSQL) | ~50–150 ms cross-region |
| **CockroachDB** | Raft | Medium (pgwire) | ~50–150 ms cross-region |
| **Citus** | Coordinator–worker | High | Not designed for cross-region |
| **AlloyDB Omni** | Google Paxos | High | GCP only |

| Attribute | Value |
|---|---|
| RPO | 0 (synchronous consensus) |
| RTO | Seconds (automatic leader election) |
| Cost | High — 3× minimum compute + cross-region data transfer |
| Best for | Globally distributed writes, financial systems, zero data-loss tolerance |

---

### Pattern D — Managed Service Bypass (Aurora Global / Cloud Spanner)

Offload the cross-region problem entirely to a managed service.
K8s pods connect to it via a standard PostgreSQL endpoint.

```
K8s Cluster (us-east-1)               K8s Cluster (us-west-2)
  application pods                       application pods
       │                                       │
       ▼                                       ▼
Aurora Global DB (Primary)  ── <1s ──▶ Aurora Global DB (Replica)
  us-east-1 (writes)                     us-west-2 (reads)
```

| Attribute | Value |
|---|---|
| RPO | < 1 second (Aurora Global) |
| RTO | < 1 minute (managed automatic failover) |
| Trade-off | Vendor lock-in; reduced PostgreSQL internals control |
| Best for | Teams that want HA without operational complexity |

---

## Recommended Architecture by Use Case

| Use case | Recommended design |
|---|---|
| Single-region HA | CloudNativePG StatefulSet, 3 nodes across 3 AZs, gp3 per pod, `synchronous_commit=on` |
| DR only (RPO minutes) | + WAL-G to S3 with cross-region replication. Warm standby restored from WAL in Region B |
| DR + read offload (RPO seconds) | + Logical replication to Region B read replica. Promote replica on failover |
| Active-active (RPO ~0) | YugabyteDB or CockroachDB (replace Postgres engine), or Aurora Global Database (managed) |
| Regulated / BCDR | WAL-G S3 + Aurora Global standby. Test restore quarterly |

---

## Decision Tree

```
Do you need cross-region?
│
├── No  →  CloudNativePG 3-node, 3 AZs, gp3, synchronous_commit=on
│                                    Done.
│
└── Yes
    │
    ├── RPO > 5 min acceptable?
    │    └── Yes  →  WAL-G to cross-region S3  (cheapest)
    │
    ├── RPO seconds OK, reads in Region B?
    │    └── Yes  →  Logical replication to Region B cluster
    │
    ├── Need active-active writes in both regions?
    │    ├── Can change DB engine?
    │    │    ├── Yes  →  YugabyteDB / CockroachDB
    │    │    └── No   →  Aurora Global Database
    │    │
    │    └── Must stay self-managed K8s Postgres?
    │         └── Logical replication + application-level conflict resolution
    │                      (last-write-wins, CRDTs, or partition writes by region)
    │
    └── RPO = 0, RTO < 30s, strict PostgreSQL compat?
         └── Aurora Global Database  (accept managed service trade-off)
```

---

## What NOT to Do

| Temptation | Why it fails |
|---|---|
| Stretch a single StatefulSet across regions | Network latency kills PostgreSQL sync replication; DCS split-brain risk |
| Use a `ReadWriteMany` volume (EFS / NFS) for Postgres | PostgreSQL requires exclusive lock on the data directory — shared filesystems cause corruption |
| Copy EBS snapshots cross-region as live replication | Snapshots are crash-consistent point-in-time, not streaming — RPO equals the snapshot interval |
| Run Ceph/Rook across regions | Cross-region Ceph replication latency makes it impractical for synchronous I/O |
| Trust gp3 multi-attach for HA | gp3 multi-attach is not supported; even `io2` multi-attach is only for clustered filesystems |

---

## Key Principle

> **gp3 is the right choice for per-pod local storage within a region** — it is fast,
> predictable, and cost-effective. Cross-region durability must be handled one layer up,
> at the database replication or managed-service layer. There is no storage-level solution
> that satisfies both constraints simultaneously without moving to a geo-distributed
> database engine.

---

# Redis Cache

Redis shares the same Kubernetes / AZ-scoped gp3 mechanics as PostgreSQL, but its
nature as a cache fundamentally changes the design priorities.

---

## What's the Same as PostgreSQL

- **EBS gp3 is still AZ-scoped** — same `WaitForFirstConsumer` StorageClass trick applies if persistence is enabled
- **StatefulSet + `topologySpreadConstraints`** — same pattern to spread pods across AZs
- **Cross-region EBS replication** — still does not exist; still needs a layer above storage

---

## What's Fundamentally Different

```
PostgreSQL                          Redis Cache
──────────────────────────────────  ──────────────────────────────────
Source of truth                     Derived data (from DB or compute)
Data loss = catastrophic            Cold cache = acceptable (repopulate)
Must persist to disk                Persistence often optional
RPO must be near zero               RPO can be high (warm up again)
Cross-region sync is hard           Per-region independent caches often fine
```

The key difference — **cache data can be repopulated from the source of truth** —
changes almost every design decision downstream.

---

## Volume Strategy — Choose Based on Persistence Mode

Unlike PostgreSQL, Redis gives you a choice of persistence. The volume type follows
directly from that choice.

| Redis Mode | Volume needed | Use case |
|---|---|---|
| **No persistence** (pure cache) | `emptyDir` — no PVC at all | Session cache, rate limiting, ephemeral data |
| **RDB snapshots** | gp3 — small, infrequent writes | Cache warm-up on restart, soft durability |
| **AOF** (Append Only File) | gp3 — higher IOPS, continuous writes | Near-durable cache, counters, leaderboards |
| **RDB + AOF** | gp3 — largest footprint | Treat Redis as a soft database |

For a pure cache the right answer is usually **emptyDir** — a pod restart means a
cold cache, not a data loss event:

```yaml
volumes:
  - name: redis-data
    emptyDir: {}          # pod restart = cold cache, repopulate from DB
```

Only use gp3 PVCs when Redis holds data that cannot be reconstructed cheaply
(distributed locks, rate-limit counters, global sessions).

---

## Layer 1 — Multi-AZ Within a Region

### Option A — Redis Sentinel (simple HA, 3 nodes)

Best for single-dataset workloads that need automatic failover without sharding.

```
AZ-a: Redis Primary  ──────┐
AZ-b: Redis Replica  ─── Sentinel monitors + promotes on failure
AZ-c: Redis Replica        └── Clients connect via Sentinel endpoint
```

- Handles single-node failure and full AZ failure
- Clients need Sentinel-aware connection (all major Redis clients support this)
- No sharding — single dataset, vertical scaling only

### Option B — Redis Cluster (sharded HA, 6+ nodes)

Best for large datasets or high-throughput workloads that need horizontal scaling.

```
AZ-a: Primary shard-1  ←── replica ──▶  AZ-b: Replica shard-1
AZ-b: Primary shard-2  ←── replica ──▶  AZ-c: Replica shard-2
AZ-c: Primary shard-3  ←── replica ──▶  AZ-a: Replica shard-3
```

- Each shard has a primary in one AZ and a replica in another
- Automatic failover per shard independently
- Data hash-slotted across shards — horizontal scaling
- Clients must be cluster-aware

```yaml
# Bitnami redis-cluster Helm values
cluster:
  enabled: true
  slaveCount: 1                   # 1 replica per primary shard

replica:
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: topology.kubernetes.io/zone
      whenUnsatisfiable: DoNotSchedule
      labelSelector:
        matchLabels:
          app: redis-cluster
```

---

## Layer 2 — Cross-Region Design

### Default Approach: Independent Caches per Region (recommended for most teams)

```
Region A                              Region B
┌──────────────────┐                 ┌──────────────────┐
│  Redis Cluster   │                 │  Redis Cluster   │
│  (its own data)  │                 │  (its own data)  │
└──────────────────┘                 └──────────────────┘
        │                                     │
        ▼                                     ▼
  Cache miss → DB replica              Cache miss → DB replica
  Cache warms independently            Cache warms independently
```

- Each region's cache warms up on its own from the local database replica
- A cache miss is slightly slower, not catastrophic
- No cross-region replication complexity
- **This is the right choice for 90% of cache workloads**

---

### When Cross-Region Cache Consistency Is Actually Required

Only these scenarios justify cross-region Redis replication:

| Scenario | Why cross-region matters |
|---|---|
| **Distributed rate limiting** | `user:X:requests` must be global, not per-region |
| **Global session store** | User logs in Region A, next request hits Region B |
| **Distributed locks** | Two regions must not both acquire the same lock simultaneously |
| **Real-time leaderboards** | Global score must be consistent everywhere |

---

### Pattern A — ElastiCache Global Datastore (managed, RPO seconds)

```
Region A (primary)                    Region B (secondary)
ElastiCache Redis ── async repl ──▶  ElastiCache Redis
  (reads + writes)                     (reads only)
        │                                     │
        └───── promote on failure ────────────┘
```

| Attribute | Value |
|---|---|
| RPO | Sub-second replication lag |
| RTO | ~1 minute (managed automatic failover) |
| Cost | Higher than self-managed; no operational overhead |
| Best for | AWS-native teams, global sessions, rate limiting |

---

### Pattern B — Redis Enterprise Active-Active (RPO ~0, CRDTs)

```
Region A                                Region B
Redis Enterprise ◀──── CRDT sync ────▶ Redis Enterprise
  (reads + writes)                       (reads + writes)
```

- Uses CRDTs (Conflict-free Replicated Data Types) for automatic conflict resolution
- True active-active — writes accepted in both regions simultaneously
- Counters, sets, and sorted sets merge automatically
- Trade-off: commercial license required; CRDT semantics differ from standard Redis

| Attribute | Value |
|---|---|
| RPO | ~0 (synchronous within region, async cross-region with CRDT merge) |
| RTO | Seconds (no promotion needed — both regions already active) |
| Best for | Global rate limiting, leaderboards, financial counters |

---

### Pattern C — KeyDB Active-Active (open-source option)

```
Region A                                Region B
KeyDB node ◀──── bidirectional ───────▶ KeyDB node
  (reads + writes)                       (reads + writes)
```

- Open-source Redis fork with built-in active-active multi-master replication
- No commercial license required
- Less battle-tested than Redis Enterprise at large scale
- Compatible with most Redis clients

| Attribute | Value |
|---|---|
| RPO | Seconds (async bidirectional replication) |
| RTO | Seconds (both sides already active) |
| Best for | Teams needing active-active without enterprise cost |

---

## Decision Tree for Redis

```
Is Redis holding data you cannot reconstruct cheaply?
│
├── No (pure cache — can repopulate from DB)
│    │
│    ├── Need HA across AZs?
│    │    ├── Yes → Redis Sentinel or Cluster, emptyDir volumes
│    │    └── No  → Single Redis, emptyDir, accept cold start on pod restart
│    │
│    └── Need cross-region?
│         └── Independent cache per region — cache misses hit local DB replica
│                                            Done. (simplest, recommended)
│
└── Yes (sessions, locks, counters, leaderboards — cannot lose this data)
     │
     ├── Single region only?
     │    └── Redis Sentinel / Cluster + gp3 PVC + AOF persistence
     │
     └── Cross-region required?
          │
          ├── AWS managed OK?
          │    └── ElastiCache Global Datastore  (easiest path)
          │
          ├── Need active-active writes in both regions?
          │    ├── Commercial license acceptable?
          │    │    └── Redis Enterprise Active-Active (CRDTs)
          │    └── Open source only?
          │         └── KeyDB  (less mature, no license cost)
          │
          └── Rate limiting / counters only?
               └── Accept eventual consistency — allow slight over-counting
                   at the region boundary, correct in aggregate
```

---

## What NOT to Do

| Temptation | Why it fails |
|---|---|
| Use gp3 PVC for a pure cache | Wasted cost and IOPS — emptyDir is faster and free |
| Stretch Redis Cluster across regions | Cross-region gossip latency causes cluster instability and false failures |
| Use Redis as a primary database cross-region | No ACID guarantees, CRDT semantics are not SQL semantics |
| Share one Redis instance across regions via VPC peering | Latency spikes cause timeouts; a network partition splits the cluster |
| Use NFS / EFS as Redis persistence volume | Sequential write performance is too poor for AOF; causes replication lag |

---

## Key Principle

> **A cold cache is not a data loss event.** Start with independent Redis clusters
> per region using `emptyDir` volumes. Only add persistence (gp3 + AOF) when Redis
> holds data that cannot be reconstructed from the database. Only add cross-region
> replication when you have provably global state — rate limits, distributed locks,
> or sessions — that must be consistent across regions.

---

# Side-by-Side Comparison

| Dimension | PostgreSQL | Redis Cache |
|---|---|---|
| **Role** | Source of truth | Derived / accelerator layer |
| **Data loss tolerance** | Zero — catastrophic | Usually acceptable — repopulate from DB |
| **Volume type** | gp3 PVC — always required | `emptyDir` usually sufficient; gp3 only for durable state |
| **Persistence** | Always on (WAL) | Optional — choose RDB, AOF, or none |
| **Multi-AZ tool** | Patroni / CloudNativePG operator | Redis Sentinel (simple) or Redis Cluster (sharded) |
| **Cross-region default** | Must replicate data — RPO drives choice | Independent caches per region — 90% of cases |
| **Cross-region sync needed** | Always | Only for global state (sessions, locks, rate limits) |
| **Managed cross-region (AWS)** | Aurora Global Database | ElastiCache Global Datastore |
| **Open-source cross-region** | Logical replication / YugabyteDB | KeyDB / Redis Enterprise (paid) |
| **RPO requirement** | Near zero | Minutes to hours usually acceptable |
| **Active-active complexity** | Very high (conflict resolution at DB layer) | Moderate (CRDTs handle most conflict types) |
