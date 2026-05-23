# Integration Guide

## 1. نظرة عامة

هذا المستند يشرح طريقة ربط مكونات مشروع `blockchain-supply-chain` ببعضها، وما هو المسار الحالي الأكثر ثباتا للتشغيل، وما الذي يحتاج توحيد قبل الاعتماد على API حقيقي أو بلوك تشين حقيقية.

المسار العملي الحالي هو:

`UserIdentity -> Record/GoodsManifest -> RepositoryV2 -> MockBlockchain -> VerificationEngine`

أما مسار FastAPI والـ blockchain الحقيقي موجود جزئيا لكنه يحتاج توحيد imports وواجهات repository قبل التشغيل المستقر.

## 2. هيكل المشروع

```text
contracts/
  SupplyChainAnchor.sol
  SupplyChainAnchor_abi.json

src/
  api/
    auth_server.py
    auth_client.py
    supply_chain_manager.py
  blockchain/
    blockchain_client.py
    deploy_contract.py
  core/
    data_structures.py
    repository_v2.py
    user_identity.py
  verification/
    verification_engine.py

tests/
  integration_test_complete.py
  test_authentication.py
  test_blockchain_integration.py
  test_integration.py
```

## 3. الاعتمادات

التثبيت:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

أهم الحزم:

- `eth-account`: إنشاء مفاتيح Ethereum والتوقيع والتحقق.
- `web3`: الاتصال بعقد Ethereum.
- `pydantic`: نماذج البيانات والتحقق من المدخلات.
- `fastapi` و `uvicorn`: API server.
- `pyjwt`: إصدار والتحقق من JWT في auth server.
- `requests`: auth client واختبارات HTTP.
- `tabulate`: إخراج جدول في integration test.

## 4. مسار البيانات

### 4.1 إنشاء مستخدم

`UserIdentity` ينشئ private key و public key و Ethereum address:

```python
user = UserIdentity()
address = user.address
private_key = user.private_key
```

### 4.2 إنشاء Manifest

يتم إنشاء `GoodsManifest` ثم حساب hash له وتخزينه:

```python
manifest = GoodsManifest(...)
manifest_hash = compute_hash(manifest.model_dump())
repo.save_manifest(manifest.model_dump(), manifest_hash)
```

### 4.3 إنشاء Record وتوقيعه

يتم إنشاء `Record`، ثم تحويله إلى dict canonical-compatible، ثم توقيعه:

```python
record = Record(...)
record_dict = record.model_dump(exclude_none=True, mode="json")
record_hash = compute_hash(record_dict)
signature = user.sign_record(record_dict)
```

### 4.4 حفظ Record

يحفظ `repository_v2.py` السجل بالشكل التالي:

```python
repo.save_record({
    "record": record_dict,
    "hash": record_hash,
    "signature": signature,
    "user_address": user.address
})
```

### 4.5 تثبيت Hash على البلوك تشين

في local mode يستخدم الاختبار `MockBlockchain`:

```python
tx_hash = blockchain.anchor_hash(record.record_id, record_hash, "dummy_key")
repo.update_tx_hash(record.record_id, tx_hash)
```

في blockchain mode المفترض استخدام `BlockchainAnchorClient`:

```python
client = BlockchainAnchorClient(
    rpc_url=RPC_URL,
    contract_address=CONTRACT_ADDRESS,
    abi_path="contracts/SupplyChainAnchor_abi.json",
)

tx_hash = client.anchor_hash(record_id, record_hash, signer_private_key)
repo.update_tx_hash(record_id, tx_hash)
```

## 5. قاعدة البيانات

`SupplyChainRepository` في `repository_v2.py` ينشئ جدولين:

### manifests

- `manifest_id`
- `good_type`
- `quantity`
- `creator`
- `timestamp`
- `hash`
- `created_at`

### records

- `record_id`
- `record_type`
- `manifest_id`
- `quantity`
- `user_address`
- `timestamp`
- `hash`
- `signature`
- `tx_hash`
- `metadata`
- `created_at`

الفهارس الحالية:

- `idx_records_manifest`
- `idx_records_user`
- `idx_records_type`

## 6. قواعد الكميات

الرصيد الحالي للمستخدم يحسب من سجلاته داخل manifest:

- `PRODUCED` يزيد الرصيد.
- `RECEIVED` يزيد الرصيد.
- `TRANSFER` يقلل الرصيد.
- `DELIVERED` يقلل الرصيد.

قبل `TRANSFER` و `DELIVERED` يجب التأكد من أن رصيد المستخدم يكفي.

قبل `PRODUCED` يجب التأكد أن إجمالي الإنتاج لا يتجاوز `manifest.quantity`.

ملاحظة: في التنفيذ الحالي لـ `integration_test_complete.py` يتم استخدام `compute_available_quantity` كبديل لحساب total produced في إنتاج جديد. هذا كاف للسيناريو التجريبي الحالي، لكنه يجب أن يستبدل لاحقا بدالة صريحة لحساب total produced فقط.

## 7. التحقق

`VerificationEngine` ينفذ أربع طبقات:

### 7.1 Hash integrity

يعيد حساب hash من `stored_record["record"]` ويقارنه بـ `stored_record["hash"]`.

### 7.2 Signature verification

يتحقق من أن توقيع السجل يستعيد نفس `user_address`.

### 7.3 Blockchain proof

إذا كان `tx_hash` غير موجود، تكون الحالة `PENDING`.

إذا كان blockchain client موجودا، ينادي:

```python
blockchain.verify_on_chain(record_id, expected_hash)
```

### 7.4 Quantity consistency

يمر على كل سجلات manifest ويحسب:

- total produced
- total transferred
- total received
- total delivered
- net available
- user balances

## 8. تشغيل الاختبار المحلي الكامل

المسار الأكثر استقرارا حاليا:

```bash
source venv/bin/activate
python tests/integration_test_complete.py
```

هذا الاختبار يستخدم:

- `repository_v2.py`
- `UserIdentity`
- `GoodsManifest` و `Record`
- `MockBlockchain`
- `VerificationEngine`

ملاحظة تشغيل: الاختبار يستخدم قاعدة `integration_test.db` في جذر المشروع. لو كان بها بيانات قديمة بنفس IDs قد يظهر conflict. الأفضل لاحقا تعديل الاختبار ليستخدم database مؤقتة أو يمسح بياناته بطريقة آمنة.

## 9. تشغيل Auth Server

`auth_server.py` يقدم challenge-response authentication مع JWT.

تشغيله:

```bash
source venv/bin/activate
PYTHONPATH=src/core:src/api uvicorn auth_server:app --host 0.0.0.0 --port 8000
```

Endpoints:

- `POST /auth/challenge`
- `POST /auth/verify`
- `GET /protected/profile`
- `GET /protected/stats`
- `GET /health`

المخرجات المهمة:

- `POST /auth/verify` يرجع JWT token.
- العميل يرسل token في `Authorization: Bearer <token>`.

## 10. تشغيل Supply Chain API

`supply_chain_manager.py` يحتاج تعديلات قبل تشغيله بشكل مستقر، لأنه يستورد `repository` غير الموجود حاليا ويستخدم methods لا تطابق `repository_v2.py`.

المطلوب قبل التشغيل:

- تغيير import إلى `from repository_v2 import SupplyChainRepository`.
- توحيد أسماء methods:
  - `create_manifest` -> `save_manifest` مع hash.
  - `create_record` -> `save_record`.
  - `anchor_record_on_blockchain` -> `update_tx_hash`.
  - `get_available_quantity` -> `get_available_quantity_per_user`.
  - `get_records_by_manifest` -> `get_all_records_for_manifest`.
- توحيد شكل الحقول:
  - الحالي في `repository_v2.py` يستخدم `tx_hash`.
  - بعض الكود القديم يتوقع `blockchain_tx_hash` و `blockchain_anchored`.

بعد التوحيد، التشغيل المتوقع:

```bash
source venv/bin/activate
PYTHONPATH=src/core:src/api:src/verification uvicorn supply_chain_manager:app --host 0.0.0.0 --port 8000
```

## 11. تكامل البلوك تشين الحقيقي

العقد Solidity في `contracts/SupplyChainAnchor.sol` يدعم:

- `anchorRecord(recordId, recordHash)`
- `getRecord(recordId)`
- `hasRecord(recordId)`
- `verifyRecord(recordId, expectedHash)`
- `anchorRecordsBatch(recordIds, recordHashesArray)`
- `getTotalRecords()`
- `getOwner()`

خطوات التكامل الحقيقي:

1. Compile للعقد واستخراج bytecode و ABI.
2. Deploy على local Anvil/Hardhat أو Sepolia.
3. حفظ `contract_address`.
4. ضبط `rpc_url`, `contract_address`, `abi_path`, `chain_id`.
5. استخدام `BlockchainAnchorClient.anchor_hash`.
6. تخزين `tx_hash` في SQLite.
7. استخدام `VerificationEngine` مع blockchain client للتحقق on-chain.

### ملاحظات تحتاج تعديل

- `abi_path` الافتراضي حاليا هو `/home/claude/contracts/SupplyChainAnchor_abi.json`، وهذا غير مناسب للمشروع المحلي. يجب جعله:

```python
contracts/SupplyChainAnchor_abi.json
```

أو يحسب relative من جذر المشروع.

- `deploy_contract.py` لا ينفذ compile فعلي حاليا عند عدم وجود bytecode، ويستخدم simulation mode.

## 12. نقاط عدم الاتساق الحالية

هذه أهم الفجوات التي يجب إصلاحها قبل البناء فوق المشروع:

- يوجد ملف README باسم `redme.md` وليس `README.md`.
- لا يوجد ملف `src/core/repository.py` رغم أن عدة ملفات تستورده.
- `repository_v2.py` هو المسار الأحدث، لكن API server والاختبارات القديمة لم تتوحد عليه.
- يوجد اختلاف بين auth server الذي يستخدم JWT و supply chain manager الذي يعتمد على `X-User-Address`.
- `auth_client.py` يتوقع endpoints مثل `/protected/profile` و `/protected/stats`، وهذه موجودة في `auth_server.py` وليس في `supply_chain_manager.py`.
- بعض الاختبارات القديمة قد لا تعمل بسبب imports أو اختلاف method names.
- قاعدة `integration_test.db` موجودة في الجذر وغير متجاهلة حاليا في git status.

## 13. خطة تكامل مقترحة للمرحلة القادمة

1. إعادة تسمية `redme.md` إلى `README.md`.
2. اختيار repository واحد رسمي: `repository_v2.py`.
3. تحديث `supply_chain_manager.py` ليستخدم `repository_v2.py`.
4. توحيد auth حول JWT Bearer في كل endpoints المحمية.
5. إضافة config مركزي:
   - `DATABASE_URL` أو `DB_PATH`
   - `RPC_URL`
   - `CONTRACT_ADDRESS`
   - `ABI_PATH`
   - `JWT_SECRET_KEY`
6. تعديل tests لتستخدم temporary DB files.
7. إضافة test للـ FastAPI flow بعد توحيد imports.
8. جعل blockchain client optional:
   - mock/local mode للتطوير.
   - real Web3 mode للتجارب على local chain أو Sepolia.

## 14. Definition of Done للتكامل

يعتبر التكامل جاهزا عندما:

- `python tests/integration_test_complete.py` يعمل من قاعدة نظيفة.
- `pytest` يعمل بدون import errors.
- `uvicorn supply_chain_manager:app` يبدأ بنجاح.
- يمكن تنفيذ flow كامل عبر HTTP:
  - auth challenge
  - auth verify
  - create manifest
  - produce
  - transfer
  - receive
  - deliver
  - verify record
- كل record محفوظ يحتوي `hash`, `signature`, `user_address`, `tx_hash`.
- `VerificationEngine` يرجع `VERIFIED` عند وجود blockchain client و `PARTIAL` عند غياب التحقق on-chain.

