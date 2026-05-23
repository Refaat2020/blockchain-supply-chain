# ChainTrack Frontend

React + Vite frontend for trying the supply chain workflow locally.

## Run

```bash
cd frontend
npm install
npm run dev -- --port 5173
```

Open:

```text
http://localhost:5173/
```

## What Works Now

- Create a manifest in local state.
- Switch the active user before creating manifests or records.
- Submit `PRODUCED`, `TRANSFER`, `RECEIVED`, and `DELIVERED` operations.
- Reject invalid production or transfer/delivery quantities.
- Generate browser-side SHA-256 hashes for demo records.
- Simulate signatures and blockchain transaction hashes.
- Simulate direct database attacks by changing quantity, changing record user, or overwriting hash/tx data.
- Select records and inspect verification status.
- View per-user balances for the selected manifest.

## Try This Flow

1. Create a manifest.
2. Change `Active user` in the top-right selector.
3. Submit an operation for the selected manifest.
4. Select the new record in the records table.
5. Click an action in `Database Attack Lab`.
6. Click `Run verification` and watch hash/signature/blockchain checks fail.
7. Click `Re-sign selected record` to simulate repairing by signing and anchoring the changed record again.

## Integration Note

This is currently a local simulator because the Python FastAPI layer still needs repository and authentication cleanup. Once the backend is unified, replace the local state handlers in `src/main.jsx` with calls to the documented API endpoints.
