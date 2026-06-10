---
title: HBase Decoder TPR 字段测试计划
tags: [protocol, hbase, test-plan, active]
created: 2026-06-10
updated: 2026-06-10
status: active
source: Q:\AI\hbase_test_plan.md
---


# HBase Decoder TPR Field Testing Plan

## Test Environment
- **Target Path**: `/home/lujun2/test_falcon_run_osms/falcon-database-protocol/output/edisk/root/usr/local/lib/`
- **Config File**: `falcon.yaml` (needs HBase configuration added)
- **Test Pcap**: `q:/AI/code/falcon-database-protocol/src/hyperbase/pcap/dbtype@hbase-dst_ip@10.66.241.5.pcap`

## TPR Fields to Verify

### DBSql Fields (FID_DBSQL_*)
| Field ID | Field Name | Expected | Extracted | Status |
|----------|------------|-----------|-----------|--------|
| 18 | dbUserName | | | |
| 20 | sqlStatement | | | |
| 28 | toolName | | | |
| 29 | actionType | | | |
| 30 | actionSubType | | | |
| 38 | dbHost | | | |
| 39 | clientHost | | | |
| 40 | dbName | | | |
| 41 | tableNames | | | |

### DBSession Fields (FID_DBSSN_*)
| Field ID | Field Name | Expected | Extracted | Status |
|----------|------------|-----------|-----------|--------|
| 1041 | dbUserName | | | |
| 1043 | toolName | | | |
| 1048 | dbHost | | | |
| 1049 | clientHost | | | |
| 1055 | dbName | | | |

### DBInfo Fields (FID_DBINFO_*)
| Field ID | Field Name | Expected | Extracted | Status |
|----------|------------|-----------|-----------|--------|
| 2064 | dbVer | | | |
| 2065 | dbName | | | |
| 2068 | dbHost | | | |

## Test Steps

1. **Setup**:
   - Copy libhbase.so to test environment
   - Update falcon.yaml with HBase protocol configuration
   - Restart the falcon service if needed

2. **Execution**:
   - Run decoder with HBase pcap file
   - Capture TPR output for each transaction
   - Log all extracted field values

3. **Verification**:
   - Compare extracted values against expected values
   - Check field format and encoding
   - Verify all mandatory fields are populated

4. **Reporting**:
   - Calculate success rate for each field
   - Document any missing or incorrect extractions
   - Provide recommendations for fixes

## Success Criteria
- All mandatory TPR fields extracted: **Pass**
- Field extraction success rate ≥ 90%: **Pass**
- Field format matches specification: **Pass**

## Test Commands (to be updated after build)
```bash
# Sync libhbase.so
scp libhbase.so user@host:/home/lujun2/test_falcon_run_osms/falcon-database-protocol/output/edisk/root/usr/local/lib/

# Run test with pcap
# Command TBD based on falcon testing framework
```

## 相关笔记

- 协议总览：[[hbase]]
- 静态分析报告：[[hbase-static-analysis]]
- 报文解析示例（dropTable）：[[hbase-drop-table-packet]]
- 测试执行计划：[[hbase-test-execution]]
- 报告模板：[[hbase-test-report-template]]
