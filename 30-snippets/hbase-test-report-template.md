---
title: HBase 测试报告模板
tags: [template,hbase,test-report]
created: 2026-06-10
updated: 2026-06-10
status: active
summary: >-
    - **Test Date**: [YYYY-MM-DD]
category: reference
source: Q:\AI\hbase_test_report_template.md
sources: []
base_confidence: 0.3
lifecycle: draft
---


# HBase Decoder TPR Field Test Report

## Test Information
- **Test Date**: [YYYY-MM-DD]
- **Tester**: remote-tester
- **Test Environment**: `/home/lujun2/test_falcon_run_osms/falcon-database-protocol/`
- **libhbase.so Version**: [Version/Build ID]
- **Pcap File**: `dbtype@hbase-dst_ip@10.66.241.5.pcap`
- **Protocol ID**: 630 (HBase)

---

## Executive Summary

### Overall Results
- **Total Transactions Processed**: [N]
- **Overall TPR Field Extraction Success Rate**: [%]
- **Test Result**: ✅ PASS / ❌ FAIL (Threshold: ≥90%)

### Success Rates by Category
| Category | Success Rate | Details |
|----------|--------------|---------|
| DBSql Fields | [%] | [N]/[M] fields correctly extracted |
| DBSession Fields | [%] | [N]/[M] fields correctly extracted |
| DBInfo Fields | [%] | [N]/[M] fields correctly extracted |

---

## Detailed Test Results

### 1. DBSql Fields (Transaction-level)

| Field ID | Field Name | Expected | Extracted | Status | Notes |
|----------|------------|----------|-----------|--------|-------|
| 18 | dbUserName | <username> | [EMPTY] | ⚠️ Expected Empty | Known issue: NOT populated in source code |
| 20 | sqlStatement | <operation> | [VALUE] | ✅/❌ | Should contain HBase operation (Get, Put, Scan, etc.) |
| 28 | toolName | protobuf/Thrift_binary/Thrift_compact/rest | [VALUE] | ✅/❌ | Based on protocol type |
| 29 | actionType | 1/2/5/6 | [VALUE] | ✅/❌ | 1=DDL, 2=DML, 5=Admin, 6=Function |
| 30 | actionSubType | <subtype_id> | [VALUE] | ✅/❌ | From sqloper_630_hbase.csv lookup |
| 38 | dbHost | <hostname/IP> | [VALUE] | ✅/❌ | Database server |
| 39 | clientHost | <hostname/IP> | [VALUE] | ✅/❌ | Client |
| 40 | dbName | <namespace> | [VALUE] | ✅/❌ | Namespace |
| 41 | tableNames | <table1:TYPE\|table2:TYPE> | [VALUE] | ✅/❌ | Comma-separated table names with types |

**DBSql Success Rate**: [%] ([N]/9 fields)

---

### 2. DBSession Fields (Session-level)

| Field ID | Field Name | Expected | Extracted | Status | Notes |
|----------|------------|----------|-----------|--------|-------|
| 1041 | dbUserName | <username> | [EMPTY] | ⚠️ Expected Empty | Known issue: hardcoded to empty string |
| 1043 | toolName | protobuf/Thrift_binary/Thrift_compact/rest | [VALUE] | ✅/❌ | |
| 1048 | dbHost | <hostname/IP> | [VALUE] | ✅/❌ | |
| 1049 | clientHost | <hostname/IP> | [VALUE] | ✅/❌ | |
| 1055 | dbName | <namespace> | [VALUE] | ✅/❌ | |

**DBSession Success Rate**: [%] ([N]/5 fields)

---

### 3. DBInfo Fields (Database info)

| Field ID | Field Name | Expected | Extracted | Status | Notes |
|----------|------------|----------|-----------|--------|-------|
| 2064 | dbVer | <version> | [EMPTY] | ⚠️ Expected Empty | Known issue: NOT populated |
| 2065 | dbName | <namespace> | [EMPTY] | ⚠️ Expected Empty | Known issue: NOT populated |
| 2068 | dbHost | <hostname> | [EMPTY] | ⚠️ Expected Empty | Known issue: Only refProtId is set |

**DBInfo Success Rate**: [%] ([N]/3 fields)

---

## Issues Found

### Critical Issues
1. **[Issue 1]**: [Description]
   - **Impact**: [High/Medium/Low]
   - **Affected Fields**: [List]
   - **Recommendation**: [Fix]

### Warnings
1. **dbUserName not populated**: DBSession.dbUserName is hardcoded to empty string in `hbase.cpp:1743`
2. **DBInfo minimal population**: Only `refProtId` is set in `addToDbInfoData()` (line 1793-1796)

---

## Source Code Analysis Summary

### What IS Populated (✅)
From `hbase.cpp` analysis:
- **DBSql**: `toolName`, `sqlStatement`, `sqlTemplate`, `actionType`, `actionSubType`, `dbName`, `tableNames`, `sqlParams`, `reqTime`, `resTime`, `duration`, `retRecordNum`, `batchType`, `ssid`
- **DBSession**: `ssid`, `ssAction`, `ssResult`, `ssErrCode`, `ssErrStr`, `toolName`, `capTime`, `refProtId`

### What is NOT Populated (❌)
From `hbase.cpp` analysis:
- **DBSession**: `dbUserName` (hardcoded to `""` at line 1743)
- **DBInfo**: `dbVer`, `dbName`, `dbHost` (only `refProtId` is set at line 1795)

---

## Test Cases Executed

### Test Case 1: Basic HBase Operations
- **Pcap**: `dbtype@hbase-dst_ip@10.66.241.5.pcap`
- **Operations Tested**: [List from pcap]
- **Result**: ✅ PASS / ❌ FAIL
- **Details**: [Notes]

### Test Case 2: [Additional test cases as needed]
...

---

## Recommendations

### For Developers
1. **Populate dbUserName**: Extract from Thrift/Protobuf message if available
2. **Populate DBInfo fields**: Add `dbVer`, `dbName`, `dbHost` extraction logic
3. **Add more field validation**: Ensure `tableNames` format matches "name:TYPE\|name:TYPE" specification

### For Testing Framework
1. **Add automated TPR field validation**: Integrate this test into CI/CD pipeline
2. **Add pcap generation**: Create test pcaps for each HBase operation type

---

## Appendices

### A. Source Code References
- `q:\AI\code\falcon-database-protocol\src\hbase\hbase.cpp` - Main decoding logic
- `q:\AI\code\falcon-database-protocol\src\hbase\app-layer-hbase.c` - App layer integration
- `q:\AI\code\falcon-database-protocol\src\yst\appcommon\aldef.h` - TPR field ID definitions

### B. Configuration Files
- `q:\AI\code\falcon-database-protocol\src\config\dae_cfg\config\sqloper_630_hbase.csv` - HBase operation definitions

### C. Test Scripts
- `q:\AI\test_hbase_tpr_fields.py` - Python test script
- `q:\AI\hbase_test_plan.md` - Test plan
- `q:\AI\hbase_test_execution_plan.md` - Test execution plan

---

**Report Generated**: [Timestamp]
**Next Steps**: [List action items]
