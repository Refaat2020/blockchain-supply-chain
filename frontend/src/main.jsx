import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const operationTypes = ["PRODUCED", "TRANSFER", "RECEIVED", "DELIVERED"];

const users = [
  {
    role: "Producer",
    name: "Book Factory A",
    address: "0x7cB57B5A97eAbe94205C07890BE4c1aD31E486A8"
  },
  {
    role: "Transporter",
    name: "Transit Co.",
    address: "0x9C48E6C5f11c2E4Ad98A8270f7B8A7e82F8b0b3D"
  },
  {
    role: "Receiver",
    name: "Warehouse B",
    address: "0x2Ac88CE2d1491f6D1A13ddC8d5F6c7fBdE76Ff95"
  }
];

function nowIso() {
  return new Date().toISOString();
}

function canonicalJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

async function sha256Hex(value) {
  const bytes = new TextEncoder().encode(value);
  const buffer = await crypto.subtle.digest("SHA-256", bytes);
  return `0x${Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("")}`;
}

function shortHash(value, size = 12) {
  if (!value) return "pending";
  return `${value.slice(0, size)}...${value.slice(-6)}`;
}

function getActor(address) {
  return users.find((user) => user.address === address)?.name ?? "Unknown";
}

function recordPayload(record) {
  return {
    record_id: record.record_id,
    record_type: record.record_type,
    manifest_id: record.manifest_id,
    quantity: Number(record.quantity),
    user: record.user,
    timestamp: record.timestamp,
    metadata: record.metadata ?? {}
  };
}

function makeSeedRecord(record) {
  const payload = recordPayload(record);
  return {
    ...record,
    actor: getActor(record.user),
    sealed_payload: canonicalJson(payload),
    signature_user: record.user,
    on_chain_hash: record.hash,
    tampered: false
  };
}

const initialManifests = [
  {
    manifest_id: "M-BOOKS-001",
    good_type: "Books",
    quantity: 100,
    creator: users[0].address,
    timestamp: "2026-05-23T08:45:00Z",
    hash: "0x19f2d76a4a216e5821de92c5a76ebd8f17d11b8d4d6cfeb1f8e30a749d1cfd92"
  },
  {
    manifest_id: "M-COFFEE-002",
    good_type: "Coffee Beans",
    quantity: 750,
    creator: users[0].address,
    timestamp: "2026-05-23T09:10:00Z",
    hash: "0x85cbba213bb1cb016b5a08b9d8e72ad005ba0c88b3e8e0da72d80a7f2bc80341"
  }
];

const initialRecords = [
  makeSeedRecord({
    record_id: "R-PROD-001",
    record_type: "PRODUCED",
    manifest_id: "M-BOOKS-001",
    quantity: 100,
    user: users[0].address,
    timestamp: "2026-05-23T08:50:00Z",
    metadata: { factory: "Book Factory A", batch: "B001" },
    hash: "0x056b771c8f7d96cd16e9d193bd1ad2641e5d3376d2a32a47e6725d4624d01e9c",
    signature: "0x9ad498cfb4e7e6b75a3d1b0bf0141dc22e4ea7b91bb54795d2b33f",
    tx_hash: "0x08bbf0798368f6cd9cfccab6f7a913cda4dbf73f58740608b9a3a4"
  }),
  makeSeedRecord({
    record_id: "R-TRANS-002",
    record_type: "TRANSFER",
    manifest_id: "M-BOOKS-001",
    quantity: 20,
    user: users[0].address,
    timestamp: "2026-05-23T09:05:00Z",
    metadata: { to: "Warehouse B", carrier: "Transit Co." },
    hash: "0x5bfaa5602b63b79e0ab4115c4a174ef11ddf2932a0dd9f956e50385b3bb98a55",
    signature: "0x34aacd3193dfe28a919ebcf01bc6d426aa45917f99e5f17f6d1a21",
    tx_hash: "0x8975b6bf34f892f5a3a1efac7c3d290e45c7268c7db6d7d5c91a0"
  }),
  makeSeedRecord({
    record_id: "R-REC-003",
    record_type: "RECEIVED",
    manifest_id: "M-BOOKS-001",
    quantity: 20,
    user: users[2].address,
    timestamp: "2026-05-23T09:16:00Z",
    metadata: { from: "Book Factory A", location: "Warehouse B" },
    hash: "0x87dda12436384481b1082e146e44fae37e224d6c42f5d14341c3fe5f6b1ee8cf",
    signature: "0xaadeb0c44299487dbf30f62d5b98372fef019d904bde4517af2d19",
    tx_hash: "0x1090d9823e9a963d6fd963bc895a2f914eb114b0fe759c05f7bccc"
  })
];

function calculateUserBalance(records, manifestId, address) {
  return records
    .filter((record) => record.manifest_id === manifestId && record.user === address)
    .reduce((balance, record) => {
      if (record.record_type === "PRODUCED" || record.record_type === "RECEIVED") {
        return balance + Number(record.quantity);
      }
      return balance - Number(record.quantity);
    }, 0);
}

function calculateManifestTotals(records, manifestId) {
  return records
    .filter((record) => record.manifest_id === manifestId)
    .reduce(
      (totals, record) => {
        totals[record.record_type] += Number(record.quantity);
        return totals;
      },
      { PRODUCED: 0, TRANSFER: 0, RECEIVED: 0, DELIVERED: 0 }
    );
}

function parseMetadata(raw) {
  return raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .reduce((metadata, item) => {
      const [key, ...rest] = item.split("=");
      if (key && rest.length) metadata[key.trim()] = rest.join("=").trim();
      return metadata;
    }, {});
}

function App() {
  const [manifests, setManifests] = useState(initialManifests);
  const [records, setRecords] = useState(initialRecords);
  const [activeUser, setActiveUser] = useState(users[0].address);
  const [selectedManifestId, setSelectedManifestId] = useState("M-BOOKS-001");
  const [selectedRecordId, setSelectedRecordId] = useState("R-REC-003");
  const [notice, setNotice] = useState("Local simulator ready");
  const [verificationRunAt, setVerificationRunAt] = useState("Not run yet");
  const [manifestForm, setManifestForm] = useState({
    manifest_id: "M-ELECTRONICS-003",
    good_type: "Electronics",
    quantity: 250
  });
  const [operationForm, setOperationForm] = useState({
    record_type: "PRODUCED",
    quantity: 50,
    metadata: "batch=B002, location=Factory A"
  });

  const selectedManifest = manifests.find(
    (manifest) => manifest.manifest_id === selectedManifestId
  );
  const selectedRecord = records.find((record) => record.record_id === selectedRecordId);
  const activeUserProfile = users.find((user) => user.address === activeUser);

  const stats = useMemo(
    () => ({
      manifests: manifests.length,
      records: records.length,
      anchored: records.filter((record) => record.tx_hash).length
    }),
    [manifests, records]
  );

  const manifestTotals = useMemo(
    () => calculateManifestTotals(records, selectedManifestId),
    [records, selectedManifestId]
  );

  const balances = useMemo(
    () =>
      users.map((user) => ({
        ...user,
        balance: calculateUserBalance(records, selectedManifestId, user.address)
      })),
    [records, selectedManifestId]
  );

  const verification = selectedRecord
    ? {
        hash: canonicalJson(recordPayload(selectedRecord)) === selectedRecord.sealed_payload,
        signature:
          selectedRecord.signature?.startsWith("0x") &&
          selectedRecord.signature_user === selectedRecord.user &&
          canonicalJson(recordPayload(selectedRecord)) === selectedRecord.sealed_payload,
        blockchain:
          Boolean(selectedRecord.tx_hash) && selectedRecord.hash === selectedRecord.on_chain_hash,
        quantity:
          selectedRecord.record_type === "TRANSFER" || selectedRecord.record_type === "DELIVERED"
            ? calculateUserBalance(
                records.filter((record) => record.record_id !== selectedRecord.record_id),
                selectedRecord.manifest_id,
                selectedRecord.user
              ) >= selectedRecord.quantity
            : true
      }
    : null;

  async function createManifest(event) {
    event.preventDefault();
    const manifestId = manifestForm.manifest_id.trim();

    if (manifests.some((manifest) => manifest.manifest_id === manifestId)) {
      setNotice("Manifest ID already exists");
      return;
    }

    const payload = {
      manifest_id: manifestId,
      good_type: manifestForm.good_type.trim(),
      quantity: Number(manifestForm.quantity),
      creator: activeUser,
      timestamp: nowIso()
    };

    const hash = await sha256Hex(canonicalJson(payload));
    const created = { ...payload, hash };
    setManifests((current) => [created, ...current]);
    setSelectedManifestId(created.manifest_id);
    setNotice(`Created ${created.manifest_id} as ${activeUserProfile.role}`);
  }

  async function submitOperation(event) {
    event.preventDefault();
    if (!selectedManifest) {
      setNotice("Select a manifest first");
      return;
    }

    const quantity = Number(operationForm.quantity);
    const recordType = operationForm.record_type;
    const userBalance = calculateUserBalance(records, selectedManifestId, activeUser);

    if ((recordType === "TRANSFER" || recordType === "DELIVERED") && userBalance < quantity) {
      setNotice(`Rejected: ${activeUserProfile.role} balance is ${userBalance}, requested ${quantity}`);
      return;
    }

    if (recordType === "PRODUCED" && manifestTotals.PRODUCED + quantity > selectedManifest.quantity) {
      setNotice(`Rejected: production would exceed manifest limit ${selectedManifest.quantity}`);
      return;
    }

    const record = {
      record_id: `R-${recordType.slice(0, 4)}-${String(records.length + 1).padStart(3, "0")}`,
      record_type: recordType,
      manifest_id: selectedManifestId,
      quantity,
      user: activeUser,
      actor: getActor(activeUser),
      timestamp: nowIso(),
      metadata: parseMetadata(operationForm.metadata)
    };

    const sealedPayload = canonicalJson(recordPayload(record));
    const hash = await sha256Hex(sealedPayload);
    const signature = await sha256Hex(`${hash}:${activeUser}`);
    const txHash = await sha256Hex(`${record.record_id}:${hash}:${Date.now()}`);
    const signedRecord = {
      ...record,
      hash,
      signature,
      tx_hash: txHash,
      sealed_payload: sealedPayload,
      signature_user: activeUser,
      on_chain_hash: hash,
      tampered: false
    };

    setRecords((current) => [signedRecord, ...current]);
    setSelectedRecordId(signedRecord.record_id);
    setNotice(`${recordType} accepted, signed by ${activeUserProfile.role}, and anchored`);
  }

  function updateSelectedRecord(mutator, message) {
    if (!selectedRecord) return;
    setRecords((current) =>
      current.map((record) =>
        record.record_id === selectedRecord.record_id
          ? { ...mutator(record), tampered: true }
          : record
      )
    );
    setNotice(message);
  }

  function attackQuantity() {
    updateSelectedRecord(
      (record) => ({ ...record, quantity: Number(record.quantity) + 10 }),
      "Attack applied: database quantity changed without re-signing"
    );
  }

  function attackUser() {
    const currentIndex = users.findIndex((user) => user.address === selectedRecord?.user);
    const nextUser = users[(currentIndex + 1) % users.length];
    updateSelectedRecord(
      (record) => ({ ...record, user: nextUser.address, actor: nextUser.name }),
      `Attack applied: database user changed to ${nextUser.role}`
    );
  }

  function attackHash() {
    updateSelectedRecord(
      (record) => ({
        ...record,
        hash: `0xdead${record.hash.slice(6)}`,
        tx_hash: `0xbad0${record.tx_hash.slice(6)}`
      }),
      "Attack applied: stored hash and tx hash overwritten"
    );
  }

  async function resealSelectedRecord() {
    if (!selectedRecord) return;
    const payload = recordPayload(selectedRecord);
    const sealedPayload = canonicalJson(payload);
    const hash = await sha256Hex(sealedPayload);
    const signature = await sha256Hex(`${hash}:${selectedRecord.user}`);
    const txHash = await sha256Hex(`${selectedRecord.record_id}:${hash}:reseal:${Date.now()}`);

    setRecords((current) =>
      current.map((record) =>
        record.record_id === selectedRecord.record_id
          ? {
              ...record,
              hash,
              signature,
              tx_hash: txHash,
              sealed_payload: sealedPayload,
              signature_user: record.user,
              on_chain_hash: hash,
              tampered: false
            }
          : record
      )
    );
    setNotice("Record re-signed and re-anchored in the simulator");
  }

  function runVerification() {
    setVerificationRunAt(new Date().toLocaleTimeString());
    if (!selectedRecord || !verification) return;
    const failed = Object.entries(verification)
      .filter(([, valid]) => !valid)
      .map(([key]) => key);
    setNotice(
      failed.length
        ? `Verification failed: ${failed.join(", ")}`
        : `${selectedRecord.record_id} fully verified`
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">C</div>
          <div>
            <strong>ChainTrack</strong>
            <span>Supply chain lab</span>
          </div>
        </div>
        <nav className="nav-list" aria-label="Main navigation">
          <button className="nav-item active">Dashboard</button>
          <button className="nav-item">Manifests</button>
          <button className="nav-item">Operations</button>
          <button className="nav-item">Attack Lab</button>
          <button className="nav-item">Verification</button>
        </nav>
        <div className="sidebar-footer">
          <span>Mode</span>
          <strong>Local simulator</strong>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div>
            <h1>Supply Chain Control</h1>
            <p>Create manifests, switch users, mutate records, and verify tamper detection.</p>
          </div>
          <div className="topbar-actions">
            <label className="active-user">
              Active user
              <select value={activeUser} onChange={(event) => setActiveUser(event.target.value)}>
                {users.map((user) => (
                  <option key={user.address} value={user.address}>
                    {user.role} · {user.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="notice">{notice}</div>
          </div>
        </header>

        <section className="workflow-strip">
          <div><span>1</span><strong>Create manifest</strong></div>
          <div><span>2</span><strong>Change user</strong></div>
          <div><span>3</span><strong>Submit operation</strong></div>
          <div><span>4</span><strong>Attack database</strong></div>
          <div><span>5</span><strong>Verify</strong></div>
        </section>

        <section className="kpi-grid" aria-label="System counters">
          <Kpi title="Manifests" value={stats.manifests} detail="tracked batches" />
          <Kpi title="Records" value={stats.records} detail="signed operations" />
          <Kpi title="Anchored" value={stats.anchored} detail="with tx hash" />
        </section>

        <section className="main-grid">
          <Panel title="Create Manifest">
            <form className="form-stack" onSubmit={createManifest}>
              <div className="context-row">
                <span>Creator</span>
                <strong>{activeUserProfile?.role}</strong>
              </div>
              <label>
                Manifest ID
                <input
                  value={manifestForm.manifest_id}
                  onChange={(event) =>
                    setManifestForm({ ...manifestForm, manifest_id: event.target.value })
                  }
                />
              </label>
              <label>
                Goods Type
                <input
                  value={manifestForm.good_type}
                  onChange={(event) =>
                    setManifestForm({ ...manifestForm, good_type: event.target.value })
                  }
                />
              </label>
              <label>
                Quantity
                <input
                  type="number"
                  min="1"
                  value={manifestForm.quantity}
                  onChange={(event) =>
                    setManifestForm({ ...manifestForm, quantity: event.target.value })
                  }
                />
              </label>
              <button className="primary-button" type="submit">Create manifest</button>
            </form>
          </Panel>

          <Panel title="Submit Operation">
            <form className="form-stack" onSubmit={submitOperation}>
              <label>
                Manifest
                <select
                  value={selectedManifestId}
                  onChange={(event) => setSelectedManifestId(event.target.value)}
                >
                  {manifests.map((manifest) => (
                    <option key={manifest.manifest_id} value={manifest.manifest_id}>
                      {manifest.manifest_id} · {manifest.good_type}
                    </option>
                  ))}
                </select>
              </label>
              <div className="segmented" role="group" aria-label="Operation type">
                {operationTypes.map((type) => (
                  <button
                    key={type}
                    type="button"
                    className={operationForm.record_type === type ? "selected" : ""}
                    onClick={() => setOperationForm({ ...operationForm, record_type: type })}
                  >
                    {type}
                  </button>
                ))}
              </div>
              <div className="two-columns">
                <label>
                  User
                  <input value={`${activeUserProfile?.role} · ${activeUserProfile?.name}`} readOnly />
                </label>
                <label>
                  Quantity
                  <input
                    type="number"
                    min="1"
                    value={operationForm.quantity}
                    onChange={(event) =>
                      setOperationForm({ ...operationForm, quantity: event.target.value })
                    }
                  />
                </label>
              </div>
              <label>
                Metadata
                <input
                  value={operationForm.metadata}
                  onChange={(event) =>
                    setOperationForm({ ...operationForm, metadata: event.target.value })
                  }
                />
              </label>
              <button className="primary-button" type="submit">Sign and anchor</button>
            </form>
          </Panel>

          <Panel title="Verification">
            {selectedRecord ? (
              <div className="verification-card">
                <div>
                  <span className="muted">Selected record</span>
                  <strong>{selectedRecord.record_id}</strong>
                </div>
                <StatusRow label="Hash integrity" valid={verification.hash} />
                <StatusRow label="Signature" valid={verification.signature} />
                <StatusRow label="Blockchain proof" valid={verification.blockchain} />
                <StatusRow label="Quantity rule" valid={verification.quantity} />
                <div className="context-row">
                  <span>Last check</span>
                  <strong>{verificationRunAt}</strong>
                </div>
                <div className="hash-box">{shortHash(selectedRecord.hash, 18)}</div>
                <button className="primary-button" type="button" onClick={runVerification}>
                  Run verification
                </button>
              </div>
            ) : (
              <p className="empty">Select a record to verify.</p>
            )}
          </Panel>
        </section>

        <section className="lower-grid">
          <Panel title="Database Attack Lab">
            <div className="attack-lab">
              <p>
                These actions mutate the local record after it was signed and anchored, like a direct database edit.
              </p>
              <button type="button" onClick={attackQuantity}>Change quantity</button>
              <button type="button" onClick={attackUser}>Change record user</button>
              <button type="button" onClick={attackHash}>Overwrite hash / tx</button>
              <button className="repair" type="button" onClick={resealSelectedRecord}>
                Re-sign selected record
              </button>
            </div>
          </Panel>

          <Panel title="Balances">
            <div className="balance-list">
              {balances.map((user) => (
                <div className="balance-row" key={user.address}>
                  <div>
                    <strong>{user.role}</strong>
                    <span>{user.name}</span>
                  </div>
                  <b>{user.balance}</b>
                </div>
              ))}
            </div>
          </Panel>
        </section>

        <section className="records-section">
          <Panel title="Records">
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Record</th>
                    <th>Type</th>
                    <th>Manifest</th>
                    <th>Actor</th>
                    <th>Qty</th>
                    <th>Hash</th>
                    <th>TX</th>
                    <th>State</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record) => (
                    <tr
                      key={record.record_id}
                      className={record.record_id === selectedRecordId ? "active-row" : ""}
                      onClick={() => setSelectedRecordId(record.record_id)}
                    >
                      <td>{record.record_id}</td>
                      <td><span className={`chip ${record.record_type.toLowerCase()}`}>{record.record_type}</span></td>
                      <td>{record.manifest_id}</td>
                      <td>{record.actor}</td>
                      <td>{record.quantity}</td>
                      <td className="mono">{shortHash(record.hash)}</td>
                      <td className="mono">{shortHash(record.tx_hash)}</td>
                      <td>
                        <span className={`chip ${record.tampered ? "failed" : "produced"}`}>
                          {record.tampered ? "TAMPERED" : "SEALED"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </section>
      </main>
    </div>
  );
}

function Kpi({ title, value, detail }) {
  return (
    <article className="kpi-card">
      <span>{title}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

function Panel({ title, children }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function StatusRow({ label, valid }) {
  return (
    <div className="status-row">
      <span>{label}</span>
      <strong className={valid ? "ok" : "bad"}>{valid ? "VALID" : "FAILED"}</strong>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);

