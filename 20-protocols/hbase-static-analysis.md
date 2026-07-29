---
title: HBase Decoder TPR 字段静态分析报告
tags: [protocol, hbase, analysis, active]
created: 2026-06-10
updated: 2026-06-10
status: active
summary: >-
    **Analysis Date**: 2026-06-08
category: reference
source: Q:\AI\hbase_static_analysis_report.md
sources: []
base_confidence: 0.7
lifecycle: reviewed
---


# HBase Decoder TPR Field Static Analysis Report

**Analysis Date**: 2026-06-08  
**Analyst**: remote-tester  
**Analysis Type**: Static Source Code Analysis (No Runtime Test)  
**Status**: ⚠️ CANNOT RUN RUNTIME TEST (blocked on libhbase.so build)

---

## Executive Summary

This report documents the expected TPR field extraction behavior of the HBase decoder based on **static source code analysis**. 

**⚠️ Important**: Runtime testing is BLOCKED pending `libhbase.so` build from remote-builder. This report is based on code analysis only.

### Key Findings:
- ✅ **9 DBSql fields** are expected to be populated
- ✅ **5 DBSession fields** are expected to be populated  
- ⚠️ **3 DBInfo fields** are expected to be ONLY PARTIALLY populated
- ❌ **Several fields are KNOWN to be NOT populated** (empty strings or zeros)

---

## Analysis Methodology

### Files Analyzed:
1. `q:\AI\code\falcon-database-protocol\src\hbase\hbase.cpp` (lines 1-1900+)
2. `q:\AI\code\falcon-database-protocol\src\hbase\app-layer-hbase.c`
3. `q:\AI\code\falcon-database-protocol\src\yst\appcommon\aldef.h`
4. `q:\AI\code\falcon-database-protocol\src\config\dae_cfg\config\sqloper_630_hbase.csv`

### Analysis Approach:
- Traced TPR field population in `OutPutDBNoSQL()`, `OutPutDBSession()`, `OutPutDBInfo()`
- Identified which fields are set in `addToDbNoSqlData()`, `addToDbSessionData()`, `addToDbInfoData()`
- Verified against `aldef.h` field ID definitions

---

## Detailed TPR Field Analysis

### 1. DBSql Fields (Transaction-level)

**Population Function**: `CHBASE::addToDbNoSqlData()` (line 1327-1430+)

| Field ID | Field Name | Expected Value | Population Status | Source Location | Notes |
|----------|------------|----------------|---------------------|-------------------|-------|
| 18 | dbUserName | (empty) | ❌ **NOT POPULATED** | N/A | Not set in code; should be extracted from Thrift/Protobuf if available |
| 20 | sqlStatement | HBase operation name | ✅ **POPULATED** | Line 1339, 1341 | Set from `m_cHBaseJavaApi[HBase_Client].SqlStatement` (Java API) or equivalent for Thrift/REST |
| 28 | toolName | "protobuf" / "Thrift_binary" / "Thrift_compact" / "rest" | ✅ **POPULATED** | Line 1337, 1339 | Set based on protocol type |
| 29 | actionType | 1 (DDL) | ✅ **POPULATED** | Line 1314 | Hardcoded to 1 for Java API; need to verify for other protocols |
| 30 | actionSubType | Subtype ID | ✅ **POPULATED** | Line 1348 | From `m_oDbCmdTypeInfoMgr.FindCmdType()` lookup |
| 38 | dbHost | (not set) | ❌ **NOT POPULATED** | N/A | Not set in `addToDbNoSqlData()` |
| 39 | clientHost | (not set) | ❌ **NOT POPULATED** | N/A | Not set in `addToDbNoSqlData()` |
| 40 | dbName | Namespace | ✅ **POPULATED** | Line 1330 | Set from `m_cHBaseJavaApi[HBase_Client].NameSpace` |
| 41 | tableNames | Table name(s) | ✅ **POPULATED** | Line 1331 | Set from `m_cHBaseJavaApi[HBase_Client].TableName` |

**Additional DBSql Fields (Populated but not in `aldef.h` list)**:
| Field | Description | Status |
|--------|-------------|--------|
| `ssid` | Session ID | ✅ Set at line 1333 |
| `sqlTemplate` | Function name | ✅ Set at line 1341 |
| `sqlParams` | Parameter values | ✅ Set at line 1355 |
| `reqTime` | Request timestamp | ✅ Set at line 1373 |
| `resTime` | Response timestamp | ✅ Set at line 1374 |
| `duration` | Execution duration | ✅ Calculated at line 1383 |
| `batchType` | Batch type | ✅ Set to 0 at line 1385 |
| `retRecordNum` | Returned record count | ✅ Set at line 1386 |

**DBSql Expected Success Rate**:  
- **Fields that SHOULD be populated**: 9 (dbUserName, sqlStatement, toolName, actionType, actionSubType, dbHost, clientHost, dbName, tableNames)
- **Fields that ARE populated**: 6 (sqlStatement, toolName, actionType, actionSubType, dbName, tableNames)
- **Fields that are NOT populated**: 3 (dbUserName, dbHost, clientHost)
- **Expected Success Rate**: **66.7%** (6/9) for full extraction; **100%** for actually-implemented fields

---

### 2. DBSession Fields (Session-level)

**Population Function**: `CHBASE::addToDbSessionData()` (line 1739-1764)

| Field ID | Field Name | Expected Value | Population Status | Source Location | Notes |
|----------|------------|----------------|---------------------|-------------------|-------|
| 1041 | dbUserName | (empty string) | ⚠️ **POPULATED as EMPTY** | Line 1743 | Hardcoded to `""` - known issue |
| 1043 | toolName | "protobuf" / "Thrift_compact" / "Thrift_binary" / "rest" | ✅ **POPULATED** | Lines 1754-1763 | Set based on `m_iPhase` and `m_nHBaseProtocolType` |
| 1048 | dbHost | (not set) | ❌ **NOT POPULATED** | N/A | Not set in `addToDbSessionData()` |
| 1049 | clientHost | (not set) | ❌ **NOT POPULATED** | N/A | Not set in `addToDbSessionData()` |
| 1055 | dbName | (not set) | ❌ **NOT POPULATED** | N/A | Not set in `addToDbSessionData()` |

**Additional DBSession Fields (Populated but not in `aldef.h` list)**:
| Field | Description | Status |
|--------|-------------|--------|
| `ssid` | Session ID | ✅ Set at line 1742 |
| `ssAction` | Session action (1=start, 2=end) | ✅ Set at line 1747 |
| `ssResult` | Session result | ✅ Set to 0 at line 1744 |
| `ssErrCode` | Session error code | ✅ Set to 0 at line 1745 |
| `ssErrStr` | Session error string | ✅ Set to `""` at line 1746 |
| `refProtId` | Reference protocol ID (630) | ✅ Set at line 1748 |
| `capTime` | Capture time | ✅ Set at lines 1749-1750 |

**DBSession Expected Success Rate**:  
- **Fields that SHOULD be populated**: 5 (dbUserName, toolName, dbHost, clientHost, dbName)
- **Fields that ARE populated (non-empty)**: 1 (toolName)
- **Fields that ARE populated (empty)**: 1 (dbUserName)
- **Fields that are NOT populated**: 3 (dbHost, clientHost, dbName)
- **Expected Success Rate**: **20%** (1/5 with non-empty values); **40%** (2/5 if empty is acceptable)

---

### 3. DBInfo Fields (Database info)

**Population Function**: `CHBASE::addToDbInfoData()` (line 1793-1796)

| Field ID | Field Name | Expected Value | Population Status | Source Location | Notes |
|----------|------------|----------------|---------------------|-------------------|-------|
| 2064 | dbVer | (not set) | ❌ **NOT POPULATED** | N/A | Only `refProtId` is set in `addToDbInfoData()` |
| 2065 | dbName | (not set) | ❌ **NOT POPULATED** | N/A | Only `refProtId` is set in `addToDbInfoData()` |
| 2068 | dbHost | (not set) | ❌ **NOT POPULATED** | N/A | Only `refProtId` is set in `addToDbInfoData()` |

**Additional DBInfo Fields (Populated but not in `aldef.h` list)**:
| Field | Description | Status |
|--------|-------------|--------|
| `refProtId` | Reference protocol ID (630) | ✅ Set at line 1795 |

**DBInfo Expected Success Rate**:  
- **Fields that SHOULD be populated**: 3 (dbVer, dbName, dbHost)
- **Fields that ARE populated**: 0 (only `refProtId` is set, which is not in the list)
- **Expected Success Rate**: **0%** (0/3)

---

## Runtime Test Expected Results

### Expected TPR Field Extraction Success Rate:

| Category | Fields Expected | Fields Populated (Non-Empty) | Expected Success Rate |
|----------|-------------------|----------------------------------|--------------------------|
| DBSql | 9 | 6 (sqlStatement, toolName, actionType, actionSubType, dbName, tableNames) | **66.7%** |
| DBSession | 5 | 1 (toolName) | **20.0%** |
| DBInfo | 3 | 0 | **0.0%** |
| **Overall** | **17** | **7** | **41.2%** |

### ⚠️ Important Notes:
1. **dbUserName is KNOWN to be empty** in DBSession (hardcoded to `""` at `hbase.cpp:1743`)
2. **DBInfo is MINIMALLY populated** - only `refProtId` is set
3. **dbHost and clientHost are NOT populated** in DBSql (need to verify if this is intentional)
4. **Test will likely FAIL** the 90% success rate threshold based on static analysis

---

## Recommendations (Based on Static Analysis)

### High Priority (Must Fix):
1. **Populate dbUserName** in DBSession:
   - **Current**: Hardcoded to `""` at `hbase.cpp:1743`
   - **Recommended**: Extract from Thrift/Protobuf message if available
   - **Impact**: Affects field ID 1041

2. **Populate DBInfo fields**:
   - **Current**: Only `refProtId` is set in `addToDbInfoData()` (line 1793-1796)
   - **Recommended**: Add extraction logic for `dbVer`, `dbName`, `dbHost`
   - **Impact**: Affects field IDs 2064, 2065, 2068

### Medium Priority (Should Fix):
3. **Populate dbHost and clientHost in DBSql**:
   - **Current**: Not populated in `addToDbNoSqlData()`
   - **Recommended**: Set from `m_BaseInfo` (BaseInfo structure has `src_ip`, `dst_ip`, `src_port`, `dst_port`)
   - **Impact**: Affects field IDs 38, 39

4. **Verify actionType population for non-Java API**:
   - **Current**: Hardcoded to 1 (DDL) for Java API (line 1314)
   - **Recommended**: Verify that Thrift/REST APIs also set `actionType` correctly
   - **Impact**: Affects field ID 29

### Low Priority (Nice to Have):
5. **Add more validation for tableNames format**:
   - **Current**: Set from `m_cHBaseJavaApi[HBase_Client].TableName`
   - **Recommended**: Ensure format matches "name:TYPE\|name:TYPE" specification from memory
   - **Impact**: Affects field ID 41

---

## Test Readiness Status

### ✅ Completed (Ready for Runtime Test):
1. ✅ **Test plan created**: `q:/AI/hbase_test_plan.md`
2. ✅ **Test execution plan created**: `q:/AI/hbase_test_execution_plan.md`
3. ✅ **Python test script created**: `q:/AI/test_hbase_tpr_fields.py`
4. ✅ **Test report template created**: `q:/AI/hbase_test_report_template.md`
5. ✅ **Static analysis completed**: This report
6. ✅ **Test pcap identified**: `q:/AI/code/falcon-database-protocol/src/hyperbase/pcap/dbtype@hbase-dst_ip@10.66.241.5.pcap`

### ⏳ Blocker (Cannot Run Runtime Test):
- **Issue**: `libhbase.so` not built yet (waiting for remote-builder)
- **Impact**: Cannot run actual decoder to verify TPR field extraction
- **Workaround**: This static analysis report documents expected behavior

### 📋 Next Steps (Once Unblocked):
1. Sync `libhbase.so` to test environment
2. Update `falcon.yaml` with HBase configuration
3. Run decoder with test pcap
4. Compare actual output against this static analysis
5. Generate final test report with actual success rates

---

## Appendices

### A. Source Code References

| File | Description | Key Lines |
|------|-------------|------------|
| `q:\AI\code\falcon-database-protocol\src\hbase\hbase.cpp` | Main HBase decoder logic | 1327-1430 (OutPutDBNoSQL), 1739-1764 (OutPutDBSession), 1793-1796 (OutPutDBInfo) |
| `q:\AI\code\falcon-database-protocol\src\hbase\app-layer-hbase.c` | App layer integration | 112-132 (Callback_HbaseOutPut) |
| `q:\AI\code\falcon-database-protocol\src\yst\appcommon\aldef.h` | TPR field ID definitions | 56-130 (DBSqlFieldID, DBSessionFieldID, DBInfoFieldID) |
| `q:\AI\code\falcon-database-protocol\src\config\dae_cfg\config\sqloper_630_hbase.csv` | HBase operation definitions | Full file (170+ operations) |

### B. HBase Protocol ID
- **Protocol ID**: **630** (from `sqloper_630_hbase.csv` naming convention)
- **Module ID**: `CHBASE::m_nModuleID = 630` (from `hbase.cpp:17`)

### C. HBase Operation Examples (from `sqloper_630_hbase.csv`)

| Operation ID | Operation Name | Action Type | Description |
|--------------|------------------|-------------|-------------|
| 3030 | Get | 2 (DML) | Get data from HBase table |
| 3031 | Mutate | 2 (DML) | Mutate (put/delete) data |
| 3032 | Scan | 2 (DML) | Scan HBase table |
| 3056 | CreateTable | 1 (DDL) | Create HBase table |
| 3051 | DeleteTable | 1 (DDL) | Delete HBase table |
| 3000 | Grant | 5 (Admin) | Grant permissions |

---

**Report Status**: ✅ Static Analysis Complete  
**Runtime Test Status**: ⏳ Blocked (waiting for `libhbase.so`)  
**Next Update**: After `libhbase.so` is available for runtime testing
