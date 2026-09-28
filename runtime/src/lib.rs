use rusqlite::{params, Connection, OptionalExtension};
use serde::{de::DeserializeOwned, Deserialize, Deserializer, Serialize};
use std::collections::{BTreeMap, HashMap, HashSet};
use std::ffi::{c_char, CString};
use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::Path;
use std::slice;
use std::str;
use std::sync::Mutex;
use unicode_normalization::UnicodeNormalization;

const CONTRACT_VERSION: &str = "marco-runtime.v1";
const NORMALIZATION_PROFILE: &str = "NFKC-UCD16.0.0+PY-RE-WHITESPACE-v1";
const MAX_INPUT_BYTES: usize = 1024 * 1024;
const MAX_OUTPUT_BYTES: usize = 4 * 1024 * 1024;
const CORRECTION_THRESHOLD: i64 = 3;
const MAX_ROUTE_BIAS: f64 = 0.10;
const UNRESOLVED_WARNING: &str = "no_grounded_deterministic_translation";

#[repr(i32)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Status {
    Ok = 0,
    InvalidArgument = 1,
    InputTooLarge = 2,
    InvalidUtf8 = 3,
    InvalidJson = 4,
    UnsupportedContract = 5,
    InvalidRequest = 6,
    UnsupportedStoreVersion = 7,
    IncompatibleStore = 8,
    StorageError = 9,
    NotFound = 10,
    InvalidState = 11,
    OutputTooLarge = 12,
    InternalError = 13,
}
#[derive(Debug)]
enum RuntimeError {
    Sqlite,
    UnsupportedStoreVersion,
    IncompatibleStore,
    NotFound,
    InvalidState,
    InvalidRequest,
}
impl From<rusqlite::Error> for RuntimeError {
    fn from(_: rusqlite::Error) -> Self {
        Self::Sqlite
    }
}
impl RuntimeError {
    fn status(&self) -> Status {
        match self {
            Self::Sqlite => Status::StorageError,
            Self::UnsupportedStoreVersion => Status::UnsupportedStoreVersion,
            Self::IncompatibleStore => Status::IncompatibleStore,
            Self::NotFound => Status::NotFound,
            Self::InvalidState => Status::InvalidState,
            Self::InvalidRequest => Status::InvalidRequest,
        }
    }
}
fn deserialize_required_option<'de, D, T>(d: D) -> Result<Option<T>, D::Error>
where
    D: Deserializer<'de>,
    T: Deserialize<'de>,
{
    Option::<T>::deserialize(d)
}

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct TranslationRequest {
    pub text: String,
    pub source_language: String,
    pub target_language: String,
    #[serde(deserialize_with = "deserialize_required_option")]
    pub domain: Option<String>,
    pub style: String,
    #[serde(deserialize_with = "deserialize_required_option")]
    pub session_id: Option<String>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct TermDecision {
    pub source: String,
    pub concept: String,
    pub target: String,
    pub confidence: f64,
    pub layer: String,
    pub evidence: Vec<String>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct SemanticFrame {
    pub source_language: String,
    pub target_language: String,
    pub source_text: String,
    #[serde(deserialize_with = "deserialize_required_option")]
    pub domain: Option<String>,
    pub intent: String,
    pub style: String,
    pub terms: Vec<TermDecision>,
    #[serde(deserialize_with = "deserialize_required_option")]
    pub template: Option<String>,
    pub slots: BTreeMap<String, String>,
    pub unresolved: Vec<String>,
    pub confidence: f64,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct TranslationResult {
    pub source_text: String,
    pub translated_text: String,
    pub path: String,
    pub confidence: f64,
    #[serde(deserialize_with = "deserialize_required_option")]
    pub frame: Option<SemanticFrame>,
    pub warnings: Vec<String>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct CorrectionReceipt {
    pub source_text: String,
    pub corrected_text: String,
    pub tm_written: bool,
    #[serde(deserialize_with = "deserialize_required_option")]
    pub proposal_id: Option<String>,
    #[serde(deserialize_with = "deserialize_required_option")]
    pub proposal_status: Option<String>,
}
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq)]
#[serde(deny_unknown_fields)]
struct OverlayProposal {
    pub id: String,
    #[serde(rename = "type")]
    pub proposal_type: String,
    pub source_language: String,
    pub target_language: String,
    pub domain: Option<String>,
    pub source: String,
    pub target: String,
    pub evidence_count: i64,
    pub status: String,
}
fn domain_or_empty(domain: Option<&str>) -> &str {
    domain.unwrap_or("")
}
fn python_regex_whitespace(ch: char) -> bool {
    matches!(ch,'\u{0009}'..='\u{000d}'|'\u{001c}'..='\u{0020}'|'\u{0085}'|'\u{00a0}'|'\u{1680}'|'\u{2000}'..='\u{200a}'|'\u{2028}'|'\u{2029}'|'\u{202f}'|'\u{205f}'|'\u{3000}')
}
fn normalize_text(input: &str) -> String {
    let value: String = input.nfkc().collect();
    let mut output = String::with_capacity(value.len());
    let mut pending = false;
    for ch in value.chars() {
        if python_regex_whitespace(ch) {
            pending = !output.is_empty();
        } else {
            if pending {
                output.push(' ');
            }
            output.push(ch);
            pending = false;
        }
    }
    output
}

#[derive(Clone)]
struct Column {
    name: &'static str,
    kind: &'static str,
    not_null: i64,
    pk: i64,
}
fn columns(table: &str) -> Option<&'static [Column]> {
    use Column as C;
    const TM: &[C] = &[
        C {
            name: "source_language",
            kind: "TEXT",
            not_null: 1,
            pk: 1,
        },
        C {
            name: "target_language",
            kind: "TEXT",
            not_null: 1,
            pk: 2,
        },
        C {
            name: "domain",
            kind: "TEXT",
            not_null: 1,
            pk: 3,
        },
        C {
            name: "source_text",
            kind: "TEXT",
            not_null: 1,
            pk: 4,
        },
        C {
            name: "target_text",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "origin",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
    ];
    const TERM: &[C] = &[
        C {
            name: "source_language",
            kind: "TEXT",
            not_null: 1,
            pk: 1,
        },
        C {
            name: "target_language",
            kind: "TEXT",
            not_null: 1,
            pk: 2,
        },
        C {
            name: "domain",
            kind: "TEXT",
            not_null: 1,
            pk: 3,
        },
        C {
            name: "source",
            kind: "TEXT",
            not_null: 1,
            pk: 4,
        },
        C {
            name: "concept",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "target",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "confidence",
            kind: "REAL",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "origin",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "active",
            kind: "INTEGER",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "created_at",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "updated_at",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
    ];
    const CORRECTIONS: &[C] = &[
        C {
            name: "source_language",
            kind: "TEXT",
            not_null: 1,
            pk: 1,
        },
        C {
            name: "target_language",
            kind: "TEXT",
            not_null: 1,
            pk: 2,
        },
        C {
            name: "domain",
            kind: "TEXT",
            not_null: 1,
            pk: 3,
        },
        C {
            name: "source_text",
            kind: "TEXT",
            not_null: 1,
            pk: 4,
        },
        C {
            name: "target_text",
            kind: "TEXT",
            not_null: 1,
            pk: 5,
        },
        C {
            name: "count",
            kind: "INTEGER",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "last_generated",
            kind: "TEXT",
            not_null: 0,
            pk: 0,
        },
        C {
            name: "first_seen",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "last_seen",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
    ];
    const PROPOSALS: &[C] = &[
        C {
            name: "id",
            kind: "TEXT",
            not_null: 0,
            pk: 1,
        },
        C {
            name: "type",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "source_language",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "target_language",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "domain",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "source",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "target",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "evidence_count",
            kind: "INTEGER",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "status",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "created_at",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "updated_at",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
    ];
    const ROUTING: &[C] = &[
        C {
            name: "domain",
            kind: "TEXT",
            not_null: 1,
            pk: 1,
        },
        C {
            name: "candidate",
            kind: "TEXT",
            not_null: 1,
            pk: 2,
        },
        C {
            name: "weight",
            kind: "REAL",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "updated_at",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
    ];
    const EVENTS: &[C] = &[
        C {
            name: "id",
            kind: "TEXT",
            not_null: 0,
            pk: 1,
        },
        C {
            name: "domain",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "candidate",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "before_weight",
            kind: "REAL",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "after_weight",
            kind: "REAL",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "delta",
            kind: "REAL",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "reason",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "reverted",
            kind: "INTEGER",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "created_at",
            kind: "TEXT",
            not_null: 1,
            pk: 0,
        },
        C {
            name: "reverted_at",
            kind: "TEXT",
            not_null: 0,
            pk: 0,
        },
    ];
    match table {
        "tm" => Some(TM),
        "terminology" => Some(TERM),
        "corrections" => Some(CORRECTIONS),
        "overlay_proposals" => Some(PROPOSALS),
        "routing_weights" => Some(ROUTING),
        "routing_weight_events" => Some(EVENTS),
        _ => None,
    }
}
const SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS tm(source_language TEXT NOT NULL,target_language TEXT NOT NULL,domain TEXT NOT NULL DEFAULT '',source_text TEXT NOT NULL,target_text TEXT NOT NULL,origin TEXT NOT NULL DEFAULT 'observed',PRIMARY KEY(source_language,target_language,domain,source_text));
CREATE TABLE IF NOT EXISTS terminology(source_language TEXT NOT NULL,target_language TEXT NOT NULL,domain TEXT NOT NULL DEFAULT '',source TEXT NOT NULL,concept TEXT NOT NULL,target TEXT NOT NULL,confidence REAL NOT NULL,origin TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(source_language,target_language,domain,source));
CREATE TABLE IF NOT EXISTS corrections(source_language TEXT NOT NULL,target_language TEXT NOT NULL,domain TEXT NOT NULL DEFAULT '',source_text TEXT NOT NULL,target_text TEXT NOT NULL,count INTEGER NOT NULL,last_generated TEXT,first_seen TEXT NOT NULL,last_seen TEXT NOT NULL,PRIMARY KEY(source_language,target_language,domain,source_text,target_text));
CREATE TABLE IF NOT EXISTS overlay_proposals(id TEXT PRIMARY KEY,type TEXT NOT NULL,source_language TEXT NOT NULL,target_language TEXT NOT NULL,domain TEXT NOT NULL DEFAULT '',source TEXT NOT NULL,target TEXT NOT NULL,evidence_count INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(type,source_language,target_language,domain,source,target));
CREATE TABLE IF NOT EXISTS routing_weights(domain TEXT NOT NULL DEFAULT '',candidate TEXT NOT NULL,weight REAL NOT NULL,updated_at TEXT NOT NULL,PRIMARY KEY(domain,candidate));
CREATE TABLE IF NOT EXISTS routing_weight_events(id TEXT PRIMARY KEY,domain TEXT NOT NULL DEFAULT '',candidate TEXT NOT NULL,before_weight REAL NOT NULL,after_weight REAL NOT NULL,delta REAL NOT NULL,reason TEXT NOT NULL,reverted INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL,reverted_at TEXT);
"#;
fn table_exists(db: &Connection, table: &str) -> rusqlite::Result<bool> {
    let n: i64 = db.query_row(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?1",
        [table],
        |r| r.get(0),
    )?;
    Ok(n != 0)
}
fn validate_table(db: &Connection, table: &str) -> Result<(), RuntimeError> {
    let expected = columns(table).ok_or(RuntimeError::IncompatibleStore)?;
    let mut s = db.prepare(&format!("PRAGMA table_info({table})"))?;
    let actual = s
        .query_map([], |r| {
            Ok((
                r.get::<_, String>(1)?,
                r.get::<_, String>(2)?,
                r.get::<_, i64>(3)?,
                r.get::<_, i64>(5)?,
            ))
        })?
        .collect::<Result<Vec<_>, _>>()?;
    if actual.len() != expected.len()
        || actual.iter().zip(expected).any(|(a, e)| {
            a.0 != e.name || a.1.to_ascii_uppercase() != e.kind || a.2 != e.not_null || a.3 != e.pk
        })
    {
        return Err(RuntimeError::IncompatibleStore);
    }
    if table == "overlay_proposals" {
        let mut indexes = db.prepare("PRAGMA index_list(overlay_proposals)")?;
        let unique_indexes = indexes
            .query_map([], |row| {
                Ok((row.get::<_, String>(1)?, row.get::<_, i64>(2)?))
            })?
            .collect::<Result<Vec<_>, _>>()?
            .into_iter()
            .filter(|(_, unique)| *unique != 0)
            .map(|(name, _)| name)
            .collect::<Vec<_>>();
        let expected_key = [
            "type",
            "source_language",
            "target_language",
            "domain",
            "source",
            "target",
        ];
        let mut found = false;
        for name in unique_indexes {
            let mut columns =
                db.prepare("SELECT name FROM pragma_index_info(?1) ORDER BY seqno")?;
            let actual_key = columns
                .query_map([name], |row| row.get::<_, String>(0))?
                .collect::<Result<Vec<_>, _>>()?;
            if actual_key.iter().map(String::as_str).eq(expected_key) {
                found = true;
                break;
            }
        }
        if !found {
            return Err(RuntimeError::IncompatibleStore);
        }
    }
    Ok(())
}
fn initialize_schema(db: &mut Connection) -> Result<(), RuntimeError> {
    let tx = db.transaction()?;
    let version: i64 = tx.query_row("PRAGMA user_version", [], |r| r.get(0))?;
    if version != 0 && version != 1 {
        return Err(RuntimeError::UnsupportedStoreVersion);
    }
    for t in [
        "tm",
        "terminology",
        "corrections",
        "overlay_proposals",
        "routing_weights",
        "routing_weight_events",
    ] {
        if table_exists(&tx, t)? {
            validate_table(&tx, t)?;
        }
    }
    tx.execute_batch(SCHEMA)?;
    for t in [
        "tm",
        "terminology",
        "corrections",
        "overlay_proposals",
        "routing_weights",
        "routing_weight_events",
    ] {
        validate_table(&tx, t)?;
    }
    tx.pragma_update(None, "user_version", 1)?;
    tx.commit()?;
    Ok(())
}
fn now(db: &Connection) -> rusqlite::Result<String> {
    db.query_row(
        "SELECT strftime('%Y-%m-%dT%H:%M:%f+00:00','now')",
        [],
        |r| r.get(0),
    )
}
fn random_id(db: &Connection) -> rusqlite::Result<String> {
    db.query_row("SELECT lower(hex(randomblob(16)))", [], |r| r.get(0))
}

struct SqliteRuntimeStore {
    db: Connection,
}
impl SqliteRuntimeStore {
    fn open(path: impl AsRef<Path>) -> Result<Self, RuntimeError> {
        let mut db = Connection::open(path)?;
        initialize_schema(&mut db)?;
        Ok(Self { db })
    }
    fn lookup_tm(
        &self,
        sl: &str,
        tl: &str,
        domain: Option<&str>,
        text: &str,
    ) -> Result<Option<String>, RuntimeError> {
        Ok(self.db.query_row("SELECT target_text FROM tm WHERE source_language=?1 AND target_language=?2 AND domain=?3 AND source_text=?4",params![sl,tl,domain_or_empty(domain),text],|r|r.get(0)).optional()?)
    }
    fn put_tm(
        &self,
        sl: &str,
        tl: &str,
        domain: Option<&str>,
        source: &str,
        target: &str,
        origin: &str,
    ) -> Result<(), RuntimeError> {
        self.db.execute("INSERT INTO tm(source_language,target_language,domain,source_text,target_text,origin) VALUES(?1,?2,?3,?4,?5,?6) ON CONFLICT(source_language,target_language,domain,source_text) DO UPDATE SET target_text=excluded.target_text,origin=excluded.origin",params![sl,tl,domain_or_empty(domain),source,target,origin])?;
        Ok(())
    }
    fn add_terminology(
        &self,
        source: &str,
        target: &str,
        sl: &str,
        tl: &str,
        domain: Option<&str>,
        concept: &str,
        confidence: f64,
        origin: &str,
    ) -> Result<(), RuntimeError> {
        let source = source.trim();
        let target = target.trim();
        if source.is_empty() || target.is_empty() || !confidence.is_finite() {
            return Err(RuntimeError::InvalidRequest);
        }
        self.db.execute("INSERT INTO terminology(source_language,target_language,domain,source,concept,target,confidence,origin,active,created_at,updated_at) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,1,?9,?9) ON CONFLICT(source_language,target_language,domain,source) DO UPDATE SET concept=excluded.concept,target=excluded.target,confidence=excluded.confidence,origin=excluded.origin,active=1,updated_at=excluded.updated_at",params![sl,tl,domain_or_empty(domain),source,concept,target,confidence.clamp(0.0,1.0),origin,now(&self.db)?])?;
        Ok(())
    }
    fn disable_terminology(
        &self,
        source: &str,
        sl: &str,
        tl: &str,
        domain: Option<&str>,
    ) -> Result<(), RuntimeError> {
        self.db.execute("UPDATE terminology SET active=0,updated_at=?1 WHERE source_language=?2 AND target_language=?3 AND domain=?4 AND source=?5",params![now(&self.db)?,sl,tl,domain_or_empty(domain),source])?;
        Ok(())
    }
    fn resolve_terms(
        &self,
        text: &str,
        sl: &str,
        tl: &str,
        domain: Option<&str>,
    ) -> Result<Vec<TermDecision>, RuntimeError> {
        let mut s=self.db.prepare("SELECT source,concept,target,confidence,domain FROM terminology WHERE source_language=?1 AND target_language=?2 AND active=1 AND (domain='' OR domain=?3)")?;
        let mut rows = s
            .query_map(params![sl, tl, domain_or_empty(domain)], |r| {
                Ok((
                    r.get::<_, String>(0)?,
                    r.get::<_, String>(1)?,
                    r.get::<_, String>(2)?,
                    r.get::<_, f64>(3)?,
                    r.get::<_, String>(4)?,
                ))
            })?
            .collect::<Result<Vec<_>, _>>()?
            .into_iter()
            .filter(|r| text.contains(&r.0))
            .collect::<Vec<_>>();
        rows.sort_by(|a, b| {
            let x = a.0.cmp(&b.0).reverse();
            if x != std::cmp::Ordering::Equal {
                return x;
            }
            let ad = a.4 == domain_or_empty(domain) && !a.4.is_empty();
            let bd = b.4 == domain_or_empty(domain) && !b.4.is_empty();
            let x = ad.cmp(&bd).reverse();
            if x != std::cmp::Ordering::Equal {
                return x;
            }
            let x = a.0.chars().count().cmp(&b.0.chars().count()).reverse();
            if x != std::cmp::Ordering::Equal {
                return x;
            }
            a.3.total_cmp(&b.3).reverse()
        });
        let mut seen = HashSet::new();
        Ok(rows
            .into_iter()
            .filter_map(|(source, concept, target, confidence, _)| {
                seen.insert(source.clone()).then_some(TermDecision {
                    source,
                    concept,
                    target,
                    confidence,
                    layer: "user".into(),
                    evidence: Vec::new(),
                })
            })
            .collect())
    }
    fn record_correction(
        &mut self,
        source: &str,
        target: &str,
        sl: &str,
        tl: &str,
        domain: Option<&str>,
        generated: Option<&str>,
    ) -> Result<Option<OverlayProposal>, RuntimeError> {
        let source = source.trim();
        let target = target.trim();
        if source.is_empty() || target.is_empty() {
            return Err(RuntimeError::InvalidRequest);
        }
        let dom = domain_or_empty(domain).to_owned();
        let timestamp = now(&self.db)?;
        let tx = self.db.transaction()?;
        tx.execute("INSERT INTO corrections(source_language,target_language,domain,source_text,target_text,count,last_generated,first_seen,last_seen) VALUES(?1,?2,?3,?4,?5,1,?6,?7,?7) ON CONFLICT(source_language,target_language,domain,source_text,target_text) DO UPDATE SET count=count+1,last_generated=excluded.last_generated,last_seen=excluded.last_seen",params![sl,tl,dom,source,target,generated,timestamp])?;
        let count:i64=tx.query_row("SELECT count FROM corrections WHERE source_language=?1 AND target_language=?2 AND domain=?3 AND source_text=?4 AND target_text=?5",params![sl,tl,dom,source,target],|r|r.get(0))?;
        let proposal = if count >= CORRECTION_THRESHOLD {
            tx.execute("INSERT INTO overlay_proposals(id,type,source_language,target_language,domain,source,target,evidence_count,status,created_at,updated_at) VALUES(lower(hex(randomblob(16))),'ADD_USER_PHRASE',?1,?2,?3,?4,?5,?6,'pending',?7,?7) ON CONFLICT(type,source_language,target_language,domain,source,target) DO UPDATE SET evidence_count=excluded.evidence_count,updated_at=excluded.updated_at",params![sl,tl,dom,source,target,count,timestamp])?;
            Some(tx.query_row("SELECT id,type,source_language,target_language,domain,source,target,evidence_count,status FROM overlay_proposals WHERE type='ADD_USER_PHRASE' AND source_language=?1 AND target_language=?2 AND domain=?3 AND source=?4 AND target=?5",params![sl,tl,dom,source,target],proposal_row)?)
        } else {
            None
        };
        tx.commit()?;
        Ok(proposal)
    }
    fn pending_proposals(&self) -> Result<Vec<OverlayProposal>, RuntimeError> {
        let mut s=self.db.prepare("SELECT id,type,source_language,target_language,domain,source,target,evidence_count,status FROM overlay_proposals WHERE status='pending' ORDER BY created_at,id")?;
        let rows = s
            .query_map([], proposal_row)?
            .collect::<Result<Vec<_>, _>>()?;
        Ok(rows)
    }
    fn proposal(&self, id: &str) -> Result<Option<OverlayProposal>, RuntimeError> {
        Ok(self.db.query_row("SELECT id,type,source_language,target_language,domain,source,target,evidence_count,status FROM overlay_proposals WHERE id=?1",[id],proposal_row).optional()?)
    }
    fn approve_proposal(&self, id: &str) -> Result<OverlayProposal, RuntimeError> {
        let p = self.proposal(id)?.ok_or(RuntimeError::NotFound)?;
        if p.status != "pending" {
            return Err(RuntimeError::InvalidState);
        }
        if p.proposal_type != "ADD_USER_PHRASE" {
            return Err(RuntimeError::InvalidRequest);
        }
        self.add_terminology(
            &p.source,
            &p.target,
            &p.source_language,
            &p.target_language,
            p.domain.as_deref(),
            "USER_PHRASE",
            1.0,
            "approved_repeated_correction",
        )?;
        self.db.execute(
            "UPDATE overlay_proposals SET status='accepted',updated_at=?1 WHERE id=?2",
            params![now(&self.db)?, id],
        )?;
        self.proposal(id)?.ok_or(RuntimeError::NotFound)
    }
    fn reject_proposal(&self, id: &str) -> Result<(), RuntimeError> {
        let status: Option<String> = self
            .db
            .query_row(
                "SELECT status FROM overlay_proposals WHERE id=?1",
                [id],
                |r| r.get(0),
            )
            .optional()?;
        let status = status.ok_or(RuntimeError::NotFound)?;
        if status != "pending" {
            return Err(RuntimeError::InvalidState);
        }
        self.db.execute(
            "UPDATE overlay_proposals SET status='rejected',updated_at=?1 WHERE id=?2",
            params![now(&self.db)?, id],
        )?;
        Ok(())
    }
    fn routing_weight(&self, domain: Option<&str>, candidate: &str) -> Result<f64, RuntimeError> {
        Ok(self
            .db
            .query_row(
                "SELECT weight FROM routing_weights WHERE domain=?1 AND candidate=?2",
                params![domain_or_empty(domain), candidate],
                |r| r.get(0),
            )
            .optional()?
            .unwrap_or(0.0))
    }
    fn adjust_routing_weight(
        &mut self,
        domain: Option<&str>,
        candidate: &str,
        delta: f64,
        reason: &str,
    ) -> Result<String, RuntimeError> {
        let candidate = candidate.trim();
        if candidate.is_empty() || reason.trim().is_empty() || !delta.is_finite() {
            return Err(RuntimeError::InvalidRequest);
        }
        let dom = domain_or_empty(domain).to_owned();
        let timestamp = now(&self.db)?;
        let event_id = random_id(&self.db)?;
        let tx = self.db.transaction()?;
        let before = route_weight(&tx, &dom, candidate)?;
        let after = (before + delta).clamp(-MAX_ROUTE_BIAS, MAX_ROUTE_BIAS);
        let actual = after - before;
        tx.execute("INSERT INTO routing_weights(domain,candidate,weight,updated_at) VALUES(?1,?2,?3,?4) ON CONFLICT(domain,candidate) DO UPDATE SET weight=excluded.weight,updated_at=excluded.updated_at",params![dom,candidate,after,timestamp])?;
        tx.execute("INSERT INTO routing_weight_events(id,domain,candidate,before_weight,after_weight,delta,reason,reverted,created_at) VALUES(?1,?2,?3,?4,?5,?6,?7,0,?8)",params![event_id,dom,candidate,before,after,actual,reason,timestamp])?;
        tx.commit()?;
        Ok(event_id)
    }
    fn rollback_routing_weight(&mut self, id: &str) -> Result<f64, RuntimeError> {
        let tx = self.db.transaction()?;
        let e = tx
            .query_row(
                "SELECT domain,candidate,delta,reverted FROM routing_weight_events WHERE id=?1",
                [id],
                |r| {
                    Ok((
                        r.get::<_, String>(0)?,
                        r.get::<_, String>(1)?,
                        r.get::<_, f64>(2)?,
                        r.get::<_, i64>(3)?,
                    ))
                },
            )
            .optional()?
            .ok_or(RuntimeError::NotFound)?;
        if e.3 != 0 {
            return Err(RuntimeError::InvalidState);
        }
        let current = route_weight(&tx, &e.0, &e.1)?;
        let restored = (current - e.2).clamp(-MAX_ROUTE_BIAS, MAX_ROUTE_BIAS);
        let timestamp = now(&tx)?;
        tx.execute(
            "UPDATE routing_weights SET weight=?1,updated_at=?2 WHERE domain=?3 AND candidate=?4",
            params![restored, timestamp, e.0, e.1],
        )?;
        tx.execute(
            "UPDATE routing_weight_events SET reverted=1,reverted_at=?1 WHERE id=?2",
            params![timestamp, id],
        )?;
        tx.commit()?;
        Ok(restored)
    }
}
fn proposal_row(r: &rusqlite::Row<'_>) -> rusqlite::Result<OverlayProposal> {
    let d: String = r.get(4)?;
    Ok(OverlayProposal {
        id: r.get(0)?,
        proposal_type: r.get(1)?,
        source_language: r.get(2)?,
        target_language: r.get(3)?,
        domain: if d.is_empty() { None } else { Some(d) },
        source: r.get(5)?,
        target: r.get(6)?,
        evidence_count: r.get(7)?,
        status: r.get(8)?,
    })
}
fn route_weight(db: &Connection, domain: &str, candidate: &str) -> rusqlite::Result<f64> {
    Ok(db
        .query_row(
            "SELECT weight FROM routing_weights WHERE domain=?1 AND candidate=?2",
            params![domain, candidate],
            |r| r.get(0),
        )
        .optional()?
        .unwrap_or(0.0))
}

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
struct SessionKey {
    sl: String,
    tl: String,
    domain: String,
    source: String,
}
#[derive(Default)]
struct SessionStateStore {
    bindings: HashMap<String, HashMap<SessionKey, TermDecision>>,
}
impl SessionStateStore {
    fn bind_entity(
        &mut self,
        session: &str,
        source: &str,
        target: &str,
        sl: &str,
        tl: &str,
        domain: Option<&str>,
        concept: &str,
    ) -> Result<(), RuntimeError> {
        let source = source.trim();
        let target = target.trim();
        if session.is_empty() || source.is_empty() || target.is_empty() {
            return Err(RuntimeError::InvalidRequest);
        }
        let key = SessionKey {
            sl: sl.into(),
            tl: tl.into(),
            domain: domain_or_empty(domain).into(),
            source: source.into(),
        };
        self.bindings.entry(session.into()).or_default().insert(
            key,
            TermDecision {
                source: source.into(),
                concept: concept.into(),
                target: target.into(),
                confidence: 1.0,
                layer: "session".into(),
                evidence: Vec::new(),
            },
        );
        Ok(())
    }
    fn unbind_entity(
        &mut self,
        session: &str,
        source: &str,
        sl: &str,
        tl: &str,
        domain: Option<&str>,
    ) {
        let empty = if let Some(bucket) = self.bindings.get_mut(session) {
            bucket.remove(&SessionKey {
                sl: sl.into(),
                tl: tl.into(),
                domain: domain_or_empty(domain).into(),
                source: source.into(),
            });
            bucket.is_empty()
        } else {
            false
        };
        if empty {
            self.bindings.remove(session);
        }
    }
    fn clear_session(&mut self, session: &str) {
        self.bindings.remove(session);
    }
    fn lookup_exact(
        &self,
        session: Option<&str>,
        sl: &str,
        tl: &str,
        domain: Option<&str>,
        text: &str,
    ) -> Option<String> {
        let bucket = self.bindings.get(session?)?;
        let exact = SessionKey {
            sl: sl.into(),
            tl: tl.into(),
            domain: domain_or_empty(domain).into(),
            source: text.into(),
        };
        bucket
            .get(&exact)
            .or_else(|| {
                bucket.get(&SessionKey {
                    domain: String::new(),
                    ..exact
                })
            })
            .map(|term| term.target.clone())
    }
    fn resolve_terms(
        &self,
        text: &str,
        sl: &str,
        tl: &str,
        domain: Option<&str>,
        session: Option<&str>,
    ) -> Vec<TermDecision> {
        let Some(bucket) = session.and_then(|s| self.bindings.get(s)) else {
            return Vec::new();
        };
        let mut rows = bucket
            .iter()
            .filter(|(key, _)| {
                key.sl == sl
                    && key.tl == tl
                    && (key.domain.is_empty() || key.domain == domain_or_empty(domain))
                    && text.contains(&key.source)
            })
            .map(|(key, term)| {
                (
                    key.domain == domain_or_empty(domain) && !key.domain.is_empty(),
                    key.source.chars().count(),
                    term.clone(),
                )
            })
            .collect::<Vec<_>>();
        rows.sort_by(|a, b| (a.0, a.1).cmp(&(b.0, b.1)).reverse());
        let mut seen = HashSet::new();
        rows.into_iter()
            .filter_map(|(_, _, term)| seen.insert(term.source.clone()).then_some(term))
            .collect()
    }
}

trait Resolver: Send {
    fn resolve(&self, request: &TranslationRequest, terms: Vec<TermDecision>) -> SemanticFrame;
}
trait NeuralRealizer: Send {
    fn realize(&mut self, frame: &SemanticFrame) -> Option<String>;
}
#[derive(Default)]
struct RuleRealizer;
impl RuleRealizer {
    fn realize(&self, frame: &SemanticFrame) -> Option<String> {
        if let Some(template) = &frame.template {
            let mut out = template.clone();
            for (name, value) in &frame.slots {
                out = out.replace(&format!("{{{name}}}"), value);
            }
            if out.contains('{') || out.contains('}') {
                return None;
            }
            return Some(out);
        }
        if frame.terms.len() == 1 && frame.terms[0].source == frame.source_text {
            return Some(frame.terms[0].target.clone());
        }
        None
    }
}
#[derive(Default)]
struct NullNeuralRealizer;
impl NeuralRealizer for NullNeuralRealizer {
    fn realize(&mut self, _: &SemanticFrame) -> Option<String> {
        None
    }
}

#[derive(Deserialize)]
struct FixtureDocument {
    contract_version: String,
    normalization_profile: String,
    cases: Vec<FixtureCase>,
}
#[derive(Deserialize)]
struct FixtureCase {
    request: TranslationRequest,
    expected: FixtureExpected,
}
#[derive(Deserialize)]
struct FixtureExpected {
    contract_version: String,
    result: TranslationResult,
}
#[derive(Clone, Debug, Eq, Hash, PartialEq)]
struct RequestKey {
    text: String,
    sl: String,
    tl: String,
    domain: Option<String>,
}
#[derive(Default)]
struct FixtureResolver {
    patterns: HashMap<RequestKey, SemanticFrame>,
}
impl FixtureResolver {
    fn new() -> Result<Self, Status> {
        let fixtures: FixtureDocument =
            serde_json::from_str(include_str!("../fixtures/conformance-v1.json"))
                .map_err(|_| Status::InternalError)?;
        if fixtures.contract_version != CONTRACT_VERSION
            || fixtures.normalization_profile != NORMALIZATION_PROFILE
        {
            return Err(Status::InternalError);
        }
        let mut patterns = HashMap::new();
        for case in fixtures.cases {
            if case.expected.contract_version != CONTRACT_VERSION {
                return Err(Status::InternalError);
            }
            if case.expected.result.path == "rule" {
                if let Some(frame) = case.expected.result.frame {
                    patterns.insert(
                        RequestKey {
                            text: normalize_text(&case.request.text),
                            sl: case.request.source_language,
                            tl: case.request.target_language,
                            domain: case.request.domain,
                        },
                        frame,
                    );
                }
            }
        }
        Ok(Self { patterns })
    }
}
impl Resolver for FixtureResolver {
    fn resolve(&self, request: &TranslationRequest, terms: Vec<TermDecision>) -> SemanticFrame {
        let key = RequestKey {
            text: request.text.clone(),
            sl: request.source_language.clone(),
            tl: request.target_language.clone(),
            domain: request.domain.clone(),
        };
        if let Some(mut frame) = self.patterns.get(&key).cloned() {
            let mut candidates = frame.terms;
            candidates.extend(terms);
            frame.terms = ordered_unique(candidates);
            if request.style != "neutral" {
                frame.style = request.style.clone();
            }
            return frame;
        }
        let terms = ordered_unique(terms);
        let covered = terms
            .iter()
            .flat_map(|t| t.source.chars())
            .collect::<HashSet<_>>();
        let unresolved = request
            .text
            .chars()
            .filter(|c| !python_regex_whitespace(*c) && !covered.contains(c))
            .map(|c| c.to_string())
            .collect::<Vec<_>>();
        let confidence = terms
            .iter()
            .map(|t| t.confidence)
            .reduce(f64::min)
            .unwrap_or(0.0);
        SemanticFrame {
            source_language: request.source_language.clone(),
            target_language: request.target_language.clone(),
            source_text: request.text.clone(),
            domain: request.domain.clone(),
            intent: "statement".into(),
            style: request.style.clone(),
            terms,
            template: None,
            slots: BTreeMap::new(),
            unresolved,
            confidence,
        }
    }
}
fn ordered_unique(mut terms: Vec<TermDecision>) -> Vec<TermDecision> {
    terms.sort_by(|a, b| {
        let x = a.source.cmp(&b.source).reverse();
        if x != std::cmp::Ordering::Equal {
            return x;
        }
        let priority = |s: &str| match s {
            "session" => 3,
            "user" => 2,
            "base" => 1,
            _ => 0,
        };
        let x = priority(&a.layer).cmp(&priority(&b.layer)).reverse();
        if x != std::cmp::Ordering::Equal {
            return x;
        }
        let x = a.confidence.total_cmp(&b.confidence).reverse();
        if x != std::cmp::Ordering::Equal {
            return x;
        }
        a.source
            .chars()
            .count()
            .cmp(&b.source.chars().count())
            .reverse()
    });
    let mut seen = HashSet::new();
    terms
        .into_iter()
        .filter(|t| seen.insert(t.source.clone()))
        .collect()
}

struct Runtime {
    store: SqliteRuntimeStore,
    sessions: SessionStateStore,
    resolver: Box<dyn Resolver>,
    rule: RuleRealizer,
    neural: Box<dyn NeuralRealizer>,
}
impl Runtime {
    fn open(path: impl AsRef<Path>) -> Result<Self, Status> {
        let store = SqliteRuntimeStore::open(path).map_err(|e| e.status())?;
        let resolver = Box::new(FixtureResolver::new()?);
        Ok(Self::with_parts(
            store,
            resolver,
            Box::<NullNeuralRealizer>::default(),
        ))
    }
    #[cfg(test)]
    fn open_with_parts(
        path: impl AsRef<Path>,
        resolver: Box<dyn Resolver>,
        neural: Box<dyn NeuralRealizer>,
    ) -> Result<Self, Status> {
        let store = SqliteRuntimeStore::open(path).map_err(|e| e.status())?;
        Ok(Self::with_parts(store, resolver, neural))
    }
    fn with_parts(
        store: SqliteRuntimeStore,
        resolver: Box<dyn Resolver>,
        neural: Box<dyn NeuralRealizer>,
    ) -> Self {
        Self {
            store,
            sessions: SessionStateStore::default(),
            resolver,
            rule: RuleRealizer,
            neural,
        }
    }
    fn translate(&mut self, mut request: TranslationRequest) -> Result<TranslationResult, Status> {
        request.text = normalize_text(&request.text);
        if let Some(hit) = self.sessions.lookup_exact(
            request.session_id.as_deref(),
            &request.source_language,
            &request.target_language,
            request.domain.as_deref(),
            &request.text,
        ) {
            return Ok(TranslationResult {
                source_text: request.text,
                translated_text: hit,
                path: "session".into(),
                confidence: 1.0,
                frame: None,
                warnings: Vec::new(),
            });
        }
        if let Some(hit) = self
            .store
            .lookup_tm(
                &request.source_language,
                &request.target_language,
                request.domain.as_deref(),
                &request.text,
            )
            .map_err(|e| e.status())?
        {
            return Ok(TranslationResult {
                source_text: request.text,
                translated_text: hit,
                path: "tm".into(),
                confidence: 1.0,
                frame: None,
                warnings: Vec::new(),
            });
        }
        let mut terms = self
            .store
            .resolve_terms(
                &request.text,
                &request.source_language,
                &request.target_language,
                request.domain.as_deref(),
            )
            .map_err(|e| e.status())?;
        terms.extend(self.sessions.resolve_terms(
            &request.text,
            &request.source_language,
            &request.target_language,
            request.domain.as_deref(),
            request.session_id.as_deref(),
        ));
        for term in &mut terms {
            let bias = self
                .store
                .routing_weight(request.domain.as_deref(), &term.concept)
                .map_err(|e| e.status())?;
            term.confidence = (term.confidence + bias).clamp(0.0, 1.0);
        }
        let frame = self.resolver.resolve(&request, terms);
        if let Some(text) = self.rule.realize(&frame) {
            return Ok(TranslationResult {
                source_text: request.text,
                translated_text: text,
                path: "rule".into(),
                confidence: frame.confidence,
                frame: Some(frame),
                warnings: Vec::new(),
            });
        }
        if frame.unresolved.is_empty() {
            if let Some(text) = self.neural.realize(&frame) {
                return Ok(TranslationResult {
                    source_text: request.text,
                    translated_text: text,
                    path: "neural-realizer".into(),
                    confidence: frame.confidence,
                    frame: Some(frame),
                    warnings: Vec::new(),
                });
            }
        }
        Ok(TranslationResult {
            source_text: request.text,
            translated_text: String::new(),
            path: "unresolved".into(),
            confidence: frame.confidence,
            frame: Some(frame),
            warnings: vec![UNRESOLVED_WARNING.into()],
        })
    }
    fn process_json(&mut self, input: &[u8]) -> Result<Vec<u8>, Status> {
        if input.len() > MAX_INPUT_BYTES {
            return Err(Status::InputTooLarge);
        }
        str::from_utf8(input).map_err(|_| Status::InvalidUtf8)?;
        let header: Header = serde_json::from_slice(input).map_err(|_| Status::InvalidJson)?;
        if header.contract_version != CONTRACT_VERSION {
            return Err(Status::UnsupportedContract);
        }
        match header.operation.as_str() {
            "translate" => {
                let c: Translate = decode(input)?;
                check(&c.contract_version, &c.operation, "translate")?;
                let result = self.translate(c.request)?;
                Self::respond(result)
            }
            "correct" => {
                let c: Correct = decode(input)?;
                check(&c.contract_version, &c.operation, "correct")?;
                let mut r = c.request;
                r.text = normalize_text(&r.text);
                let target = normalize_text(&c.corrected_text);
                if target.is_empty() {
                    return Err(Status::InvalidRequest);
                }
                self.store
                    .put_tm(
                        &r.source_language,
                        &r.target_language,
                        r.domain.as_deref(),
                        &r.text,
                        &target,
                        "user_correction",
                    )
                    .map_err(|e| e.status())?;
                let proposal = self
                    .store
                    .record_correction(
                        &r.text,
                        &target,
                        &r.source_language,
                        &r.target_language,
                        r.domain.as_deref(),
                        c.generated_text.as_deref(),
                    )
                    .map_err(|e| e.status())?;
                Self::respond(CorrectionReceipt {
                    source_text: r.text,
                    corrected_text: target,
                    tm_written: true,
                    proposal_id: proposal.as_ref().map(|p| p.id.clone()),
                    proposal_status: proposal.map(|p| p.status),
                })
            }
            "bind_session_entity" => {
                let c: Bind = decode(input)?;
                check(&c.contract_version, &c.operation, "bind_session_entity")?;
                self.sessions
                    .bind_entity(
                        &c.session_id,
                        &c.source,
                        &c.target,
                        &c.source_language,
                        &c.target_language,
                        c.domain.as_deref(),
                        &c.concept,
                    )
                    .map_err(|e| e.status())?;
                Self::respond(Action { status: "ok" })
            }
            "unbind_session_entity" => {
                let c: Unbind = decode(input)?;
                check(&c.contract_version, &c.operation, "unbind_session_entity")?;
                self.sessions.unbind_entity(
                    &c.session_id,
                    &c.source,
                    &c.source_language,
                    &c.target_language,
                    c.domain.as_deref(),
                );
                Self::respond(Action { status: "ok" })
            }
            "clear_session" => {
                let c: Clear = decode(input)?;
                check(&c.contract_version, &c.operation, "clear_session")?;
                self.sessions.clear_session(&c.session_id);
                Self::respond(Action { status: "ok" })
            }
            "add_terminology" => {
                let c: AddTerm = decode(input)?;
                check(&c.contract_version, &c.operation, "add_terminology")?;
                self.store
                    .add_terminology(
                        &c.source,
                        &c.target,
                        &c.source_language,
                        &c.target_language,
                        c.domain.as_deref(),
                        &c.concept,
                        c.confidence,
                        &c.origin,
                    )
                    .map_err(|e| e.status())?;
                Self::respond(Action { status: "ok" })
            }
            "disable_terminology" => {
                let c: DisableTerm = decode(input)?;
                check(&c.contract_version, &c.operation, "disable_terminology")?;
                self.store
                    .disable_terminology(
                        &c.source,
                        &c.source_language,
                        &c.target_language,
                        c.domain.as_deref(),
                    )
                    .map_err(|e| e.status())?;
                Self::respond(Action { status: "ok" })
            }
            "pending_proposals" => {
                let c: Simple = decode(input)?;
                check(&c.contract_version, &c.operation, "pending_proposals")?;
                let rows = self.store.pending_proposals().map_err(|e| e.status())?;
                Self::respond(rows)
            }
            "approve_proposal" => {
                let c: Proposal = decode(input)?;
                check(&c.contract_version, &c.operation, "approve_proposal")?;
                let proposal = self
                    .store
                    .approve_proposal(&c.proposal_id)
                    .map_err(|e| e.status())?;
                Self::respond(proposal)
            }
            "reject_proposal" => {
                let c: Proposal = decode(input)?;
                check(&c.contract_version, &c.operation, "reject_proposal")?;
                self.store
                    .reject_proposal(&c.proposal_id)
                    .map_err(|e| e.status())?;
                Self::respond(Action { status: "ok" })
            }
            "routing_weight" => {
                let c: Route = decode(input)?;
                check(&c.contract_version, &c.operation, "routing_weight")?;
                let weight = self
                    .store
                    .routing_weight(c.domain.as_deref(), &c.candidate)
                    .map_err(|e| e.status())?;
                Self::respond(Weight { weight })
            }
            "adjust_routing_weight" => {
                let c: Adjust = decode(input)?;
                check(&c.contract_version, &c.operation, "adjust_routing_weight")?;
                let event_id = self
                    .store
                    .adjust_routing_weight(c.domain.as_deref(), &c.candidate, c.delta, &c.reason)
                    .map_err(|e| e.status())?;
                Self::respond(Event { event_id })
            }
            "rollback_routing_weight" => {
                let c: Rollback = decode(input)?;
                check(&c.contract_version, &c.operation, "rollback_routing_weight")?;
                let weight = self
                    .store
                    .rollback_routing_weight(&c.event_id)
                    .map_err(|e| e.status())?;
                Self::respond(Weight { weight })
            }
            _ => Err(Status::InvalidRequest),
        }
    }
    fn respond<T: Serialize>(result: T) -> Result<Vec<u8>, Status> {
        #[derive(Serialize)]
        struct Out<'a, T> {
            contract_version: &'a str,
            result: T,
        }
        let bytes = serde_json::to_vec(&Out {
            contract_version: CONTRACT_VERSION,
            result,
        })
        .map_err(|_| Status::InternalError)?;
        if bytes.len() > MAX_OUTPUT_BYTES {
            return Err(Status::OutputTooLarge);
        }
        Ok(bytes)
    }
}
#[derive(Deserialize)]
struct Header {
    contract_version: String,
    operation: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Translate {
    contract_version: String,
    operation: String,
    request: TranslationRequest,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Correct {
    contract_version: String,
    operation: String,
    request: TranslationRequest,
    corrected_text: String,
    #[serde(default)]
    generated_text: Option<String>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Bind {
    contract_version: String,
    operation: String,
    session_id: String,
    source: String,
    target: String,
    source_language: String,
    target_language: String,
    #[serde(deserialize_with = "deserialize_required_option")]
    domain: Option<String>,
    concept: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Unbind {
    contract_version: String,
    operation: String,
    session_id: String,
    source: String,
    source_language: String,
    target_language: String,
    #[serde(deserialize_with = "deserialize_required_option")]
    domain: Option<String>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Clear {
    contract_version: String,
    operation: String,
    session_id: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct AddTerm {
    contract_version: String,
    operation: String,
    source: String,
    target: String,
    source_language: String,
    target_language: String,
    #[serde(deserialize_with = "deserialize_required_option")]
    domain: Option<String>,
    concept: String,
    confidence: f64,
    origin: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct DisableTerm {
    contract_version: String,
    operation: String,
    source: String,
    source_language: String,
    target_language: String,
    #[serde(deserialize_with = "deserialize_required_option")]
    domain: Option<String>,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Simple {
    contract_version: String,
    operation: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Proposal {
    contract_version: String,
    operation: String,
    proposal_id: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Route {
    contract_version: String,
    operation: String,
    #[serde(deserialize_with = "deserialize_required_option")]
    domain: Option<String>,
    candidate: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Adjust {
    contract_version: String,
    operation: String,
    #[serde(deserialize_with = "deserialize_required_option")]
    domain: Option<String>,
    candidate: String,
    delta: f64,
    reason: String,
}
#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Rollback {
    contract_version: String,
    operation: String,
    event_id: String,
}
#[derive(Serialize)]
struct Action {
    status: &'static str,
}
#[derive(Serialize)]
struct Weight {
    weight: f64,
}
#[derive(Serialize)]
struct Event {
    event_id: String,
}
fn decode<T: DeserializeOwned>(input: &[u8]) -> Result<T, Status> {
    serde_json::from_slice(input).map_err(|_| Status::InvalidRequest)
}
fn check(version: &str, operation: &str, expected: &str) -> Result<(), Status> {
    if version != CONTRACT_VERSION {
        return Err(Status::UnsupportedContract);
    }
    if operation != expected {
        return Err(Status::InvalidRequest);
    }
    Ok(())
}

#[repr(C)]
pub struct MarcoRuntime {
    inner: Mutex<Runtime>,
}
/// Opens a UTF-8 path to the shared SQLite runtime store.
/// The returned handle must be closed exactly once and may not be closed concurrently with a call.
#[no_mangle]
pub unsafe extern "C" fn marco_runtime_open(
    path: *const u8,
    path_len: usize,
    out: *mut *mut MarcoRuntime,
) -> Status {
    if out.is_null() {
        return Status::InvalidArgument;
    }
    unsafe {
        *out = std::ptr::null_mut();
    }
    if path.is_null() || path_len == 0 {
        return Status::InvalidArgument;
    }
    if path_len > MAX_INPUT_BYTES {
        return Status::InputTooLarge;
    }
    match catch_unwind(AssertUnwindSafe(|| {
        let bytes = unsafe { slice::from_raw_parts(path, path_len) };
        let path = str::from_utf8(bytes).map_err(|_| Status::InvalidUtf8)?;
        let runtime = Runtime::open(path)?;
        Ok::<_, Status>(Box::into_raw(Box::new(MarcoRuntime {
            inner: Mutex::new(runtime),
        })))
    })) {
        Ok(Ok(handle)) => {
            unsafe {
                *out = handle;
            }
            Status::Ok
        }
        Ok(Err(status)) => status,
        Err(_) => Status::InternalError,
    }
}
/// Processes one `marco-runtime.v1` JSON operation; release the NUL-terminated result with `marco_runtime_string_free`.
#[no_mangle]
pub unsafe extern "C" fn marco_runtime_process_json(
    runtime: *mut MarcoRuntime,
    input: *const u8,
    input_len: usize,
    out: *mut *mut c_char,
) -> Status {
    if out.is_null() {
        return Status::InvalidArgument;
    }
    unsafe {
        *out = std::ptr::null_mut();
    }
    if runtime.is_null() || (input.is_null() && input_len != 0) {
        return Status::InvalidArgument;
    }
    if input_len > MAX_INPUT_BYTES {
        return Status::InputTooLarge;
    }
    match catch_unwind(AssertUnwindSafe(|| {
        let bytes = if input_len == 0 {
            &[]
        } else {
            unsafe { slice::from_raw_parts(input, input_len) }
        };
        let handle = unsafe { &*runtime };
        let mut inner = handle.inner.lock().map_err(|_| Status::InternalError)?;
        let json = CString::new(inner.process_json(bytes)?).map_err(|_| Status::InternalError)?;
        Ok::<_, Status>(json.into_raw())
    })) {
        Ok(Ok(json)) => {
            unsafe {
                *out = json;
            }
            Status::Ok
        }
        Ok(Err(status)) => status,
        Err(_) => Status::InternalError,
    }
}
/// Closes a non-null runtime handle. It must not be reused or closed twice.
#[no_mangle]
pub unsafe extern "C" fn marco_runtime_close(runtime: *mut MarcoRuntime) {
    if !runtime.is_null() {
        let _ = catch_unwind(AssertUnwindSafe(|| unsafe {
            drop(Box::from_raw(runtime));
        }));
    }
}
/// Releases a JSON string returned by `marco_runtime_process_json`.
#[no_mangle]
pub unsafe extern "C" fn marco_runtime_string_free(json: *mut c_char) {
    if !json.is_null() {
        let _ = catch_unwind(AssertUnwindSafe(|| unsafe {
            drop(CString::from_raw(json));
        }));
    }
}
#[no_mangle]
pub extern "C" fn marco_runtime_status_name(status: i32) -> *const c_char {
    let name = match status {
        0 => b"ok\0".as_slice(),
        1 => b"invalid_argument\0".as_slice(),
        2 => b"input_too_large\0".as_slice(),
        3 => b"invalid_utf8\0".as_slice(),
        4 => b"invalid_json\0".as_slice(),
        5 => b"unsupported_contract\0".as_slice(),
        6 => b"invalid_request\0".as_slice(),
        7 => b"unsupported_store_version\0".as_slice(),
        8 => b"incompatible_store\0".as_slice(),
        9 => b"storage_error\0".as_slice(),
        10 => b"not_found\0".as_slice(),
        11 => b"invalid_state\0".as_slice(),
        12 => b"output_too_large\0".as_slice(),
        13 => b"internal_error\0".as_slice(),
        _ => b"unknown_status\0".as_slice(),
    };
    name.as_ptr().cast()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};
    use std::ffi::CStr;
    use std::fs;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
    use std::sync::Arc;

    fn temp_db() -> PathBuf {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        std::env::temp_dir().join(format!(
            "marco-runtime-p1f-{}-{}.sqlite",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed)
        ))
    }

    fn operation(name: &str, fields: Value) -> Vec<u8> {
        let mut value = fields;
        value["contract_version"] = json!(CONTRACT_VERSION);
        value["operation"] = json!(name);
        serde_json::to_vec(&value).unwrap()
    }

    fn request(text: &str, session_id: Option<&str>) -> Value {
        json!({
            "text": text,
            "source_language": "zh",
            "target_language": "ko",
            "domain": "gaming",
            "style": "neutral",
            "session_id": session_id,
        })
    }

    fn output(runtime: &mut Runtime, bytes: Vec<u8>) -> Value {
        serde_json::from_slice(&runtime.process_json(&bytes).unwrap()).unwrap()
    }

    fn cleanup(path: &Path) {
        let _ = fs::remove_file(path);
        let _ = fs::remove_file(path.with_extension("sqlite-wal"));
        let _ = fs::remove_file(path.with_extension("sqlite-shm"));
    }

    #[test]
    fn normalization_matches_the_frozen_whitespace_profile() {
        let whitespace = (0..=0x10ffff)
            .filter_map(char::from_u32)
            .filter(|ch| python_regex_whitespace(*ch))
            .collect::<Vec<_>>();
        assert_eq!(whitespace.len(), 29);
        for ch in whitespace {
            assert_eq!(normalize_text(&format!("{ch}x{ch}")), "x");
        }
        assert_eq!(normalize_text("  Ａ\u{00a0}Ｂ  \n"), "A B");
    }

    #[test]
    fn every_frozen_fixture_matches_the_rust_runtime() {
        let path = temp_db();
        let mut runtime = Runtime::open(&path).unwrap();
        let fixtures: Value =
            serde_json::from_str(include_str!("../fixtures/conformance-v1.json")).unwrap();
        assert_eq!(fixtures["contract_version"], CONTRACT_VERSION);
        assert_eq!(fixtures["normalization_profile"], NORMALIZATION_PROFILE);
        for case in fixtures["cases"].as_array().unwrap() {
            let bytes = operation("translate", json!({ "request": case["request"] }));
            assert_eq!(
                output(&mut runtime, bytes),
                case["expected"],
                "{}",
                case["id"]
            );
        }
        drop(runtime);
        cleanup(&path);
    }

    struct GroundedMiss;
    impl Resolver for GroundedMiss {
        fn resolve(&self, request: &TranslationRequest, terms: Vec<TermDecision>) -> SemanticFrame {
            SemanticFrame {
                source_language: request.source_language.clone(),
                target_language: request.target_language.clone(),
                source_text: request.text.clone(),
                domain: request.domain.clone(),
                intent: "statement".into(),
                style: request.style.clone(),
                terms,
                template: None,
                slots: BTreeMap::new(),
                unresolved: Vec::new(),
                confidence: 0.7,
            }
        }
    }

    struct GuessingNeural(Arc<AtomicBool>);
    impl NeuralRealizer for GuessingNeural {
        fn realize(&mut self, _: &SemanticFrame) -> Option<String> {
            self.0.store(true, Ordering::SeqCst);
            Some("추측 번역".into())
        }
    }

    #[test]
    fn neural_seam_runs_only_after_a_grounded_rule_miss() {
        let path = temp_db();
        let called = Arc::new(AtomicBool::new(false));
        let mut runtime = Runtime::open_with_parts(
            &path,
            Box::new(GroundedMiss),
            Box::new(GuessingNeural(called.clone())),
        )
        .unwrap();
        let bytes = operation("translate", json!({ "request": request("未翻译", None) }));
        let result = output(&mut runtime, bytes);
        assert_eq!(result["result"]["path"], "neural-realizer");
        assert_eq!(result["result"]["translated_text"], "추측 번역");
        assert!(called.load(Ordering::SeqCst));
        drop(runtime);
        cleanup(&path);

        let path = temp_db();
        let called = Arc::new(AtomicBool::new(false));
        let mut runtime = Runtime::open_with_parts(
            &path,
            Box::new(FixtureResolver::new().unwrap()),
            Box::new(GuessingNeural(called.clone())),
        )
        .unwrap();
        let bytes = operation(
            "translate",
            json!({ "request": request("完全未知的新句子", None) }),
        );
        let result = output(&mut runtime, bytes);
        assert_eq!(result["result"]["path"], "unresolved");
        assert_eq!(result["result"]["translated_text"], "");
        assert!(!result["result"]["frame"]["unresolved"]
            .as_array()
            .unwrap()
            .is_empty());
        assert!(!called.load(Ordering::SeqCst));
        drop(runtime);
        cleanup(&path);
    }

    #[test]
    fn session_precedes_fixture_translation_and_is_ephemeral() {
        let path = temp_db();
        let mut runtime = Runtime::open(&path).unwrap();
        let bind = operation(
            "bind_session_entity",
            json!({ "session_id":"s1", "source":"西边有狙", "target":"임시 결과", "source_language":"zh", "target_language":"ko", "domain":"gaming", "concept":"TEMP" }),
        );
        output(&mut runtime, bind);
        let result = output(
            &mut runtime,
            operation(
                "translate",
                json!({ "request": request("西边有狙", Some("s1")) }),
            ),
        );
        assert_eq!(result["result"]["path"], "session");
        assert_eq!(result["result"]["translated_text"], "임시 결과");
        drop(runtime);

        let mut reopened = Runtime::open(&path).unwrap();
        let result = output(
            &mut reopened,
            operation(
                "translate",
                json!({ "request": request("西边有狙", Some("s1")) }),
            ),
        );
        assert_eq!(result["result"]["path"], "rule");
        assert_eq!(result["result"]["translated_text"], "서쪽에 저격수 있음");
        drop(reopened);
        cleanup(&path);
    }

    #[test]
    fn correction_requires_explicit_approval_and_survives_reopen() {
        let path = temp_db();
        let mut runtime = Runtime::open(&path).unwrap();
        let mut proposal_id = String::new();
        for _ in 0..3 {
            let result = output(
                &mut runtime,
                operation(
                    "correct",
                    json!({ "request": request("新增词", None), "corrected_text":"새 단어", "generated_text":null }),
                ),
            );
            if !result["result"]["proposal_id"].is_null() {
                proposal_id = result["result"]["proposal_id"].as_str().unwrap().into();
            }
        }
        assert!(!proposal_id.is_empty());
        let pending = output(&mut runtime, operation("pending_proposals", json!({})));
        assert_eq!(pending["result"][0]["status"], "pending");
        let approved = output(
            &mut runtime,
            operation("approve_proposal", json!({ "proposal_id":proposal_id })),
        );
        assert_eq!(approved["result"]["status"], "accepted");
        drop(runtime);

        let db = Connection::open(&path).unwrap();
        db.execute("DELETE FROM tm WHERE source_text='新增词'", [])
            .unwrap();
        drop(db);
        let mut reopened = Runtime::open(&path).unwrap();
        let translated = output(
            &mut reopened,
            operation("translate", json!({ "request":request("新增词", None) })),
        );
        assert_eq!(translated["result"]["path"], "rule");
        assert_eq!(translated["result"]["translated_text"], "새 단어");
        assert_eq!(translated["result"]["frame"]["terms"][0]["layer"], "user");
        drop(reopened);
        cleanup(&path);
    }

    #[test]
    fn route_bias_is_bounded_and_rollback_is_single_use() {
        let path = temp_db();
        let mut runtime = Runtime::open(&path).unwrap();
        let adjusted = output(
            &mut runtime,
            operation(
                "adjust_routing_weight",
                json!({ "domain":"gaming", "candidate":"resolver-a", "delta":0.7, "reason":"explicit user choice" }),
            ),
        );
        let event_id = adjusted["result"]["event_id"].as_str().unwrap().to_owned();
        let weight = output(
            &mut runtime,
            operation(
                "routing_weight",
                json!({ "domain":"gaming", "candidate":"resolver-a" }),
            ),
        );
        assert_eq!(weight["result"]["weight"], 0.1);
        let rolled_back = output(
            &mut runtime,
            operation("rollback_routing_weight", json!({ "event_id":event_id })),
        );
        assert_eq!(rolled_back["result"]["weight"], 0.0);
        drop(runtime);
        cleanup(&path);
    }

    #[test]
    fn sqlite_v0_migrates_but_unknown_or_incompatible_stores_fail_closed() {
        let path = temp_db();
        let db = Connection::open(&path).unwrap();
        db.execute_batch("CREATE TABLE tm(source_language TEXT NOT NULL,target_language TEXT NOT NULL,domain TEXT NOT NULL DEFAULT '',source_text TEXT NOT NULL,target_text TEXT NOT NULL,origin TEXT NOT NULL DEFAULT 'observed',PRIMARY KEY(source_language,target_language,domain,source_text)); INSERT INTO tm VALUES('zh','ko','gaming','来源','目标','user');").unwrap();
        drop(db);
        let store = SqliteRuntimeStore::open(&path).unwrap();
        assert_eq!(
            store
                .lookup_tm("zh", "ko", Some("gaming"), "来源")
                .unwrap()
                .as_deref(),
            Some("目标")
        );
        let version: i64 = store
            .db
            .query_row("PRAGMA user_version", [], |r| r.get(0))
            .unwrap();
        assert_eq!(version, 1);
        drop(store);
        cleanup(&path);

        let path = temp_db();
        let db = Connection::open(&path).unwrap();
        db.pragma_update(None, "user_version", 99).unwrap();
        drop(db);
        assert!(matches!(
            Runtime::open(&path),
            Err(Status::UnsupportedStoreVersion)
        ));
        cleanup(&path);

        let path = temp_db();
        let db = Connection::open(&path).unwrap();
        db.execute_batch("CREATE TABLE tm(source_language TEXT);")
            .unwrap();
        drop(db);
        assert!(matches!(
            Runtime::open(&path),
            Err(Status::IncompatibleStore)
        ));
        cleanup(&path);
    }

    #[test]
    fn ffi_validates_bounds_utf8_json_contract_and_status_codes() {
        let path = temp_db();
        let path_bytes = path.to_str().unwrap().as_bytes();
        let mut handle = std::ptr::null_mut();
        assert_eq!(
            unsafe { marco_runtime_open(path_bytes.as_ptr(), path_bytes.len(), &mut handle) },
            Status::Ok
        );
        assert!(!handle.is_null());

        unsafe {
            let mut output = std::ptr::null_mut();
            let invalid_utf8 = [0xff];
            assert_eq!(
                marco_runtime_process_json(
                    handle,
                    invalid_utf8.as_ptr(),
                    invalid_utf8.len(),
                    &mut output
                ),
                Status::InvalidUtf8
            );
            assert!(output.is_null());
            let invalid_json = b"{";
            assert_eq!(
                marco_runtime_process_json(
                    handle,
                    invalid_json.as_ptr(),
                    invalid_json.len(),
                    &mut output
                ),
                Status::InvalidJson
            );
            let unsupported = br#"{"contract_version":"marco-runtime.v2","operation":"translate"}"#;
            assert_eq!(
                marco_runtime_process_json(
                    handle,
                    unsupported.as_ptr(),
                    unsupported.len(),
                    &mut output
                ),
                Status::UnsupportedContract
            );
            let oversized = vec![b' '; MAX_INPUT_BYTES + 1];
            assert_eq!(
                marco_runtime_process_json(
                    handle,
                    oversized.as_ptr(),
                    oversized.len(),
                    &mut output
                ),
                Status::InputTooLarge
            );
            let valid = operation("translate", json!({ "request":request("西边有狙", None) }));
            assert_eq!(
                marco_runtime_process_json(handle, valid.as_ptr(), valid.len(), &mut output),
                Status::Ok
            );
            assert_eq!(
                serde_json::from_slice::<Value>(CStr::from_ptr(output).to_bytes()).unwrap()
                    ["result"]["path"],
                "rule"
            );
            marco_runtime_string_free(output);
            assert_eq!(
                CStr::from_ptr(marco_runtime_status_name(999)).to_bytes(),
                b"unknown_status"
            );
            marco_runtime_close(handle);
        }
        cleanup(&path);
    }
}
